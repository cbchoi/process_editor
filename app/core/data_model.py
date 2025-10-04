"""
core/data_model.py
Graph data model, node template loader, and validation utilities.
"""
import yaml
import os
import uuid
from typing import List, Dict, Any, Optional, Tuple

class NodeTemplate:
    def __init__(self, data: Dict[str, Any]):
        self.type = data.get('type')
        self.title = data.get('title')
        self.inputs = data.get('inputs', []) or []  # list of {name, dtype?}
        self.outputs = data.get('outputs', []) or []
        self.attributes = data.get('attributes', []) or []  # list of {name,type,default,...}
        self.constraints = data.get('constraints', {}) or {}

    def pin_exists(self, name: str, kind: str) -> bool:
        pins = self.inputs if kind == 'input' else self.outputs
        return any(p.get('name') == name for p in pins)

    def get_attr_default_map(self) -> Dict[str, Any]:
        defaults = {}
        for a in self.attributes:
            if 'default' in a:
                defaults[a['name']] = a['default']
        return defaults


class GraphModel:
    def __init__(self):
        self.nodes: List[Dict[str, Any]] = []
        self.links: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {}
        # internal indexes (not serialized)
        self._node_index: Dict[str, Dict[str, Any]] = {}

    # --- basic io ---
    def load_from_dict(self, data: Dict[str, Any]):
        graph = data.get('graph', data) or {}
        self.nodes = graph.get('nodes', []) or []
        self.links = graph.get('links', []) or []
        self.metadata = graph.get('metadata', {}) or {}
        self._rebuild_index()

    def to_dict(self):
        return {
            'nodes': self.nodes,
            'links': self.links,
            'metadata': self.metadata
        }

    # --- index helpers ---
    def _rebuild_index(self):
        self._node_index = {n['id']: n for n in self.nodes if 'id' in n}

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        return self._node_index.get(node_id)

    # --- node operations ---
    def add_node(self, template: NodeTemplate, position: Optional[Tuple[float, float]] = None) -> str:
        node_id = str(uuid.uuid4())
        node = {
            'id': node_id,
            'type': template.type,
            'title': template.title or template.type,
            'position': {'x': float(position[0]) if position else 0.0, 'y': float(position[1]) if position else 0.0},
            'attributes': template.get_attr_default_map(),
            'pins': {
                'inputs': [p['name'] for p in template.inputs],
                'outputs': [p['name'] for p in template.outputs],
            },
        }
        self.nodes.append(node)
        self._node_index[node_id] = node
        return node_id

    def remove_node(self, node_id: str):
        self.nodes = [n for n in self.nodes if n.get('id') != node_id]
        self.links = [l for l in self.links if l.get('from', {}).get('node_id') != node_id and l.get('to', {}).get('node_id') != node_id]
        self._rebuild_index()

    # --- link operations ---
    def add_link(self, from_node_id: str, from_pin: str, to_node_id: str, to_pin: str) -> str:
        link_id = str(uuid.uuid4())
        link = {
            'id': link_id,
            'from': {'node_id': from_node_id, 'pin': from_pin},
            'to': {'node_id': to_node_id, 'pin': to_pin},
        }
        self.links.append(link)
        return link_id

    def remove_link(self, link_id: str):
        self.links = [l for l in self.links if l.get('id') != link_id]

    # --- validation ---
    def validate(self, templates: Dict[str, NodeTemplate]) -> List[str]:
        errors: List[str] = []
        # nodes type and pins
        for n in self.nodes:
            t = templates.get(n.get('type'))
            if not t:
                errors.append(f"Unknown node type: {n.get('type')} (node {n.get('id')})")
                continue
            # pin names
            in_pins = set(p.get('name') for p in t.inputs)
            out_pins = set(p.get('name') for p in t.outputs)
            for p in n.get('pins', {}).get('inputs', []):
                if p not in in_pins:
                    errors.append(f"Invalid input pin '{p}' for node {n.get('id')}")
            for p in n.get('pins', {}).get('outputs', []):
                if p not in out_pins:
                    errors.append(f"Invalid output pin '{p}' for node {n.get('id')}")
            # attributes required/type
            attr_defs = {a['name']: a for a in t.attributes}
            for name, val in (n.get('attributes') or {}).items():
                adef = attr_defs.get(name)
                if not adef:
                    continue
                etype = adef.get('type')
                if not _validate_type(val, etype, adef):
                    errors.append(f"Invalid attribute '{name}' value for node {n.get('id')}")
            for name, adef in attr_defs.items():
                if adef.get('required') and name not in (n.get('attributes') or {}):
                    errors.append(f"Missing required attribute '{name}' for node {n.get('id')}")
        # links
        in_count: Dict[Tuple[str, str], int] = {}
        out_count: Dict[Tuple[str, str], int] = {}
        for l in self.links:
            fn = self.get_node(l.get('from', {}).get('node_id'))
            tn = self.get_node(l.get('to', {}).get('node_id'))
            if not fn or not tn:
                errors.append(f"Link {l.get('id')} references missing node")
                continue
            ft = templates.get(fn['type'])
            tt = templates.get(tn['type'])
            fpin = l.get('from', {}).get('pin')
            tpin = l.get('to', {}).get('pin')
            if not ft or not tt:
                continue
            if not ft.pin_exists(fpin, 'output'):
                errors.append(f"Invalid from pin '{fpin}' on node {fn['id']}")
            if not tt.pin_exists(tpin, 'input'):
                errors.append(f"Invalid to pin '{tpin}' on node {tn['id']}")
            out_count[(fn['id'], fpin)] = out_count.get((fn['id'], fpin), 0) + 1
            in_count[(tn['id'], tpin)] = in_count.get((tn['id'], tpin), 0) + 1
        # check constraints per node
        for n in self.nodes:
            t = templates.get(n['type'])
            if not t:
                continue
            max_in = t.constraints.get('max_input_links')
            max_out = t.constraints.get('max_output_links')
            if max_in is not None:
                total_in = sum(cnt for (nid, _), cnt in in_count.items() if nid == n['id'])
                if total_in > max_in:
                    errors.append(f"Input link count exceeds max for node {n['id']} ({total_in}>{max_in})")
            if max_out is not None:
                total_out = sum(cnt for (nid, _), cnt in out_count.items() if nid == n['id'])
                if total_out > max_out:
                    errors.append(f"Output link count exceeds max for node {n['id']} ({total_out}>{max_out})")
        # cycles
        if self._has_cycle():
            errors.append('Graph contains a cycle')
        return errors

    def _has_cycle(self) -> bool:
        # build adjacency by node
        adj: Dict[str, List[str]] = {}
        for l in self.links:
            s = l.get('from', {}).get('node_id')
            t = l.get('to', {}).get('node_id')
            if not s or not t:
                continue
            adj.setdefault(s, []).append(t)
        temp_mark = set()
        perm_mark = set()

        def visit(nid: str) -> bool:
            if nid in perm_mark:
                return False
            if nid in temp_mark:
                return True
            temp_mark.add(nid)
            for m in adj.get(nid, []):
                if visit(m):
                    return True
            temp_mark.remove(nid)
            perm_mark.add(nid)
            return False

        for n in self.nodes:
            nid = n['id']
            if visit(nid):
                return True
        return False


# Node template loader

def load_node_templates(nodes_dir: str) -> List[NodeTemplate]:
    templates: List[NodeTemplate] = []
    if not os.path.exists(nodes_dir):
        return templates
    for fname in os.listdir(nodes_dir):
        if fname.endswith('.yaml'):
            path = os.path.join(nodes_dir, fname)
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
                templates.append(NodeTemplate(data))
    return templates


# .process file IO

def load_process_file(path: str) -> GraphModel:
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    model = GraphModel()
    model.load_from_dict(data)
    return model


def save_process_file(path: str, model: GraphModel):
    with open(path, 'w', encoding='utf-8') as f:
        yaml.safe_dump({'graph': model.to_dict()}, f, allow_unicode=True)


# Template validation (basic checks)

def validate_templates(templates: List[NodeTemplate]) -> List[str]:
    errors = []
    types = set()
    for t in templates:
        if not t or not getattr(t, 'type', None):
            errors.append('Invalid template or missing type')
            continue
        if t.type in types:
            errors.append(f"Duplicate node type: {t.type}")
        types.add(t.type)
    return errors


def templates_by_type(templates: List[NodeTemplate]) -> Dict[str, NodeTemplate]:
    return {t.type: t for t in templates if getattr(t, 'type', None)}


# helpers

def _validate_type(val: Any, etype: Optional[str], spec: Dict[str, Any]) -> bool:
    if etype is None:
        return True
    try:
        if etype == 'int':
            if not isinstance(val, int):
                return False
            return _check_min_max(val, spec)
        if etype == 'float':
            if not isinstance(val, (int, float)):
                return False
            return _check_min_max(float(val), spec)
        if etype == 'str':
            return isinstance(val, str)
        if etype == 'bool':
            return isinstance(val, bool)
        if etype == 'enum':
            return val in (spec.get('enum') or [])
        return True
    except Exception:
        return False


def _check_min_max(v: float, spec: Dict[str, Any]) -> bool:
    mn = spec.get('min')
    mx = spec.get('max')
    if mn is not None and v < mn:
        return False
    if mx is not None and v > mx:
        return False
    return True

"""
core/data_model.py
Graph data model, node template loader, and validation utilities.
"""
import yaml
import os
import uuid
from typing import List, Dict, Any, Optional, Tuple

from app.core.node_user_template import NodeUserTemplate


class Node:
    """Node entity with helpers and stable serialization format."""
    def __init__(self,
                 node_id: str,
                 type_: str,
                 title: Optional[str] = None,
                 position: Optional[Dict[str, float]] = None,
                 attributes: Optional[Dict[str, Any]] = None,
                 pins: Optional[Dict[str, List[str]]] = None,
                 ui: Optional[Dict[str, Any]] = None):
        self.id: str = node_id
        self.type: str = type_
        self.title: str = title or type_
        self.position: Dict[str, float] = position or {'x': 0.0, 'y': 0.0}
        self.attributes: Dict[str, Any] = attributes or {}
        self.pins: Dict[str, List[str]] = pins or {'inputs': [], 'outputs': []}
        self.ui: Dict[str, Any] = ui or {}

    @staticmethod
    def from_template(template: 'NodeUserTemplate', position: Optional[Tuple[float, float]] = None) -> 'Node':
        node_id = str(uuid.uuid4())
        pos = {'x': float(position[0]) if position else 0.0, 'y': float(position[1]) if position else 0.0}
        pins = {
            'inputs': [p['name'] for p in (template.inputs or [])],
            'outputs': [p['name'] for p in (template.outputs or [])],
        }
        attrs = template.get_attr_default_map()
        return Node(node_id, template.type, template.title or template.type, pos, attrs, pins, ui={})

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'Node':
        return Node(
            node_id=data.get('id'),
            type_=data.get('type'),
            title=data.get('title'),
            position=data.get('position') or {'x': 0.0, 'y': 0.0},
            attributes=data.get('attributes') or {},
            pins=data.get('pins') or {'inputs': [], 'outputs': []},
            ui=data.get('ui') or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        out = {
            'id': self.id,
            'type': self.type,
            'title': self.title,
            'position': self.position,
            'attributes': self.attributes,
            'pins': self.pins,
        }
        # persist UI info if present
        if self.ui:
            out['ui'] = self.ui
        return out


class GraphModel:
    def __init__(self):
        self.nodes: List[Node] = []
        self.links: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {}
        # internal indexes (not serialized)
        self._node_index: Dict[str, Node] = {}

    # --- basic io ---
    def load_from_dict(self, data: Dict[str, Any]):
        graph = data.get('graph', data) or {}
        raw_nodes = graph.get('nodes', []) or []
        self.nodes = [Node.from_dict(n) if not isinstance(n, Node) else n for n in raw_nodes]
        self.links = graph.get('links', []) or []
        self.metadata = graph.get('metadata', {}) or {}
        self._rebuild_index()

    def to_dict(self):
        return {
            'nodes': [n.to_dict() for n in self.nodes],
            'links': self.links,
            'metadata': self.metadata
        }

    # --- index helpers ---
    def _rebuild_index(self):
        self._node_index = {n.id: n for n in self.nodes if getattr(n, 'id', None)}

    def get_node(self, node_id: str) -> Optional[Node]:
        return self._node_index.get(node_id)

    # --- node operations ---
    def add_node(self, template: 'NodeUserTemplate', position: Optional[Tuple[float, float]] = None) -> str:
        node = Node.from_template(template, position)
        self.nodes.append(node)
        self._node_index[node.id] = node
        return node.id

    def remove_node(self, node_id: str):
        self.nodes = [n for n in self.nodes if n.id != node_id]
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
    def validate(self, templates: Dict[str, 'NodeUserTemplate']) -> List[str]:
        errors: List[str] = []
        # nodes type and pins
        for n in self.nodes:
            t = templates.get(n.type)
            if not t:
                errors.append(f"Unknown node type: {n.type} (node {n.id})")
                continue
            # pin names
            in_pins = set(p.get('name') for p in t.inputs)
            out_pins = set(p.get('name') for p in t.outputs)
            for p in n.pins.get('inputs', []):
                if p not in in_pins:
                    errors.append(f"Invalid input pin '{p}' for node {n.id}")
            for p in n.pins.get('outputs', []):
                if p not in out_pins:
                    errors.append(f"Invalid output pin '{p}' for node {n.id}")
            # attributes required/type
            attr_defs = {a['name']: a for a in t.attributes}
            for name, val in (n.attributes or {}).items():
                adef = attr_defs.get(name)
                if not adef:
                    continue
                etype = adef.get('type')
                if not _validate_type(val, etype, adef):
                    errors.append(f"Invalid attribute '{name}' value for node {n.id}")
            for name, adef in attr_defs.items():
                if adef.get('required') and name not in (n.attributes or {}):
                    errors.append(f"Missing required attribute '{name}' for node {n.id}")
        # links
        in_count: Dict[Tuple[str, str], int] = {}
        out_count: Dict[Tuple[str, str], int] = {}
        for l in self.links:
            fn = self.get_node(l.get('from', {}).get('node_id'))
            tn = self.get_node(l.get('to', {}).get('node_id'))
            if not fn or not tn:
                errors.append(f"Link {l.get('id')} references missing node")
                continue
            ft = templates.get(fn.type)
            tt = templates.get(tn.type)
            fpin = l.get('from', {}).get('pin')
            tpin = l.get('to', {}).get('pin')
            if not ft or not tt:
                continue
            if not ft.pin_exists(fpin, 'output'):
                errors.append(f"Invalid from pin '{fpin}' on node {fn.id}")
            if not tt.pin_exists(tpin, 'input'):
                errors.append(f"Invalid to pin '{tpin}' on node {tn.id}")
            out_count[(fn.id, fpin)] = out_count.get((fn.id, fpin), 0) + 1
            in_count[(tn.id, tpin)] = in_count.get((tn.id, tpin), 0) + 1
        # check constraints per node
        for n in self.nodes:
            t = templates.get(n.type)
            if not t:
                continue
            max_in = t.constraints.get('max_input_links')
            max_out = t.constraints.get('max_output_links')
            if max_in is not None:
                total_in = sum(cnt for (nid, _), cnt in in_count.items() if nid == n.id)
                if total_in > max_in:
                    errors.append(f"Input link count exceeds max for node {n.id} ({total_in}>{max_in})")
            if max_out is not None:
                total_out = sum(cnt for (nid, _), cnt in out_count.items() if nid == n.id)
                if total_out > max_out:
                    errors.append(f"Output link count exceeds max for node {n.id} ({total_out}>{max_out})")
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
            nid = n.id
            if visit(nid):
                return True
        return False


# Node template loader

def load_node_templates(nodes_dir: str) -> List[NodeUserTemplate]:
    templates: List[NodeUserTemplate] = []
    if not os.path.exists(nodes_dir):
        return templates
    for fname in os.listdir(nodes_dir):
        if fname.endswith('.yaml'):
            path = os.path.join(nodes_dir, fname)
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
                templates.append(NodeUserTemplate(data))
    return templates


# .process file IO

def load_process_file(path: str) -> 'GraphModel':
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    model = GraphModel()
    model.load_from_dict(data)
    return model


def save_process_file(path: str, model: 'GraphModel'):
    with open(path, 'w', encoding='utf-8') as f:
        yaml.safe_dump({'graph': model.to_dict()}, f, allow_unicode=True)


# Template validation (basic checks)

def validate_templates(templates: List[NodeUserTemplate]) -> List[str]:
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


def templates_by_type(templates: List[NodeUserTemplate]) -> Dict[str, NodeUserTemplate]:
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

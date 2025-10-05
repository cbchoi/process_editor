# -*- coding: utf-8 -*-
"""
executor_generic.py
Generic dataflow executor driven by node templates (no hard-coded node types).
- Starts from nodes with no inbound links.
- Topologically orders the graph.
- For each node, builds an IN dict from upstream node OUT values, an ATTR dict from node.attributes.
- Executes a template-provided compute snippet (Python) with sandboxed locals: IN, ATTR, OUT.
- After compute, writes back ATTR to node.attributes and OUT to outputs map.
Security: This uses exec on user-provided snippets (trusted environment assumed).
"""
from typing import Dict, Any, List, Tuple

class GenericExecutor:
    supports_cycles = False

    def validate(self, graph: dict) -> list:
        # minimal structure validation
        if not isinstance(graph, dict):
            return ['Invalid graph']
        if not isinstance(graph.get('nodes'), list):
            return ['Invalid nodes list']
        if not isinstance(graph.get('links'), list):
            return ['Invalid links list']
        return []

    def execute(self, graph: dict, templates: Dict[str, dict]) -> dict:
        nodes = graph.get('nodes', [])
        links = graph.get('links', [])
        node_by_id = {n['id']: n for n in nodes}
        # build adjacency and indegree
        outgoing: Dict[str, List[Tuple[str, str, str]]] = {}
        indeg: Dict[str, int] = {n['id']: 0 for n in nodes}
        incoming_by_node: Dict[str, List[Tuple[str, str, str]]] = {}
        for l in links:
            s = l['from']['node_id']
            t = l['to']['node_id']
            outgoing.setdefault(s, []).append((t, l['from']['pin'], l['to']['pin']))
            incoming_by_node.setdefault(t, []).append((s, l['from']['pin'], l['to']['pin']))
            indeg[t] = indeg.get(t, 0) + 1
        # topo order
        q = [nid for nid, d in indeg.items() if d == 0]
        order = []
        while q:
            nid = q.pop(0)
            order.append(nid)
            for (t, fpin, tpin) in outgoing.get(nid, []):
                indeg[t] -= 1
                if indeg[t] == 0:
                    q.append(t)
        # evaluate
        outputs: Dict[str, Dict[str, Any]] = {}
        for nid in order:
            n = node_by_id[nid]
            ntype = n.get('type')
            t = templates.get(ntype) or {}
            compute = t.get('compute')
            IN: Dict[str, Any] = {}
            for (src, from_pin, to_pin) in incoming_by_node.get(nid, []) or []:
                IN[to_pin] = outputs.get(src, {}).get(from_pin)
            ATTR: Dict[str, Any] = dict(n.get('attributes') or {})
            OUT: Dict[str, Any] = {}
            if compute:
                # exec compute snippet with IN, ATTR, OUT
                local_env = {'IN': IN, 'ATTR': ATTR, 'OUT': OUT}
                # allow math functions if needed
                import math
                local_env['math'] = math
                exec(compute, {}, local_env)
                ATTR = local_env['ATTR']
                OUT = local_env['OUT']
            else:
                # default behavior: pass-through attributes to OUT if names match outputs
                for out_def in t.get('outputs') or []:
                    name = out_def.get('name')
                    if name in ATTR:
                        OUT[name] = ATTR[name]
            # write back
            n.setdefault('attributes', {}).update(ATTR)
            outputs[nid] = OUT
        return {'status': 'ok', 'order': order, 'node_outputs': outputs, 'final_graph': graph}

# -*- coding: utf-8 -*-
"""
executor_sum.py
Simple executor that evaluates a tiny dataflow graph with Const1, Const2 and Sum nodes.
- Const1/Const2: output fixed value from attributes['value']
- Sum: A + B, store to attributes['result'] and also return as outputs map
Execution is topologically sorted based on links; cycles are not supported.
"""
from typing import Dict, Any, List, Tuple

class SumExecutor:
    supports_cycles = False

    def validate(self, graph: dict) -> list:
        errors: List[str] = []
        nodes = graph.get('nodes', [])
        links = graph.get('links', [])
        if not nodes:
            errors.append('No nodes in graph')
        # simple validation: at most 1 link per Sum input A/B
        for n in nodes:
            if n.get('type') == 'Sum':
                a_in = 0
                b_in = 0
                for l in links:
                    if l.get('to', {}).get('node_id') == n.get('id'):
                        if l.get('to', {}).get('pin') == 'A':
                            a_in += 1
                        if l.get('to', {}).get('pin') == 'B':
                            b_in += 1
                if a_in > 1 or b_in > 1:
                    errors.append('Sum inputs must have at most one link each')
        return errors

    def execute(self, graph: dict) -> dict:
        nodes = graph.get('nodes', [])
        links = graph.get('links', [])
        node_by_id = {n['id']: n for n in nodes}
        # build adjacency and indegree for topological order
        outgoing: Dict[str, List[Tuple[str, str, str]]] = {}
        indeg: Dict[str, int] = {n['id']: 0 for n in nodes}
        for l in links:
            s = l['from']['node_id']
            t = l['to']['node_id']
            outgoing.setdefault(s, []).append((t, l['from']['pin'], l['to']['pin']))
            indeg[t] = indeg.get(t, 0) + 1
        # init values
        outputs: Dict[str, Dict[str, Any]] = {}
        # queue nodes with indeg 0
        q = [nid for nid, d in indeg.items() if d == 0]
        order = []
        while q:
            nid = q.pop(0)
            order.append(nid)
            for (t, fpin, tpin) in outgoing.get(nid, []):
                indeg[t] -= 1
                if indeg[t] == 0:
                    q.append(t)
        # evaluate in order
        for nid in order:
            n = node_by_id[nid]
            ntype = n.get('type')
            attrs = n.setdefault('attributes', {})
            if ntype in ('Const1', 'Const2'):
                val = float(attrs.get('value', 0.0))
                outputs.setdefault(nid, {})['Value'] = val
            elif ntype == 'Sum':
                # gather inputs from connected nodes' outputs
                a_val = None
                b_val = None
                for l in links:
                    if l.get('to', {}).get('node_id') == nid:
                        if l['to']['pin'] == 'A':
                            a_val = outputs.get(l['from']['node_id'], {}).get(l['from']['pin'])
                        if l['to']['pin'] == 'B':
                            b_val = outputs.get(l['from']['node_id'], {}).get(l['from']['pin'])
                a_val = float(a_val) if a_val is not None else 0.0
                b_val = float(b_val) if b_val is not None else 0.0
                result = a_val + b_val
                attrs['result'] = result
                outputs.setdefault(nid, {})['Out'] = result
            else:
                # passthrough default: nothing
                pass
        return {'status': 'ok', 'order': order, 'node_outputs': outputs, 'final_graph': graph}

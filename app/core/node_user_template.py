# -*- coding: utf-8 -*-
"""
NodeUserTemplate: user-defined node template description loaded from YAML.
Separated from data_model to decouple UI/runtime node objects from template schema.
"""
from typing import Any, Dict, List


class NodeUserTemplate:
    def __init__(self, data: Dict[str, Any]):
        self.type: str = data.get('type')
        self.title: str = data.get('title')
        self.inputs: List[Dict[str, Any]] = data.get('inputs', []) or []
        self.outputs: List[Dict[str, Any]] = data.get('outputs', []) or []
        self.attributes: List[Dict[str, Any]] = data.get('attributes', []) or []
        self.constraints: Dict[str, Any] = data.get('constraints', {}) or {}

    def pin_exists(self, name: str, kind: str) -> bool:
        pins = self.inputs if kind == 'input' else self.outputs
        return any(p.get('name') == name for p in pins)

    def get_attr_default_map(self) -> Dict[str, Any]:
        defaults: Dict[str, Any] = {}
        for a in self.attributes:
            if 'default' in a:
                defaults[a['name']] = a['default']
        return defaults

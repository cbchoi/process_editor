# -*- coding: utf-8 -*-
"""
GUINode: UI-focused node wrapper, binds a model Node to DearPyGui elements.
This isolates UI-specific state like DPG item tags and provides helpers.
"""
from typing import Optional


class GUINode:
    def __init__(self, node_id: str):
        self.node_id = node_id
        # DPG tags for convenience (computed from node_id)
        self.node_tag = f"node::{node_id}"
        self.attr_container_tag = f"attr_container::{node_id}"
        self.width_spacer_tag = f"width_spacer::{node_id}"
        self.sizer_tag = f"sizer::{node_id}"

    # convenience accessors
    def pin_text_tag(self, pin_name: str, kind: str) -> str:
        return f"{ 'pintext' }::{self.node_id}::{pin_name}::{kind}"

    def attr_value_tag(self, attr_name: str) -> str:
        return f"attrval::{self.node_id}::{attr_name}"

    def attr_label_tag(self, attr_name: str) -> str:
        return f"attrlabel::{self.node_id}::{attr_name}"

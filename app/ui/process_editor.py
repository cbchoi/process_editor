# -*- coding: utf-8 -*-
"""
ProcessEditor: DearPyGui-based process editor UI
Encapsulates all UI logic in a class, so app/ui/main.py can simply construct and run it.
"""
import os
import sys
import logging
import traceback

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.data_model import GraphModel, load_process_file, save_process_file, load_node_templates, templates_by_type
from app.core.node_user_template import NodeUserTemplate
from app.ui.gui_node import GUINode
from app.plugins.plugin_loader import run_plugin, load_executor

logger = logging.getLogger(__name__)


class ProcessEditor:
    def __init__(self, model: GraphModel, templates_map: dict):
        self.model = model
        self.templates_map: dict[str, NodeUserTemplate] = templates_map or {}
        # runtime UI state
        self.dpg = None
        self.node_editor_tag = "NodeEditor"
        self.dpg_node_by_model_id = {}
        self.dpg_attr_to_pin = {}
        self.dpg_link_to_model_link = {}
        self.next_pos = [40.0, 40.0]
        self.current_path = {"value": None}
        self.pending_delete_path = {"value": None}
        self.dirty = False
        # sizing
        self.resize_state = {"node_id": None, "start_x": 0.0, "start_w": 180.0}
        self.MIN_NODE_WIDTH = 120
        self.SIZER_WIDTH = 14
        self.CONTENT_PADDING = 8
        self.ATTR_LABEL_WIDTH = 110
        self.ATTR_CONTAINER_MAX_HEIGHT = 140

    # ---------- low-level helpers ----------
    def _content_width(self, node_id: str) -> int:
        return max(self.MIN_NODE_WIDTH - self.SIZER_WIDTH - self.CONTENT_PADDING,
                   self._get_node_width(node_id) - self.SIZER_WIDTH - self.CONTENT_PADDING)

    def _processes_dir(self) -> str:
        path = os.path.join(PROJECT_ROOT, 'processes')
        return path if os.path.isdir(path) else PROJECT_ROOT

    def _status_text(self) -> str:
        base = os.path.basename(self.current_path['value']) if self.current_path.get('value') else 'Untitled.process'
        star = '*' if self.dirty else ''
        return f"{base}{' ' + star if star else ''} | Nodes: {len(self.model.nodes)} Links: {len(self.model.links)}"

    def _update_status(self):
        if self.dpg and self.dpg.does_item_exist('StatusText'):
            self.dpg.set_value('StatusText', self._status_text())

    def _mark_dirty(self):
        if not self.dirty:
            self.dirty = True
            self._update_status()

    def _set_status(self, text: str):
        logger.info('STATUS: %s', text)
        if self.dpg and self.dpg.does_item_exist('StatusText'):
            self.dpg.set_value('StatusText', f"{self._status_text()} | {text}")

    def _show_message(self, title: str, message: str):
        dpg = self.dpg
        logger.warning('MESSAGE [%s]: %s', title, message.replace('\n', ' | '))
        if not dpg.does_item_exist('MsgModal'):
            with dpg.window(label=title, modal=True, show=True, tag='MsgModal', autosize=True):
                dpg.add_text(message, tag='MsgText')
                dpg.add_spacer(height=6)
                dpg.add_button(label='Close', width=100, callback=lambda: dpg.configure_item('MsgModal', show=False))
        else:
            dpg.configure_item('MsgModal', label=title, show=True)
            dpg.set_value('MsgText', message)

    def _refresh_templates_menu(self):
        dpg = self.dpg
        if dpg.does_item_exist('NodeMenu'):
            for child in list(dpg.get_item_children('NodeMenu', 1) or []):
                dpg.delete_item(child)
            for ntype in sorted(self.templates_map.keys()):
                dpg.add_menu_item(label=f"Add {ntype}", callback=self._on_add_node, user_data=ntype, parent='NodeMenu')

    def _register_pin(self, attr_tag: str, node_id: str, pin_name: str, kind: str):
        dpg = self.dpg
        self.dpg_attr_to_pin[attr_tag] = (node_id, pin_name, kind)
        attr_id = None
        try:
            attr_id = dpg.get_alias_id(attr_tag)
        except Exception:
            try:
                info = dpg.get_item_info(attr_tag)
                if isinstance(info, dict):
                    attr_id = info.get('id')
            except Exception:
                attr_id = None
        if attr_id is not None:
            self.dpg_attr_to_pin[attr_id] = (node_id, pin_name, kind)

    def _get_attr_id(self, alias_or_id):
        dpg = self.dpg
        if isinstance(alias_or_id, int):
            return alias_or_id
        try:
            return dpg.get_alias_id(alias_or_id)
        except Exception:
            try:
                info = dpg.get_item_info(alias_or_id)
                if isinstance(info, dict):
                    return info.get('id')
            except Exception:
                pass
        return None

    # ---------- sizing helpers ----------
    def _get_node_width(self, node_id: str) -> int:
        node = self.model.get_node(node_id)
        if not node:
            return 220
        ui = getattr(node, 'ui', None) or {}
        w = ui.get('width')
        try:
            return int(w) if w is not None else 220
        except Exception:
            return 220

    def _set_node_width(self, node_id: str, width: int):
        dpg = self.dpg
        width = max(self.MIN_NODE_WIDTH, int(width))
        spacer_tag = f"width_spacer::{node_id}"
        if dpg.does_item_exist(spacer_tag):
            dpg.configure_item(spacer_tag, width=width - self.SIZER_WIDTH)
        node = self.model.get_node(node_id)
        if node is not None:
            if getattr(node, 'ui', None) is None:
                node.ui = {}
            node.ui['width'] = width
        cw = self._content_width(node_id)
        cont_tag = f"attr_container::{node_id}"
        if dpg.does_item_exist(cont_tag):
            try:
                dpg.configure_item(cont_tag, width=cw, height=self.ATTR_CONTAINER_MAX_HEIGHT)
            except Exception:
                pass
        n = self.model.get_node(node_id)
        t = self.templates_map.get(n.type) if n else None
        for a in (t.attributes if t else []) or []:
            name = a.get('name')
            wtag = f"attrval::{node_id}::{name}"
            if dpg.does_item_exist(wtag):
                try:
                    dpg.configure_item(wtag, width=max(32, cw - self.ATTR_LABEL_WIDTH - 6))
                except Exception:
                    pass
        for kind in ('input', 'output'):
            pins = (t.inputs if (t and kind == 'input') else (t.outputs if t else [])) or []
            for pin in pins:
                pname = pin.get('name')
                ttag = f"pintext::{node_id}::{pname}::{kind}"
                if dpg.does_item_exist(ttag):
                    try:
                        dpg.configure_item(ttag, wrap=cw)
                    except Exception:
                        pass

    # ---------- position sync ----------
    def _sync_positions_from_ui(self):
        dpg = self.dpg
        for node_id, tag in list(self.dpg_node_by_model_id.items()):
            if dpg.does_item_exist(tag):
                try:
                    x, y = dpg.get_item_pos(tag)
                    node = self.model.get_node(node_id)
                    if node is not None:
                        node.position = {'x': float(x), 'y': float(y)}
                except Exception:
                    continue

    # ---------- attribute sync ----------
    def _sync_attributes_from_ui(self):
        dpg = self.dpg
        for node in list(self.model.nodes):
            t = self.templates_map.get(node.type)
            if not t:
                continue
            for a in (t.attributes or []):
                name = a.get('name')
                atype = a.get('type')
                tag = f"attrval::{node.id}::{name}"
                if not dpg.does_item_exist(tag):
                    continue
                try:
                    v = dpg.get_value(tag)
                except Exception:
                    continue
                # coerce type
                try:
                    if atype == 'int':
                        v = int(v)
                    elif atype == 'float':
                        v = float(v)
                    elif atype == 'bool':
                        v = bool(v)
                    elif atype == 'enum' or atype == 'str':
                        v = str(v)
                except Exception:
                    pass
                node.attributes[name] = v

    # ---------- apply graph updates to model/UI ----------
    def _apply_graph_update(self, graph_dict: dict):
        dpg = self.dpg
        if not isinstance(graph_dict, dict):
            return
        nodes = graph_dict.get('nodes') or []
        for n in nodes:
            nid = n.get('id')
            attrs = (n.get('attributes') or {})
            node_obj = self.model.get_node(nid)
            if not node_obj:
                continue
            # merge model attrs
            if getattr(node_obj, 'attributes', None) is None:
                node_obj.attributes = {}
            node_obj.attributes.update(dict(attrs))
            # update UI widgets if present
            for name, val in attrs.items():
                wtag = f"attrval::{nid}::{name}"
                if dpg.does_item_exist(wtag):
                    try:
                        dpg.set_value(wtag, val)
                    except Exception:
                        pass
        # mark dirty since model changed via execution
        self._mark_dirty()

    # ---------- DearPyGui callbacks ----------
    def _on_sizer_pressed(self, sender, app_data, user_data):
        dpg = self.dpg
        nid = user_data
        self.resize_state['node_id'] = nid
        try:
            x, _ = dpg.get_mouse_pos(local=False)
        except Exception:
            x = 0.0
        self.resize_state['start_x'] = float(x)
        self.resize_state['start_w'] = float(self._get_node_width(nid))

    def _on_global_drag(self, sender, app_data):
        dpg = self.dpg
        nid = self.resize_state.get('node_id')
        if not nid:
            return
        try:
            x, _ = dpg.get_mouse_pos(local=False)
        except Exception:
            return
        dx = float(x) - float(self.resize_state.get('start_x', 0.0))
        new_w = int(self.resize_state.get('start_w', 200.0) + dx)
        self._set_node_width(nid, new_w)

    def _on_global_release(self, sender, app_data):
        self.resize_state['node_id'] = None

    def _on_attr_changed(self, node_id: str, attr_name: str, value):
        node = self.model.get_node(node_id)
        if not node:
            return
        if getattr(node, 'attributes', None) is None:
            node.attributes = {}
        node.attributes[attr_name] = value
        self._mark_dirty()

    def _on_execute(self):
        # ensure latest edits are captured even if a widget still has focus
        self._sync_attributes_from_ui()
        errors = self.model.validate(self.templates_map)
        if errors:
            self._show_message('Validation Errors', "\n".join(errors))
            return
        # build plain templates dict for executor
        tdict = {}
        for ttype, t in (self.templates_map or {}).items():
            tdict[ttype] = {
                'type': t.type,
                'title': t.title,
                'inputs': t.inputs,
                'outputs': t.outputs,
                'attributes': t.attributes,
                'constraints': t.constraints,
                'compute': getattr(t, 'compute', None),
            }
        executor = load_executor('app.plugins.executor_generic.GenericExecutor')
        try:
            result = executor.execute(self.model.to_dict(), tdict)
        except Exception as e:
            logger.exception('Executor error: %s', e)
            self._show_message('Execute Error', str(e))
            return
        if isinstance(result, dict) and result.get('status') == 'ok' and isinstance(result.get('final_graph'), dict):
            self._apply_graph_update(result.get('final_graph'))
        if self.dpg.does_item_exist('OutputText'):
            try:
                import json
                self.dpg.set_value('OutputText', json.dumps(result, ensure_ascii=False, indent=2))
            except Exception:
                self.dpg.set_value('OutputText', str(result))
        self._set_status('Execute done')

    def _on_new_process(self):
        self.model.load_from_dict({'graph': {'nodes': [], 'links': [], 'metadata': {}}})
        self._ui_clear_nodes_and_links()
        self.current_path['value'] = None
        self.dirty = False
        self._update_status()
        self._set_status('New process')

    def _on_add_node(self, sender, app_data, user_data):
        ntype = user_data
        t: NodeUserTemplate = self.templates_map.get(ntype)
        if not t:
            self._show_message('Error', f'Unknown template: {ntype}')
            return
        nid = self.model.add_node(t)
        node_obj = self.model.get_node(nid)
        self._ui_create_node(nid, t, node_obj)
        self._mark_dirty()
        self._set_status(f'Added node {ntype}')

    def _on_delete_node(self, sender, app_data, user_data):
        dpg = self.dpg
        node_id = user_data
        to_delete = []
        for ltag, mid in list(self.dpg_link_to_model_link.items()):
            link = next((L for L in self.model.links if L.get('id') == mid), None)
            if link and (link['from']['node_id'] == node_id or link['to']['node_id'] == node_id):
                to_delete.append(ltag)
        for ltag in to_delete:
            if dpg.does_item_exist(ltag):
                dpg.delete_item(ltag)
            self.dpg_link_to_model_link.pop(ltag, None)
        tag = self.dpg_node_by_model_id.pop(node_id, None)
        if tag and dpg.does_item_exist(tag):
            dpg.delete_item(tag)
        self.model.remove_node(node_id)
        self._mark_dirty()
        self._set_status(f'Deleted node {node_id}')

    def _on_link_created(self, sender, app_data):
        dpg = self.dpg
        dpg_link_id = None
        if isinstance(app_data, (list, tuple)) and len(app_data) >= 3:
            dpg_link_id, a1, a2 = app_data[0], app_data[1], app_data[2]
        elif isinstance(app_data, (list, tuple)) and len(app_data) == 2:
            a1, a2 = app_data[0], app_data[1]
        else:
            return
        pin1 = self.dpg_attr_to_pin.get(a1)
        pin2 = self.dpg_attr_to_pin.get(a2)
        if not pin1 or not pin2:
            if dpg_link_id is not None and dpg.does_item_exist(dpg_link_id):
                try:
                    dpg.delete_item(dpg_link_id)
                except Exception:
                    pass
            return
        if pin1[2] == 'input' and pin2[2] == 'output':
            pin_out, pin_in = pin2, pin1
            attr_out_raw, attr_in_raw = a2, a1
        elif pin1[2] == 'output' and pin2[2] == 'input':
            pin_out, pin_in = pin1, pin2
            attr_out_raw, attr_in_raw = a1, a2
        else:
            self._show_message('Link Error', 'Links must be from output to input')
            if dpg_link_id is not None and dpg.does_item_exist(dpg_link_id):
                try:
                    dpg.delete_item(dpg_link_id)
                except Exception:
                    pass
            return
        model_link_id = self.model.add_link(pin_out[0], pin_out[1], pin_in[0], pin_in[1])
        errors = self.model.validate(self.templates_map)
        if errors:
            self.model.remove_link(model_link_id)
            self._show_message('Validation Error', "\n".join(errors))
            if dpg_link_id is not None and dpg.does_item_exist(dpg_link_id):
                try:
                    dpg.delete_item(dpg_link_id)
                except Exception:
                    pass
            return
        if dpg_link_id is None:
            out_id = self._get_attr_id(attr_out_raw)
            in_id = self._get_attr_id(attr_in_raw)
            if out_id is None or in_id is None:
                self.model.remove_link(model_link_id)
                return
            dpg_link_id = dpg.add_node_link(out_id, in_id, parent=self.node_editor_tag)
            try:
                if dpg_link_id is None:
                    dpg_link_id = dpg.last_item()
            except Exception:
                pass
        self.dpg_link_to_model_link[dpg_link_id] = model_link_id
        # link context menu
        try:
            with dpg.popup(dpg_link_id, mousebutton=dpg.mvMouseButton_Right):
                dpg.add_menu_item(label="Delete Link", callback=lambda s, a, u=dpg_link_id: self._delete_link_by_id(u))
        except Exception:
            pass
        self._mark_dirty()
        self._set_status('Link created')

    def _delete_link_by_id(self, dpg_link_id):
        if self.dpg.does_item_exist(dpg_link_id):
            # Deleting the item triggers delink_callback which updates model
            self.dpg.delete_item(dpg_link_id)

    def _on_link_deleted(self, sender, app_data):
        dpg_link_id = app_data
        mid = self.dpg_link_to_model_link.pop(dpg_link_id, None)
        if mid is None:
            try:
                alias = None
                if isinstance(dpg_link_id, int):
                    alias = self.dpg.get_item_alias(dpg_link_id)
                if alias:
                    mid = self.dpg_link_to_model_link.pop(alias, None)
            except Exception:
                pass
        if mid:
            self.model.remove_link(mid)
            self._mark_dirty()
        self._set_status('Link deleted')

    # ---------- file handlers ----------
    def _on_open_dialog(self, sender, app_data):
        dpg = self.dpg
        path = app_data.get('file_path_name') if isinstance(app_data, dict) else None
        if not path or not os.path.isfile(path) or not path.lower().endswith('.process'):
            self._show_message('Open Error', 'Select a valid .process file.')
            return
        try:
            loaded = load_process_file(path)
            self._ui_clear_nodes_and_links()
            self.model.load_from_dict({'graph': loaded.to_dict()})
            for n in self.model.nodes:
                t = self.templates_map.get(n.type)
                if t:
                    self._ui_create_node(n.id, t, n)
            for l in self.model.links:
                out_attr = f"attr::{l['from']['node_id']}::{l['from']['pin']}::output"
                in_attr = f"attr::{l['to']['node_id']}::{l['to']['pin']}::input"
                link_tag = f"link::{l['id']}"
                if dpg.does_item_exist(out_attr) and dpg.does_item_exist(in_attr):
                    dpg.add_node_link(out_attr, in_attr, parent=self.node_editor_tag, tag=link_tag)
                    self.dpg_link_to_model_link[link_tag] = l['id']
            self.current_path['value'] = path
            self.dirty = False
            self._update_status()
            self._set_status(f'Opened: {path}')
        except Exception as e:
            logger.exception('Failed to open file: %s', e)
            self._show_message('Open Error', str(e))

    def _on_save(self, path: str):
        try:
            # ensure latest positions are captured
            self._sync_positions_from_ui()
            # ensure extension
            if not path.lower().endswith('.process'):
                path = f"{path}.process"
            os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
            save_process_file(path, self.model)
            self.current_path['value'] = path
            self.dirty = False
            self._update_status()
            self._set_status(f'Saved: {path}')
        except Exception as e:
            logger.exception('Failed to save file: %s', e)
            self._show_message('Save Error', str(e))

    def _on_save_dialog(self, sender, app_data):
        path = app_data.get('file_path_name') if isinstance(app_data, dict) else None
        if path:
            self._on_save(path)

    def _on_save_menu(self):
        # Save to current path or fall back to Save As
        if self.current_path.get('value'):
            self._on_save(self.current_path['value'])
        else:
            self._on_save_as_menu()

    def _on_save_as_menu(self):
        base = self._processes_dir()
        default_name = 'untitled.process'
        try:
            self.dpg.configure_item('SaveDialog', default_path=base, default_filename=default_name, show=True)
        except Exception:
            self.dpg.configure_item('SaveDialog', show=True)

    def _on_open_menu(self):
        base = self._processes_dir()
        try:
            self.dpg.configure_item('OpenDialog', default_path=base, show=True)
        except Exception:
            self.dpg.configure_item('OpenDialog', show=True)

    def _on_delete_menu(self):
        base = self._processes_dir()
        try:
            self.dpg.configure_item('DeleteDialog', default_path=base, show=True)
        except Exception:
            self.dpg.configure_item('DeleteDialog', show=True)

    def _on_delete_dialog(self, sender, app_data):
        dpg = self.dpg
        path = app_data.get('file_path_name') if isinstance(app_data, dict) else None
        if not path or not os.path.isfile(path) or not path.lower().endswith('.process'):
            self._show_message('Delete Error', 'Select a valid .process file.')
            return
        self.pending_delete_path['value'] = path
        if not dpg.does_item_exist('ConfirmDelete'):
            with dpg.window(label='Confirm Delete', modal=True, show=True, tag='ConfirmDelete', autosize=True):
                dpg.add_text(f"Delete file?\n{path}", tag='ConfirmDeleteText')
                with dpg.group(horizontal=True):
                    dpg.add_button(label='Yes', width=80, callback=lambda: self._on_confirm_delete())
                    dpg.add_button(label='No', width=80, callback=lambda: dpg.configure_item('ConfirmDelete', show=False))
        else:
            dpg.set_value('ConfirmDeleteText', f"Delete file?\n{path}")
            dpg.configure_item('ConfirmDelete', show=True)

    def _on_confirm_delete(self):
        dpg = self.dpg
        path = self.pending_delete_path.get('value')
        try:
            if path and os.path.exists(path):
                os.remove(path)
                self._set_status(f'Deleted file: {path}')
            else:
                self._show_message('Delete Error', 'File does not exist.')
        except Exception as e:
            logger.exception('Failed to delete file: %s', e)
            self._show_message('Delete Error', str(e))
        finally:
            if dpg.does_item_exist('ConfirmDelete'):
                dpg.configure_item('ConfirmDelete', show=False)

    def _on_refresh_templates(self):
        try:
            templates = load_node_templates('nodes')
            self.templates_map = templates_by_type(templates)
            self._refresh_templates_menu()
            self._set_status('Templates refreshed')
        except Exception as e:
            logger.exception('Failed to refresh templates: %s', e)
            self._show_message('Template Error', str(e))

    def _delete_selected(self):
        dpg = self.dpg
        # delete selected links first
        try:
            links = list(dpg.get_selected_links(self.node_editor_tag) or [])
        except Exception:
            links = []
        for lid in links:
            if dpg.does_item_exist(lid):
                dpg.delete_item(lid)
        # nodes
        try:
            nodes = list(dpg.get_selected_nodes(self.node_editor_tag) or [])
        except Exception:
            nodes = []
        # map tag -> model id
        rev = {v: k for k, v in self.dpg_node_by_model_id.items()}
        for ntag in nodes:
            mid = rev.get(ntag)
            if mid:
                self._on_delete_node(None, None, mid)
        self._mark_dirty()

    # ---------- UI builders ----------
    def _ui_create_node(self, node_id: str, template: NodeUserTemplate, node_obj):
        dpg = self.dpg
        gui_node = GUINode(node_id)
        title = getattr(node_obj, 'title', None) or template.title or template.type
        with dpg.node(label=title, parent=self.node_editor_tag, tag=gui_node.node_tag):
            # Inputs
            for pin in (template.inputs or []):
                attr_tag = f"attr::{node_id}::{pin.get('name')}::input"
                with dpg.node_attribute(attribute_type=dpg.mvNode_Attr_Input, tag=attr_tag):
                    dpg.add_text(pin.get('name'), tag=gui_node.pin_text_tag(pin.get('name'), 'input'), wrap=self._content_width(node_id))
                self._register_pin(attr_tag, node_id, pin.get('name'), 'input')
            # Outputs
            for pin in (template.outputs or []):
                attr_tag = f"attr::{node_id}::{pin.get('name')}::output"
                with dpg.node_attribute(attribute_type=dpg.mvNode_Attr_Output, tag=attr_tag):
                    dpg.add_text(pin.get('name'), tag=gui_node.pin_text_tag(pin.get('name'), 'output'), wrap=self._content_width(node_id))
                self._register_pin(attr_tag, node_id, pin.get('name'), 'output')
            # Attributes (STATIC so it doesn't create ports)
            attrs = getattr(node_obj, 'attributes', {}) or {}
            if template.attributes:
                with dpg.node_attribute(attribute_type=dpg.mvNode_Attr_Static):
                    with dpg.child_window(tag=gui_node.attr_container_tag, autosize_y=False, width=self._content_width(node_id), height=min(max(len(template.attributes)*20, 20), self.ATTR_CONTAINER_MAX_HEIGHT), border=False):
                        for a in template.attributes:
                            name = a.get('name')
                            atype = a.get('type')
                            val = attrs.get(name, a.get('default'))
                            widget_tag = gui_node.attr_value_tag(name)
                            with dpg.group(horizontal=True):
                                dpg.add_text(name, tag=gui_node.attr_label_tag(name), wrap=self.ATTR_LABEL_WIDTH)
                                w = max(32, self._content_width(node_id) - self.ATTR_LABEL_WIDTH - 6)
                                if atype == 'int':
                                    dpg.add_input_int(label="", default_value=int(val) if val is not None else 0, tag=widget_tag, width=w,
                                                      callback=lambda s, a, u=name: self._on_attr_changed(node_id, u, dpg.get_value(s)))
                                elif atype == 'float':
                                    dpg.add_input_float(label="", default_value=float(val) if val is not None else 0.0, tag=widget_tag, width=w,
                                                        callback=lambda s, a, u=name: self._on_attr_changed(node_id, u, dpg.get_value(s)))
                                elif atype == 'bool':
                                    dpg.add_checkbox(label="", default_value=bool(val) if val is not None else False, tag=widget_tag)
                                    dpg.set_item_callback(widget_tag, lambda s, a, u=name: self._on_attr_changed(node_id, u, dpg.get_value(s)))
                                elif atype == 'enum':
                                    items = a.get('enum') or []
                                    current = val if val in items else (items[0] if items else '')
                                    dpg.add_combo(items=items, label="", default_value=current, tag=widget_tag, width=w,
                                                  callback=lambda s, a, u=name: self._on_attr_changed(node_id, u, dpg.get_value(s)))
                                else:
                                    dpg.add_input_text(label="", default_value=str(val) if val is not None else '', tag=widget_tag, width=w,
                                                       callback=lambda s, a, u=name: self._on_attr_changed(node_id, u, dpg.get_value(s)))
            # Bottom-right sizer
            with dpg.node_attribute(attribute_type=dpg.mvNode_Attr_Static):
                with dpg.group(horizontal=True):
                    dpg.add_spacer(tag=gui_node.width_spacer_tag, width=max(self.MIN_NODE_WIDTH, self._get_node_width(node_id)) - self.SIZER_WIDTH)
                    dpg.add_button(tag=gui_node.sizer_tag, label="⠿", width=self.SIZER_WIDTH, height=16, callback=self._on_sizer_pressed, user_data=node_id)
        pos = getattr(node_obj, 'position', None) or {'x': self.next_pos[0], 'y': self.next_pos[1]}
        self.dpg.set_item_pos(gui_node.node_tag, (pos.get('x', self.next_pos[0]), pos.get('y', self.next_pos[1])))
        self.dpg_node_by_model_id[node_id] = gui_node.node_tag
        with self.dpg.popup(gui_node.node_tag, mousebutton=self.dpg.mvMouseButton_Right):
            self.dpg.add_menu_item(label="Delete Node", callback=self._on_delete_node, user_data=node_id)
        self.next_pos[0] += 80.0
        self.next_pos[1] += 60.0

    def _ui_clear_nodes_and_links(self):
        dpg = self.dpg
        for tag in list(self.dpg_link_to_model_link.keys()):
            if dpg.does_item_exist(tag):
                dpg.delete_item(tag)
        self.dpg_link_to_model_link.clear()
        for tag in list(self.dpg_node_by_model_id.values()):
            if dpg.does_item_exist(tag):
                dpg.delete_item(tag)
        self.dpg_node_by_model_id.clear()
        self.dpg_attr_to_pin.clear()

    # ---------- font ----------
    def _try_bind_custom_font(self):
        dpg = self.dpg
        try:
            candidates = [
                os.path.join(PROJECT_ROOT, 'assets', 'fonts', 'NotoSansMono-Regular.ttf'),
                os.path.join(PROJECT_ROOT, 'app', 'ui', 'assets', 'fonts', 'NotoSansMono-Regular.ttf'),
                os.environ.get('PROCESS_EDITOR_FONT_PATH') or '',
            ]
            candidates = [p for p in candidates if p and os.path.isfile(p)]
            if not candidates:
                logger.warning('Custom font not found; using default DearPyGui font')
                return None
            with dpg.font_registry():
                font_tag = dpg.add_font(candidates[0], 14)
            dpg.bind_font(font_tag)
            return font_tag
        except Exception:
            logger.exception('Failed to load/bind custom font')
            return None

    # ---------- run ----------
    def run(self):
        try:
            import dearpygui.dearpygui as dpg
        except Exception as e:
            logger.exception('Failed to import dearpygui: %s', e)
            print('Failed to import dearpygui:', e, file=sys.stderr)
            raise
        self.dpg = dpg
        try:
            dpg.create_context()
            self._try_bind_custom_font()
            try:
                dpg.set_exit_callback(lambda: logger.info('DearPyGui exit callback invoked'))
            except Exception:
                pass
            with dpg.window(tag="Primary Window", label="Process Editor", width=1200, height=800):
                with dpg.menu_bar():
                    with dpg.menu(label="File"):
                        dpg.add_menu_item(label="New Process", callback=lambda: self._on_new_process())
                        dpg.add_menu_item(label="Open...", callback=lambda: self._on_open_menu())
                        dpg.add_menu_item(label="Save", callback=lambda: self._on_save_menu())
                        dpg.add_menu_item(label="Save As...", callback=lambda: self._on_save_as_menu())
                        dpg.add_menu_item(label="Delete...", callback=lambda: self._on_delete_menu())
                    with dpg.menu(label="Node", tag='NodeMenu'):
                        pass
                    with dpg.menu(label="Templates"):
                        dpg.add_menu_item(label="Refresh", callback=lambda: self._on_refresh_templates())
                    with dpg.menu(label="Edit"):
                        dpg.add_menu_item(label="Delete Selected", shortcut="Del", callback=lambda: self._delete_selected())
                    with dpg.menu(label="Run"):
                        dpg.add_menu_item(label="Execute", shortcut="F5", callback=lambda: self._on_execute())
                dpg.add_node_editor(tag=self.node_editor_tag,
                                    callback=self._on_link_created,
                                    delink_callback=self._on_link_deleted,
                                    minimap=True,
                                    minimap_location=dpg.mvNodeMiniMap_Location_BottomRight)
                dpg.add_spacer(height=8)
                dpg.add_button(label="Execute", callback=lambda: self._on_execute())
                dpg.add_spacer(height=8)
                dpg.add_separator()
                dpg.add_text("Ready", tag='StatusText')
                dpg.add_spacer(height=6)
                dpg.add_text("Output:")
                dpg.add_input_text(tag='OutputText', default_value='', multiline=True, readonly=True, height=120, width=-1)
            # file dialogs: restrict to .process only to avoid invalid selections like test.*
            with dpg.file_dialog(directory_selector=False, show=False, callback=self._on_open_dialog, tag='OpenDialog', width=700, height=400, modal=True):
                dpg.add_file_extension(".process", color=(0, 255, 0, 255))
            with dpg.file_dialog(directory_selector=False, show=False, callback=self._on_save_dialog, tag='SaveDialog', width=700, height=400, modal=True):
                dpg.add_file_extension(".process", color=(0, 255, 0, 255))
            with dpg.file_dialog(directory_selector=False, show=False, callback=self._on_delete_dialog, tag='DeleteDialog', width=700, height=400, modal=True):
                dpg.add_file_extension(".process", color=(255, 0, 0, 255))
            if not dpg.does_item_exist('GlobalHandlers'):
                with dpg.handler_registry(tag='GlobalHandlers'):
                    dpg.add_mouse_drag_handler(button=0, threshold=0.0, callback=self._on_global_drag)
                    dpg.add_mouse_release_handler(button=0, callback=self._on_global_release)
                    try:
                        dpg.add_key_press_handler(key=dpg.mvKey_Delete, callback=lambda: self._delete_selected())
                        dpg.add_key_press_handler(key=dpg.mvKey_F5, callback=lambda: self._on_execute())
                    except Exception:
                        pass
            self._refresh_templates_menu()
            dpg.create_viewport(title='Process Editor', width=1300, height=900)
            dpg.setup_dearpygui()
            dpg.show_viewport()
            dpg.set_primary_window("Primary Window", True)
            self._update_status()
            dpg.start_dearpygui()
        except Exception:
            logger.exception('Error while running DearPyGui event loop')
            print('Error while running DearPyGui event loop:', file=sys.stderr)
            traceback.print_exc()
            raise
        finally:
            try:
                dpg.destroy_context()
            except Exception:
                logger.exception('Error destroying DearPyGui context')
                pass

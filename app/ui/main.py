# -*- coding: utf-8 -*-
"""
Minimal UI skeleton evolved: core/plugin integration, Node Editor with nodes/links,
File/Node menus, attribute editors, execute, and basic persistence.
This module is safe to import for tests (won't start GUI unless run as script).
"""
import sys
import os
import argparse
import traceback
import logging

# Ensure project root is on sys.path so `import app` works when running this file directly
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.data_model import (
    load_node_templates,
    GraphModel,
    templates_by_type,
    NodeTemplate,
    validate_templates,
    save_process_file,
    load_process_file,
)
from app.plugins.plugin_loader import run_plugin
from app.util.logging_config import setup_logging

logger = logging.getLogger(__name__)


def start_gui(model: GraphModel, templates_map):
    try:
        import dearpygui.dearpygui as dpg
    except Exception as e:
        logger.exception('Failed to import dearpygui: %s', e)
        print('Failed to import dearpygui:', e, file=sys.stderr)
        raise

    logger.debug('Starting GUI with %d templates', len(templates_map))

    # State for UI <-> model mapping
    node_editor_tag = "NodeEditor"
    dpg_node_by_model_id = {}
    dpg_attr_to_pin = {}  # maps both alias (str) and id (int) -> (node_id, pin_name, kind)
    dpg_link_to_model_link = {}  # dpg_link_id -> model_link_id
    next_pos = [40.0, 40.0]  # simple cascading placement
    current_path = {"value": None}
    pending_delete_path = {"value": None}

    def processes_dir() -> str:
        path = os.path.join(PROJECT_ROOT, 'processes')
        return path if os.path.isdir(path) else PROJECT_ROOT

    # --- helpers ---
    def set_status(text: str):
        logger.info('STATUS: %s', text)
        if dpg.does_item_exist('StatusText'):
            dpg.set_value('StatusText', text)

    def show_message(title: str, message: str):
        logger.warning('MESSAGE [%s]: %s', title, message.replace('\n', ' | '))
        if not dpg.does_item_exist('MsgModal'):
            with dpg.window(label=title, modal=True, show=True, tag='MsgModal', autosize=True):
                dpg.add_text(message, tag='MsgText')
                dpg.add_spacer(height=6)
                dpg.add_button(label='Close', width=100, callback=lambda: dpg.configure_item('MsgModal', show=False))
        else:
            dpg.configure_item('MsgModal', label=title, show=True)
            dpg.set_value('MsgText', message)

    def refresh_templates_menu():
        logger.debug('Refreshing Node menu with %d templates', len(templates_map))
        # Rebuild Node menu items
        if dpg.does_item_exist('NodeMenu'):
            for child in list(dpg.get_item_children('NodeMenu', 1) or []):
                dpg.delete_item(child)
            for ntype in templates_map.keys():
                dpg.add_menu_item(label=f"Add {ntype}", callback=on_add_node, user_data=ntype, parent='NodeMenu')

    def _register_pin(attr_tag: str, node_id: str, pin_name: str, kind: str):
        # map alias
        dpg_attr_to_pin[attr_tag] = (node_id, pin_name, kind)
        # map numeric id if available
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
            dpg_attr_to_pin[attr_id] = (node_id, pin_name, kind)
            logger.debug('Registered pin: alias=%s id=%s (%s.%s.%s)', attr_tag, attr_id, node_id, pin_name, kind)
        else:
            logger.debug('Registered pin: alias=%s (no id) (%s.%s.%s)', attr_tag, node_id, pin_name, kind)

    def _get_attr_id(alias_or_id):
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

    def ui_create_node(node_id: str, template: NodeTemplate, node_data: dict):
        logger.debug('UI create node: id=%s type=%s', node_id, template.type)
        node_tag = f"node::{node_id}"
        with dpg.node(label=node_data.get('title') or template.title or template.type, parent=node_editor_tag, tag=node_tag):
            # Inputs
            for pin in (template.inputs or []):
                attr_tag = f"attr::{node_id}::{pin.get('name')}::input"
                with dpg.node_attribute(label=pin.get('name'), attribute_type=dpg.mvNode_Attr_Input, tag=attr_tag):
                    dpg.add_text(pin.get('name'))
                _register_pin(attr_tag, node_id, pin.get('name'), 'input')
            # Outputs
            for pin in (template.outputs or []):
                attr_tag = f"attr::{node_id}::{pin.get('name')}::output"
                with dpg.node_attribute(label=pin.get('name'), attribute_type=dpg.mvNode_Attr_Output, tag=attr_tag):
                    dpg.add_text(pin.get('name'))
                _register_pin(attr_tag, node_id, pin.get('name'), 'output')
            # Attributes (editable)
            if template.attributes:
                with dpg.node_attribute():
                    dpg.add_separator()
                    dpg.add_text("Attributes:")
                    for a in template.attributes:
                        name = a.get('name')
                        atype = a.get('type')
                        val = (node_data.get('attributes') or {}).get(name, a.get('default'))
                        widget_tag = f"attrval::{node_id}::{name}"
                        if atype == 'int':
                            dpg.add_input_int(label=name, default_value=int(val) if val is not None else 0, tag=widget_tag,
                                              callback=lambda s, a, u=name: on_attr_changed(node_id, u, dpg.get_value(s)))
                        elif atype == 'float':
                            dpg.add_input_float(label=name, default_value=float(val) if val is not None else 0.0, tag=widget_tag,
                                                callback=lambda s, a, u=name: on_attr_changed(node_id, u, dpg.get_value(s)))
                        elif atype == 'bool':
                            dpg.add_checkbox(label=name, default_value=bool(val) if val is not None else False, tag=widget_tag,
                                             callback=lambda s, a, u=name: on_attr_changed(node_id, u, dpg.get_value(s)))
                        elif atype == 'enum':
                            items = a.get('enum') or []
                            current = val if val in items else (items[0] if items else '')
                            dpg.add_combo(items=items, label=name, default_value=current, tag=widget_tag,
                                          callback=lambda s, a, u=name: on_attr_changed(node_id, u, dpg.get_value(s)))
                        else:
                            dpg.add_input_text(label=name, default_value=str(val) if val is not None else '', tag=widget_tag,
                                               callback=lambda s, a, u=name: on_attr_changed(node_id, u, dpg.get_value(s)))
        pos = node_data.get('position') or {'x': next_pos[0], 'y': next_pos[1]}
        dpg.set_item_pos(node_tag, (pos.get('x', next_pos[0]), pos.get('y', next_pos[1])))
        dpg_node_by_model_id[node_id] = node_tag
        with dpg.popup(node_tag, mousebutton=dpg.mvMouseButton_Right):
            dpg.add_menu_item(label="Delete Node", callback=on_delete_node, user_data=node_id)
        next_pos[0] += 80.0
        next_pos[1] += 60.0

    def ui_clear_nodes_and_links():
        logger.debug('Clearing all nodes and links from UI')
        for tag in list(dpg_link_to_model_link.keys()):
            if dpg.does_item_exist(tag):
                dpg.delete_item(tag)
        dpg_link_to_model_link.clear()
        for tag in list(dpg_node_by_model_id.values()):
            if dpg.does_item_exist(tag):
                dpg.delete_item(tag)
        dpg_node_by_model_id.clear()
        dpg_attr_to_pin.clear()

    def on_attr_changed(node_id: str, attr_name: str, value):
        logger.debug('Attribute changed: node=%s attr=%s value=%r', node_id, attr_name, value)
        node = model.get_node(node_id)
        if not node:
            logger.warning('Attribute change ignored: node not found: %s', node_id)
            return
        node.setdefault('attributes', {})[attr_name] = value

    def on_execute():
        logger.info('Execute requested')
        errors = model.validate(templates_map)
        if errors:
            show_message('Validation Errors', "\n".join(errors))
            logger.error('Validation failed: %s', errors)
            return
        result = run_plugin('app.plugins.sample.SampleExecutor', model.to_dict())
        logger.info('Plugin result: %s', result)
        print(result)

    def on_new_process():
        logger.info('New process')
        model.load_from_dict({'graph': {'nodes': [], 'links': [], 'metadata': {}}})
        ui_clear_nodes_and_links()
        set_status('New process')

    def on_add_node(sender, app_data, user_data):
        ntype = user_data
        logger.info('Add node requested: %s', ntype)
        t = templates_map.get(ntype)
        if not t:
            show_message('Error', f'Unknown template: {ntype}')
            logger.error('Unknown template: %s', ntype)
            return
        nid = model.add_node(t)
        node_data = model.get_node(nid)
        ui_create_node(nid, t, node_data)
        set_status(f'Added node {ntype}')

    def on_delete_node(sender, app_data, user_data):
        node_id = user_data
        logger.info('Delete node requested: %s', node_id)
        # Remove links related to node in UI first
        to_delete = []
        for ltag, mid in list(dpg_link_to_model_link.items()):
            link = next((L for L in model.links if L.get('id') == mid), None)
            if link and (link['from']['node_id'] == node_id or link['to']['node_id'] == node_id):
                to_delete.append(ltag)
        for ltag in to_delete:
            if dpg.does_item_exist(ltag):
                dpg.delete_item(ltag)
            dpg_link_to_model_link.pop(ltag, None)
        # Remove node in UI and model
        tag = dpg_node_by_model_id.pop(node_id, None)
        if tag and dpg.does_item_exist(tag):
            dpg.delete_item(tag)
        model.remove_node(node_id)
        set_status(f'Deleted node {node_id}')

    def on_link_created(sender, app_data):
        logger.debug('Link created callback: app_data=%r', app_data)
        dpg_link_id = None
        if isinstance(app_data, (list, tuple)) and len(app_data) >= 3:
            # (dpg_link_id, attr_start, attr_end)
            dpg_link_id, a1, a2 = app_data[0], app_data[1], app_data[2]
        elif isinstance(app_data, (list, tuple)) and len(app_data) == 2:
            # (attr_start, attr_end)
            a1, a2 = app_data[0], app_data[1]
        else:
            logger.warning('Unexpected link created app_data: %r', app_data)
            return
        # Identify pins (support alias or id)
        pin1 = dpg_attr_to_pin.get(a1)
        pin2 = dpg_attr_to_pin.get(a2)
        if not pin1 or not pin2:
            logger.warning('Unknown pin(s) for link: %r, %r', pin1, pin2)
            # roll back UI-created link if present
            if dpg_link_id is not None and dpg.does_item_exist(dpg_link_id):
                try:
                    dpg.delete_item(dpg_link_id)
                except Exception:
                    logger.exception('Failed to rollback UI link: %s', dpg_link_id)
            return
        # Determine direction
        if pin1[2] == 'input' and pin2[2] == 'output':
            pin_out, pin_in = pin2, pin1
            attr_out_raw, attr_in_raw = a2, a1
        elif pin1[2] == 'output' and pin2[2] == 'input':
            pin_out, pin_in = pin1, pin2
            attr_out_raw, attr_in_raw = a1, a2
        else:
            show_message('Link Error', 'Links must be from output to input')
            logger.warning('Invalid link direction: %r, %r', pin1, pin2)
            if dpg_link_id is not None and dpg.does_item_exist(dpg_link_id):
                try:
                    dpg.delete_item(dpg_link_id)
                except Exception:
                    logger.exception('Failed to rollback UI link: %s', dpg_link_id)
            return
        # Create model link
        model_link_id = model.add_link(pin_out[0], pin_out[1], pin_in[0], pin_in[1])
        # Validate constraints; if invalid, rollback
        errors = model.validate(templates_map)
        if errors:
            model.remove_link(model_link_id)
            show_message('Validation Error', "\n".join(errors))
            logger.error('Validation failed on link create: %s', errors)
            if dpg_link_id is not None and dpg.does_item_exist(dpg_link_id):
                try:
                    dpg.delete_item(dpg_link_id)
                except Exception:
                    logger.exception('Failed to rollback UI link: %s', dpg_link_id)
            return
        # Create UI link if DearPyGui didn't create one (len==2 case)
        if dpg_link_id is None:
            out_id = _get_attr_id(attr_out_raw)
            in_id = _get_attr_id(attr_in_raw)
            if out_id is None or in_id is None:
                logger.error('Failed to resolve attribute ids for link creation: out=%r in=%r', attr_out_raw, attr_in_raw)
                model.remove_link(model_link_id)
                return
            dpg_link_id = dpg.add_node_link(out_id, in_id, parent=node_editor_tag)
            try:
                # DearPyGui returns id; ensure we have it
                if dpg_link_id is None:
                    dpg_link_id = dpg.last_item()
            except Exception:
                pass
        dpg_link_to_model_link[dpg_link_id] = model_link_id
        set_status('Link created')

    def on_link_deleted(sender, app_data):
        # app_data is the dpg link id
        dpg_link_id = app_data
        logger.debug('Link deleted callback: link_id=%r', dpg_link_id)
        mid = dpg_link_to_model_link.pop(dpg_link_id, None)
        if mid is None:
            # try alias resolution if key is id
            try:
                alias = None
                if isinstance(dpg_link_id, int):
                    alias = dpg.get_item_alias(dpg_link_id)
                if alias:
                    mid = dpg_link_to_model_link.pop(alias, None)
            except Exception:
                pass
        if mid:
            model.remove_link(mid)
        set_status('Link deleted')

    # File menu handlers
    def on_open_dialog(sender, app_data):
        path = app_data.get('file_path_name') if isinstance(app_data, dict) else None
        logger.info('Open dialog path: %r', path)
        if not path:
            return
        try:
            loaded = load_process_file(path)
            # Rebuild UI from loaded model
            ui_clear_nodes_and_links()
            model.load_from_dict({'graph': loaded.to_dict()})
            # Recreate nodes (links handled after nodes)
            for n in model.nodes:
                t = templates_map.get(n['type'])
                if t:
                    ui_create_node(n['id'], t, n)
            # Recreate links
            for l in model.links:
                out_attr = f"attr::{l['from']['node_id']}::{l['from']['pin']}::output"
                in_attr = f"attr::{l['to']['node_id']}::{l['to']['pin']}::input"
                link_tag = f"link::{l['id']}"
                if dpg.does_item_exist(out_attr) and dpg.does_item_exist(in_attr):
                    dpg.add_node_link(out_attr, in_attr, parent=node_editor_tag, tag=link_tag)
                    dpg_link_to_model_link[link_tag] = l['id']
            current_path['value'] = path
            set_status(f'Opened: {path}')
        except Exception as e:
            logger.exception('Failed to open file: %s', e)
            show_message('Open Error', str(e))

    def on_save(path: str):
        logger.info('Save to: %r', path)
        try:
            os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
            save_process_file(path, model)
            current_path['value'] = path
            set_status(f'Saved: {path}')
        except Exception as e:
            logger.exception('Failed to save file: %s', e)
            show_message('Save Error', str(e))

    def on_save_dialog(sender, app_data):
        path = app_data.get('file_path_name') if isinstance(app_data, dict) else None
        logger.info('Save dialog path: %r', path)
        if path:
            on_save(path)

    def on_save_menu():
        logger.info('Save menu clicked')
        # Always show save file dialog as requested; set default path/name
        base = processes_dir()
        default_name = 'untitled.process'
        try:
            dpg.configure_item('SaveDialog', default_path=base, default_filename=default_name, show=True)
        except Exception:
            dpg.configure_item('SaveDialog', show=True)

    def on_open_menu():
        logger.info('Open menu clicked')
        base = processes_dir()
        try:
            dpg.configure_item('OpenDialog', default_path=base, show=True)
        except Exception:
            dpg.configure_item('OpenDialog', show=True)

    def on_delete_menu():
        logger.info('Delete menu clicked')
        base = processes_dir()
        try:
            dpg.configure_item('DeleteDialog', default_path=base, show=True)
        except Exception:
            dpg.configure_item('DeleteDialog', show=True)

    def on_delete_dialog(sender, app_data):
        path = app_data.get('file_path_name') if isinstance(app_data, dict) else None
        logger.info('Delete dialog path: %r', path)
        if not path:
            return
        pending_delete_path['value'] = path
        # Show confirm modal
        if not dpg.does_item_exist('ConfirmDelete'):
            with dpg.window(label='Confirm Delete', modal=True, show=True, tag='ConfirmDelete', autosize=True):
                dpg.add_text(f"Delete file?\n{path}", tag='ConfirmDeleteText')
                with dpg.group(horizontal=True):
                    dpg.add_button(label='Yes', width=80, callback=lambda: on_confirm_delete())
                    dpg.add_button(label='No', width=80, callback=lambda: dpg.configure_item('ConfirmDelete', show=False))
        else:
            dpg.set_value('ConfirmDeleteText', f"Delete file?\n{path}")
            dpg.configure_item('ConfirmDelete', show=True)

    def on_confirm_delete():
        path = pending_delete_path.get('value')
        logger.info('Confirm delete: %r', path)
        try:
            if path and os.path.exists(path):
                os.remove(path)
                set_status(f'Deleted file: {path}')
            else:
                show_message('Delete Error', 'File does not exist.')
        except Exception as e:
            logger.exception('Failed to delete file: %s', e)
            show_message('Delete Error', str(e))
        finally:
            if dpg.does_item_exist('ConfirmDelete'):
                dpg.configure_item('ConfirmDelete', show=False)

    try:
        dpg.create_context()
        with dpg.window(tag="Primary Window", label="Process Editor", width=1200, height=800):
            with dpg.menu_bar():
                with dpg.menu(label="File"):
                    dpg.add_menu_item(label="New Process", callback=lambda: on_new_process())
                    dpg.add_menu_item(label="Open...", callback=lambda: on_open_menu())
                    dpg.add_menu_item(label="Save", callback=lambda: on_save_menu())
                    dpg.add_menu_item(label="Save As...", callback=lambda: on_save_menu())
                    dpg.add_menu_item(label="Delete...", callback=lambda: on_delete_menu())
                with dpg.menu(label="Node", tag='NodeMenu'):
                    pass  # will be populated below
            # Node editor area
            dpg.add_node_editor(tag=node_editor_tag,
                                callback=on_link_created,
                                delink_callback=on_link_deleted,
                                minimap=True,
                                minimap_location=dpg.mvNodeMiniMap_Location_BottomRight)
            # Execute button at bottom
            dpg.add_spacer(height=8)
            dpg.add_button(label="Execute", callback=lambda: on_execute())
            # Status bar
            dpg.add_spacer(height=8)
            dpg.add_separator()
            dpg.add_text("Ready", tag='StatusText')

        # File dialogs (hidden) - add All Files first so it becomes default filter
        with dpg.file_dialog(directory_selector=False, show=False, callback=on_open_dialog, tag='OpenDialog', width=700 ,height=400, modal=True):
            dpg.add_file_extension(".*")
            dpg.add_file_extension(".process", color=(0, 255, 0, 255))
        with dpg.file_dialog(directory_selector=False, show=False, callback=on_save_dialog, tag='SaveDialog', width=700 ,height=400,  modal=True):
            dpg.add_file_extension(".*")
            dpg.add_file_extension(".process", color=(0, 255, 0, 255))
        with dpg.file_dialog(directory_selector=False, show=False, callback=on_delete_dialog, tag='DeleteDialog', width=700 ,height=400,  modal=True):
            dpg.add_file_extension(".*")
            dpg.add_file_extension(".process", color=(255, 0, 0, 255))

        # Build node menu items
        refresh_templates_menu()

        dpg.create_viewport(title='Process Editor', width=1300, height=900)
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_primary_window("Primary Window", True)
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


def main(argv=None):
    setup_logging()
    logger.info('Process Editor starting')
    import dearpygui.dearpygui as dpg  # ensure DPG dependency error is early
    parser = argparse.ArgumentParser(description='Process Editor')
    parser.add_argument('--nogui', action='store_true', help='Run in headless mode (no GUI)')
    parser.add_argument('--list-templates', action='store_true', help='List discovered node templates and exit')
    args = parser.parse_args(argv)

    # Load node templates and create empty model
    templates = load_node_templates('nodes')
    tmap = templates_by_type(templates)
    # validate templates once
    terrs = validate_templates(templates)
    if terrs:
        logger.error('Template validation errors: %s', terrs)
        print('Template validation errors:')
        for e in terrs:
            print('-', e)
    model = GraphModel()

    logger.info('Loaded %d templates', len(templates))
    print(f'Found {len(templates)} templates')
    if args.list_templates:
        for t in templates:
            ttype = getattr(t, 'type', None)
            title = getattr(t, 'title', None)
            print(f'- {ttype} ({title})')
        return 0

    if args.nogui:
        logger.info('Running in headless mode')
        result = run_plugin('app.plugins.sample.SampleExecutor', model.to_dict())
        logger.info('Plugin result: %s', result)
        print('Plugin result:', result)
        return 0

    start_gui(model, tmap)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        logger.exception('Fatal error in main')
        traceback.print_exc()
        sys.exit(1)

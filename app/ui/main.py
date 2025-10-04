# -*- coding: utf-8 -*-
"""
App entry for Process Editor.
Delegates GUI to ProcessEditor class (app.ui.process_editor).
"""
import sys
import os
import argparse
import traceback
import logging

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.data_model import (
    load_node_templates,
    GraphModel,
    templates_by_type,
    validate_templates,
)
from app.plugins.plugin_loader import run_plugin
from app.util.logging_config import setup_logging
from app.ui.process_editor import ProcessEditor

logger = logging.getLogger(__name__)


def main(argv=None):
    setup_logging()
    logger.info('Process Editor starting')
    try:
        import dearpygui.dearpygui as dpg  # pre-check DPG availability
    except Exception as e:
        logger.exception('DearPyGui import failed: %s', e)
        print('DearPyGui not available:', e, file=sys.stderr)
        return 1

    parser = argparse.ArgumentParser(description='Process Editor')
    parser.add_argument('--nogui', action='store_true', help='Run in headless mode (no GUI)')
    parser.add_argument('--list-templates', action='store_true', help='List discovered node templates and exit')
    args = parser.parse_args(argv)

    templates = load_node_templates('nodes')
    tmap = templates_by_type(templates)
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

    # GUI path: delegate to ProcessEditor
    editor = ProcessEditor(model, tmap)
    editor.run()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        logger.exception('Fatal error in main')
        traceback.print_exc()
        sys.exit(1)

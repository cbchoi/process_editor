"""
plugins/plugin_loader.py
Plugin dynamic loader and runner utilities.
"""
import importlib

def load_executor(plugin_path: str):
    # plugin_path: 'app.plugins.sample.SampleExecutor' or 'plugins.sample.SampleExecutor'
    mod_path, cls_name = plugin_path.rsplit('.', 1)
    mod = importlib.import_module(mod_path)
    executor_cls = getattr(mod, cls_name)
    return executor_cls()

def run_plugin(plugin_path: str, graph: dict):
    executor = load_executor(plugin_path)
    errors = executor.validate(graph)
    if errors:
        return {'status': 'error', 'errors': errors}
    try:
        result = executor.execute(graph)
        return result
    except Exception as e:
        return {'status': 'error', 'exception': str(e)}

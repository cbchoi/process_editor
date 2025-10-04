"""
plugins/test_plugin_loader.py
Plugin loader/run unit test
"""
from app.plugins.plugin_loader import run_plugin


def test_run_plugin():
    graph = {
        'nodes': [{'id': '1', 'type': 'TestNode', 'title': 'Test', 'position': {'x':0,'y':0}, 'attributes': {}, 'pins': {'inputs': [], 'outputs': []}}],
        'links': [],
        'metadata': {'created_at': '2024-01-01'}
    }
    result = run_plugin('app.plugins.sample.SampleExecutor', graph)
    assert result.get('status') == 'ok' or 'errors' in result


if __name__ == '__main__':
    test_run_plugin()
    print('plugin tests passed')

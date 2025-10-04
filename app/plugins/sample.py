"""
plugins/sample.py
Sample plugin implementing the Executor interface.
"""
class SampleExecutor:
    supports_cycles = False

    def validate(self, graph: dict) -> list:
        # Basic validation: ensure nodes and links exist
        errors = []
        if not graph.get('nodes'):
            errors.append('No nodes in graph')
        if not graph.get('links'):
            errors.append('No links in graph')
        return errors

    def execute(self, graph: dict) -> dict:
        # Return node ids as a simple example
        node_ids = [n['id'] for n in graph.get('nodes', [])]
        return {'status': 'ok', 'node_ids': node_ids}

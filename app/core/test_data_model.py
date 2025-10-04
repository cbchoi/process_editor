"""
core/test_data_model.py
Unit tests for core/data_model.py
"""
import os
from app.core.data_model import load_node_templates, validate_templates, GraphModel, save_process_file, load_process_file


def test_load_and_validate_templates():
    nodes_dir = 'nodes'  # test directory for sample yaml
    if not os.path.exists(nodes_dir):
        os.makedirs(nodes_dir)
        with open(os.path.join(nodes_dir, 'test.yaml'), 'w', encoding='utf-8') as f:
            f.write('type: TestNode\ntitle: Test\ninputs: []\noutputs: []\nattributes: []\nconstraints: {}\n')
    templates = load_node_templates(nodes_dir)
    errors = validate_templates(templates)
    assert not errors, f"Template validation errors: {errors}"


def test_graph_model_io():
    model = GraphModel()
    model.nodes = [{'id': '1', 'type': 'TestNode', 'title': 'Test', 'position': {'x':0,'y':0}, 'attributes': {}, 'pins': {'inputs': [], 'outputs': []}}]
    model.links = []
    model.metadata = {'created_at': '2024-01-01'}
    save_process_file('test.process', model)
    loaded = load_process_file('test.process')
    assert loaded.nodes == model.nodes
    assert loaded.metadata == model.metadata


if __name__ == '__main__':
    test_load_and_validate_templates()
    test_graph_model_io()
    print('core tests passed')

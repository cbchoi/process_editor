# process_editor

Lightweight visual process (node graph) editor using DearPyGui.

Features
- Node templates (YAML) with inputs/outputs/attributes and optional compute snippet
- Graph model with validation, links, and persistence to .process files (YAML)
- Generic template-driven executor (no type hardcoding)
- DearPyGui UI: node editor, link creation, context menus, file dialogs

Requirements
- Python 3.9+
- Packages: dearpygui, pyyaml

Install
- pip install -U dearpygui pyyaml

Run
- python app/ui/main.py

Usage
- File > New/Open/Save/Save As/Delete
- Node > Add <Type> to create nodes from templates
- Connect outputs to inputs by dragging between pins
- Run > Execute (F5) to execute the graph
- Right-click node to delete; Edit > Delete Selected or Delete key for multi-delete
- Output panel shows execution result JSON

Shortcuts
- F5: Execute
- Delete: Delete selected links/nodes

Node templates (YAML)
- Location: nodes/*.yaml
- Minimal schema:
  - type: unique node type id
  - title: display name
  - inputs/outputs: list of pins with name and optional dtype
  - attributes: list of {name, type[int|float|str|bool|enum], default}
  - constraints: optional limits (e.g., max_input_links)
  - compute: optional Python snippet executed with IN, ATTR, OUT dicts

Example (constant value and sum)
- Const template compute:
  OUT['Value'] = float(ATTR.get('value', 0.0))
- Sum template compute:
  a = float(IN.get('A', 0.0) or 0.0)
  b = float(IN.get('B', 0.0) or 0.0)
  s = a + b
  ATTR['result'] = s
  OUT['Out'] = s

Execution
- Starts from nodes with no inbound links (topological order)
- For each node: IN is built from upstream OUT, ATTR from node attributes
- Runs template compute, writes results back to node ATTR and downstream IN

Persistence
- Saves/loads .process files in YAML format (graph: {nodes, links, metadata})
- Node positions and widths are persisted

Fonts (optional)
- Set PROCESS_EDITOR_FONT_PATH to a TTF file to override default font

Development
- Templates are hot-refreshable via Templates > Refresh
- Generic executor: app/plugins/executor_generic.py
- UI entry: app/ui/main.py, ProcessEditor in app/ui/process_editor.py

# Project Specification (dearpygui-node-process)
> **All menu labels and UI texts are in English.**  
> **주석은 한글로 표기합니다.**

## 0. Scope and Progressive Structure
This specification is modular and **progressively extensible**. Component-specific specifications MUST be appended as separate files:
- `specification.node.md`: Node template format, validation rules, and editor behaviors.
- `specification.execution.md`: Execution plugin interface and traversal semantics.
- Additional files may follow the pattern `specification.<component>.md`.

> 주석: 세부 요소는 파일을 분리해 점진적으로 확장합니다.

## 1. Overview
The application provides a **process modeling GUI** built on **Dear PyGui**’s **Node Editor**. Users compose a process by placing nodes and links, then serialize/deserialize process graphs as `.process` files (YAML). An **Execution Plugin** traverses the graph and produces results per user-defined business logic.

## 2. Functional Requirements
### 2.1 GUI & Node Editor
- Provide a main window with a **menu bar** and a **node editor** viewport.
- Support **pan/zoom**, **node drag**, **link creation** (in/out slots), and **context menus**.

### 2.2 Nodes Directory & Templates
- Directory: `nodes/`.
- When YAML node templates exist in `nodes/`, the **Node** menu auto-populates with available node types.
- Adding a node inserts a GUI node with:
  - Named input/output links (pins).
  - Editable attributes (types and default values per template).
> 주석: 템플릿 파일 추가만으로 편집기에 노드 종류가 자동 등록되어야 합니다.

### 2.3 File Menu (Feature 1)
Menu: **File**
- **New Process**: Clear current editor to an empty graph (prompt for unsaved changes).
- **Save**: Save to the current `.process` path (YAML).
- **Save As…**: Save to another path via file dialog.
- **Open…**: Load a `.process` file via file dialog (YAML → graph).
Constraints:
- File extension: `.process` (internally YAML).  
- File dialogs are provided via Dear PyGui’s file dialog widgets or OS-native equivalents.
> 주석: 저장/불러오기는 별도의 파일 다이얼로그로 구성합니다.

### 2.4 Node Menu (Feature 2)
Menu: **Node**
- **Add <NodeType>** entries generated from templates in `nodes/`.
- **Delete Node** via right-click context on node.
- **Delete Link** via right-click context on link.
- **Multi-select** (drag rectangle) and **Delete Selection** to remove multiple nodes/links.
> 주석: 노드/링크 삭제는 우클릭 또는 다중 선택 후 일괄 삭제가 가능해야 합니다.

### 2.5 Execution (Feature 3)
- **Execute** button on toolbar.
- On click: Traverse the node graph and pass **collected nodes/links + attributes** to a **Python Execution Plugin**.
- Execution Plugin:
  - A user-implemented Python class (plugin) loaded dynamically.
  - Consumes the graph model (nodes, attributes, links) and returns a result object (dict/JSON/YAML).
> 주석: 플러그인은 비즈니스 로직을 외부화하여 사용자가 교체 가능하게 합니다.

## 3. Non-Functional Requirements
- **Portability**: Python 3.10+; Windows/Linux/macOS.
- **Dependencies**: dearpygui (latest stable), pyyaml.
- **Extensibility**: New node templates via `nodes/*.yaml`; new execution strategies via plugin classes.
- **Persistence**: `.process` as YAML (UTF-8).

## 4. Data Model
### 4.1 In-Memory Graph
```yaml
# 주석: 내부 그래프 모델(개념 스키마)
graph:
  nodes:
    - id: "<uuid>"
      type: "<NodeType>"
      title: "<display title>"
      position: { x: 0.0, y: 0.0 }
      attributes:
        <attr_name>: <value>   # 타입은 템플릿이 정의
      pins:
        inputs:  [ "<pin_name>", ... ]
        outputs: [ "<pin_name>", ... ]
  links:
    - id: "<uuid>"
      from: { node_id: "<uuid>", pin: "<output_pin_name>" }
      to:   { node_id: "<uuid>", pin: "<input_pin_name>" }
  metadata:
    created_at: "<iso8601>"
    updated_at: "<iso8601>"
```

### 4.2 .process File (YAML Serialization)
- File extension: `.process`
- Schema aligns with §4.1.
- Additional `plugin` field (optional) to suggest a default execution plugin:

```yaml
# 주석: 저장 포맷 예시(.process)
plugin: "plugins.sample.SampleExecutor"
graph:
  nodes: [ ... ]
  links: [ ... ]
  metadata: { ... }
```

## 5. Node Template (YAML)
- Location: `nodes/*.yaml`
- Each file defines a **Node Type**.

```yaml
# nodes/example.math.add.yaml
# 주석(한글): 기본 예제 - 두 숫자를 더하는 노드 템플릿
type: "MathAdd"                  # Node name shown in Node menu
title: "Add"                     # Display title
inputs:                          # Input pins (link targets)
  - name: "A"
  - name: "B"
outputs:                         # Output pins (link sources)
  - name: "Sum"
attributes:                      # Editable properties on the node
  - name: "precision"
    type: "int"
    default: 2
constraints:
  max_input_links: 2             # 총 입력 링크 수
  max_output_links: 1            # 총 출력 링크 수
```

> 상세 규칙은 `specification.node.md`에 기술.

## 6. Execution Plugin Interface (Concept)
Plugins must implement:
- A **class** with a known **entrypoint**: `execute(graph: dict) -> dict`
- Optional: `validate(graph: dict) -> list[str]` returning validation messages (empty if OK).
> 상세 인터페이스는 `specification.execution.md`에 기술.

## 7. Traversal Semantics (High-Level)
- Topological order by link direction (from outputs to inputs).
- On cycles: either reject or support iterative/feedback semantics (configurable).
- Node evaluation uses attributes + resolved inputs to compute outputs.
> 주석: 순환 검출 필요. 초기 버전에서는 사이클 금지 권장.

## 8. UI/UX Details
- **Context Menus**: Right-click on nodes/links to show **Delete**.
- **Multi-Select**: Drag marquee to select; **Delete** key removes selection.
- **Status Bar**: Show current file path, unsaved indicator, and execution result summary.
- **Error Toasts**: Validation or execution errors appear as non-blocking toasts.

## 9. Validation
- On **Save**: Validate graph against node templates (pin names, link counts, attribute types).
- On **Execute**: Re-validate + plugin-specific checks.

## 10. Directory Structure (Suggested)
```
project-root/
  app/
    main.py
    ui/
    core/
    plugins/
  nodes/                 # node templates (.yaml)
  processes/             # sample .process files
  tests/
  specification.md
  specification.node.md
  specification.execution.md
  instruction.md
  acceptance_test.md
  requirements.txt
  README.md
```

## 11. Risks & Mitigations
- **Template drift**: Add JSON Schema/YAML schema validation step.
- **Cyclic graphs**: Provide cycle detection; fail fast with diagnostics.
- **Plugin errors**: Sandbox plugin exceptions; display user-friendly messages.

## 12. Roadmap (Incremental)
1) Core UI + File I/O → 2) Node templates loader & palette → 3) Validation → 4) Execution plugin API → 5) Advanced traversal (cycles/async) → 6) Packaging.

---
*End of specification.md*

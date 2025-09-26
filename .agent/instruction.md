# Instruction (Build & Run Guide)
> **Menus in English, comments in Korean**  
> 주석: 개발/실행/구조/포맷 안내서입니다.

## 1. Prerequisites
- Python 3.10+
- pip, virtualenv (optional)

## 2. Setup
```bash
# Create and activate venv (optional)
python -m venv .venv
# Windows
.venv\\Scripts\\activate
# Linux/macOS
source .venv/bin/activate

pip install -U dearpygui pyyaml
```

## 3. Project Layout (Suggested)
```
project-root/
  app/
    main.py                 # Entry point
    ui/                     # DPG windows, dialogs, node editor controls
    core/                   # model, io (yaml), validation
    plugins/                # execution plugins
  nodes/                    # YAML node templates
  processes/                # sample .process files
  specification.md
  specification.node.md
  specification.execution.md
  instruction.md
  acceptance_test.md
  requirements.txt
  README.md
```

## 4. Running
```bash
python app/main.py
```

## 5. File Formats
### 5.1 Node Template (`nodes/*.yaml`)
See `specification.node.md` (§1–§6).

### 5.2 Process File (`*.process` YAML)
- Extension: `.process`
- Keys: `plugin` (optional), `graph` (nodes, links, metadata).

## 6. UI Behavior Summary
- **File** menu: `New Process`, `Save`, `Save As…`, `Open…`  
  - Uses file dialogs for open/save-as.  
  - Prompts on unsaved state.
- **Node** menu: Items generated from templates → `Add <NodeType>`.
- **Execution**: Toolbar button `Execute` → validates → loads plugin → runs.

## 7. Plugin Development
- Create `plugins/<name>.py` with class `Executor` (or named accordingly) implementing:
  - `validate(graph) -> list[str]`
  - `execute(graph) -> dict`
- Reference plugin path in `.process` or select via UI.
> 주석: 플러그인 클래스명과 import 경로를 일치시켜야 합니다.

## 8. Validation Pipeline
1. Load templates → template validation.
2. Graph edits → live checks (pin/link constraints).
3. On Save/Open/Execute → full validation.

## 9. Example: Minimal `main.py` Skeleton
```python
# 주석: 개념적 골격 (실행 코드 아님)
def main():
    # init DPG, build menus, node editor
    # load nodes/*.yaml into registry
    # wire File menu actions (new/save/save-as/open)
    # wire Node menu (dynamic add)
    # wire Execute (collect graph -> plugin.execute)
    pass
```

---
*End of instruction.md*

# Execution Specification (specification.execution.md)
> **Menus in English, comments in Korean**  
> 주석: 실행 로직은 플러그인으로 분리합니다.

## 1. Plugin Interface
A plugin is a Python class discoverable by an import path, e.g., `plugins.sample.SampleExecutor`.

```python
# 주석: 최소 인터페이스
class Executor:
    def validate(self, graph: dict) -> list[str]:
        """Return a list of validation error messages; empty if valid."""

    def execute(self, graph: dict) -> dict:
        """Run traversal + business logic; return result as dict."""
```

- `graph` follows the schema in `specification.md` §4.1.
- Return value can be shown in UI and/or saved as YAML/JSON.

## 2. Traversal Semantics
- **Default**: Topological order; edges follow `links.from -> links.to`.
- **Cycle Policy**:
  - Default: disallow cycles (fail validation).
  - Optional: if a plugin advertises `supports_cycles=True`, the app may permit iterative execution:
    - Fixed-point iteration with max-iterations and tolerance.
    - Or time-stepped propagation.

## 3. Data Exchange
- Inputs to `execute`:
  - `graph`: normalized, validated.
  - Optional `context`: execution parameters (seed, limits).
- Outputs:
  - `result`: arbitrary dict; include `logs`, `metrics`, `artifacts` as needed.

## 4. Errors & Reporting
- Exceptions are caught and displayed as an error toast with stack summary.
- Validation errors block execution and are listed in a panel.

## 5. Example Plugin Skeleton
```python
# plugins/sample.py
# 주석: 예제 실행기
from collections import deque

class SampleExecutor:
    supports_cycles = False

    def validate(self, graph: dict) -> list[str]:
        return []

    def execute(self, graph: dict) -> dict:
        order = self._topo_order(graph)
        values = {}
        for node_id in order:
            node = self._get_node(graph, node_id)
            values[node_id] = self._eval_node(node, values, graph)
        return {"status": "ok", "values": values}

    # ... helpers (topo sort, eval per type, etc.)
```

## 6. Security Considerations
- Plugins run in-process; treat as trusted code.
- Optionally restrict to a signed set or sandbox via subprocess.

---
*End of specification.execution.md*

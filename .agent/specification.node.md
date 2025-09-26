# Node Specification (specification.node.md)
> **Menus in English, comments in Korean**  
> 주석: 노드 템플릿은 YAML로 정의하며, 자동 로딩/검증됩니다.

## 1. Template File
- Location: `nodes/*.yaml`
- One file = One Node Type.

### 1.1 Required Keys
- `type` *(str)*: Unique node type identifier (menu label source).
- `title` *(str)*: Display title.
- `inputs` *(list of pin objects)*: Input pins (names).
- `outputs` *(list of pin objects)*: Output pins (names).
- `attributes` *(list of attribute objects)*: Editable attributes.
- `constraints` *(object)*: Link count limits, etc.

### 1.2 Pin Object
```yaml
# 주석: 입력/출력 핀 정의
- name: "<pin_name>"
  dtype: "<optional: int|float|str|bool|any>"   # default: any
```

### 1.3 Attribute Object
```yaml
# 주석: 노드 속성 정의
- name: "<attr_name>"
  type: "int|float|str|bool|enum"
  default: <value>
  enum: ["opt1","opt2"]           # type=enum일 때 필수
  min: <number>                   # type=int/float일 때 선택
  max: <number>                   # type=int/float일 때 선택
  required: true|false            # default: false
```

### 1.4 Constraints
```yaml
constraints:
  max_input_links: <int>          # 총 입력 링크 수 제한
  max_output_links: <int>         # 총 출력 링크 수 제한
  allow_self_loop: false          # 자기 루프 허용 여부
  allow_cycles: false             # 사이클 허용 여부
```

## 2. Validation Rules
1. `type` is unique across all templates.
2. Pin names are unique within inputs/outputs.
3. Attributes:
   - Names unique per node type.
   - `enum` provided iff `type=enum`.
   - Values must satisfy type and (min,max).
4. Links:
   - Source pin must exist in `outputs` of source node type.
   - Target pin must exist in `inputs` of target node type.
   - Respect `{max_input_links, max_output_links}`.
5. Graph:
   - No cycles if `allow_cycles=false` on any participating node.
   - All `required` attributes present.

## 3. Example Templates
### 3.1 Source Node
```yaml
# nodes/example.source.yaml
# 주석: 외부 데이터를 그래프로 주입하는 소스 노드
type: "DataSource"
title: "Source"
inputs: []
outputs:
  - name: "Out"
    dtype: "any"
attributes:
  - name: "path"
    type: "str"
    required: true
constraints:
  max_input_links: 0
  max_output_links: 4
```

### 3.2 Transform Node
```yaml
# nodes/example.transform.filter.yaml
# 주석: 조건에 따라 데이터를 필터링
type: "Filter"
title: "Filter"
inputs:
  - name: "In"
    dtype: "any"
outputs:
  - name: "Out"
    dtype: "any"
attributes:
  - name: "predicate"
    type: "str"
    required: true
constraints:
  max_input_links: 1
  max_output_links: 2
```

### 3.3 Sink Node
```yaml
# nodes/example.sink.yaml
# 주석: 결과를 파일로 저장
type: "DataSink"
title: "Sink"
inputs:
  - name: "In"
    dtype: "any"
outputs: []
attributes:
  - name: "format"
    type: "enum"
    default: "csv"
    enum: ["csv","json","yaml"]
  - name: "path"
    type: "str"
    required: true
constraints:
  max_input_links: 2
  max_output_links: 0
```

## 4. Loading Behavior
- On startup or on **Refresh Templates** (optional menu), read all `nodes/*.yaml`.
- Validate and cache templates.
- Populate **Node** menu with `Add <type>` entries, ordered by filename or `title`.

## 5. Editor Behavior
- When adding a node:
  - Instantiate GUI node with pins & attribute editors.
  - Initialize attributes with defaults.
- On attribute edit:
  - Validate type/range; mark invalid fields.
- On link creation:
  - Validate pin existence and constraints before commit; otherwise reject with toast.

## 6. Serialization Mapping
- Node instance YAML keys:
  - `id`, `type`, `title`, `position`, `attributes`, `pins` (explicit pin names for forward-compat).

---
*End of specification.node.md*

# Acceptance Test (dearpygui-node-process)
> **All UI labels in English; comments in Korean.**  
> 주석: 테스트는 수동/반자동으로 수행 가능하며, 명확한 합격 기준을 둡니다.

## 0. Test Environment
- OS: Windows 10/11, Ubuntu 22.04, macOS 13+ (choose at least one)
- Python 3.10+; dearpygui (latest), pyyaml
- Clean repo clone; empty `nodes/` except templates under test

## 1. Node Template Loading
**Given** a valid YAML template `nodes/example.math.add.yaml`  
**When** the app starts  
**Then** the **Node** menu contains `Add MathAdd`
- **Pass if** the menu item appears and adding it places a node with pins `A`, `B`, output `Sum`, attribute `precision=2`.

## 2. File Menu – New/Save/Save As/Open
### 2.1 New Process
- **Action**: File → New Process
- **Expect**: Editor cleared; unsaved indicator shown.
- **Pass if** no nodes/links remain.

### 2.2 Save As
- **Action**: File → Save As… → choose `processes/test.process`
- **Expect**: File created with YAML content per schema.
- **Pass if** file exists; top-level contains `graph` and optional `plugin`.

### 2.3 Save
- **Action**: Modify graph; File → Save
- **Expect**: `updated_at` changes.
- **Pass if** serialization reflects current nodes/links/attributes.

### 2.4 Open
- **Action**: File → Open… → select `processes/test.process`
- **Expect**: Graph loads identically.
- **Pass if** node positions, pins, and links match pre-save state.

## 3. Node Operations
### 3.1 Add from Template
- **Action**: Node → Add MathAdd
- **Pass if** GUI node is created with correct pins and attributes.

### 3.2 Delete Node (Context)
- **Action**: Right-click node → Delete
- **Pass if** node disappears and incident links are removed.

### 3.3 Delete Link (Context)
- **Action**: Right-click link → Delete
- **Pass if** link disappears without affecting node attributes.

### 3.4 Multi-Select & Delete
- **Action**: Drag-select multiple nodes/links → press Delete
- **Pass if** all selected objects are removed.

## 4. Validation
### 4.1 Pin/Link Constraints
- **Setup**: Template with `max_input_links: 1`
- **Action**: Attempt to connect 2 inputs to the same pin.
- **Pass if** second link is rejected with an error toast.

### 4.2 Attribute Types
- **Setup**: Attribute `precision: int`
- **Action**: Enter non-integer value.
- **Pass if** field is marked invalid and Save/Execute blocked until corrected.

## 5. Execution
### 5.1 Plugin Invocation
- **Setup**: `.process` specifies `plugins.sample.SampleExecutor`
- **Action**: Click **Execute**
- **Pass if** plugin is imported; `validate` called (no errors); `execute` returns dict; summary shown in status bar.

### 5.2 Traversal
- **Setup**: Source → Filter → Sink
- **Action**: Execute
- **Pass if** evaluation order respects edges (Source first, Sink last).

### 5.3 Cycle Handling
- **Setup**: Create cyclic links
- **Action**: Execute
- **Pass if** validation blocks execution with explicit cycle error.

## 6. Persistence Fidelity
- **Action**: Save → Close App → Reopen → Open same file
- **Pass if** visual layout (positions) and data (attributes) match byte-for-byte aside from timestamps.

## 7. Negative Tests
- **Malformed Template**
  - **Action**: Place YAML with missing `type`
  - **Pass if** app reports validation error and ignores the template.
- **Unknown Plugin**
  - **Action**: Set `plugin: "nonexistent.Executor"`
  - **Pass if** Execute shows import error without crashing.

## 8. Exit Criteria
- All tests in §1–§7 **pass on at least one target OS**.
- Critical defects: none open; major defects have workarounds documented.

---
*End of acceptance_test.md*

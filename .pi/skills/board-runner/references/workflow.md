# Board Runner Workflow Reference

## Source of truth
- `board.md` = overview / current status by lane
- `tasks/todos.md` = detailed scope, dependencies, done criteria

If they disagree, fix them.

---

## Simple operating loop

1. Read `board.md`
2. Read `tasks/todos.md`
3. Pick:
   - `In Progress` first
   - else first valid `Ready`
4. Restate task simply
5. Execute only that scope
6. Update statuses when state changes
7. Mark done only when done criteria are met

---

## Pull order

### 1. In Progress
If a task is already active, continue it first.

### 2. Ready
If nothing is active, pull from `Ready`.

### 3. Backlog
Only move work from `Backlog` to `Ready` if dependencies are satisfied and the task is well-bounded.

---

## Dependency rule

Do not pull a task if its dependencies are not done.

Example:
- If `VIL-002` depends on `VIL-001`, then `VIL-001` must be done first.

---

## Suggested task response format

```text
Task: VIL-000 — Create project scaffold
Why: We need a real codebase before any module work can happen.
Scope: Create the Python project structure, pyproject, app/, tests/, profiles/, runs/.
Done when: The folders and starter files exist and the project shape is clear.
Next concrete action: scaffold the project structure.
```

---

## When to mark blocked

Mark `Blocked` if:
- missing dependency
- task needs a product/architecture decision
- external credentials or system access missing
- task scope became unclear

Always write the blocker explicitly.

---

## When to create a new task

Create a new task instead of expanding an existing one when:
- new work was discovered outside the original scope
- cleanup/refactor is useful but not required
- integration follow-up appears after finishing the main task

Keep tasks small.

---

## First tasks in recommended order

1. `VIL-000` — Create project scaffold
2. `VIL-001` — Define core schemas in code
3. `VIL-002` — Add repo profile loader
4. `VIL-003` — Add CLI shell for `villager run`
5. `VIL-004` — Define and implement sandbox happy path
6. `VIL-005` — Add stub orchestrator end-to-end flow

---

## Best first move right now

Pull:
- `VIL-000 — Create project scaffold`

Because it unlocks everything after it.

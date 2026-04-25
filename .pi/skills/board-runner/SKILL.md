---
name: board-runner
description: Use for working from Villager's local board and task files. Reads board.md and tasks/todos.md, picks ready tasks, explains task status, updates progress, and helps execute one task at a time.
---

# Board Runner

Use this skill when the user wants to:
- understand how to use the local board
- pick the next task
- run a task from the board
- update task status
- move work between Backlog / Ready / In Progress / Blocked / Done
- keep execution aligned with `board.md` and `tasks/todos.md`

This skill is for the Villager project local workflow.

## Files to use

Always read these first:
- `./board.md`
- `./tasks/todos.md`

If needed, also read:
- `./mvp-build-plan.md`
- `./product-scope.md`
- `./tech-stack.md`

## Core rules

1. **Pull from Ready first**
   Do not invent new work if a good Ready task already exists.

2. **One active task at a time**
   Prefer one `In Progress` item only.

3. **Use task ids everywhere**
   Refer to work as `VIL-000`, `VIL-001`, etc.

4. **Read the detailed task before acting**
   `board.md` is the overview.
   `tasks/todos.md` is the source of truth for scope, done criteria, and dependencies.

5. **Keep board and task detail in sync**
   If status changes in one place, update the other.

6. **Finish small before pulling more**
   Small finished work beats many half-started tasks.

## Default workflow

When asked to work from the board:

### Step 1 — Read status
Read `board.md` and `tasks/todos.md`.

### Step 2 — Choose next task
Use this priority order:
1. existing `In Progress`
2. top `Ready` task with satisfied dependencies
3. otherwise explain what is blocked

### Step 3 — Restate the task simply
Answer in this format:
- **Task**
- **Why**
- **Scope**
- **Done when**
- **Next concrete action**

### Step 4 — If execution starts
Move the task to `In Progress` in `board.md` and update the task status in `tasks/todos.md`.

### Step 5 — During execution
Keep changes scoped to the task.
Do not silently expand scope.

### Step 6 — On completion
Move the task to `Done` in `board.md` and update the detailed task status.
If follow-up work appears, add a new task instead of bloating the finished one.

## Status transition rules

### Backlog -> Ready
Move only if:
- scope is clear
- dependencies are met
- deliverable is visible

### Ready -> In Progress
Move only when work actually starts.

### In Progress -> Blocked
Move if waiting on:
- decision
- dependency
- missing input
- external system

### In Progress -> Done
Move only when the task's `Done when` criteria are satisfied.

## Response patterns

### If user asks "what should I do next?"
- read board and tasks
- recommend one task only
- justify in 2-3 lines max

### If user asks "start task X"
- read that task details
- summarize goal and done criteria
- update board/task status to `In Progress`
- then proceed

### If user asks "what is blocked?"
- read board and tasks
- list blocked tasks and exact blocker

### If user asks "close this task"
- verify done criteria from `tasks/todos.md`
- if satisfied, move to `Done`
- if not, say exactly what remains

## Grug mode

Keep workflow simple:
- one task at a time
- one recommendation at a time
- no extra process theater
- do the smallest real thing next

## Recommended command style

Useful prompts with this skill:
- `/skill:board-runner what should I pull next?`
- `/skill:board-runner start VIL-000`
- `/skill:board-runner what is blocked?`
- `/skill:board-runner close VIL-000 if done`

## Reference

For the workflow cheat sheet, see:
- [references/workflow.md](references/workflow.md)

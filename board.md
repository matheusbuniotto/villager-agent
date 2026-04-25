# Villager Board

Local board for planning and pulling work, like a lightweight Linear/Jira.

## How to use
- `Backlog`: not started yet
- `Ready`: well-defined and can be pulled
- `In Progress`: active work
- `Blocked`: waiting on decision or dependency
- `Done`: finished

## Pull rule
Always pull from **Ready**.
A task should move to `Ready` only if:
- scope is clear
- output is visible
- dependencies are known
- it fits the current MVP phase

## Task detail source
Detailed task breakdown lives in:
- [`tasks/todos.md`](./tasks/todos.md)

---

## Backlog
- VIL-016 — Research agent framework: PydanticAI vs deepagents
- VIL-011 — Replace stub executor with real agent executor
- VIL-012 — Add retry loop
- VIL-013 — Add Postgres state store
- VIL-014 — Add real Git provider integration

## Ready
_empty_

## In Progress
_empty_

## Blocked
_empty_

## Done
- VIL-000 — Create project scaffold
- VIL-001 — Define core schemas in code
- VIL-002 — Add repo profile loader
- VIL-003 — Add CLI shell for `villager run`
- VIL-004 — Define and implement sandbox happy path
- VIL-005 — Add stub orchestrator end-to-end flow
- VIL-006 — Implement JIRA intake adapter
- VIL-007 — Implement spec builder happy path
- VIL-008 — Implement validator skeleton
- VIL-009 — Implement artifact writer and run folder export
- VIL-015 — Add execution progress feedback to CLI
- VIL-010 — Implement draft PR composer

---

## MVP milestone map

### Milestone 1 — App skeleton
- VIL-000
- VIL-001
- VIL-002
- VIL-003

### Milestone 2 — Sandbox happy path
- VIL-004
- VIL-005

### Milestone 3 — Core execution flow
- VIL-006
- VIL-007
- VIL-008
- VIL-009
- VIL-010

### Milestone 4 — Real agent loop
- VIL-011
- VIL-012

### Milestone 5 — Persistence and external integration
- VIL-013
- VIL-014

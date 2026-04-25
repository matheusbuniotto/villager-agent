# Villager Tasks

Detailed local task list linked from [`../board.md`](../board.md).

---

## VIL-000 — Create project scaffold
**Status:** Done  
**Priority:** P0  
**Milestone:** Milestone 1 — App skeleton

### Why
Create the minimum runnable structure so Villager stops being only docs and becomes a real codebase.

### Scope
- create Python project structure
- add `pyproject.toml`
- create `app/` modules
- create `tests/`
- create `profiles/`
- create `runs/`
- add starter README or package entrypoint if needed

### Deliverable
A bootable project skeleton with folders and starter files committed locally.

### Done when
- project folders exist
- `pyproject.toml` exists
- app package exists
- basic entrypoint exists
- repo can be opened and understood without guessing structure

### Dependencies
- none

### Notes
This is the first task to pull.

---

## VIL-001 — Define core schemas in code
**Status:** In Progress  
**Priority:** P0  
**Milestone:** Milestone 1 — App skeleton

### Why
The schemas are the backbone of the harness. Without them, modules will drift into ad hoc payloads.

### Scope
Implement first typed models for:
- `TaskPacket`
- `RepoProfile`
- `ExecutionSpec`
- `ValidationReport`
- `ReviewDecision`
- `ArtifactBundle`
- `RunRecord`

### Deliverable
Python schema module with validating models and a couple of tests.

### Done when
- models load correctly
- example objects can be instantiated
- schema tests pass

### Dependencies
- VIL-000

---

## VIL-002 — Add repo profile loader
**Status:** Ready  
**Priority:** P0  
**Milestone:** Milestone 1 — App skeleton

### Why
Repo personalization needs one real loading path early.

### Scope
- load YAML repo profiles
- validate against `RepoProfile`
- expose helper to fetch profile by repo name

### Deliverable
Working loader for `profiles/*.yaml`.

### Done when
- sample profile can be loaded
- invalid profile raises clear error

### Dependencies
- VIL-000
- VIL-001

---

## VIL-003 — Add CLI shell for `villager run`
**Status:** Ready  
**Priority:** P0  
**Milestone:** Milestone 1 — App skeleton

### Why
The CLI is the simplest control surface for MVP execution.

### Scope
- add Typer CLI
- add `villager run --jira <KEY>` command
- create stub run flow that prints or logs a run id

### Deliverable
Runnable CLI entrypoint.

### Done when
- command executes locally
- accepts issue key input
- creates a stub run record or output

### Dependencies
- VIL-000

---

## VIL-004 — Define and implement sandbox happy path
**Status:** Backlog  
**Priority:** P1  
**Milestone:** Milestone 2 — Sandbox happy path

### Scope
- choose base image
- create container
- clone repo
- checkout branch
- export one test artifact
- destroy container

### Dependencies
- VIL-000
- VIL-003

---

## VIL-005 — Add stub orchestrator end-to-end flow
**Status:** Backlog  
**Priority:** P1  
**Milestone:** Milestone 2 — Sandbox happy path

### Scope
- call intake stub
- call spec builder stub
- call sandbox stub/happy path
- write run artifacts

### Dependencies
- VIL-001
- VIL-002
- VIL-003
- VIL-004

---

## VIL-006 — Implement JIRA intake adapter
**Status:** Backlog  
**Priority:** P1  
**Milestone:** Milestone 3 — Core execution flow

### Scope
- fetch issue via API
- normalize issue to `TaskPacket`
- handle missing fields clearly

### Dependencies
- VIL-001
- VIL-003

---

## VIL-007 — Implement spec builder happy path
**Status:** Backlog  
**Priority:** P1  
**Milestone:** Milestone 3 — Core execution flow

### Scope
- classify task type
- assess basic ambiguity
- create `ExecutionSpec`
- fail closed on unsupported scope

### Dependencies
- VIL-001
- VIL-002
- VIL-006

---

## VIL-008 — Implement validator skeleton
**Status:** Backlog  
**Priority:** P1  
**Milestone:** Milestone 3 — Core execution flow

### Scope
- path policy check
- lint/test command execution shape
- basic `ValidationReport`

### Dependencies
- VIL-001
- VIL-002
- VIL-004

---

## VIL-009 — Implement artifact writer and run folder export
**Status:** Backlog  
**Priority:** P1  
**Milestone:** Milestone 3 — Core execution flow

### Scope
- create `runs/<run_id>/`
- write JSON/MD/TXT artifacts
- persist validation and summary outputs

### Dependencies
- VIL-001
- VIL-005
- VIL-008

---

## VIL-010 — Implement draft PR composer
**Status:** Backlog  
**Priority:** P1  
**Milestone:** Milestone 3 — Core execution flow

### Scope
- generate PR title/body
- include validation summary
- include acceptance criteria mapping

### Dependencies
- VIL-001
- VIL-007
- VIL-008
- VIL-009

---

## VIL-011 — Replace stub executor with real agent executor
**Status:** Backlog  
**Priority:** P2  
**Milestone:** Milestone 4 — Real agent loop

### Scope
- add PydanticAI executor
- inject task/spec/profile context
- produce real file changes in sandbox

### Dependencies
- VIL-004
- VIL-005
- VIL-007
- VIL-008

---

## VIL-012 — Add retry loop
**Status:** Backlog  
**Priority:** P2  
**Milestone:** Milestone 4 — Real agent loop

### Scope
- track retry count
- build retry instruction
- rerun executor on retryable failures
- stop at max retries

### Dependencies
- VIL-008
- VIL-011

---

## VIL-013 — Add Postgres state store
**Status:** Backlog  
**Priority:** P2  
**Milestone:** Milestone 5 — Persistence and external integration

### Scope
- persist run records
- persist state transitions
- persist validation refs and artifact refs

### Dependencies
- VIL-001
- VIL-005

---

## VIL-014 — Add real Git provider integration
**Status:** Backlog  
**Priority:** P2  
**Milestone:** Milestone 5 — Persistence and external integration

### Scope
- create draft PR through API
- attach title/body/branch metadata

### Dependencies
- VIL-010
- VIL-013

---

## Pull recommendation
Pull in this order:
1. VIL-000
2. VIL-001
3. VIL-002
4. VIL-003
5. VIL-004
6. VIL-005

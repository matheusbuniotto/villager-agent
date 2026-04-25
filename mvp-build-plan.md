# Villager — MVP Build Plan

## One-sentence goal

Build the smallest end-to-end version of Villager that can take one small JIRA ticket, generate a bounded spec, run inside Docker, validate the result, and output a draft PR package.

---

# 1. Grug rule

Do not build the platform.
Build the first ugly working path.

That means:
- one repo first
- one ticket type family first
- one trigger first
- one agent first
- one sandbox path first
- one validation path first

Anything else is backlog.

---

# 2. Definition of MVP

Villager MVP exists when this flow works:

1. you run a CLI command with a JIRA issue key
2. Villager fetches the issue
3. Villager loads one repo profile
4. Villager creates a valid `ExecutionSpec`
5. Villager starts a Docker sandbox
6. Villager clones the repo and creates a branch
7. Villager runs one executor pass
8. Villager runs validators
9. Villager writes artifacts to a run folder
10. Villager generates a draft PR markdown file

That is enough.

No web UI.
No queue system.
No multi-repo orchestration.
No merge automation.

---

# 3. Build strategy

Use 4 phases.

## Phase 1
Contracts and skeleton

## Phase 2
Happy path without real coding intelligence

## Phase 3
Real executor + validation loop

## Phase 4
JIRA and PR integration polish

This is the right order because:
- first make the shapes real
- then make the pipeline run
- then make the agent useful
- then make the integrations nicer

---

# 4. Phase 1 — Contracts and skeleton

## Goal
Create the basic project shape and typed contracts.

## Build
- project scaffold
- `uv` project setup
- base module layout
- Pydantic schemas:
  - `TaskPacket`
  - `RepoProfile`
  - `ExecutionSpec`
  - `ValidationReport`
  - `ReviewDecision`
  - `ArtifactBundle`
  - `RunRecord`
- YAML loader for repo profiles
- Typer CLI shell
- simple state persistence model

## Done when
You can:
- load a repo profile from YAML
- build and validate schema objects locally
- run a CLI command that creates a stub run record

## Artifact
A CLI command like:

```bash
villager run --jira BILL-142
```

that does not complete the full flow yet, but proves the app boots and objects are wired.

---

# 5. Phase 2 — Happy path without real coding intelligence

## Goal
Prove the pipeline works end to end, even with a fake or stub executor.

## Build
- intake module that can fetch or mock JIRA issue data
- spec builder that creates an `ExecutionSpec`
- sandbox manager that:
  - starts Docker
  - clones repo
  - creates branch
  - writes context files
- stub executor that makes a known trivial change
  - example: edit a test file or markdown file in a demo repo
- validator that runs at least:
  - path policy check
  - lint/test command
- artifact export to `runs/<run_id>/`
- PR composer that writes `pr-body.md`

## Why stub first
Because you want to prove the harness and sandbox before blaming the model.

## Done when
One CLI command can produce:
- run folder
- changed files
- validation report
- PR markdown

Even if the code change is fake/simple.

---

# 6. Phase 3 — Real executor + retry loop

## Goal
Replace the stub executor with the real coding agent.

## Build
- PydanticAI executor wrapper
- prompt/context assembly from:
  - `TaskPacket`
  - `ExecutionSpec`
  - `RepoProfile`
- sandbox command runner for executor actions
- validator result routing
- retry instruction builder
- retry count tracking in orchestrator

## Keep small
Use only:
- one model
- one executor agent
- one retry loop
- max 3 retries

## Done when
The system can:
- attempt a small real code change
- fail validation once
- retry with focused feedback
- either pass or escalate

---

# 7. Phase 4 — Real integrations and polish

## Goal
Connect the system cleanly to external systems.

## Build
- real JIRA fetch via `httpx`
- real Git provider PR draft creation via `httpx`
- Postgres-backed run/state persistence
- better error handling/logging
- support for 2nd repo profile

## Done when
You can run on a real issue and get:
- DB-tracked run
- sandbox execution
- local artifacts
- draft PR content ready for posting

---

# 8. Recommended implementation order inside the codebase

Keep the order boring.

## First
- schemas
- config/profile loading
- CLI entrypoint

## Second
- orchestrator skeleton
- state store skeleton

## Third
- sandbox manager
- validator skeleton

## Fourth
- spec builder

## Fifth
- stub executor

## Sixth
- PR composer

## Seventh
- replace stub executor with real agent

## Eighth
- real external integrations

This order reduces confusion.

---

# 9. What to stub first

You should stub aggressively at the start.

## Stub these first
- JIRA fetch
- PR creation API
- executor coding behavior
- some validator outputs if needed

## Do NOT stub these for too long
- schema validation
- sandbox lifecycle
- file artifact writing
- branch handling

Why:
These are core system behaviors.
You want them real early.

---

# 10. First demo artifact

The first believable demo should be:

## Demo
Run:

```bash
villager run --jira DEMO-1
```

And get:
- a run id
- a created sandbox
- a repo cloned
- a tiny file change
- a validation report
- a draft PR markdown file in `runs/<run_id>/`

If that works, Villager exists.

---

# 11. First target repo recommendation

Do not start with a complicated real production repo.

## Start with
- one small internal test repo
- predictable commands
- low-risk task examples
- easy lint/test setup

## Why
You want signal, not pain.

After that, move to one real repo.

---

# 12. First supported task examples

Use tasks like:
- add missing validation to one endpoint
- fix wrong status code
- add regression test for a known bug
- simplify one helper function with no behavior change

Do not start with:
- auth logic
- migrations
- infra
- async distributed workflows

---

# 13. First repo profile recommendation

Your first real profile should be as small as possible.

## Needed
- commands.install
- commands.lint
- commands.test
- paths.owned
- paths.sensitive
- paths.forbidden
- rules
- pr settings

No inheritance.
No examples retrieval.
No org-wide profile system yet.

---

# 14. Milestone table

## Milestone 1 — App skeleton
Done when:
- CLI works
- schemas validate
- profile loads

## Milestone 2 — Sandbox happy path
Done when:
- Docker run works
- repo clone works
- branch creation works
- artifacts export works

## Milestone 3 — Stub end-to-end
Done when:
- fake executor can produce draft PR package

## Milestone 4 — Real executor
Done when:
- agent performs one small real task

## Milestone 5 — Retry loop
Done when:
- validation failure can trigger one focused retry

## Milestone 6 — Real integration path
Done when:
- real JIRA issue can produce a real draft PR package

---

# 15. Frozen backlog

Explicitly not building yet:
- web UI
- queue fleet
- multi-agent system
- multiple providers
- profile inheritance engine
- cloud object storage
- auto merge
- deploy hooks
- org-wide approval system

This backlog freeze is important.

---

# 16. Suggested developer workflow

Use a tight loop:

1. implement one module slice
2. test locally
3. run one demo task
4. inspect `runs/<run_id>/`
5. fix the obvious thing
6. repeat

## Rule
Do not build 5 modules before running one ugly flow.

---

# 17. Recommended directory target for early code

Something like:

```text
villager/
  app/
    main.py
    schemas/
    intake/
    spec_builder/
    orchestrator/
    sandbox/
    validator/
    pr_composer/
    state_store/
  profiles/
  runs/
  tests/
```

This is enough.

---

# 18. First three engineering tasks I would do

## Task 1
Create schemas + profile loader + CLI command shell.

## Task 2
Create sandbox manager that can:
- start container
- clone repo
- create branch
- export one file
- tear down

## Task 3
Create stub end-to-end orchestrator flow that writes:
- validation-report.json
- pr-body.md
- run-summary.json

If these 3 tasks are done, you have real momentum.

---

# 19. Grug conclusion

Do not try to build Villager all at once.

Build this first:

**CLI in -> repo in Docker -> tiny change -> validation -> PR file out**

That is the whole MVP.

Everything else is later.

---

# 20. Next practical step

Best next move after this doc:

Create either:
1. `decision-log.md`
2. `todo.md`
3. actual project scaffold files

## My recommendation
Stop writing planning docs and start scaffolding the project.

If you want, next I can create:
- `todo.md`
- the initial folder structure
- a starter `pyproject.toml`
- the first app skeleton

That would be the right move now.
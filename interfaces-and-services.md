# Villager — Interfaces and Services

## One-sentence definition

This document defines the internal module boundaries of Villager so the system can be built as one simple application with clear responsibilities.

---

# 1. Design stance

Villager v1 should be:
- one application
- modular inside
- boring to run
- easy to debug

Do not start with microservices.
Do not start with distributed queues everywhere.
Do not start with agent swarms.

**One app. Clean modules.**

---

# 2. Real question

The point of this document is not “how many services can we invent?”
The point is:

> What are the minimum clean boundaries needed so the system does not become a blob?

---

# 3. Recommended top-level modules

For v1, I recommend only these modules:

1. `intake`
2. `spec_builder`
3. `orchestrator`
4. `sandbox`
5. `validator`
6. `pr_composer`
7. `state_store`

That is enough.

---

# 4. Module responsibilities

## 4.1 `intake`

### Purpose
Convert external triggers into a normalized `TaskPacket` request.

### Responsibilities
- receive JIRA-triggered or manual tasks
- fetch ticket data
- normalize fields
- reject obviously unsupported tasks early
- create initial run record

### Should not own
- sandbox creation
- validation
- PR creation

---

## 4.2 `spec_builder`

### Purpose
Turn intake data plus repo profile into an `ExecutionSpec`.

### Responsibilities
- load `RepoProfile`
- classify task type
- assess ambiguity and risk
- generate bounded spec
- run spec quality gate

### Should not own
- execution retries
- sandbox commands
- final review routing

---

## 4.3 `orchestrator`

### Purpose
This is the control brain of Villager.

### Responsibilities
- own run state machine
- call modules in the right order
- track retry counts
- decide retry / wait human / escalate / accept
- coordinate artifact creation
- decide when PR drafting happens

### Important
This is the real center of the system.

### Should not own
- direct repo-specific command logic
- low-level Docker handling
- specialized validation implementations

It coordinates; it should not do everything itself.

---

## 4.4 `sandbox`

### Purpose
Create and manage ephemeral execution environments.

### Responsibilities
- choose image
- create run workspace
- start container
- clone repo
- create work branch
- inject context
- run commands in container
- export artifacts
- destroy container

### Should not own
- ticket classification
- validation policy decisions
- PR review decisions

---

## 4.5 `validator`

### Purpose
Run checks and return structured validation results.

### Responsibilities
- run mechanical validators
- run policy validators
- run spec-alignment validators
- create `ValidationReport`
- recommend routing outcome

### Should not own
- final transition decisions

The validator reports. The orchestrator decides.

---

## 4.6 `pr_composer`

### Purpose
Turn accepted run output into a draft PR package.

### Responsibilities
- compose PR title/body
- map acceptance criteria to evidence
- include warnings and risks
- apply repo profile PR formatting rules
- prepare data for Git hosting integration

### Should not own
- whether a PR should exist at all

---

## 4.7 `state_store`

### Purpose
Persist the system of record outside the sandbox.

### Responsibilities
- store run metadata
- store state transitions
- store retry counts
- store spec/validation references
- store artifact references
- support querying runs later

### Should not own
- business logic about transitions

---

# 5. Module interaction view

```text
intake
  -> spec_builder
  -> orchestrator
      -> sandbox
      -> validator
      -> pr_composer
      -> state_store
```

More precisely:

```text
JIRA/manual trigger
  -> intake
  -> spec_builder
  -> orchestrator
      -> sandbox.execute()
      -> validator.validate()
      -> pr_composer.compose()
      -> state_store.save(...)
```

---

# 6. Simple control flow

The orchestrator should own the main sequence:

1. get task from `intake`
2. ask `spec_builder` for an `ExecutionSpec`
3. ask `sandbox` to prepare run environment
4. ask `sandbox` to run executor work
5. ask `validator` to validate outputs
6. decide next action
7. if accepted, ask `pr_composer` to build draft PR package
8. persist everything via `state_store`

This is simple and enough.

---

# 7. Suggested interfaces

Keep interfaces small and boring.

## `intake`
Possible functions:
- `fetch_task(source_ref) -> RawIssue`
- `normalize_task(raw_issue) -> TaskPacket`

## `spec_builder`
Possible functions:
- `load_repo_profile(repo_name) -> RepoProfile`
- `build_spec(task_packet, repo_profile) -> ExecutionSpec`
- `quality_gate(spec) -> SpecDecision`

## `sandbox`
Possible functions:
- `prepare(run_context) -> SandboxHandle`
- `execute(handle, execution_spec) -> ExecutionArtifacts`
- `run_commands(handle, commands) -> CommandResults`
- `teardown(handle) -> None`

## `validator`
Possible functions:
- `validate(run_context, execution_artifacts) -> ValidationReport`

## `pr_composer`
Possible functions:
- `compose(task_packet, execution_spec, validation_report, artifacts) -> DraftPR`

## `state_store`
Possible functions:
- `create_run(run_record)`
- `update_state(run_id, state, reason)`
- `save_validation_report(run_id, report)`
- `save_artifacts(run_id, artifact_refs)`
- `complete_run(run_id, final_status)`

## `orchestrator`
Possible functions:
- `start_run(source_ref)`
- `execute_run(run_id)`
- `handle_validation_outcome(run_id, validation_report)`

That is enough interface shape for now.

---

# 8. Data contracts between modules

These are the main objects moving through the app:
- `TaskPacket`
- `RepoProfile`
- `ExecutionSpec`
- `ValidationReport`
- `ReviewDecision`
- `ArtifactBundle`
- `RunRecord` (later/top-level)

## Rule
Modules should talk through these structured objects, not giant ad hoc dictionaries.

---

# 9. Where external integrations belong

Keep external integrations at the edges.

## JIRA integration
Belongs in or under `intake`.

## Git hosting integration
Can live near `pr_composer` or a small `git_provider` helper.

## Docker execution
Belongs in `sandbox`.

## Persistence
Belongs in `state_store`.

## Rule
Do not spread third-party API calls everywhere.
Keep them at the boundary modules.

---

# 10. What the orchestrator should decide

The orchestrator should decide:
- whether the run continues
- whether a retry happens
- whether human input is needed
- whether to draft a PR
- whether to mark the run failed

The orchestrator should not decide by vibes.
It should decide from:
- state
- retry counts
- validation report
- repo policy

That is the harness brain.

---

# 11. What should be synchronous vs asynchronous

Keep this simple.

## V1 recommendation
You can build Villager as one process that executes one run at a time or a small number of runs with a simple queue.

Do not force async/event complexity unless needed.

## Simple starting model
- trigger arrives
- orchestrator starts run
- run proceeds step by step
- state persisted after each important transition

This is enough for an MVP.

---

# 12. Suggested project layout

A simple layout could look like this:

```text
villager/
  app/
    intake/
    spec_builder/
    orchestrator/
    sandbox/
    validator/
    pr_composer/
    state_store/
    schemas/
    config/
  profiles/
  docs/
  runs/
```

This is only an example, but the principle is:
- modules by responsibility
- schemas in one shared place
- profiles/config outside the app core

---

# 13. What not to split too early

Do not create separate services yet for:
- JIRA sync
- validator workers
- PR writer
- profile manager
- retry engine

All of that can stay inside one app first.

## Why
Because most early changes will cross these boundaries anyway.
Microservices here would create ceremony, not clarity.

---

# 14. Minimal runtime shape

The simplest runtime model is:

```text
trigger -> orchestrator -> module calls -> persisted result
```

If you want a tiny step up:

```text
trigger -> queue -> worker process -> orchestrator -> module calls
```

## Recommendation
The second is nice if you want controlled execution.
But keep it one app.

---

# 15. Grug recommendation on service boundaries

If you are unsure whether something should be a module or a service, pick module first.

A module can become a service later.
A service is expensive to become simple again.

That rule alone will save you pain.

---

# 16. Opinionated v1 recommendation

Build Villager as:
- one app
- one orchestrator as control brain
- six supporting modules
- one state store
- one sandbox manager
- one queue or trigger entrypoint

That is enough to ship a real first version.

---

# 17. Grug conclusion

The architecture should feel boring:
- intake gets work
- spec builder bounds it
- orchestrator drives it
- sandbox runs it
- validator judges it
- PR composer packages it
- state store remembers it

Nothing fancy.
That is why it will work.

---

# 18. Next doc

Best next document:

**`mvp-build-plan.md`**

Why:
You now have enough design clarity to turn the docs into a practical implementation order.
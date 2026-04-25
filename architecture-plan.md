# Villager — Architecture Plan

## One-sentence definition

Villager is a JIRA-triggered, repo-personalized coding worker that converts a tagged issue into a bounded execution spec, performs the task in an ephemeral sandbox, validates results through a harnessed loop, and outputs a draft PR with evidence.

---

# 1. Design stance

## What Villager is
A **harnessed SWE worker** for bounded engineering tasks.

## What Villager is not
- not a general autonomous engineer
- not a replacement for code review
- not a self-judging one-shot coder
- not an auto-merge system in v1

## Core thesis
Most failures in agentic coding are not model failures. They are failures of:
- task framing
- environmental isolation
- validation design
- loop control
- memory/state
- human gating

So the product should optimize the system around the model, not only the model.

---

# 2. Main problem to solve

Translate ambiguous work from JIRA into a **safe, bounded, testable software task** that can be executed repeatably across different repos and teams.

This splits into 5 sub-problems:
1. **Task normalization** — JIRA is often messy and incomplete
2. **Repo/team personalization** — every codebase has different rules
3. **Execution safety** — ephemeral, reproducible environments
4. **Validation quality** — proving the work is good enough
5. **Review packaging** — making output easy for humans to trust

---

# 3. Recommended v1 architecture

## Recommendation
Start with:
- **one executor agent**
- **one strong harness/orchestrator**
- **deterministic sensors first**
- **ephemeral Docker sandbox per run**
- **structured repo/team profiles**
- **draft PR only**

## Why this architecture
It is the simplest architecture that can still express:
- bounded planning
- execution
- validation
- retries
- escalation
- personalization

It also keeps future options open:
- split planner/reviewer into separate agents later
- add richer retrieval later
- add more nuanced approval routing later

---

# 4. Architecture overview

```text
                    +----------------------+
                    |      JIRA Queue      |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    |   Task Normalizer    |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    |     Spec Builder     |
                    +----+------------+----+
                         |            |
                         |            v
                         |   +-------------------+
                         |   | Repo/Team Profile |
                         |   +-------------------+
                         |
                         v
                +------------------------------+
                | Harness Orchestrator         |
                | - state machine              |
                | - loop control               |
                | - approvals                  |
                | - memory/logging             |
                +-----+-------------------+----+
                      |                   |
                      |                   v
                      |         +----------------------+
                      |         | Validation Sensors   |
                      |         | lint/test/typecheck  |
                      |         | policy/review/risk   |
                      |         +----------+-----------+
                      |                    |
                      v                    |
            +-------------------+          |
            | Sandbox Manager   |----------+
            +---------+---------+
                      |
                      v
            +-------------------+
            | Executor Agent    |
            | inspect/edit/run  |
            +---------+---------+
                      |
                      v
            +-------------------+
            | Artifact Bundle   |
            +---------+---------+
                      |
                      v
            +-------------------+
            | PR Composer       |
            +---------+---------+
                      |
                      v
            +-------------------+
            | Draft PR          |
            +-------------------+
```

---

# 5. Core subsystems

## 5.1 Intake / Task Normalizer

### Purpose
Convert raw JIRA ticket data into a machine-usable `TaskPacket`.

### Inputs
- issue key
- title
- description
- labels/tags
- linked repo/service
- assignee/reporter
- custom fields
- comments or acceptance criteria

### Outputs
A normalized packet with:
- `task_id`
- `source_issue`
- `repo`
- `requested_outcome`
- `acceptance_criteria`
- `constraints`
- `priority`
- `risk_level`
- `ambiguity_flags`

### Why it matters
You want the agent to operate on normalized semantics, not raw issue sludge.

---

## 5.2 Spec Builder

### Purpose
Create a bounded `ExecutionSpec` before coding begins.

### Responsibilities
- summarize the problem
- identify in-scope vs out-of-scope
- infer likely code areas
- define validation commands
- define stop conditions
- identify uncertainties and escalation points

### Output shape
The spec should answer:
- what problem is being solved?
- what counts as done?
- what should not be changed?
- what evidence must be produced?
- when should the agent stop and escalate?

### Key principle
No code execution before spec generation.

---

## 5.3 Repo / Team Profile Layer

### Purpose
Provide personalization that is stable, versioned, and machine-readable.

### Why structured config matters
A giant system prompt cannot reliably encode:
- exact commands
- directory-level permissions
- sensitive paths
- PR style conventions
- testing expectations

### Recommended contents
```yaml
repo_name: billing-service
language: python
build_system: poetry
commands:
  lint: poetry run ruff check .
  format: poetry run ruff format .
  typecheck: poetry run mypy src
  test: poetry run pytest -q
paths:
  owned:
    - src/
    - tests/
  sensitive:
    - infra/
    - migrations/
rules:
  require_tests_for_behavior_change: true
  block_dependency_changes_without_reason: true
pr:
  template: standard
  reviewers:
    - payments-team
examples:
  good_prs:
    - PR-142
    - PR-188
```

### Personalization levels
1. **Tooling** — commands/build/test/lint
2. **Codebase norms** — patterns and constraints
3. **Process norms** — branch/PR/review expectations
4. **Historical examples** — good prior diffs/PRs

---

## 5.4 Executor Agent

### Purpose
Perform the actual coding work.

### Responsibilities
- inspect relevant code
- produce local plan
- edit files
- run local commands
- react to structured validation failures
- summarize changes

### Non-responsibilities
The agent should not be the final authority on:
- whether the task is complete
- whether the risk is acceptable
- whether retries should continue
- whether a PR should be opened

Those belong to the harness.

### Execution style
The executor should work in small steps:
1. inspect
2. propose local plan
3. make minimal edits
4. run narrow checks
5. hand off to harness validation

This reduces large, noisy diffs.

---

## 5.5 Validation Sensors

### Purpose
Produce objective signals about correctness, safety, and scope alignment.

## Sensor categories

### A. Mechanical sensors
- formatting
- lint
- typecheck
- tests
- build

### B. Policy sensors
- touched sensitive paths?
- dependency file changed?
- migration added?
- large diff threshold exceeded?
- secrets or tokens introduced?

### C. Spec-alignment sensors
- acceptance criteria coverage
- out-of-scope changes
- missing tests for behavior change

### D. Optional semantic review
- LLM reviewer for code quality/risk/spec mismatch

### Key principle
Deterministic sensors first. LLM review second.

---

## 5.6 Loop Controller

### Purpose
Turn validator output into decisions.

### Decisions
- `accept`
- `retry`
- `escalate`
- `wait_human`

### Retry policy
Max autonomous retries: **3**

### Why cap retries
After multiple failures, the issue is usually one of:
- bad spec
- unclear ticket
- wrong assumptions
- environmental problem
- risky change boundary

### Structured retry input
Never feed the whole raw log back.
Provide:
- failed sensor name
- concise failure summary
- suspected files
- previous attempt summary
- constraints
- forbidden repeated actions

This prevents random thrashing.

---

## 5.7 PR Composer

### Purpose
Turn execution results into a review-ready draft PR.

### PR body should include
- problem summary
- what changed
- acceptance criteria coverage
- validation evidence
- risks/open questions
- screenshots/logs if relevant
- labels/metadata

### Why this matters
Humans trust systems that show their work.

---

## 5.8 Memory / State Store

### Purpose
Persist important state outside the sandbox.

### Persisted data
- task packet
- execution spec
- repo profile version
- loop count
- validation reports
- decisions taken
- artifacts generated
- timestamps
- final status

### Suggested v1 storage
- relational DB for metadata/state
- object storage or filesystem for logs/artifacts

Simple wins here.

---

# 6. Harness design

## 6.1 State machine

Recommended states:

```text
INTAKE
SPEC_READY
SANDBOX_READY
EXECUTING
VALIDATING
RETRYING
WAITING_HUMAN
REVIEW_READY
PR_DRAFTED
DONE
FAILED_RETRYABLE
FAILED_ESCALATE
```

### Benefits
- observable progress
- easier debugging
- cleaner incident handling
- explicit ownership of transitions

---

## 6.2 Transition logic

### Example flow
1. `INTAKE` → task received
2. `SPEC_READY` → execution spec validated
3. `SANDBOX_READY` → container/workspace prepared
4. `EXECUTING` → agent edits code
5. `VALIDATING` → sensors run
6. if pass enough threshold → `REVIEW_READY`
7. if acceptable → `PR_DRAFTED`
8. if published successfully → `DONE`

### Failure routes
- validation failure + retries left → `RETRYING`
- high ambiguity or risky edit → `WAITING_HUMAN`
- repeated failure or serious issue → `FAILED_ESCALATE`

---

## 6.3 Human gates

### Mandatory gates
- sensitive directories changed
- destructive migrations proposed
- secrets/auth/payment logic touched
- tests intentionally skipped
- acceptance criteria remain ambiguous
- retry cap exceeded

### Optional gates
- before opening PR in high-sensitivity repos
- before dependency upgrades
- before generated diff exceeds threshold

### Interaction pattern
Agent proposes → harness summarizes → human approves/rejects → harness proceeds.

---

# 7. Sandbox design

## 7.1 Principles
- ephemeral
- reproducible
- bounded
- isolated
- observable
- disposable

## 7.2 Lifecycle
1. create run workspace
2. provision Docker container
3. clone repo / checkout branch
4. inject task/spec/profile
5. run executor inside sandbox
6. run validators inside same sandbox
7. export artifacts
8. destroy sandbox

## 7.3 Why same-environment validation matters
The environment that produced the change should also validate it.
This avoids “works in one shell, fails in another” drift.

---

## 7.4 Image strategy

### Option A: one generic image
Pros:
- simple startup
- fewer base images

Cons:
- slow bootstrap
- less reproducible
- more setup drift

### Option B: language/repo-family images
Examples:
- python-worker
- node-worker
- jvm-worker
- polyglot-worker

**Recommended for v1**
Use a few family images, not one image per repo.

---

## 7.5 Sandbox restrictions

Recommended default restrictions:
- no privileged mode
- limited CPU/memory/time
- restricted network by default
- mounted credentials only if required
- write only within workspace
- no persistent container state

These constraints reduce blast radius.

---

# 8. Contracts / schemas

These are the core contracts that keep the system legible.

## 8.1 TaskPacket
Represents normalized input.

Suggested fields:
- `task_id`
- `jira_issue_key`
- `title`
- `description`
- `repo`
- `labels`
- `acceptance_criteria[]`
- `constraints[]`
- `priority`
- `risk_level`
- `ambiguity_flags[]`

## 8.2 RepoProfile
Represents repo/team personalization.

Suggested fields:
- `repo_name`
- `team_name`
- `language`
- `commands`
- `paths.owned[]`
- `paths.sensitive[]`
- `rules`
- `pr_template`
- `reviewer_groups[]`
- `examples[]`

## 8.3 ExecutionSpec
Represents the bounded job to perform.

Suggested fields:
- `problem_statement`
- `scope_in[]`
- `scope_out[]`
- `target_areas[]`
- `acceptance_criteria[]`
- `validation_steps[]`
- `stop_conditions[]`
- `escalation_conditions[]`
- `artifacts_required[]`

## 8.4 ValidationReport
Represents the output of all sensors.

Suggested fields:
- `mechanical_checks[]`
- `policy_checks[]`
- `spec_alignment_checks[]`
- `summary`
- `status`
- `failures[]`
- `warnings[]`

## 8.5 ReviewDecision
Represents harness routing.

Suggested fields:
- `decision`
- `reason`
- `retry_count`
- `required_human_input`
- `next_action`

## 8.6 ArtifactBundle
Represents everything exported from a run.

Suggested fields:
- `diff_patch`
- `changed_files`
- `command_log`
- `execution_summary`
- `validation_report`
- `pr_body`
- `metadata`

---

# 9. Review loop design

A clean review loop has three layers.

## Layer 1: mechanical correctness
Questions:
- does it build?
- do tests pass?
- is typechecking green?
- is formatting/lint clean?

## Layer 2: scope correctness
Questions:
- did it address the issue?
- are acceptance criteria covered?
- did it change things outside scope?

## Layer 3: change quality / risk
Questions:
- is the diff unexpectedly large?
- are sensitive paths touched?
- were tests added when behavior changed?
- is there hidden operational risk?

### Routing principle
Fail early on mechanical checks.
Only do higher-order review after basic correctness passes.

---

# 10. Confidence model

Confidence should be computed by the harness, not self-reported by the agent.

## Possible signals
- all checks green
- retry count
- diff size
- number of changed files
- sensitive directories touched
- acceptance criteria coverage score
- unresolved warnings
- ambiguity score from ticket/spec

## Example output classes
- **high confidence** → open draft PR automatically
- **medium confidence** → open draft PR with warning labels
- **low confidence** → escalate before PR

This gives practical routing without fake certainty.

---

# 11. Risk model

## Common failure modes

### 1. Spec drift
The agent solves a different problem than the ticket asked.

**Mitigation:** explicit execution spec + acceptance criteria checks

### 2. Repo norm violations
The code works but ignores team conventions.

**Mitigation:** structured repo profile + policy checks

### 3. Infinite repair loop
The agent keeps trying random fixes.

**Mitigation:** capped loops + structured retry feedback

### 4. Unsafe modifications
Sensitive files or migrations are touched unexpectedly.

**Mitigation:** path/risk sensors + human gates

### 5. Environment mismatch
The code passes in one environment but not in the real repo setup.

**Mitigation:** reproducible sandbox + same-environment validation

---

# 12. v1 scope and non-goals

## In scope
- 1 JIRA project/tag family
- 1-3 repos
- text/code tasks with clear acceptance criteria
- single-branch implementation
- deterministic checks
- draft PR output

## Not in scope
- multi-repo orchestration
- deployment automation
- auto-merge
- broad autonomous refactors
- product/design decision making
- unlimited agent autonomy

This is important. Keep Villager narrow enough to become trustworthy.

---

# 13. Suggested implementation roadmap

## Milestone 1 — Contracts first
Deliver:
- `TaskPacket`
- `RepoProfile`
- `ExecutionSpec`
- `ValidationReport`
- `ReviewDecision`
- `ArtifactBundle`

**Done when:** you can simulate a full run on paper using only structured objects.

## Milestone 2 — Happy path execution
Deliver:
- JIRA intake
- one repo profile
- sandbox spin-up
- executor run
- one validator path
- draft PR body

**Done when:** one tagged ticket can produce one plausible PR draft.

## Milestone 3 — Harnessed retries
Deliver:
- loop controller
- validation failure routing
- retry count caps
- structured retry prompts

**Done when:** a failing first attempt can recover on a second/third attempt.

## Milestone 4 — Repo personalization
Deliver:
- multiple repo profiles
- command differences handled by config
- path/risk policy enforcement

**Done when:** the same platform can operate on at least two repos with different conventions.

## Milestone 5 — Better review quality
Deliver:
- scope alignment checks
- risk checks
- improved PR composition
- optional review agent

**Done when:** humans can review the PR efficiently with evidence included.

---

# 14. Open design questions

These are the most valuable next questions to answer.

1. How will repo/team profiles be authored and versioned?
2. Who owns acceptance criteria quality when JIRA is ambiguous?
3. Will spec generation be fully automatic or human-reviewable in sensitive repos?
4. What are the default human gate thresholds?
5. How will Villager authenticate to JIRA, GitHub/GitLab, and internal repos?
6. What observability is needed for failed runs?
7. What tasks are explicitly unsupported in v1?

---

# 15. Opinionated conclusion

The best first version of Villager is **not** a swarm of agents.
It is:
- one good executor
- one strict harness
- one disposable sandbox
- one clear set of contracts
- one narrow path from ticket to draft PR

If that works reliably, everything else can be added later.

---

# 16. Recommended next step

Define the schemas for:
- `TaskPacket`
- `RepoProfile`
- `ExecutionSpec`
- `ValidationReport`
- `ReviewDecision`

That is the foundation that will keep the architecture clean as the system grows.

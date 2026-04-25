# Villager

JIRA-tagged agentic SWE worker: takes a scoped task, executes it inside an ephemeral repo-aware sandbox, validates through a harnessed review loop, and produces a draft PR with evidence.

## Goal

Build a reliable coding worker for software teams that can:
1. Pick up a JIRA issue by tag/queue
2. Understand repo/team-specific conventions
3. Generate an execution spec before coding
4. Implement the task in an ephemeral Docker sandbox
5. Validate changes with deterministic sensors and review loops
6. Produce a draft PR with summary, evidence, and risks

## Core Product Idea

Villager is **not just an agent**.
It is a **harnessed software worker** made of:
- an **Agent** that reasons and edits code
- a **Harness** that controls state, loops, validation, and safety
- a **Sandbox** that executes work in a disposable environment

## Minimal v1

A usable first version should:
- read a tagged JIRA ticket
- map it to one repo
- load repo/team profile config
- create an execution spec
- run in an ephemeral Docker container
- make a bounded code change
- run lint/tests/typecheck
- generate:
  - diff/patch
  - validation report
  - draft PR body

## Architecture at a glance

```text
[JIRA Listener]
    -> [Task Normalizer]
    -> [Spec Builder]
    -> [Harness Orchestrator]
        -> [Sandbox Manager]
            -> [Executor Agent]
        -> [Validation Sensors]
        -> [Loop Controller]
    -> [PR Composer]
    -> [Draft PR + Artifacts]
```

## Main components

### 1. Intake / Dispatcher
Normalizes raw JIRA data into a task packet.

### 2. Spec Builder
Turns the issue into a bounded execution spec with scope, constraints, acceptance criteria, and validation commands.

### 3. Repo/Team Profile Layer
Stores personalization per repo/team:
- tooling commands
- architecture rules
- PR conventions
- forbidden or sensitive directories
- examples of good PRs

### 4. Executor Agent
Inspects the codebase, edits files, runs commands, and responds to structured feedback.

### 5. Validation Sensors
Run checks such as:
- lint
- tests
- typecheck
- build/smoke checks
- policy/risk checks
- optional LLM review

### 6. Loop Controller
Decides whether to:
- accept
- retry with targeted feedback
- escalate to human

### 7. PR Composer
Builds a draft PR with:
- summary
- acceptance criteria coverage
- validation evidence
- risks/open questions

## Harness principles

- **Builder does not validate itself**
- **Explicit state machine over hidden reasoning**
- **Max 3 autonomous loops before escalation**
- **Deterministic checks before subjective review**
- **Human gates for destructive or high-risk work**
- **Structured config beats giant prompts**

## State machine

```text
INTAKE
  -> SPEC_READY
  -> SANDBOX_READY
  -> EXECUTING
  -> VALIDATING
  -> REVIEW_READY
  -> PR_DRAFTED
  -> DONE

Failure states:
- FAILED_RETRYABLE
- FAILED_ESCALATE
- WAITING_HUMAN
```

## Suggested project contracts

Keep these as first-class schemas:
- `TaskPacket`
- `RepoProfile`
- `ExecutionSpec`
- `ValidationReport`
- `ReviewDecision`
- `ArtifactBundle`

## v1 scope

In scope:
- one JIRA project/tag family
- 1-3 repos
- one executor agent
- one sandbox strategy
- draft PR only
- deterministic validators

Out of scope:
- auto-merge
- cross-repo orchestration
- prod deployment
- long-term autonomous planning
- complex multi-agent debates

## Recommended build order

1. Define schemas/contracts
2. Build task normalization + spec creation
3. Build sandbox lifecycle
4. Integrate executor agent
5. Add validation sensors
6. Add retry/escalation logic
7. Add PR drafting
8. Add repo/team personalization

## First milestone

**Done when:** a tagged JIRA issue can trigger one end-to-end run in one repo and produce a draft PR with validation evidence.

## Next document

See [`architecture-plan.md`](./architecture-plan.md) for the deeper architectural plan.

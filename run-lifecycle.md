# Villager — Run Lifecycle

This document explains how a Villager run moves through the harness from intake to draft PR.

It connects:
- the architecture from `architecture-plan.md`
- the contracts from `schemas.md`
- the operational behavior of the harness

---

# 1. Purpose

A run lifecycle exists to make agent execution:
- observable
- debuggable
- bounded
- repeatable
- safe

Without an explicit lifecycle, agent systems become hard to trust because no one can clearly answer:
- what state is this task in?
- why is it blocked?
- what happened on the last attempt?
- why did the system decide to retry or escalate?

---

# 2. Core idea

Each Villager run should be represented as a stateful process with:
- a unique run id
- explicit state transitions
- attached structured objects
- logs and artifacts preserved outside the sandbox

A run is not just “prompt in, code out.”
It is a controlled sequence of decisions.

---

# 3. Main lifecycle states

Recommended states:

```text
INTAKE
SPEC_BUILDING
SPEC_READY
SANDBOX_PREPARING
SANDBOX_READY
EXECUTING
VALIDATING
RETRYING
WAITING_HUMAN
REVIEW_READY
PR_DRAFTING
PR_DRAFTED
DONE
FAILED_RETRYABLE
FAILED_ESCALATE
CANCELLED
```

---

# 4. What each state means

## INTAKE
The run has been triggered but not yet normalized.

### Entry conditions
- JIRA event received
- manual trigger received
- scheduled queue pickup found a matching tag

### Main actions
- create run id
- fetch raw issue data
- identify repo/team target
- create initial record

### Exit condition
A raw task has been collected and can be normalized.

---

## SPEC_BUILDING
The harness is transforming issue data into a bounded execution contract.

### Main actions
- build `TaskPacket`
- fetch `RepoProfile`
- derive `ExecutionSpec`
- detect ambiguity/risk early

### Exit conditions
- success → `SPEC_READY`
- too ambiguous/risky → `WAITING_HUMAN`
- malformed input/system failure → `FAILED_ESCALATE`

---

## SPEC_READY
The execution contract exists and can be used to drive the run.

### Attached artifacts
- `TaskPacket`
- `RepoProfile`
- `ExecutionSpec`

### Main checkpoint
The system should now be able to answer:
- what problem is being solved?
- what is in scope?
- how will it be validated?
- when should the run stop?

---

## SANDBOX_PREPARING
The runtime environment is being provisioned.

### Main actions
- choose sandbox image
- create workspace
- clone repo
- checkout base branch
- create work branch
- inject spec/profile/context files
- configure runtime limits

### Exit conditions
- success → `SANDBOX_READY`
- environment failure → `FAILED_RETRYABLE` or `FAILED_ESCALATE`

---

## SANDBOX_READY
The environment is available for execution.

### Main checkpoint
The system should confirm:
- repo is present
- target branch is ready
- required commands are available
- execution context is mounted

---

## EXECUTING
The executor agent is actively working inside the sandbox.

### Main actions
- inspect relevant files
- create local plan
- edit code
- run narrow checks if useful
- produce work summary

### Important rule
The executor can propose or perform code changes, but it does not decide final success.

### Exit conditions
- code change attempt completed → `VALIDATING`
- blocked by ambiguity/risk → `WAITING_HUMAN`
- internal failure → `FAILED_RETRYABLE`

---

## VALIDATING
Sensors run against the current workspace.

### Main actions
- run lint/typecheck/tests/build as defined by `RepoProfile` and `ExecutionSpec`
- run policy checks
- run spec-alignment checks
- optionally run semantic review
- produce `ValidationReport`

### Exit conditions
- acceptable result → `REVIEW_READY`
- retryable result → `RETRYING`
- unsafe/unclear/high-risk result → `WAITING_HUMAN` or `FAILED_ESCALATE`

---

## RETRYING
The harness is preparing a targeted retry after a failed validation cycle.

### Main actions
- increment retry count
- summarize failures
- build focused retry instructions
- narrow the scope for the next executor attempt

### Important rule
Do not send the agent back with only raw logs.
Provide structured guidance.

### Exit conditions
- retries remaining → `EXECUTING`
- retry cap exceeded → `WAITING_HUMAN` or `FAILED_ESCALATE`

---

## WAITING_HUMAN
The run needs human input before proceeding.

### Common reasons
- ambiguous acceptance criteria
- sensitive paths touched
- migration or destructive change required
- retry cap exceeded
- validation produced unresolved risk

### Human inputs may include
- approve to continue
- clarify acceptance criteria
- reduce scope
- cancel run

### Exit conditions
- approved/clarified → previous appropriate state
- rejected → `CANCELLED` or `FAILED_ESCALATE`

---

## REVIEW_READY
The run has passed enough checks to be packaged for PR drafting.

### Attached artifacts
- `ValidationReport`
- final diff summary
- changed files
- risk notes

### Main checkpoint
The harness should now be able to explain:
- what changed
- why it changed
- how it was validated
- what remains risky or uncertain

---

## PR_DRAFTING
The harness is composing a review-ready PR body.

### Main actions
- summarize ticket and implementation
- map acceptance criteria to evidence
- attach validation summary
- add risks/open questions
- apply repo/team PR formatting conventions

### Exit condition
Draft PR body and metadata are ready.

---

## PR_DRAFTED
The system has produced the review package.

### Outputs
- branch
- diff/patch
- PR title
- PR body
- linked artifacts/logs

### Exit conditions
- if PR creation succeeds → `DONE`
- if PR creation fails due to integration issue → `FAILED_RETRYABLE` or `FAILED_ESCALATE`

---

## DONE
The run completed successfully.

### Completion criteria
- draft PR exists
- artifacts are stored
- final state and timestamps are persisted
- run is queryable for audit/debugging

---

## FAILED_RETRYABLE
A temporary/system recoverable problem occurred.

### Examples
- Git clone transient failure
- package install network hiccup
- temporary service/auth failure

### Typical next steps
- retry infrastructure step
- do not count against code-fix retry budget unless execution already started

---

## FAILED_ESCALATE
The run cannot safely continue autonomously.

### Examples
- task fundamentally ambiguous
- repeated execution failure
- unsupported task type
- major environment misconfiguration
- high-risk requested change outside policy

### Typical next steps
- notify operator
- preserve artifacts and logs
- mark run for manual takeover or redesign

---

## CANCELLED
The run was intentionally stopped.

### Examples
- human rejected the proposed approach
- task was superseded
- queue item was invalid

---

# 5. Happy path flow

This is the simplest successful path.

```text
INTAKE
  -> SPEC_BUILDING
  -> SPEC_READY
  -> SANDBOX_PREPARING
  -> SANDBOX_READY
  -> EXECUTING
  -> VALIDATING
  -> REVIEW_READY
  -> PR_DRAFTING
  -> PR_DRAFTED
  -> DONE
```

## Happy path narrative
1. A tagged JIRA issue enters the queue.
2. Villager normalizes it into a `TaskPacket`.
3. It loads the repo’s `RepoProfile`.
4. It builds an `ExecutionSpec`.
5. It provisions a sandbox and checks out the repo.
6. The executor makes a bounded implementation.
7. Validation passes.
8. The harness drafts a PR.
9. Artifacts are saved and the run is marked done.

---

# 6. Retry path flow

This handles normal implementation mistakes.

```text
INTAKE
  -> SPEC_BUILDING
  -> SPEC_READY
  -> SANDBOX_PREPARING
  -> SANDBOX_READY
  -> EXECUTING
  -> VALIDATING
  -> RETRYING
  -> EXECUTING
  -> VALIDATING
  -> REVIEW_READY
  -> PR_DRAFTING
  -> PR_DRAFTED
  -> DONE
```

## Retry path narrative
1. Initial implementation attempt finishes.
2. Validation fails for a retryable reason.
3. The harness produces a structured retry instruction.
4. The executor retries with narrowed goals.
5. Validation passes on a later attempt.

## Retry budget recommendation
Use two counters:

### A. Execution retry count
For code-fix loops.
Recommended max: **3**

### B. Infrastructure retry count
For sandbox/network/tooling transient failures.
Recommended max: **2-3**, separate from execution retries.

Why separate them:
A flaky clone step should not consume the same budget as repeated bad code fixes.

---

# 7. Human gate flow

This handles ambiguity or high-risk cases.

```text
INTAKE
  -> SPEC_BUILDING
  -> WAITING_HUMAN
  -> SPEC_READY
  -> SANDBOX_PREPARING
  -> SANDBOX_READY
  -> EXECUTING
  -> VALIDATING
  -> WAITING_HUMAN
  -> REVIEW_READY
  -> PR_DRAFTING
  -> PR_DRAFTED
  -> DONE
```

## Human gate examples

### Example 1: ambiguous ticket
The issue says “improve checkout validation” with no exact behavior specified.

Villager should stop and ask:
- what exact validation behavior is expected?
- what error response is correct?
- should existing clients be preserved exactly?

### Example 2: migration required
The code fix seems to require a schema change.

Villager should not decide alone if migrations are acceptable.
It should request approval.

### Example 3: sensitive path touched
If the fix touches auth, billing, infra, or deployment files, the run should pause depending on policy.

---

# 8. Escalation path flow

This handles non-recoverable or policy-blocked work.

```text
INTAKE
  -> SPEC_BUILDING
  -> SPEC_READY
  -> SANDBOX_PREPARING
  -> SANDBOX_READY
  -> EXECUTING
  -> VALIDATING
  -> RETRYING
  -> EXECUTING
  -> VALIDATING
  -> FAILED_ESCALATE
```

## Escalation examples
- the ticket cannot be bounded into a safe spec
- every retry changes more unrelated files
- validation keeps failing for contradictory reasons
- required dependencies or environment are broken beyond allowed recovery
- the task is unsupported in v1

---

# 9. Objects created across the lifecycle

## At INTAKE / SPEC_BUILDING
Created or attached:
- `RunRecord` (future top-level lifecycle object)
- `TaskPacket`
- `RepoProfile`
- `ExecutionSpec`

## At VALIDATING
Created:
- `ValidationReport`

## After validation routing
Created:
- `ReviewDecision`

## At PR_DRAFTING / PR_DRAFTED
Created:
- `ArtifactBundle`

---

# 10. Suggested top-level RunRecord

Even though it is not fully defined yet, Villager will likely need a top-level lifecycle object.

## Purpose
Track one run across all states and references.

## Suggested fields
- `run_id`
- `task_id`
- `current_state`
- `state_history`
- `retry_counts`
- `task_packet_ref`
- `repo_profile_ref`
- `execution_spec_ref`
- `validation_reports[]`
- `review_decisions[]`
- `artifact_bundle_ref`
- `started_at`
- `updated_at`
- `finished_at`
- `final_status`

This is useful for observability and operations.

---

# 11. Transition ownership

One of the most important harness rules:

**the harness owns state transitions, not the executor agent.**

## Why
If the agent can declare “done,” “safe,” or “good enough” without external checks, trust collapses.

## Correct ownership model
- **executor**: propose/work/change
- **validators**: measure
- **harness**: decide
- **human**: approve where policy/risk requires

---

# 12. What should be logged at every state

For each state transition, log at minimum:
- run id
- previous state
- next state
- timestamp
- reason for transition
- actor causing transition (`system`, `executor`, `validator`, `human`)
- related artifact references

This gives you operational traceability.

---

# 13. Retry instruction design

When moving from `VALIDATING` to `RETRYING`, the harness should generate structured feedback.

## Recommended contents
- `failed_checks`
- `summary_of_failures`
- `likely_impacted_files`
- `do_not_repeat`
- `scope_reminder`
- `suggested_next_focus`

## Example
```yaml
retry_instruction:
  failed_checks:
    - targeted_tests
  summary_of_failures:
    - Empty coupon code returns 422 instead of expected 400
  likely_impacted_files:
    - src/api/coupons.py
    - tests/api/test_coupons.py
  do_not_repeat:
    - Do not change pricing logic
    - Do not broaden the change into async worker code
  scope_reminder:
    - Only fix API-side validation and related tests
  suggested_next_focus:
    - Align validation error handling with existing API contract
```

---

# 14. Human gate request design

When moving to `WAITING_HUMAN`, the harness should ask concise, decision-friendly questions.

## Recommended contents
- why the run paused
- files/areas involved
- risk summary
- exact decision needed
- safe options available

## Example
```yaml
human_gate_request:
  reason: Shared validation layer change may affect multiple services
  impacted_areas:
    - src/validation/
    - tests/api/
  risk_summary:
    - Change appears small but touches reusable validation path
  decision_needed:
    - Approve proceeding with shared validation change?
  options:
    - approve_and_continue
    - restrict_scope_to_api_only
    - cancel_run
```

The goal is to minimize decision fatigue.

---

# 15. Timeouts and operational limits

Every run should have explicit operational bounds.

## Recommended limits for v1
- max execution retries: 3
- max infrastructure retries: 3
- max sandbox duration per attempt: fixed threshold
- max changed files before review gate: configurable threshold
- max diff size before warning/escalation: configurable threshold

Without hard limits, systems drift into expensive loops.

---

# 16. Observability recommendations

For each run, you should be able to inspect:
- current state
- last successful state
- latest validation report
- retry counts
- changed files
- open human gate requests
- final artifact bundle

## Suggested operator views later
- queue view
- active runs view
- failed runs view
- waiting-human view
- completed runs view

---

# 17. Opinionated operating rules

## Rule 1
No execution before `ExecutionSpec` exists.

## Rule 2
No success without `ValidationReport`.

## Rule 3
No unbounded retries.

## Rule 4
No hidden transitions.
Every state change should be logged.

## Rule 5
No silent risk acceptance.
Warnings and sensitive changes must be explicit.

## Rule 6
No final authority inside the executor.
The harness decides.

---

# 18. Minimal v1 lifecycle

If you want the smallest possible first implementation, keep only these states:

```text
INTAKE
SPEC_READY
SANDBOX_READY
EXECUTING
VALIDATING
WAITING_HUMAN
PR_DRAFTED
DONE
FAILED
```

This compressed model is enough to ship an initial version.

Later, you can expand into the richer lifecycle in this document.

---

# 19. Recommendation

For implementation, I recommend:

### Start operationally simple
Use the **minimal v1 lifecycle** first.

### But design conceptually rich
Keep the richer state model in the docs so the architecture does not collapse as you add complexity.

This gives you:
- low implementation burden now
- clean expansion path later

---

# 20. Next step

Best next document:

**`repo-profile-template.yaml`**

Why:
- architecture exists
- schemas exist
- lifecycle exists
- now you need one concrete artifact that makes personalization real

A good next move is to create:
1. a generic repo profile template
2. one concrete example for a Python repo
3. one concrete example for a Node repo

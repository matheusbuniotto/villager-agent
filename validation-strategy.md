# Villager — Validation Strategy

## One-sentence definition

Validation Strategy defines how Villager proves a code change is good enough for a draft PR, when it should retry, and when it should stop and escalate.

---

# 1. Why this matters

This is the trust engine of the system.

Without strong validation, Villager is just:
- a code generator
- a patch generator
- a confident guesser

With strong validation, Villager becomes:
- bounded
- reviewable
- safer
- more trustworthy

## Core principle
The executor does not decide whether the work is correct.
The harness decides based on validation evidence.

---

# 2. Validation goals

Validation in Villager should answer five questions:

1. Did the code still build or run correctly?
2. Did the change satisfy the acceptance criteria?
3. Did the change stay within allowed scope?
4. Did the change trigger any policy or risk concerns?
5. Is the result good enough to spend human review time on?

If validation cannot answer these, the run is weak.

---

# 3. Validation philosophy

## Deterministic first
Always prefer checks that produce objective signals:
- lint
- tests
- typecheck
- build
- diff checks
- path policy checks

## Semantic review second
Use LLM or heuristic review only after basic correctness checks pass.

## Fail early
If the code does not pass core mechanical checks, do not spend time on richer review.

## Evidence over confidence
Do not trust “I think it works.”
Trust:
- test outputs
- type/lint status
- explicit policy checks
- spec coverage analysis

---

# 4. Validation layers

Use three layers.

## Layer 1: Mechanical validation
These are the first checks.

### Purpose
Verify that the code still works at a basic engineering level.

### Typical checks
- format/lint
- typecheck
- unit tests
- targeted tests
- build
- smoke tests

### Rule
If required mechanical checks fail, the run is not ready.

---

## Layer 2: Policy validation
These check whether the change obeys repo/team rules.

### Typical checks
- sensitive path touched?
- forbidden path touched?
- migration added?
- dependency file changed?
- generated files edited?
- changed files threshold exceeded?
- diff line threshold exceeded?

### Rule
A policy issue may produce:
- warning
- human gate
- escalate

depending on `RepoProfile` and task context.

---

## Layer 3: Spec-alignment validation
These check whether the change appears to solve the intended problem.

### Typical checks
- acceptance criteria coverage
- missing test for behavior change
- out-of-scope files changed
- target area mismatch
- implementation appears to solve a different problem than the ticket

### Rule
This layer exists because passing tests alone is not enough.

---

# 5. Validator categories

## 5.1 Required validators for v1

These should exist in the first real version.

### Mechanical
- `lint`
- `test`
- `typecheck` if repo supports it

### Policy
- `path_policy_check`
- `dependency_change_check`
- `generated_code_check`

### Spec alignment
- `acceptance_criteria_check`
- `scope_change_check`

This is enough for a useful v1.

---

## 5.2 Optional validators for later
- `build_check`
- `smoke_check`
- `secret_scan`
- `review_agent_check`
- `risk_score_check`
- `codeowner_sensitivity_check`

These are useful, but do not block v1.

---

# 6. Validation result model

Each validator should produce a structured result.

## Suggested fields
- `name`
- `category`
- `status`
- `summary`
- `details`
- `artifacts`

## Suggested status values
- `pass`
- `warning`
- `fail_retryable`
- `fail_escalate`
- `skipped`

### Why this matters
If every validator produces a different kind of output, routing becomes messy.

---

# 7. Routing model

Validation should not only say “good” or “bad.”
It should drive the next action.

## Main decisions
- `accept`
- `retry`
- `wait_human`
- `escalate`

## General routing rules

### Accept
Use when:
- required mechanical checks passed
- no blocking policy violations
- acceptance criteria appear covered
- warnings are visible but acceptable

### Retry
Use when:
- failure seems fixable by another implementation pass
- issue is local and clear
- risk level remains acceptable

### Wait human
Use when:
- decision requires business or risk judgment
- acceptance criteria are unclear
- sensitive paths or changes cross configured gates

### Escalate
Use when:
- task is unsafe or unsupported
- repeated failures suggest the run is fundamentally off track
- environment/profile is broken in a non-recoverable way

---

# 8. Retry policy

## Main recommendation
Keep retries small and capped.

### Execution retries
These are retries after code validation failure.
Recommended max: **3**

### Infrastructure retries
These are retries for environment/network/tool failures.
Recommended max: **2-3**, tracked separately.

## Important
Do not use the same budget for:
- bad code fixes
- temporary sandbox/network issues

---

# 9. Retryable vs non-retryable failures

## Retryable examples
- lint failure
- failing targeted test with clear assertion mismatch
- missing import / typing issue
- test added incorrectly
- small scope drift fixable by narrowing change

## Non-retryable or escalate examples
- task too ambiguous to validate
- forbidden path required for solution
- migration needed in v1
- unsupported repo/profile state
- repeated drift after max retries
- payment/auth-sensitive logic crossing policy threshold

---

# 10. Draft PR threshold

This is one of the most important product rules.

A result is eligible for draft PR when:

## Required
- required validators have completed
- required mechanical checks passed
- no forbidden changes exist
- policy issues are either clear warnings or approved
- spec alignment is good enough to justify human review
- `ValidationReport` is complete
- artifacts are preserved

## Allowed imperfections
- warning-level risk remains
- optional checks were skipped with explanation
- review notes include uncertainty

## Not allowed
- failing required tests
- unknown scope expansion
- unbounded diff with no explanation
- forbidden path edits
- unclear acceptance coverage

## Product framing
Draft PR threshold should be:
**high enough to protect reviewer time, low enough to allow useful iteration**

---

# 11. Acceptance criteria validation

This deserves special handling.

## Goal
Map each acceptance criterion to explicit evidence.

## Example mapping
Criterion:
- Empty coupon code returns 400

Evidence:
- targeted test `tests/api/test_coupons.py::test_empty_coupon_code`
- implementation touched validation layer
- no regression in related valid flow tests

## Rule
If Villager cannot explain how each acceptance criterion was addressed, the result is weak.

---

# 12. Scope validation

Passing tests is not enough.
Villager must also ask:
- did the diff stay in expected areas?
- did the agent touch unrelated files?
- did the change become broader than the spec?

## Suggested checks
- changed file paths vs `ExecutionSpec.target_areas`
- changed file count vs profile threshold
- diff lines vs profile threshold
- touched sensitive/forbidden paths

## Example
If a ticket is about API input validation but the diff also edits infra config and worker code, that is a red flag.

---

# 13. Policy validation

Policy checks turn repo profile rules into operational gates.

## Example policy outputs

### Warning
- diff touched 6 files when threshold is 5

### Wait human
- dependency file changed without explanation
- sensitive path touched in medium-risk repo

### Escalate
- forbidden path touched
- migration added in unsupported v1 flow

## Important
Policy checks should be boring and explicit.
No mystery scoring.

---

# 14. Confidence model

Confidence should be computed by the harness.
Never let the executor self-score in a way that decides routing.

## Suggested confidence inputs
- required checks pass rate
- retry count
- diff size
- changed file count
- sensitive path count
- acceptance criteria coverage
- unresolved warnings count
- ambiguity score from spec generation

## Example confidence classes
- `high`
- `medium`
- `low`

## Example use
- high -> auto draft PR
- medium -> draft PR with warning labels
- low -> wait human or escalate

## Grug rule
Keep confidence simple.
It is a routing helper, not fake science.

---

# 15. ValidationReport shape

Validation should roll up into one `ValidationReport`.

## Report should include
- summary status
- mechanical check results
- policy check results
- spec alignment results
- warnings
- failures
- confidence signals
- recommended next action

## Why
This gives the harness one standard object for decision-making and audit.

---

# 16. Example validation scenarios

## Scenario A: Accept
- lint pass
- typecheck pass
- tests pass
- no sensitive paths
- acceptance criteria covered
- one small warning

Result:
- `accept`
- create draft PR

---

## Scenario B: Retry
- tests fail due to wrong expected error body
- scope stayed narrow
- no risky paths touched

Result:
- `retry`
- provide focused retry instruction

---

## Scenario C: Wait human
- all tests pass
- shared module touched
- acceptance criteria are covered
- blast radius uncertain

Result:
- `wait_human`
- ask for approval or narrower scope

---

## Scenario D: Escalate
- required solution needs migration
- or forbidden path touched
- or task remains ambiguous after review

Result:
- `escalate`

---

# 17. Validator ordering

Run validators in a practical order.

## Suggested order for v1
1. path/forbidden checks
2. dependency/migration/generation checks
3. lint
4. typecheck
5. targeted tests
6. broader tests if needed
7. acceptance criteria coverage check
8. scope/diff review

## Why this order
- fail fast on obviously unsafe changes
- avoid expensive checks when the change is already disqualified
- only do richer review after basic correctness passes

---

# 18. What should block immediately

The harness should stop fast when:
- forbidden paths are edited
- repo profile is invalid
- required validator commands are missing
- migration is required in unsupported flow
- retry cap exceeded
- acceptance criteria cannot be validated at all

No need for more agent effort in these cases.

---

# 19. Human review packaging

Validation should make human review easier.

A draft PR should include:
- what was changed
- why it was changed
- which checks ran
- which criteria were covered
- what warnings remain
- where reviewer attention is needed

This is part of validation strategy, not only PR formatting.

---

# 20. Opinionated v1 recommendation

For v1, implement only a small validation set in real code:

## Must have
- path policy check
- dependency change check
- lint
- test
- typecheck if supported
- acceptance coverage check
- scope change check

## Can wait
- review agent
- secret scan
- advanced risk scoring
- codeowner integration
- build matrix

That is enough to protect quality without overbuilding.

---

# 21. Grug conclusion

Validation is not decoration.
It is the system that makes Villager worth using.

Villager should only open a draft PR when it can say:

- here is what changed
- here is why
- here is the evidence
- here are the warnings
- here is why this is worth your review time

That is the bar.

---

# 22. Next doc

Best next document:

**`sandbox-design.md`**

Why:
Now that scope, spec generation, repo profiles, and validation are defined, the next missing piece is the execution environment that actually runs the work safely.

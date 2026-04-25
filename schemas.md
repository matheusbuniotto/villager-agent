# Villager — Core Schemas

This document defines the first version of the core contracts for Villager.

Goal: make the system legible before implementation.

We start with:
- plain English definitions
- required fields
- optional fields
- YAML examples

Later, these can become typed models in Python/TypeScript.

---

# 1. Design principles for schemas

## 1. Structured first, prompt second
The agent should consume well-structured objects, not only long freeform prompts.

## 2. Separate concerns
Do not overload one schema with multiple responsibilities.
For example:
- `TaskPacket` = normalized intake
- `ExecutionSpec` = bounded work order
- `ValidationReport` = sensor output

## 3. Preserve auditability
Every important decision should be recoverable from stored objects.

## 4. Prefer explicitness over cleverness
If a field matters for routing, safety, or trust, make it explicit.

---

# 2. TaskPacket

## Purpose
`TaskPacket` is the normalized representation of incoming work from JIRA.

It exists to convert messy external inputs into a stable internal contract.

## Responsibilities
A `TaskPacket` should answer:
- what task is this?
- where did it come from?
- which repo does it target?
- what outcome is requested?
- what constraints or ambiguity already exist?

## Required fields
- `task_id`: internal unique id for this run/task
- `source`: source system, usually `jira`
- `source_issue_key`: issue identifier like `PROJ-123`
- `title`: short title of the issue
- `description`: normalized issue description
- `repo`: target repository name or identifier
- `labels`: list of issue labels/tags
- `requested_outcome`: concise statement of requested result
- `acceptance_criteria`: list of expected outcomes
- `priority`: priority level
- `risk_level`: initial risk guess from intake

## Optional fields
- `assignee`
- `reporter`
- `linked_services`
- `constraints`
- `ambiguity_flags`
- `comments_summary`
- `attachments`
- `team`
- `target_branch`
- `metadata`

## Example YAML
```yaml
task_packet:
  task_id: villager-run-2026-04-24-001
  source: jira
  source_issue_key: BILL-142
  title: Add validation for empty coupon code
  description: >
    Users can submit an empty coupon code and receive a confusing error.
    Update API validation so empty strings are rejected with a clear message.
  repo: billing-service
  labels:
    - villager
    - backend
    - api
  requested_outcome: Reject empty coupon codes with a clear validation error.
  acceptance_criteria:
    - Empty coupon code returns 400
    - Error message is clear and stable
    - Existing valid coupon flow remains unchanged
  priority: medium
  risk_level: low
  assignee: matheus
  reporter: payments-pm
  constraints:
    - Do not modify checkout flow beyond input validation
  ambiguity_flags:
    - No explicit error response schema in ticket
  target_branch: main
  metadata:
    jira_url: https://company.atlassian.net/browse/BILL-142
```

---

# 3. RepoProfile

## Purpose
`RepoProfile` defines repo- and team-specific behavior.

It is the personalization layer for Villager.

## Responsibilities
A `RepoProfile` should answer:
- how do we build/test/lint this repo?
- which paths are safe or sensitive?
- which team conventions matter?
- what extra review expectations exist?

## Required fields
- `repo_name`
- `team_name`
- `language`
- `build_system`
- `commands`
- `paths`
- `rules`
- `pr`

## Optional fields
- `dependencies`
- `service_type`
- `deployment_sensitivity`
- `reviewer_groups`
- `examples`
- `known_gotchas`
- `environment_notes`
- `agent_instructions`

## Nested structure suggestions

### `commands`
Should include as many of these as relevant:
- `install`
- `lint`
- `format`
- `typecheck`
- `test`
- `build`
- `smoke`

### `paths`
Should include:
- `owned`
- `sensitive`
- `forbidden`
- `test_locations`

### `rules`
Examples:
- require tests for behavior changes
- block dependency changes without explanation
- require human approval for migrations
- forbid edits under generated code folders

### `pr`
Should define:
- PR template style
- labels to add
- expected reviewers
- required summary sections

## Example YAML
```yaml
repo_profile:
  repo_name: billing-service
  team_name: payments
  language: python
  build_system: poetry
  service_type: backend-api
  deployment_sensitivity: medium

  commands:
    install: poetry install
    lint: poetry run ruff check .
    format: poetry run ruff format .
    typecheck: poetry run mypy src
    test: poetry run pytest -q
    build: poetry build
    smoke: poetry run pytest tests/smoke -q

  paths:
    owned:
      - src/
      - tests/
    sensitive:
      - migrations/
      - infra/
      - .github/workflows/
    forbidden:
      - secrets/
    test_locations:
      - tests/

  rules:
    require_tests_for_behavior_change: true
    block_dependency_changes_without_reason: true
    require_human_approval_for_migrations: true
    forbid_generated_code_edits: true

  pr:
    template: standard-backend
    labels:
      - team-payments
      - villager
    reviewers:
      - payments-backend
    required_sections:
      - summary
      - acceptance-criteria
      - validation
      - risks

  known_gotchas:
    - Coupon validation is reused across API and async worker paths
    - Some tests require env vars from .env.test

  examples:
    good_prs:
      - BILL-101
      - BILL-118
```

---

# 4. ExecutionSpec

## Purpose
`ExecutionSpec` is the bounded work order given to the executor.

It should be generated after intake and before code changes begin.

## Responsibilities
An `ExecutionSpec` should answer:
- what exact problem are we solving?
- what is in scope and out of scope?
- where should the agent look?
- how will success be validated?
- when should the agent stop and escalate?

## Required fields
- `spec_id`
- `task_id`
- `problem_statement`
- `scope_in`
- `scope_out`
- `target_areas`
- `acceptance_criteria`
- `validation_steps`
- `artifacts_required`
- `stop_conditions`
- `escalation_conditions`

## Optional fields
- `implementation_notes`
- `assumptions`
- `risk_notes`
- `suggested_plan`
- `max_files_to_change`
- `test_expectations`
- `review_focus`

## Important note
This is not just a restatement of the ticket.
It is a constrained execution contract.

## Example YAML
```yaml
execution_spec:
  spec_id: spec-2026-04-24-001
  task_id: villager-run-2026-04-24-001
  problem_statement: >
    Reject empty coupon codes at API validation time and return a clear 400 error
    without changing valid coupon behavior.

  scope_in:
    - API request validation for coupon code field
    - Tests covering empty-string input behavior
    - Error message update if needed for consistency

  scope_out:
    - Coupon business logic changes
    - Pricing or discount calculation changes
    - Async worker behavior unless directly impacted by shared validation
    - Database schema changes

  target_areas:
    - src/api/coupons.py
    - src/validation/
    - tests/api/

  acceptance_criteria:
    - Empty coupon code returns 400
    - Response includes clear error message
    - Existing valid coupon behavior remains unchanged

  validation_steps:
    - Run lint
    - Run typecheck
    - Run targeted tests for coupon API
    - Run full test suite if shared validation module changes

  artifacts_required:
    - diff_patch
    - changed_files
    - execution_summary
    - validation_report
    - draft_pr_body

  stop_conditions:
    - If solution requires schema migration, stop
    - If more than 5 files need modification, stop and escalate
    - If target behavior cannot be confirmed by tests, stop

  escalation_conditions:
    - Ticket acceptance criteria are too ambiguous to validate
    - Shared validation layer changes impact unrelated services
    - Sensitive paths are required for the fix

  assumptions:
    - Empty coupon code currently reaches business logic layer

  risk_notes:
    - Shared validator may affect multiple entry points

  suggested_plan:
    - Inspect coupon API validation flow
    - Add or tighten empty-string validation
    - Add regression tests
    - Run targeted validation commands
```

---

# 5. ValidationReport

## Purpose
`ValidationReport` captures the output of all sensors after execution.

It is the main evidence object used by the harness to route decisions.

## Responsibilities
A `ValidationReport` should answer:
- what checks were run?
- which passed, failed, or were skipped?
- what warnings or risks exist?
- is the current result acceptable, retryable, or escalatable?

## Required fields
- `report_id`
- `task_id`
- `status`
- `mechanical_checks`
- `policy_checks`
- `spec_alignment_checks`
- `summary`

## Optional fields
- `warnings`
- `failures`
- `skipped_checks`
- `review_notes`
- `confidence_signals`
- `recommended_decision`

## Status suggestions
Use one of:
- `pass`
- `pass_with_warnings`
- `fail_retryable`
- `fail_escalate`

## Example YAML
```yaml
validation_report:
  report_id: validation-2026-04-24-001
  task_id: villager-run-2026-04-24-001
  status: pass_with_warnings

  mechanical_checks:
    - name: lint
      status: pass
    - name: typecheck
      status: pass
    - name: targeted_tests
      status: pass
    - name: full_test_suite
      status: skipped
      reason: Shared validation module not changed

  policy_checks:
    - name: sensitive_paths_touched
      status: pass
    - name: dependency_changes
      status: pass
    - name: migrations_added
      status: pass

  spec_alignment_checks:
    - name: acceptance_criteria_coverage
      status: pass
      details:
        covered: 3
        total: 3
    - name: out_of_scope_change_check
      status: warning
      reason: Shared validation helper changed but impact appears low

  summary: >
    All required checks passed. One warning raised because a shared validation helper
    was modified, but no sensitive paths or dependency changes were detected.

  warnings:
    - Shared validation helper changed; reviewer should confirm no external behavior drift.

  confidence_signals:
    retry_count: 1
    changed_files: 3
    sensitive_paths_touched: 0
    acceptance_criteria_coverage: 1.0

  recommended_decision: accept
```

---

# 6. ReviewDecision

## Purpose
`ReviewDecision` is the harness output that decides what happens next after validation.

## Responsibilities
It should answer:
- what is the decision?
- why was it made?
- what should happen next?
- does a human need to intervene?

## Required fields
- `decision_id`
- `task_id`
- `decision`
- `reason`
- `next_action`

## Optional fields
- `retry_count`
- `human_input_required`
- `blocking_issues`
- `notes_for_retry`
- `notes_for_human`

## Decision values
Use one of:
- `accept`
- `retry`
- `escalate`
- `wait_human`

## Example YAML
```yaml
review_decision:
  decision_id: decision-2026-04-24-001
  task_id: villager-run-2026-04-24-001
  decision: accept
  reason: >
    Required validation checks passed and acceptance criteria were covered.
    One warning remains, but it does not cross escalation threshold.
  next_action: Generate draft PR
  retry_count: 1
  human_input_required: false
```

## Retry example YAML
```yaml
review_decision:
  decision_id: decision-2026-04-24-002
  task_id: villager-run-2026-04-24-002
  decision: retry
  reason: Targeted tests failed due to incorrect error response assertion.
  next_action: Re-run executor with focused feedback on failing test expectation
  retry_count: 2
  human_input_required: false
  blocking_issues:
    - tests/api/test_coupons.py::test_empty_coupon_code
  notes_for_retry:
    - Keep scope limited to API validation behavior
    - Do not modify discount logic
    - Fix response shape or align test with existing validated contract
```

---

# 7. ArtifactBundle

## Purpose
`ArtifactBundle` is the exported package from a run.

It contains the evidence and deliverables needed for human review and system audit.

## Responsibilities
It should answer:
- what changed?
- how was it validated?
- what commands were run?
- what PR summary should be generated?

## Required fields
- `artifact_id`
- `task_id`
- `changed_files`
- `diff_patch`
- `execution_summary`
- `validation_report_ref`
- `pr_body`
- `metadata`

## Optional fields
- `command_log`
- `test_results`
- `screenshots`
- `review_annotations`
- `timings`
- `sandbox_info`

## Example YAML
```yaml
artifact_bundle:
  artifact_id: artifact-2026-04-24-001
  task_id: villager-run-2026-04-24-001
  changed_files:
    - src/api/coupons.py
    - src/validation/coupon_rules.py
    - tests/api/test_coupons.py
  diff_patch: artifacts/BILL-142.patch
  execution_summary: >
    Added empty-string validation for coupon code requests and updated tests to
    verify a clear 400 response without changing valid coupon flow.
  validation_report_ref: validation-2026-04-24-001
  pr_body: artifacts/BILL-142-pr.md
  metadata:
    branch_name: villager/BILL-142-empty-coupon-validation
    repo: billing-service
    base_branch: main
    loop_count: 1
    profile_version: repo-profile-v3
    spec_id: spec-2026-04-24-001
```

---

# 8. Relationship between schemas

These schemas should connect cleanly.

```text
TaskPacket
   -> ExecutionSpec
   -> Executor Run
   -> ValidationReport
   -> ReviewDecision
   -> ArtifactBundle
```

And `RepoProfile` influences multiple stages:

```text
RepoProfile
   -> Spec Builder
   -> Sandbox bootstrap
   -> Validation commands
   -> PR formatting
```

---

# 9. Suggested future additions

Not needed on day 1, but likely useful later:

## Candidate future schema: `RunRecord`
Top-level object for full orchestration state.
Could include:
- current state
- timestamps
- attempt history
- linked schema refs
- final outcome

## Candidate future schema: `HumanGateRequest`
Represents a structured approval request when escalation is needed.
Could include:
- reason for gate
- impacted files
- risk summary
- options for human decision

## Candidate future schema: `RetryInstruction`
Structured feedback for the executor after a failed validation cycle.
Could include:
- failed checks
- concise diagnosis
- do-not-repeat instructions
- narrowed target areas

---

# 10. Opinionated guidance

If you only implement a few things first, make them these:
1. `TaskPacket`
2. `RepoProfile`
3. `ExecutionSpec`
4. `ValidationReport`

Why:
These define the backbone of intake, personalization, execution, and trust.

`ReviewDecision` and `ArtifactBundle` are still important, but they come naturally once the first four are stable.

---

# 11. Next step

The best next move after this document is to create either:
- `run-lifecycle.md` — showing how these schemas move through the state machine
- `repo-profile-template.yaml` — a concrete starter template for real repos

## Recommendation
Do **`run-lifecycle.md`** next.
That will connect the schemas to the harness behavior.
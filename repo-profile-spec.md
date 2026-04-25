# Villager — Repo Profile Specification

## One-sentence definition

A Repo Profile is the structured configuration that tells Villager how a specific repo and team expect code to be changed, validated, reviewed, and constrained.

---

# 1. Why this matters

This is one of Villager’s core differentiators.

Without a real repo profile, Villager is just a generic coding agent with extra prompt text.
With a good repo profile, Villager becomes:
- safer
- more repo-aware
- more team-aware
- easier to validate
- easier to trust

## Product principle
Personalization should live in **structured config first**, not only prompt prose.

---

# 2. Purpose of a Repo Profile

A Repo Profile should answer these practical questions:

1. How do I install, lint, typecheck, test, and build this repo?
2. Which paths are normal to touch?
3. Which paths are sensitive or forbidden?
4. What review/process rules does this team care about?
5. What changes require stronger checks or human approval?
6. How should the draft PR be formatted?

If the profile cannot answer these questions, it is not good enough.

---

# 3. Design principles

## 1. Structured first
The profile should be machine-readable and stable.

## 2. Minimal v1 surface area
Do not try to encode the whole culture of a team on day 1.
Start with the fields that change execution and validation behavior.

## 3. Explicit safety rules
If a rule affects autonomy, make it explicit.
Examples:
- migrations require approval
- auth paths are sensitive
- dependency changes require explanation

## 4. Defaults where safe, not where risky
Commands can have defaults.
Sensitive path policy should not be guessed.

## 5. Versionable and reviewable
Repo profiles should live in version control so teams can inspect and evolve them.

---

# 4. Recommended profile layers

Use a simple override model.

```text
Org Default
   -> Team Default
      -> Repo Profile
```

## Why this is useful
- avoids repeating common conventions
- keeps repo-specific config smaller
- allows consistent policy at team/org level

## V1 recommendation
Support the concept, but implement lightly.

For v1, it is enough if you support:
- one base/default profile
- one repo-specific override

Do not build a fancy inheritance engine yet.

---

# 5. Minimum viable Repo Profile for v1

These are the minimum fields I recommend supporting in code.

## Required fields
- `repo_name`
- `team_name`
- `language`
- `build_system`
- `commands`
- `paths`
- `rules`
- `pr`

If any of these are missing, the profile is incomplete.

---

# 6. Required sections in detail

## 6.1 Basic identity

### Required
- `repo_name`
- `team_name`
- `language`
- `build_system`

### Why
This anchors the profile and helps select the right sandbox image and command behavior.

### Example
```yaml
repo_name: billing-service
team_name: payments
language: python
build_system: poetry
```

---

## 6.2 Commands

### Purpose
Tell Villager how to operate the repo.

### Required command keys for v1
- `install`
- `lint`
- `test`

### Strongly recommended
- `typecheck`
- `build`
- `format`
- `smoke`

### Rules
- commands should be runnable as-is in the sandbox
- commands should avoid hidden shell assumptions where possible
- commands should be explicit, not implied by language only

### Example
```yaml
commands:
  install: poetry install
  lint: poetry run ruff check .
  format: poetry run ruff format .
  typecheck: poetry run mypy src
  test: poetry run pytest -q
  build: poetry build
  smoke: poetry run pytest tests/smoke -q
```

## Grug rule
If a repo cannot say how to test itself, Villager should not pretend it knows.

---

## 6.3 Paths

### Purpose
Constrain where Villager can safely operate.

### Required path keys
- `owned`
- `sensitive`
- `forbidden`

### Strongly recommended
- `test_locations`
- `generated`
- `docs`

### Meaning
- `owned`: normal paths Villager can inspect/change
- `sensitive`: paths that may trigger warnings or human gates
- `forbidden`: paths Villager should never modify in v1
- `test_locations`: where tests usually live
- `generated`: areas that should not be hand-edited

### Example
```yaml
paths:
  owned:
    - src/
    - tests/
  sensitive:
    - migrations/
    - infra/
    - .github/workflows/
    - src/auth/
  forbidden:
    - secrets/
    - generated/
  test_locations:
    - tests/
```

## Important
This section has direct safety impact.
Do not make it optional in spirit, even if the exact fields evolve.

---

## 6.4 Rules

### Purpose
Define policy that shapes autonomy.

### Recommended v1 rules
- `require_tests_for_behavior_change`
- `block_dependency_changes_without_reason`
- `require_human_approval_for_migrations`
- `forbid_generated_code_edits`
- `max_changed_files_before_warning`
- `max_diff_lines_before_warning`

### Example
```yaml
rules:
  require_tests_for_behavior_change: true
  block_dependency_changes_without_reason: true
  require_human_approval_for_migrations: true
  forbid_generated_code_edits: true
  max_changed_files_before_warning: 5
  max_diff_lines_before_warning: 300
```

### Why this matters
These rules turn “team preference” into routing behavior.

---

## 6.5 PR settings

### Purpose
Control how the output is packaged for reviewers.

### Required keys
- `template`
- `labels`
- `reviewers`

### Strongly recommended
- `required_sections`
- `draft_by_default`
- `branch_prefix`

### Example
```yaml
pr:
  template: standard-backend
  labels:
    - villager
    - team-payments
  reviewers:
    - payments-backend
  required_sections:
    - summary
    - acceptance-criteria
    - validation
    - risks
  draft_by_default: true
  branch_prefix: villager/
```

---

# 7. Optional but valuable sections

These are not required for first implementation, but are useful.

## 7.1 Known gotchas
Examples:
- hidden env requirements
- flaky tests
- unusual repo setup
- shared modules with surprising blast radius

```yaml
known_gotchas:
  - Some tests require .env.test
  - Validation helpers are shared across API and workers
```

## 7.2 Examples
Useful for future retrieval or review assistance.

```yaml
examples:
  good_prs:
    - BILL-101
    - BILL-118
```

## 7.3 Agent instructions
Short repo-specific advice.

```yaml
agent_instructions:
  - Prefer adding narrow tests near the changed module
  - Avoid touching async worker code unless required by shared validation
```

## Warning
Keep this section short.
If it grows too much, you are replacing design with prompt soup.

---

# 8. What should be hard-coded vs profile-driven

## Good things to keep in the profile
- commands
- path ownership/sensitivity
- review labels/reviewers
- warning thresholds
- approval requirements
- branch naming conventions

## Good things to keep in code
- lifecycle/state machine
- retry logic
- schema validation
- artifact persistence
- general risk routing framework

## Rule of thumb
If it varies by repo/team, prefer profile.
If it is core system behavior, prefer code.

---

# 9. Minimum viability rule

A repo is only onboarded to Villager v1 if it has:

- working install/lint/test commands
- defined owned/sensitive/forbidden paths
- at least one reviewer group or default reviewer
- basic warning/approval rules

If not, the repo is not ready.

This is good.
Not every repo should be supported on day 1.

---

# 10. Strict vs light profile modes

You may want two profile styles.

## Light profile
Use when the repo is low risk and simple.

Characteristics:
- fewer sensitive paths
- lower review friction
- smaller policy surface

## Strict profile
Use when the repo has sensitive logic.

Characteristics:
- more sensitive paths
- lower warning thresholds
- more mandatory gates
- tighter PR packaging requirements

## V1 recommendation
Do not build “modes” as a product feature yet.
Just let the actual field values make a profile strict or light.

---

# 11. Example minimal v1 profile

```yaml
repo_name: billing-service
team_name: payments
language: python
build_system: poetry

commands:
  install: poetry install
  lint: poetry run ruff check .
  test: poetry run pytest -q
  typecheck: poetry run mypy src

paths:
  owned:
    - src/
    - tests/
  sensitive:
    - migrations/
    - infra/
  forbidden:
    - secrets/

rules:
  require_tests_for_behavior_change: true
  block_dependency_changes_without_reason: true
  require_human_approval_for_migrations: true
  forbid_generated_code_edits: true
  max_changed_files_before_warning: 5
  max_diff_lines_before_warning: 300

pr:
  template: standard
  labels:
    - villager
  reviewers:
    - payments-backend
  required_sections:
    - summary
    - validation
    - risks
  draft_by_default: true
  branch_prefix: villager/
```

This is enough to make personalization real.

---

# 12. Validation rules for Repo Profiles

Villager should validate the repo profile itself before using it.

## Basic profile validation checks
- required top-level fields exist
- required command keys exist
- path lists are valid arrays
- warning thresholds are numeric
- PR config includes at least one reviewer or fallback

## Why
Bad profile data can produce unsafe or confusing behavior.
Treat the profile as a contract, not loose config.

---

# 13. Recommended file layout

For now, keep it boring.

## Option A: one profile per repo
```text
profiles/
  billing-service.yaml
  checkout-ui.yaml
```

## Option B: base + overrides
```text
profiles/
  defaults/base.yaml
  teams/payments.yaml
  repos/billing-service.yaml
```

## Recommendation
Start with **Option A** for v1.

Why:
- easier to debug
- easier to reason about
- less config merging complexity

Inheritance can come later.

---

# 14. Suggested onboarding flow for a new repo

1. Create repo profile file
2. Validate profile schema
3. Test commands manually in sandbox image
4. Confirm path ownership and sensitive paths
5. Run one dry-run task in non-destructive mode
6. Adjust thresholds/rules
7. Mark repo as supported

## Grug rule
Do not mark a repo “supported” just because the YAML exists.
Prove the commands and constraints actually work.

---

# 15. Relationship to other docs

Repo Profile influences:

```text
RepoProfile
  -> ExecutionSpec generation
  -> Sandbox image/bootstrapping
  -> Validation command selection
  -> Risk routing
  -> PR formatting
```

This means Repo Profile is not metadata.
It is active control input.

---

# 16. Opinionated v1 recommendation

For v1, support only these profile features in actual code:

1. identity (`repo_name`, `team_name`, `language`, `build_system`)
2. commands (`install`, `lint`, `test`, optional `typecheck`)
3. paths (`owned`, `sensitive`, `forbidden`)
4. rules (`require_tests_for_behavior_change`, dependency/migration guardrails, warning thresholds)
5. PR formatting (`labels`, `reviewers`, `branch_prefix`, `draft_by_default`)

Everything else can exist in docs but stay optional until needed.

That keeps the system small and useful.

---

# 17. Recommended next artifact

Best next move is one of these:

1. create real example profiles
2. define validation strategy

## My recommendation
Do **`validation-strategy.md`** next.

Why:
- product scope is defined
- spec generation is defined
- personalization is defined
- now you need to define what proof is enough to trust a draft PR

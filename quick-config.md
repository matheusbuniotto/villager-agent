# Quick Config

This is the fastest way to get the current `VIL-002` repo profile loader running locally.

## 1. Install dependencies

```bash
uv sync --extra dev
```

## 2. Create or edit a repo profile

Profiles live in `profiles/*.yaml`.
The file name must match the repo name you want to load.

Example: `profiles/example.yaml`

```yaml
repo_name: example
team_name: platform
language: python
build_system: uv
service_type: automation
commands:
  install: uv sync --extra dev
  lint: uv run ruff check .
  format: uv run ruff format .
  typecheck: uv run mypy app
  test: uv run pytest -q
paths:
  owned:
    - app/
    - tests/
    - profiles/
  sensitive:
    - .github/
  forbidden:
    - runs/
  test_locations:
    - tests/
rules:
  require_tests_for_behavior_change: true
  block_dependency_changes_without_reason: true
  require_human_approval_for_migrations: true
  forbid_generated_code_edits: true
pr:
  template: standard
  labels:
    - villager
  reviewers:
    - platform-team
  required_sections:
    - summary
    - validation
    - risks
  draft_by_default: true
  branch_prefix: villager/
```

Required top-level fields:
- `repo_name`
- `team_name`
- `language`
- `build_system`
- `commands.install`
- `commands.lint`
- `commands.test`
- `paths.owned`
- `paths.sensitive`
- `paths.forbidden`
- `rules`
- `pr.template`

## 3. Load a profile directly

```bash
./.venv/bin/python - <<'PY'
from app.spec_builder import load_repo_profile

profile = load_repo_profile("example")
print(profile)
print(profile.commands.test)
PY
```

## 4. Run the focused tests

```bash
./.venv/bin/python -m pytest tests/test_repo_profile_loader.py tests/test_schemas.py tests/test_main.py
```

## 5. Run lint

```bash
./.venv/bin/ruff check .
```

## Notes

- `load_repo_profile("example")` reads `profiles/example.yaml`.
- The loader also accepts files that wrap the data under a top-level `repo_profile:` key.
- Invalid profiles raise `RepoProfileLoadError` with a message that points to the bad field.
- If `uv run ...` fails because `UV_ENV_FILE=.env` is set in your shell and the file does not exist, use the `./.venv/bin/...` commands above or temporarily run `unset UV_ENV_FILE` first.

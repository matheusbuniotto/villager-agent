from pathlib import Path

import pytest

from app.spec_builder import RepoProfileLoadError, load_repo_profile, load_repo_profile_file


def test_load_repo_profile_by_repo_name() -> None:
    profile = load_repo_profile("example")

    assert profile.repo_name == "example"
    assert profile.commands.test == "uv run pytest -q"
    assert profile.paths.owned == ["app/", "tests/", "profiles/"]


def test_load_repo_profile_file_supports_nested_repo_profile_key(tmp_path: Path) -> None:
    profile_file = tmp_path / "billing-service.yaml"
    profile_file.write_text(
        """
repo_profile:
  repo_name: billing-service
  team_name: payments
  language: python
  build_system: uv
  commands:
    install: uv sync --extra dev
    lint: uv run ruff check .
    test: uv run pytest -q
  paths:
    owned:
      - app/
    sensitive:
      - infra/
    forbidden:
      - secrets/
  rules:
    require_tests_for_behavior_change: true
    block_dependency_changes_without_reason: true
    require_human_approval_for_migrations: true
    forbid_generated_code_edits: true
  pr:
    template: standard
""".strip(),
        encoding="utf-8",
    )

    profile = load_repo_profile_file(profile_file)

    assert profile.repo_name == "billing-service"
    assert profile.paths.sensitive == ["infra/"]


def test_invalid_repo_profile_raises_clear_error(tmp_path: Path) -> None:
    profile_file = tmp_path / "broken.yaml"
    profile_file.write_text(
        """
repo_name: broken
language: python
build_system: uv
commands:
  install: uv sync --extra dev
  lint: uv run ruff check .
  test: uv run pytest -q
paths:
  owned: app/
  sensitive: []
  forbidden: []
rules:
  require_tests_for_behavior_change: true
  block_dependency_changes_without_reason: true
  require_human_approval_for_migrations: true
  forbid_generated_code_edits: true
pr:
  template: standard
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(RepoProfileLoadError, match="missing required field 'team_name'"):
        load_repo_profile_file(profile_file)

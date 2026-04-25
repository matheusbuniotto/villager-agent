from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from app.schemas import RepoProfile

DEFAULT_PROFILES_DIR = Path(__file__).resolve().parents[2] / "profiles"


class RepoProfileLoadError(ValueError):
    """Raised when a repo profile cannot be loaded safely."""


def load_repo_profile(repo_name: str, profiles_dir: str | Path | None = None) -> RepoProfile:
    """Load a repo profile by repo name from the profiles directory."""
    base_dir = Path(profiles_dir) if profiles_dir is not None else DEFAULT_PROFILES_DIR
    profile_path = base_dir / f"{repo_name}.yaml"

    if not profile_path.is_file():
        raise RepoProfileLoadError(f"Repo profile '{repo_name}' was not found at {profile_path}")

    profile = load_repo_profile_file(profile_path)
    if profile.repo_name != repo_name:
        raise RepoProfileLoadError(
            f"Repo profile '{profile_path}' declares repo_name '{profile.repo_name}', "
            f"expected '{repo_name}'"
        )

    return profile


def load_repo_profile_file(path: str | Path) -> RepoProfile:
    """Load and validate a repo profile YAML file."""
    profile_path = Path(path)

    try:
        raw_data = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RepoProfileLoadError(f"Repo profile file was not found: {profile_path}") from exc
    except OSError as exc:
        raise RepoProfileLoadError(f"Unable to read repo profile '{profile_path}': {exc}") from exc
    except yaml.YAMLError as exc:
        raise RepoProfileLoadError(f"Invalid YAML in repo profile '{profile_path}': {exc}") from exc

    profile_data = _normalize_profile_data(profile_path, raw_data)
    _validate_profile_shape(profile_path, profile_data)

    try:
        return RepoProfile.from_dict(profile_data)
    except (KeyError, TypeError, ValueError) as exc:
        raise RepoProfileLoadError(f"Invalid repo profile '{profile_path}': {exc}") from exc


def _normalize_profile_data(path: Path, raw_data: Any) -> dict[str, Any]:
    if not isinstance(raw_data, Mapping):
        raise RepoProfileLoadError(f"Repo profile '{path}' must contain a top-level mapping")

    if "repo_profile" in raw_data:
        nested = raw_data["repo_profile"]
        if not isinstance(nested, Mapping):
            raise RepoProfileLoadError(
                f"Repo profile '{path}' has a non-mapping 'repo_profile' section"
            )
        return dict(nested)

    return dict(raw_data)


def _validate_profile_shape(path: Path, data: dict[str, Any]) -> None:
    _require_string(path, data, "repo_name")
    _require_string(path, data, "team_name")
    _require_string(path, data, "language")
    _require_string(path, data, "build_system")

    commands = _require_mapping(path, data, "commands")
    for key in ("install", "lint", "test"):
        _require_string(path, commands, key, section="commands")

    paths = _require_mapping(path, data, "paths")
    for key in ("owned", "sensitive", "forbidden"):
        _require_string_list(path, paths, key, section="paths")

    if "test_locations" in paths:
        _require_string_list(path, paths, "test_locations", section="paths")

    rules = _require_mapping(path, data, "rules")
    for key in (
        "require_tests_for_behavior_change",
        "block_dependency_changes_without_reason",
        "require_human_approval_for_migrations",
        "forbid_generated_code_edits",
    ):
        if key in rules and not isinstance(rules[key], bool):
            raise RepoProfileLoadError(
                f"Repo profile '{path}' field 'rules.{key}' must be a boolean"
            )

    pr = _require_mapping(path, data, "pr")
    _require_string(path, pr, "template", section="pr")

    for key in ("labels", "reviewers", "required_sections"):
        if key in pr:
            _require_string_list(path, pr, key, section="pr")


def _require_mapping(
    path: Path,
    data: Mapping[str, Any],
    field_name: str,
) -> Mapping[str, Any]:
    if field_name not in data:
        raise RepoProfileLoadError(
            f"Repo profile '{path}' is missing required field '{field_name}'"
        )

    value = data[field_name]
    if not isinstance(value, Mapping):
        raise RepoProfileLoadError(f"Repo profile '{path}' field '{field_name}' must be a mapping")

    return value


def _require_string(
    path: Path,
    data: Mapping[str, Any],
    field_name: str,
    *,
    section: str | None = None,
) -> None:
    if field_name not in data:
        label = field_name if section is None else f"{section}.{field_name}"
        raise RepoProfileLoadError(f"Repo profile '{path}' is missing required field '{label}'")

    value = data[field_name]
    if not isinstance(value, str) or not value.strip():
        label = field_name if section is None else f"{section}.{field_name}"
        raise RepoProfileLoadError(
            f"Repo profile '{path}' field '{label}' must be a non-empty string"
        )


def _require_string_list(
    path: Path,
    data: Mapping[str, Any],
    field_name: str,
    *,
    section: str,
) -> None:
    value = data[field_name]
    label = f"{section}.{field_name}"

    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise RepoProfileLoadError(
            f"Repo profile '{path}' field '{label}' must be a list of strings"
        )

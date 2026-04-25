from __future__ import annotations

import pytest

from app.schemas import ExecutionSpec, RepoCommands, RepoPaths, RepoProfile, RepoRules, TaskPacket
from app.spec_builder import SpecBuildError, build_spec
from app.spec_builder.builder import assess_ambiguity, classify_task_type


def _make_task(
    title: str,
    description: str = "Some description.",
    priority: str = "medium",
    **kwargs: object,
) -> TaskPacket:
    return TaskPacket(
        task_id="task-001",
        source="jira",
        source_issue_key="VIL-001",
        title=title,
        description=description,
        repo="example",
        requested_outcome="Do the thing.",
        priority=priority,  # type: ignore[arg-type]
        risk_level="low",
        **kwargs,  # type: ignore[arg-type]
    )


def _make_profile(**kwargs: object) -> RepoProfile:
    defaults = {
        "repo_name": "example",
        "team_name": "platform",
        "language": "python",
        "build_system": "uv",
        "commands": RepoCommands(install="uv sync", lint="ruff check .", test="pytest"),
        "paths": RepoPaths(owned=["app/", "tests/"], sensitive=[".github/"], forbidden=["runs/"]),
        "rules": RepoRules(),
        "pr": {"template": "standard"},
    }
    defaults.update(kwargs)  # type: ignore[arg-type]
    return RepoProfile(**defaults)


class TestClassifyTaskType:
    def test_bug_fix_keywords(self) -> None:
        assert classify_task_type(_make_task("Fix null pointer in billing")) == "bug_fix"
        assert classify_task_type(_make_task("Handle error on empty input")) == "bug_fix"

    def test_feature_keywords(self) -> None:
        assert classify_task_type(_make_task("Add coupon validation")) == "feature"
        assert classify_task_type(_make_task("Implement new endpoint")) == "feature"

    def test_refactor_keywords(self) -> None:
        assert classify_task_type(_make_task("Refactor payment module")) == "refactor"
        assert classify_task_type(_make_task("Clean up legacy code")) == "refactor"

    def test_migration_keywords(self) -> None:
        assert classify_task_type(_make_task("Database migration for users")) == "migration"
        assert classify_task_type(_make_task("Migrate schema v2")) == "migration"

    def test_dependency_keywords(self) -> None:
        assert classify_task_type(_make_task("Bump pydantic to v2")) == "dependency_change"
        assert classify_task_type(_make_task("Update package lockfile")) == "dependency_change"

    def test_unknown_when_no_match(self) -> None:
        assert classify_task_type(_make_task("General maintenance")) == "unknown"


class TestAssessAmbiguity:
    def test_clear_task_is_not_ambiguous(self) -> None:
        task = _make_task(
            "Add validation for empty coupon code",
            description="Reject empty strings with a clear error message.",
            acceptance_criteria=["Empty code returns 400"],
        )
        is_ambiguous, flags = assess_ambiguity(task)
        assert not is_ambiguous
        assert not flags

    def test_missing_acceptance_criteria_is_not_a_blocker(self) -> None:
        task = _make_task(
            "Add login timeout feature",
            description="Sessions should expire after 30 minutes of inactivity.",
            acceptance_criteria=[],
        )
        is_ambiguous, flags = assess_ambiguity(task)
        assert not is_ambiguous
        assert "no_acceptance_criteria" not in flags

    def test_short_description(self) -> None:
        task = _make_task("Fix bug", description="Fix it.", acceptance_criteria=["Works"])
        is_ambiguous, flags = assess_ambiguity(task)
        assert is_ambiguous
        assert "description_too_short" in flags

    def test_generic_title(self) -> None:
        task = _make_task("Update", acceptance_criteria=["Works"])
        is_ambiguous, flags = assess_ambiguity(task)
        assert is_ambiguous
        assert "generic_title" in flags


class TestBuildSpecHappyPath:
    def test_builds_spec_for_bug_fix(self) -> None:
        task = _make_task(
            "Fix null pointer on empty coupon",
            description="When coupon is empty, the service crashes.",
            acceptance_criteria=["Empty coupon does not crash"],
        )
        profile = _make_profile()

        spec = build_spec(task, profile)

        assert isinstance(spec, ExecutionSpec)
        assert "bug_fix" in spec.problem_statement
        assert "Reproduce issue" in spec.suggested_plan
        assert profile.paths.owned[0] in spec.target_areas

    def test_builds_spec_for_feature(self) -> None:
        task = _make_task(
            "Add discount code validation",
            description="Validate discount codes before applying them to the cart.",
            acceptance_criteria=["Valid code applies discount", "Invalid code rejected"],
        )
        profile = _make_profile()

        spec = build_spec(task, profile)

        assert "feature" in spec.problem_statement
        assert "Understand current flow" in spec.suggested_plan

    def test_infers_target_area_from_description(self) -> None:
        task = _make_task(
            "Fix routing issue in app/api.py",
            description="The app/ module has a routing issue.",
            acceptance_criteria=["Routing works"],
        )
        profile = _make_profile()

        spec = build_spec(task, profile)

        assert "app/" in spec.target_areas

    def test_escalation_conditions_for_high_priority(self) -> None:
        task = _make_task(
            "Critical fix",
            description="Something is very broken in the payment processing pipeline.",
            priority="critical",
            acceptance_criteria=["Fixed"],
        )
        profile = _make_profile()

        spec = build_spec(task, profile)

        assert any("high priority" in c for c in spec.escalation_conditions)


class TestBuildSpecFailClosed:
    def test_migration_blocked_when_rule_enabled(self) -> None:
        task = _make_task(
            "Database migration for users table",
            description="Add new columns to users.",
            acceptance_criteria=["Migration runs"],
        )
        profile = _make_profile(
            rules=RepoRules(require_human_approval_for_migrations=True),
        )

        with pytest.raises(SpecBuildError, match="migration"):
            build_spec(task, profile)

    def test_dependency_change_blocked_when_rule_enabled(self) -> None:
        task = _make_task(
            "Bump pydantic to v2",
            description="Upgrade pydantic dependency.",
            acceptance_criteria=["Tests pass"],
        )
        profile = _make_profile(
            rules=RepoRules(block_dependency_changes_without_reason=True),
        )

        with pytest.raises(SpecBuildError, match="dependency change"):
            build_spec(task, profile)

    def test_ambiguous_task_blocked(self) -> None:
        task = _make_task("Fix bug", description="Fix it.")
        profile = _make_profile()

        with pytest.raises(SpecBuildError, match="ambiguous"):
            build_spec(task, profile)

    def test_migration_allowed_when_rule_disabled(self) -> None:
        task = _make_task(
            "Database migration for users table",
            description="Add new columns to the users table for profile data.",
            acceptance_criteria=["Migration runs"],
        )
        profile = _make_profile(
            rules=RepoRules(require_human_approval_for_migrations=False),
        )

        spec = build_spec(task, profile)
        assert "migration" in spec.problem_statement

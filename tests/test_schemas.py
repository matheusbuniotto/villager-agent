from datetime import datetime
from typing import cast

import pytest

from app.schemas import (
    ArtifactBundle,
    ExecutionSpec,
    Priority,
    RepoProfile,
    ReviewDecision,
    RunRecord,
    RunStateTransition,
    TaskPacket,
    ValidationCheck,
    ValidationReport,
)


def test_task_packet_instantiates() -> None:
    packet = TaskPacket(
        task_id="villager-run-001",
        source="jira",
        source_issue_key="BILL-142",
        title="Add validation for empty coupon code",
        description="Reject empty strings with a clear error.",
        repo="billing-service",
        labels=["villager", "backend"],
        requested_outcome="Reject empty coupon codes with a clear validation error.",
        acceptance_criteria=[
            "Empty coupon code returns 400",
            "Existing valid flow remains unchanged",
        ],
        priority="medium",
        risk_level="low",
    )

    assert packet.source == "jira"
    assert packet.priority == "medium"


def test_repo_profile_instantiates() -> None:
    profile = RepoProfile.from_dict(
        {
            "repo_name": "billing-service",
            "team_name": "payments",
            "language": "python",
            "build_system": "uv",
            "commands": {
                "install": "uv sync --extra dev",
                "lint": "uv run ruff check .",
                "test": "uv run pytest -q",
                "typecheck": "uv run mypy app",
            },
            "paths": {
                "owned": ["app/", "tests/"],
                "sensitive": ["infra/"],
                "forbidden": ["secrets/"],
                "test_locations": ["tests/"],
            },
            "rules": {
                "require_tests_for_behavior_change": True,
                "block_dependency_changes_without_reason": True,
                "require_human_approval_for_migrations": True,
                "forbid_generated_code_edits": True,
                "max_changed_files_before_warning": 5,
                "max_diff_lines_before_warning": 300,
            },
            "pr": {
                "template": "standard",
                "labels": ["villager"],
                "reviewers": ["payments-backend"],
                "required_sections": ["summary", "validation", "risks"],
                "draft_by_default": True,
                "branch_prefix": "villager/",
            },
        }
    )

    assert profile.commands.test == "uv run pytest -q"
    assert profile.paths.owned == ["app/", "tests/"]


def test_execution_and_validation_models_instantiates() -> None:
    spec = ExecutionSpec(
        spec_id="spec-001",
        task_id="villager-run-001",
        problem_statement="Reject empty coupon codes.",
        scope_in=["API validation"],
        scope_out=["Discount logic"],
        target_areas=["app/api.py"],
        acceptance_criteria=["400 on empty coupon code"],
        validation_steps=["Run tests"],
        artifacts_required=["validation_report", "draft_pr_body"],
        stop_conditions=["Needs migration"],
        escalation_conditions=["Sensitive paths required"],
    )
    report = ValidationReport(
        report_id="validation-001",
        task_id="villager-run-001",
        status="pass",
        mechanical_checks=[ValidationCheck(name="lint", status="pass")],
        policy_checks=[ValidationCheck(name="sensitive_paths_touched", status="pass")],
        spec_alignment_checks=[ValidationCheck(name="coverage", status="pass")],
        summary="All required checks passed.",
        recommended_decision="accept",
    )

    assert spec.spec_id == "spec-001"
    assert report.recommended_decision == "accept"


def test_review_artifact_and_run_record_instantiates() -> None:
    decision = ReviewDecision(
        decision_id="decision-001",
        task_id="villager-run-001",
        decision="accept",
        reason="Checks passed.",
        next_action="Generate draft PR",
    )
    artifact = ArtifactBundle(
        artifact_id="artifact-001",
        task_id="villager-run-001",
        changed_files=["app/api.py"],
        diff_patch="runs/run-001/patch.diff",
        execution_summary="Added validation for empty coupon code.",
        validation_report_ref="validation-001",
        pr_body="runs/run-001/pr.md",
    )
    run = RunRecord(
        run_id="run-001",
        task_id="villager-run-001",
        repo_name="billing-service",
        state="DONE",
        created_at=datetime(2026, 4, 24, 10, 0, 0),
        updated_at=datetime(2026, 4, 24, 10, 5, 0),
        retry_count=1,
        spec_ref="spec-001",
        validation_report_ref="validation-001",
        review_decision_ref="decision-001",
        artifact_bundle_ref="artifact-001",
        summary_ref="runs/run-001/summary.md",
        pr_ref="runs/run-001/pr.md",
        final_outcome="accepted",
    )
    transition = RunStateTransition(
        run_id="run-001",
        from_state="PR_DRAFTED",
        to_state="DONE",
        occurred_at=datetime(2026, 4, 24, 10, 5, 0),
        reason="finalized artifacts",
    )

    assert decision.next_action == "Generate draft PR"
    assert artifact.changed_files == ["app/api.py"]
    assert run.state == "DONE"
    assert transition.to_state == "DONE"


def test_invalid_priority_raises_clear_error() -> None:
    with pytest.raises(ValueError, match="priority must be one of"):
        TaskPacket(
            task_id="villager-run-001",
            source="jira",
            source_issue_key="BILL-142",
            title="Bad priority example",
            description="Example",
            repo="billing-service",
            requested_outcome="Do something",
            priority=cast(Priority, "urgent"),
            risk_level="low",
        )

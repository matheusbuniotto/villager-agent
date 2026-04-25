from __future__ import annotations

import pytest

from app.pr_composer import compose_pr
from app.schemas import ExecutionSpec, TaskPacket, ValidationCheck, ValidationReport


def _make_task() -> TaskPacket:
    return TaskPacket(
        task_id="KAN-42",
        source="jira",
        source_issue_key="KAN-42",
        title="Add payment retry logic",
        description="Users see checkout failures when the payment provider times out. We need a retry with backoff.",
        repo="checkout-service",
        requested_outcome="Retries on timeout up to 3 times before surfacing error to user.",
        priority="high",
        risk_level="medium",
        acceptance_criteria=[
            "Retries up to 3 times on timeout",
            "Exponential backoff between retries",
            "Error logged after final failure",
        ],
    )


def _make_spec() -> ExecutionSpec:
    return ExecutionSpec(
        spec_id="spec-KAN-42",
        task_id="KAN-42",
        problem_statement="[bug_fix] Add payment retry logic",
        acceptance_criteria=[
            "Retries up to 3 times on timeout",
            "Exponential backoff between retries",
            "Error logged after final failure",
        ],
        implementation_notes=["Follow existing retry pattern in payments/utils.py"],
    )


def test_title_contains_issue_key_and_task_title() -> None:
    title, _ = compose_pr(_make_task(), _make_spec())
    assert "KAN-42" in title
    assert "Add payment retry logic" in title


def test_body_contains_task_description() -> None:
    _, body = compose_pr(_make_task(), _make_spec())
    assert "checkout failures" in body


def test_body_contains_all_acceptance_criteria() -> None:
    _, body = compose_pr(_make_task(), _make_spec())
    assert "Retries up to 3 times on timeout" in body
    assert "Exponential backoff between retries" in body
    assert "Error logged after final failure" in body


def test_body_without_validation_says_not_run() -> None:
    _, body = compose_pr(_make_task(), _make_spec(), validation=None)
    assert "not run" in body


def test_body_with_validation_shows_status() -> None:
    report = ValidationReport(
        report_id="validation-KAN-42",
        task_id="KAN-42",
        status="pass",
        summary="All checks passed.",
        mechanical_checks=[ValidationCheck(name="lint", status="pass")],
        policy_checks=[ValidationCheck(name="forbidden_paths_touched", status="pass")],
        recommended_decision="accept",
    )
    _, body = compose_pr(_make_task(), _make_spec(), validation=report)
    assert "pass" in body
    assert "All checks passed." in body
    assert "lint" in body

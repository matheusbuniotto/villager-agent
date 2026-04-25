from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.executor.agent import ExecutorResult
from app.orchestrator import run_end_to_end
from app.schemas import ValidationReport


def _validation_report(
    *,
    status: str = "pass",
    summary: str = "All validation checks passed.",
    decision: str = "accept",
) -> ValidationReport:
    return ValidationReport(
        report_id="validation-VIL-005",
        task_id="VIL-005",
        status=status,  # type: ignore[arg-type]
        summary=summary,
        recommended_decision=decision,  # type: ignore[arg-type]
    )


def _mock_session(tmp_path: Path) -> MagicMock:
    session = MagicMock()
    session.container_name = "villager-test"
    session.artifact_dir = tmp_path / "sandbox"
    session.artifact_dir.mkdir(parents=True, exist_ok=True)
    return session


def test_run_end_to_end_writes_all_artifacts(tmp_path: Path) -> None:
    mock_executor_result = ExecutorResult(
        summary="Agent wrote changes.",
        changed_files=["app/foo.py"],
    )

    with (
        patch("app.orchestrator.runner.fetch_task") as mock_fetch_task,
        patch("app.orchestrator.runner.DockerSandboxManager") as mock_mgr_cls,
        patch("app.orchestrator.runner.load_model") as mock_load_model,
        patch("app.orchestrator.runner.run_executor", return_value=mock_executor_result),
        patch("app.orchestrator.runner.Validator") as mock_validator_cls,
    ):
        from app.intake.stub import fetch_task as stub_fetch

        mock_fetch_task.side_effect = stub_fetch
        mock_mgr = mock_mgr_cls.return_value
        mock_mgr.start_sandbox.return_value = _mock_session(tmp_path)
        mock_load_model.return_value = MagicMock()
        mock_validator_cls.return_value.validate.return_value = _validation_report()

        run_dir = run_end_to_end(jira_key="VIL-005", repo_name="example", runs_dir=tmp_path)

    assert run_dir.exists()
    assert (run_dir / "run.json").is_file()
    assert (run_dir / "task.json").is_file()
    assert (run_dir / "spec.json").is_file()
    assert (run_dir / "executor-summary.txt").is_file()
    assert (run_dir / "validation.json").is_file()
    assert (run_dir / "pr.md").is_file()
    assert (run_dir / "summary.md").is_file()

    task = json.loads((run_dir / "task.json").read_text(encoding="utf-8"))
    assert task["source_issue_key"] == "VIL-005"

    spec = json.loads((run_dir / "spec.json").read_text(encoding="utf-8"))
    assert spec["task_id"] == task["task_id"]
    assert "python" in spec["scope_in"]

    validation = json.loads((run_dir / "validation.json").read_text(encoding="utf-8"))
    assert validation["status"] == "pass"

    record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert record["task_id"] == "VIL-005"
    assert record["repo_name"] == "example"
    assert record["state"] == "DONE"
    assert record["retry_count"] == 0
    assert record["validation_report_ref"].endswith("validation.json")


def test_run_end_to_end_retries_once_then_succeeds(tmp_path: Path) -> None:
    with (
        patch("app.orchestrator.runner.fetch_task") as mock_fetch_task,
        patch("app.orchestrator.runner.DockerSandboxManager") as mock_mgr_cls,
        patch("app.orchestrator.runner.load_model") as mock_load_model,
        patch(
            "app.orchestrator.runner.run_executor",
            side_effect=[
                ExecutorResult(summary="First attempt.", changed_files=["app/foo.py"]),
                ExecutorResult(summary="Second attempt.", changed_files=["app/foo.py"]),
            ],
        ) as mock_run_executor,
        patch("app.orchestrator.runner.Validator") as mock_validator_cls,
    ):
        from app.intake.stub import fetch_task as stub_fetch

        mock_fetch_task.side_effect = stub_fetch
        mock_mgr = mock_mgr_cls.return_value
        mock_mgr.start_sandbox.return_value = _mock_session(tmp_path)
        mock_load_model.return_value = MagicMock()
        mock_validator_cls.return_value.validate.side_effect = [
            _validation_report(
                status="fail_retryable",
                summary="Validation failed with 1 failure(s).",
                decision="retry",
            ),
            _validation_report(),
        ]

        run_dir = run_end_to_end(
            jira_key="VIL-005",
            repo_name="example",
            runs_dir=tmp_path,
            max_retries=2,
        )

    assert mock_run_executor.call_count == 2
    assert mock_run_executor.call_args_list[0].kwargs["instruction"] is None
    retry_instruction = mock_run_executor.call_args_list[1].kwargs["instruction"]
    assert retry_instruction is not None
    assert "Retry 1 of 2." in retry_instruction
    assert "Validation failed with 1 failure(s)." not in retry_instruction

    record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert record["state"] == "DONE"
    assert record["retry_count"] == 1


def test_run_end_to_end_stops_at_max_retries(tmp_path: Path) -> None:
    with (
        patch("app.orchestrator.runner.fetch_task") as mock_fetch_task,
        patch("app.orchestrator.runner.DockerSandboxManager") as mock_mgr_cls,
        patch("app.orchestrator.runner.load_model") as mock_load_model,
        patch(
            "app.orchestrator.runner.run_executor",
            side_effect=[
                ExecutorResult(summary="Attempt one.", changed_files=["app/foo.py"]),
                ExecutorResult(summary="Attempt two.", changed_files=["app/foo.py"]),
                ExecutorResult(summary="Attempt three.", changed_files=["app/foo.py"]),
            ],
        ) as mock_run_executor,
        patch("app.orchestrator.runner.Validator") as mock_validator_cls,
    ):
        from app.intake.stub import fetch_task as stub_fetch

        mock_fetch_task.side_effect = stub_fetch
        mock_mgr = mock_mgr_cls.return_value
        mock_mgr.start_sandbox.return_value = _mock_session(tmp_path)
        mock_load_model.return_value = MagicMock()
        mock_validator_cls.return_value.validate.side_effect = [
            _validation_report(
                status="fail_retryable",
                summary="Validation failed with 1 failure(s).",
                decision="retry",
            ),
            _validation_report(
                status="fail_retryable",
                summary="Validation failed with 1 failure(s).",
                decision="retry",
            ),
            _validation_report(
                status="fail_retryable",
                summary="Validation failed with 1 failure(s).",
                decision="retry",
            ),
        ]

        run_dir = run_end_to_end(
            jira_key="VIL-005",
            repo_name="example",
            runs_dir=tmp_path,
            max_retries=2,
        )

    assert mock_run_executor.call_count == 3

    record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert record["state"] == "FAILED_RETRYABLE"
    assert record["retry_count"] == 2

    validation = json.loads((run_dir / "validation.json").read_text(encoding="utf-8"))
    assert validation["status"] == "fail_retryable"

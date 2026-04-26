from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.executor.agent import ExecutorResult
from app.orchestrator import run_end_to_end
from app.schemas import ValidationReport
from app.state_store import JsonlStateStore
from app.git_provider import PullRequestRequest


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
    assert record["summary_ref"].endswith("summary.md")
    assert record["pr_ref"].endswith("pr.md")

    store = JsonlStateStore(tmp_path / "state")
    latest = store.get_run(run_dir.name)
    assert latest is not None
    assert latest.state == "DONE"
    assert latest.summary_ref is not None
    assert latest.pr_ref is not None

    transitions = store.list_transitions(run_dir.name)
    assert [transition.to_state for transition in transitions] == [
        "INTAKE",
        "SPEC_READY",
        "SANDBOX_READY",
        "EXECUTING",
        "VALIDATING",
        "DONE",
        "PR_DRAFTED",
        "DONE",
    ]


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

    transitions = JsonlStateStore(tmp_path / "state").list_transitions(run_dir.name)
    executing_count = sum(1 for transition in transitions if transition.to_state == "EXECUTING")
    validating_count = sum(1 for transition in transitions if transition.to_state == "VALIDATING")
    assert executing_count == 2
    assert validating_count == 2


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

    latest = JsonlStateStore(tmp_path / "state").get_run(run_dir.name)
    assert latest is not None
    assert latest.state == "FAILED_RETRYABLE"
    assert latest.validation_report_ref is not None


def test_run_end_to_end_creates_github_pr_on_success(tmp_path: Path) -> None:
    mock_executor_result = ExecutorResult(
        summary="Agent wrote changes.",
        changed_files=["app/foo.py"],
    )

    mock_pr_response = {
        "html_url": "https://github.com/acme/example/pull/42",
        "number": 42,
        "draft": True,
    }

    with (
        patch("app.orchestrator.runner.fetch_task") as mock_fetch_task,
        patch("app.orchestrator.runner.DockerSandboxManager") as mock_mgr_cls,
        patch("app.orchestrator.runner.load_model") as mock_load_model,
        patch("app.orchestrator.runner.run_executor", return_value=mock_executor_result),
        patch("app.orchestrator.runner.Validator") as mock_validator_cls,
        patch("app.orchestrator.runner.GitHubPullRequestProvider") as mock_provider_cls,
        patch("app.orchestrator.runner.verify_push_access"),
        patch.dict("os.environ", {"GITHUB_PAT": "test-token"}),
    ):
        from app.intake.stub import fetch_task as stub_fetch

        mock_fetch_task.side_effect = stub_fetch
        mock_mgr = mock_mgr_cls.return_value
        mock_session = _mock_session(tmp_path)
        mock_session.work_branch = "villager/vil-005"
        mock_mgr.start_sandbox.return_value = mock_session
        mock_load_model.return_value = MagicMock()
        mock_validator_cls.return_value.validate.return_value = _validation_report()
        mock_provider_cls.return_value.create_draft_pr.return_value = mock_pr_response

        # patch profile to include repo_url
        from app.spec_builder import load_repo_profile as real_load

        def patched_load(name: str):  # type: ignore[no-untyped-def]
            p = real_load(name)
            object.__setattr__(p, "repo_url", "https://github.com/acme/example.git")
            return p

        with patch("app.orchestrator.runner.load_repo_profile", side_effect=patched_load):
            run_dir = run_end_to_end(jira_key="VIL-005", repo_name="example", runs_dir=tmp_path)

    # commit_and_push was called
    mock_mgr.commit_and_push.assert_called_once()
    call_kwargs = mock_mgr.commit_and_push.call_args
    assert call_kwargs.kwargs.get("github_pat") == "test-token"

    # GitHub provider was called with correct payload
    mock_provider_cls.assert_called_once_with("test-token")
    pr_request: PullRequestRequest = mock_provider_cls.return_value.create_draft_pr.call_args.args[0]
    assert pr_request.repo_owner == "acme"
    assert pr_request.repo_name == "example"
    assert pr_request.head_branch == "villager/vil-005"
    assert pr_request.draft is True

    # run record has pr_url and final state is DONE
    record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert record["state"] == "DONE"
    assert record["pr_url"] == "https://github.com/acme/example/pull/42"

    store = JsonlStateStore(tmp_path / "state")
    latest = store.get_run(run_dir.name)
    assert latest is not None
    assert latest.pr_url == "https://github.com/acme/example/pull/42"

    transitions = store.list_transitions(run_dir.name)
    state_sequence = [t.to_state for t in transitions]
    assert "PR_SUBMITTED" in state_sequence
    assert state_sequence[-1] == "DONE"


def test_run_end_to_end_fails_fast_on_pat_permission_error(tmp_path: Path) -> None:
    """PAT preflight failure lands run in FAILED_ESCALATE before the sandbox starts."""
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
        patch(
            "app.orchestrator.runner.verify_push_access",
            side_effect=PermissionError("GITHUB_PAT cannot write to acme/example."),
        ),
        patch.dict("os.environ", {"GITHUB_PAT": "readonly-token"}),
    ):
        from app.intake.stub import fetch_task as stub_fetch
        import pytest

        mock_fetch_task.side_effect = stub_fetch
        mock_mgr_cls.return_value.start_sandbox.return_value = _mock_session(tmp_path)
        mock_load_model.return_value = MagicMock()
        mock_validator_cls.return_value.validate.return_value = _validation_report()

        from app.spec_builder import load_repo_profile as real_load

        def patched_load(name: str):  # type: ignore[no-untyped-def]
            p = real_load(name)
            object.__setattr__(p, "repo_url", "https://github.com/acme/example.git")
            return p

        with patch("app.orchestrator.runner.load_repo_profile", side_effect=patched_load):
            with pytest.raises(PermissionError, match="GITHUB_PAT cannot write"):
                run_end_to_end(jira_key="VIL-005", repo_name="example", runs_dir=tmp_path)

        # Sandbox was never started
        mock_mgr_cls.return_value.start_sandbox.assert_not_called()

    # State store records FAILED_ESCALATE — find the run_id from the records file
    import json as _json

    state_dir = tmp_path / "state"
    records_file = state_dir / "run-records.jsonl"
    assert records_file.exists(), "state store should have written run records"
    records = [_json.loads(line) for line in records_file.read_text().splitlines() if line.strip()]
    assert records, "expected at least one run record"
    last_record = records[-1]
    assert last_record["state"] == "FAILED_ESCALATE"

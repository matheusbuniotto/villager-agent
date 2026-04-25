from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from app.main import cli


runner = CliRunner()


def test_run_command_requires_jira_key() -> None:
    result = runner.invoke(cli, ["run"])

    assert result.exit_code != 0
    assert "Missing option '--jira'" in result.output


def test_run_command_with_explicit_repo() -> None:
    mock_task = MagicMock()
    mock_task.repo = "billing"

    with (
        runner.isolated_filesystem() as fs_dir,
        patch("app.main.fetch_task", return_value=mock_task),
        patch("app.main.run_end_to_end") as mock_run,
    ):
        run_dir = Path(fs_dir) / "runs" / "run-abc123"
        run_dir.mkdir(parents=True)
        mock_run.return_value = run_dir

        result = runner.invoke(cli, ["run", "--jira", "VIL-005", "--repo", "example"])

        assert result.exit_code == 0
        assert "Run complete" in result.output
        mock_run.assert_called_once_with(jira_key="VIL-005", repo_name="example")


def test_run_command_uses_repo_from_jira() -> None:
    mock_task = MagicMock()
    mock_task.repo = "billing-service"

    with (
        runner.isolated_filesystem() as fs_dir,
        patch("app.main.fetch_task", return_value=mock_task),
        patch("app.main.run_end_to_end") as mock_run,
    ):
        run_dir = Path(fs_dir) / "runs" / "run-abc123"
        run_dir.mkdir(parents=True)
        mock_run.return_value = run_dir

        result = runner.invoke(cli, ["run", "--jira", "VIL-005"])

        assert result.exit_code == 0
        mock_run.assert_called_once_with(jira_key="VIL-005", repo_name="billing-service")


def test_run_command_warns_when_no_repo_found() -> None:
    mock_task = MagicMock()
    mock_task.repo = "unknown"

    with (
        runner.isolated_filesystem() as fs_dir,
        patch("app.main.fetch_task", return_value=mock_task),
        patch("app.main.run_end_to_end") as mock_run,
    ):
        run_dir = Path(fs_dir) / "runs" / "run-abc123"
        run_dir.mkdir(parents=True)
        mock_run.return_value = run_dir

        result = runner.invoke(cli, ["run", "--jira", "VIL-005"])

        assert result.exit_code == 0
        assert "Warning: no repo found" in (result.output + (result.stderr or ""))
        mock_run.assert_called_once_with(jira_key="VIL-005", repo_name="example")

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from app.main import cli


runner = CliRunner()


def test_run_command_creates_stub_run_record() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["run", "--jira", "VIL-003"])

        assert result.exit_code == 0
        assert "Started stub run run-" in result.output
        assert "for VIL-003" in result.output

        runs_dir = Path("runs")
        run_record_paths = list(runs_dir.glob("run-*/run.json"))
        assert len(run_record_paths) == 1

        run_record = json.loads(run_record_paths[0].read_text(encoding="utf-8"))
        assert run_record["task_id"] == "VIL-003"
        assert run_record["state"] == "INTAKE"
        assert run_record["repo_name"] == "unknown"


def test_run_command_requires_jira_key() -> None:
    result = runner.invoke(cli, ["run"])

    assert result.exit_code != 0
    assert "Missing option '--jira'" in result.output

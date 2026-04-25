from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from app.main import cli


runner = CliRunner()


def test_run_command_requires_jira_key() -> None:
    result = runner.invoke(cli, ["run"])

    assert result.exit_code != 0
    assert "Missing option '--jira'" in result.output


def test_run_command_creates_run_artifacts() -> None:
    with runner.isolated_filesystem() as fs_dir, patch("app.main.run_end_to_end") as mock_run:
        run_dir = Path(fs_dir) / "runs" / "run-abc123"
        run_dir.mkdir(parents=True)
        (run_dir / "run.json").write_text(json.dumps({"run_id": "run-abc123"}), encoding="utf-8")
        mock_run.return_value = run_dir

        result = runner.invoke(cli, ["run", "--jira", "VIL-005", "--repo", "example"])

        assert result.exit_code == 0
        assert "Run complete" in result.output
        mock_run.assert_called_once_with(jira_key="VIL-005", repo_name="example")

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from app.orchestrator import run_end_to_end


def test_run_end_to_end_writes_all_artifacts(tmp_path: Path) -> None:
    with patch("app.orchestrator.runner.DockerSandboxManager") as mock_mgr_cls:
        mock_mgr = mock_mgr_cls.return_value
        mock_mgr.run_happy_path.return_value.artifact_dir = tmp_path / "sandbox"
        mock_mgr.run_happy_path.return_value.artifact_dir.mkdir(parents=True, exist_ok=True)

        run_dir = run_end_to_end(jira_key="VIL-005", repo_name="example", runs_dir=tmp_path)

    assert run_dir.exists()
    assert (run_dir / "run.json").is_file()
    assert (run_dir / "task.json").is_file()
    assert (run_dir / "spec.json").is_file()

    task = json.loads((run_dir / "task.json").read_text(encoding="utf-8"))
    assert task["source_issue_key"] == "VIL-005"

    spec = json.loads((run_dir / "spec.json").read_text(encoding="utf-8"))
    assert spec["task_id"] == task["task_id"]
    assert "python" in spec["scope_in"]

    record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert record["task_id"] == "VIL-005"
    assert record["repo_name"] == "example"
    assert record["state"] == "DONE"

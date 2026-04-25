from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from app.artifact_writer import ArtifactWriter
from app.schemas import ExecutionSpec, RunRecord, TaskPacket


def test_write_json_creates_file(tmp_path: Path) -> None:
    writer = ArtifactWriter(tmp_path)
    task = TaskPacket(
        task_id="task-001",
        source="jira",
        source_issue_key="VIL-001",
        title="Test",
        description="Desc",
        repo="example",
        requested_outcome="Do it",
        priority="medium",
        risk_level="low",
    )

    path = writer.write_json("task.json", task)

    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["task_id"] == "task-001"


def test_write_text_creates_file(tmp_path: Path) -> None:
    writer = ArtifactWriter(tmp_path)
    path = writer.write_text("notes.txt", "hello world")

    assert path.exists()
    assert path.read_text(encoding="utf-8") == "hello world\n"


def test_write_summary_md(tmp_path: Path) -> None:
    writer = ArtifactWriter(tmp_path)
    record = RunRecord(
        run_id="run-001",
        task_id="VIL-001",
        repo_name="example",
        state="DONE",
        created_at=datetime(2026, 4, 25, 12, 0, 0, tzinfo=UTC),
        updated_at=datetime(2026, 4, 25, 12, 1, 0, tzinfo=UTC),
    )
    task = TaskPacket(
        task_id="task-001",
        source="jira",
        source_issue_key="VIL-001",
        title="Test title",
        description="Test description",
        repo="example",
        requested_outcome="Do it",
        priority="medium",
        risk_level="low",
    )
    spec = ExecutionSpec(
        spec_id="spec-001",
        task_id="task-001",
        problem_statement="[bug_fix] Test title",
        target_areas=["app/"],
        acceptance_criteria=["Works"],
    )

    path = writer.write_summary_md(record, task, spec)

    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "# Run run-001" in content
    assert "Test title" in content
    assert "app/" in content
    assert "Works" in content


def test_creates_run_dir_if_missing(tmp_path: Path) -> None:
    run_dir = tmp_path / "nested" / "run"
    assert not run_dir.exists()
    ArtifactWriter(run_dir)
    assert run_dir.exists()

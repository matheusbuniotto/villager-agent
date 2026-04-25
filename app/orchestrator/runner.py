from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.intake import fetch_task
from app.sandbox import DockerSandboxManager
from app.schemas import RunRecord
from app.spec_builder import build_spec, load_repo_profile


def run_end_to_end(
    jira_key: str,
    repo_name: str,
    runs_dir: str | Path | None = None,
) -> Path:
    """Run the stub end-to-end flow and write artifacts."""
    run_id = f"run-{uuid4().hex[:12]}"
    target_dir = Path(runs_dir) if runs_dir is not None else Path.cwd() / "runs"
    run_dir = target_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(UTC)

    # 1. Intake stub
    task = fetch_task(jira_key)
    _write_json(run_dir / "task.json", task)

    # 2. Load repo profile
    profile = load_repo_profile(repo_name)

    # 3. Spec builder stub
    spec = build_spec(task, profile)
    _write_json(run_dir / "spec.json", spec)

    # 4. Sandbox happy path
    repo_source = Path.cwd()  # current repo as test subject
    sandbox_mgr = DockerSandboxManager(runs_dir=run_dir)
    _sandbox_result = sandbox_mgr.run_happy_path(repo_source, jira_key=jira_key, run_id=run_id)

    # 5. Run record
    record = RunRecord(
        run_id=run_id,
        task_id=jira_key,
        repo_name=repo_name,
        state="DONE",
        created_at=now,
        updated_at=datetime.now(UTC),
        task_packet_ref=str(run_dir / "task.json"),
        profile_ref=f"profiles/{repo_name}.yaml",
        spec_ref=str(run_dir / "spec.json"),
    )
    _write_json(run_dir / "run.json", record)

    return run_dir


def _write_json(path: Path, obj: object) -> None:
    data = asdict(obj)  # type: ignore[arg-type]
    for key, value in list(data.items()):
        if isinstance(value, datetime):
            data[key] = value.isoformat()
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import typer
from dotenv import load_dotenv

from app.artifact_writer import ArtifactWriter
from app.executor.agent import run_executor
from app.executor.model import load_model
from app.intake import fetch_task
from app.pr_composer import compose_pr
from app.sandbox import DockerSandboxManager
from app.schemas import RunRecord
from app.spec_builder import build_spec, load_repo_profile

load_dotenv()


def _log(phase: str, detail: str = "") -> None:
    ts = datetime.now(UTC).strftime("%H:%M:%S")
    msg = f"[{ts}] ▸ {phase}"
    if detail:
        msg += f" — {detail}"
    typer.secho(msg, fg=typer.colors.CYAN)


def run_end_to_end(
    jira_key: str,
    repo_name: str,
    runs_dir: str | Path | None = None,
) -> Path:
    """Run the stub end-to-end flow and write artifacts."""
    run_id = f"run-{uuid4().hex[:12]}"
    target_dir = Path(runs_dir) if runs_dir is not None else Path.cwd() / "runs"
    run_dir = target_dir / run_id
    writer = ArtifactWriter(run_dir)

    now = datetime.now(UTC)
    _log("Run started", run_id)
    t0 = perf_counter()

    # 1. Intake
    _log("Intake", f"fetching {jira_key}")
    task = fetch_task(jira_key)
    writer.write_json("task.json", task)

    # 2. Profile
    _log("Profile", f"loading {repo_name}")
    profile = load_repo_profile(repo_name)

    # 3. Spec builder
    _log("Spec", "building execution spec")
    spec = build_spec(task, profile)
    writer.write_json("spec.json", spec)

    # 4. Sandbox — start, execute, teardown
    _log("Sandbox", "starting container and cloning repo")
    repo_source = Path.cwd()
    sandbox_mgr = DockerSandboxManager(runs_dir=run_dir)
    session = sandbox_mgr.start_sandbox(repo_source, jira_key=jira_key, run_id=run_id)
    _log("Sandbox", f"container {session.container_name} ready")

    try:
        # 5. Executor
        _log("Executor", "loading model and running agent")
        model = load_model()
        executor_result = run_executor(spec, profile, session.container_name, model)
        _log("Executor", f"done — {len(executor_result.changed_files)} file(s) changed")
        writer.write_text("executor-summary.txt", executor_result.summary)
    finally:
        _log("Sandbox", "tearing down container")
        sandbox_mgr.teardown_sandbox(session)

    # 7. Run record + summary
    _log("Artifacts", "writing run record and summary")
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
    writer.write_json("run.json", record)
    writer.write_summary_md(record, task, spec)

    # 8. PR draft
    _log("PR", "composing draft PR body")
    pr_title, pr_body = compose_pr(task, spec)
    writer.write_text("pr.md", f"# {pr_title}\n\n{pr_body}")

    elapsed = perf_counter() - t0
    _log("Done", f"run folder {run_dir.name} — elapsed {elapsed:.2f}s")

    return run_dir

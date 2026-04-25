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
from app.schemas import RunRecord, ValidationReport
from app.spec_builder import build_spec, load_repo_profile
from app.validator import Validator

load_dotenv()

DEFAULT_MAX_RETRIES = 2


def _log(phase: str, detail: str = "") -> None:
    ts = datetime.now(UTC).strftime("%H:%M:%S")
    msg = f"[{ts}] ▸ {phase}"
    if detail:
        msg += f" — {detail}"
    typer.secho(msg, fg=typer.colors.CYAN)


def _build_retry_instruction(
    validation: ValidationReport,
    retry_count: int,
    max_retries: int,
) -> str:
    lines = [
        f"Retry {retry_count} of {max_retries}.",
        "Fix the validation failures below and re-run the relevant checks before stopping.",
    ]

    if validation.failures:
        lines.append("")
        lines.append("Failures:")
        lines.extend(f"- {failure}" for failure in validation.failures)

    failing_checks = [
        check
        for check in (validation.mechanical_checks + validation.policy_checks)
        if check.status in {"fail", "warning"}
    ]
    if failing_checks:
        lines.append("")
        lines.append("Check details:")
        for check in failing_checks:
            detail = f"- {check.name}: {check.status}"
            if check.reason:
                detail += f" - {check.reason}"
            lines.append(detail)

    if validation.warnings:
        lines.append("")
        lines.append("Warnings to keep in mind:")
        lines.extend(f"- {warning}" for warning in validation.warnings)

    return "\n".join(lines)


def _resolve_run_state(validation: ValidationReport | None) -> tuple[str, str]:
    if validation is None:
        return "DONE", "Execution completed without validation output."
    if validation.recommended_decision == "retry":
        return "FAILED_RETRYABLE", validation.summary
    if validation.recommended_decision == "escalate":
        return "FAILED_ESCALATE", validation.summary
    if validation.recommended_decision == "wait_human":
        return "WAITING_HUMAN", validation.summary
    return "DONE", validation.summary


def run_end_to_end(
    jira_key: str,
    repo_name: str,
    runs_dir: str | Path | None = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> Path:
    """Run the end-to-end flow, including validation retries, and write artifacts."""
    if max_retries < 0:
        raise ValueError("max_retries must be >= 0")

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

    # 4. Sandbox — start, execute, validate, teardown
    _log("Sandbox", "starting container and cloning repo")
    repo_url = profile.repo_url
    github_pat = os.environ.get("GITHUB_PAT")
    repo_source = Path.cwd()
    sandbox_image = profile.sandbox_image
    if sandbox_image:
        sandbox_mgr = DockerSandboxManager(runs_dir=run_dir, image=sandbox_image)
    else:
        sandbox_mgr = DockerSandboxManager(runs_dir=run_dir)
    session = sandbox_mgr.start_sandbox(
        repo_source,
        jira_key=jira_key,
        run_id=run_id,
        repo_url=repo_url,
        github_pat=github_pat,
    )
    _log("Sandbox", f"container {session.container_name} ready")

    retry_count = 0
    retry_instruction: str | None = None
    validation: ValidationReport | None = None

    try:
        # 5. Executor + validation loop
        _log("Executor", "loading model")
        model = load_model()
        validator = Validator()

        while True:
            attempt_number = retry_count + 1
            _log("Executor", f"attempt {attempt_number} running agent")
            executor_result = run_executor(
                spec,
                profile,
                session.container_name,
                model,
                instruction=retry_instruction,
            )
            _log(
                "Executor",
                f"attempt {attempt_number} done - {len(executor_result.changed_files)} file(s) changed",
            )
            writer.write_text("executor-summary.txt", executor_result.summary)

            _log("Validation", f"attempt {attempt_number} running checks")
            validation = validator.validate(session.container_name, profile, jira_key)
            writer.write_json("validation.json", validation)
            _log("Validation", validation.summary)

            if validation.recommended_decision != "retry":
                break

            if retry_count >= max_retries:
                _log("Retry", f"max retries reached ({max_retries})")
                break

            retry_count += 1
            retry_instruction = _build_retry_instruction(validation, retry_count, max_retries)
            _log("Retry", f"preparing retry {retry_count} of {max_retries}")
    finally:
        _log("Sandbox", "tearing down container")
        sandbox_mgr.teardown_sandbox(session)

    run_state, final_outcome = _resolve_run_state(validation)

    # 6. Run record + summary
    _log("Artifacts", "writing run record and summary")
    record = RunRecord(
        run_id=run_id,
        task_id=jira_key,
        repo_name=repo_name,
        state=run_state,  # type: ignore[arg-type]
        created_at=now,
        updated_at=datetime.now(UTC),
        retry_count=retry_count,
        task_packet_ref=str(run_dir / "task.json"),
        profile_ref=f"profiles/{repo_name}.yaml",
        spec_ref=str(run_dir / "spec.json"),
        validation_report_ref=str(run_dir / "validation.json") if validation else None,
        final_outcome=final_outcome,
    )
    writer.write_json("run.json", record)
    writer.write_summary_md(record, task, spec, validation=validation)

    # 7. PR draft
    _log("PR", "composing draft PR body")
    pr_title, pr_body = compose_pr(task, spec, validation=validation)
    writer.write_text("pr.md", f"# {pr_title}\n\n{pr_body}")

    elapsed = perf_counter() - t0
    _log("Done", f"run folder {run_dir.name} - elapsed {elapsed:.2f}s")

    return run_dir

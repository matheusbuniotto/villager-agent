from __future__ import annotations

import os
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from dotenv import load_dotenv

from app.artifact_writer import ArtifactWriter
from app.executor.agent import run_executor
from app.executor.model import load_model
from app.git_provider import GitHubPullRequestProvider, PullRequestRequest, parse_github_repo, verify_push_access
from app.intake import fetch_task
from app.pr_composer import compose_pr
from app.sandbox import DockerSandboxManager
from app.schemas import RunRecord, RunState, RunStateTransition, ValidationReport
from app.spec_builder import build_spec, load_repo_profile
from app.state_store import JsonlStateStore
from app.ui import (
    log,
    print_metrics_summary,
    print_pr_summary,
    print_spec_summary,
    print_validation_table,
    spinner,
)
from app.validator import Validator

load_dotenv()

DEFAULT_MAX_RETRIES = 2


def _log(phase: str, detail: str = "") -> None:
    log(phase, detail)


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


def _resolve_run_state(validation: ValidationReport | None) -> tuple[RunState, str]:
    if validation is None:
        return "DONE", "Execution completed without validation output."
    if validation.recommended_decision == "retry":
        return "FAILED_RETRYABLE", validation.summary
    if validation.recommended_decision == "escalate":
        return "FAILED_ESCALATE", validation.summary
    if validation.recommended_decision == "wait_human":
        return "WAITING_HUMAN", validation.summary
    return "DONE", validation.summary


def _persist_run(
    state_store: JsonlStateStore,
    record: RunRecord,
    *,
    state: RunState | None = None,
    reason: str | None = None,
    **changes: object,
) -> RunRecord:
    updated_at = datetime.now(UTC)
    next_state = state if state is not None else record.state
    next_record = replace(record, updated_at=updated_at, state=next_state, **changes)
    state_store.write_run(next_record)

    if next_state != record.state:
        state_store.append_transition(
            RunStateTransition(
                run_id=record.run_id,
                from_state=record.state,
                to_state=next_state,
                occurred_at=updated_at,
                reason=reason,
            )
        )

    return next_record


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
    state_store = JsonlStateStore(target_dir / "state")

    now = datetime.now(UTC)
    record = RunRecord(
        run_id=run_id,
        task_id=jira_key,
        repo_name=repo_name,
        state="INTAKE",
        created_at=now,
        updated_at=now,
        profile_ref=f"profiles/{repo_name}.yaml",
    )
    state_store.write_run(record)
    state_store.append_transition(
        RunStateTransition(
            run_id=run_id,
            from_state=None,
            to_state="INTAKE",
            occurred_at=now,
            reason="run started",
        )
    )

    _log("Run started", run_id)
    t0 = perf_counter()
    phase_timings: dict[str, float] = {}
    total_input_tokens = 0
    total_output_tokens = 0
    total_tool_calls = 0

    # 1. Intake
    _log("Intake", f"fetching {jira_key}")
    _t = perf_counter()
    with spinner(f"Fetching {jira_key} from JIRA…"):
        task = fetch_task(jira_key)
    phase_timings["intake"] = perf_counter() - _t
    task_path = writer.write_json("task.json", task)
    record = _persist_run(
        state_store,
        record,
        task_packet_ref=str(task_path),
        reason="task fetched",
    )
    _log("Intake", f"fetched: {task.title}")

    # 2. Profile
    _log("Profile", f"loading {repo_name}")
    profile = load_repo_profile(repo_name)

    # 3. Spec builder
    _log("Spec", "building execution spec")
    _t = perf_counter()
    with spinner("Building execution spec…"):
        spec = build_spec(task, profile)
    phase_timings["spec"] = perf_counter() - _t
    spec_path = writer.write_json("spec.json", spec)
    record = _persist_run(
        state_store,
        record,
        state="SPEC_READY",
        spec_ref=str(spec_path),
        reason="execution spec built",
    )
    print_spec_summary(spec)

    # 4. Sandbox — start, execute, validate, teardown
    _log("Sandbox", "starting container and cloning repo")
    repo_url = task.metadata.get("repo_url") or profile.repo_url
    github_pat = os.environ.get("GITHUB_PAT")

    # Fail fast: verify the PAT can actually push before spinning up the sandbox.
    # Fine-grained PATs may have metadata:read only — permissions.push in the repo
    # API reflects user role, not token scope, so we probe a write endpoint directly.
    if repo_url and github_pat:
        try:
            _repo_owner, _repo_name_check = parse_github_repo(repo_url)
            verify_push_access(github_pat, _repo_owner, _repo_name_check)
        except PermissionError as exc:
            _log("Preflight", str(exc))
            record = _persist_run(
                state_store,
                record,
                state="FAILED_ESCALATE",
                final_outcome=str(exc),
                reason="GITHUB_PAT lacks push access",
            )
            raise

    repo_source = Path.cwd()
    sandbox_image = profile.sandbox_image
    if sandbox_image:
        sandbox_mgr = DockerSandboxManager(runs_dir=run_dir, image=sandbox_image)
    else:
        sandbox_mgr = DockerSandboxManager(runs_dir=run_dir)
    _t = perf_counter()
    with spinner("Starting Docker sandbox and cloning repo…"):
        session = sandbox_mgr.start_sandbox(
            repo_source,
            jira_key=jira_key,
            run_id=run_id,
            repo_url=repo_url,
            github_pat=github_pat,
            install_cmd=profile.commands.install or None,
        )
    phase_timings["sandbox_start"] = perf_counter() - _t
    _log("Sandbox", f"container {session.container_name} ready")
    record = _persist_run(
        state_store,
        record,
        state="SANDBOX_READY",
        reason="sandbox ready for execution",
    )

    retry_count = 0
    retry_instruction: str | None = None
    validation: ValidationReport | None = None
    work_branch = session.work_branch
    push_succeeded = False

    try:
        # 5. Executor + validation loop
        _log("Executor", "loading model")
        with spinner("Loading model…"):
            model = load_model()
        validator = Validator()

        while True:
            attempt_number = retry_count + 1
            record = _persist_run(
                state_store,
                record,
                state="EXECUTING",
                retry_count=retry_count,
                reason=f"executor attempt {attempt_number} started",
            )
            _log("Executor", f"attempt {attempt_number} — agent running")

            def _on_tool(name: str, input_str: str) -> None:
                preview = input_str[:120].replace("\n", " ")
                log("  ↳ tool", f"{name}({preview}{'…' if len(input_str) > 120 else ''})")

            _t = perf_counter()
            executor_result = run_executor(
                spec,
                profile,
                session.container_name,
                model,
                instruction=retry_instruction,
                on_tool=_on_tool,
            )
            phase_timings[f"executor_attempt_{attempt_number}"] = perf_counter() - _t

            total_input_tokens += executor_result.input_tokens
            total_output_tokens += executor_result.output_tokens
            total_tool_calls += executor_result.tool_calls

            _log(
                "Executor",
                f"attempt {attempt_number} done — {len(executor_result.changed_files)} file(s) changed"
                f", {executor_result.tool_calls} tool calls"
                f", {executor_result.input_tokens}/{executor_result.output_tokens} tok in/out",
            )
            writer.write_text("executor-summary.txt", executor_result.summary)

            record = _persist_run(
                state_store,
                record,
                state="VALIDATING",
                reason=f"validation attempt {attempt_number} started",
            )
            _log("Validation", f"attempt {attempt_number} running checks")
            _t = perf_counter()
            validation = validator.validate(session.container_name, profile, jira_key)
            phase_timings[f"validation_attempt_{attempt_number}"] = perf_counter() - _t
            validation_path = writer.write_json("validation.json", validation)
            record = _persist_run(
                state_store,
                record,
                validation_report_ref=str(validation_path),
                retry_count=retry_count,
                reason=f"validation attempt {attempt_number} finished",
            )
            print_validation_table(validation, attempt_number)

            if validation.recommended_decision != "retry":
                break

            if retry_count >= max_retries:
                _log("Retry", f"max retries reached ({max_retries})")
                break

            retry_count += 1
            retry_instruction = _build_retry_instruction(validation, retry_count, max_retries)
            _log("Retry", f"preparing retry {retry_count} of {max_retries}")

        # 6. Commit + push inside sandbox (must happen before teardown)
        if _resolve_run_state(validation)[0] == "DONE" and repo_url and github_pat:
            _log("PR", f"committing and pushing branch {work_branch}")
            with spinner(f"Pushing {work_branch}…"):
                commit_msg = f"{jira_key}: {task.title}"
                sandbox_mgr.commit_and_push(session, commit_msg, github_pat=github_pat)
            push_succeeded = True
    finally:
        _log("Sandbox", "tearing down container")
        sandbox_mgr.teardown_sandbox(session)

    run_state, final_outcome = _resolve_run_state(validation)

    # 7. Run record + summary
    _log("Artifacts", "writing run record and summary")
    record = _persist_run(
        state_store,
        record,
        state=run_state,
        retry_count=retry_count,
        final_outcome=final_outcome,
        reason="run finished",
    )
    run_path = writer.write_json("run.json", record)
    summary_path = writer.write_summary_md(record, task, spec, validation=validation)
    record = _persist_run(
        state_store,
        record,
        summary_ref=str(summary_path),
        reason="summary written",
    )
    writer.write_json("run.json", record)

    # 8. PR draft + GitHub API call
    _log("PR", "composing draft PR body")
    pr_title, pr_body = compose_pr(task, spec, validation=validation)
    pr_path = writer.write_text("pr.md", f"# {pr_title}\n\n{pr_body}")
    record = _persist_run(
        state_store,
        record,
        state="PR_DRAFTED" if run_state == "DONE" else run_state,
        pr_ref=str(pr_path),
        reason="draft PR written",
    )

    pr_url: str | None = None
    base_branch = task.target_branch or "main"

    if push_succeeded:
        try:
            repo_owner, repo_name_parsed = parse_github_repo(repo_url)  # type: ignore[arg-type]
            provider = GitHubPullRequestProvider(github_pat)  # type: ignore[arg-type]
            with spinner("Opening GitHub draft PR…"):
                pr_response = provider.create_draft_pr(
                    PullRequestRequest(
                        repo_owner=repo_owner,
                        repo_name=repo_name_parsed,
                        title=pr_title,
                        body=pr_body,
                        head_branch=work_branch,
                        base_branch=base_branch,
                    )
                )
            pr_url = pr_response.get("html_url", "")
            record = _persist_run(
                state_store,
                record,
                state="PR_SUBMITTED",
                pr_url=pr_url,
                reason="GitHub draft PR created",
            )
        except Exception as exc:
            _log("PR", f"GitHub PR creation failed (continuing): {exc}")

    final_state = "DONE" if record.state == "PR_SUBMITTED" else run_state
    record = _persist_run(
        state_store,
        record,
        state=final_state,
        reason="run completed",
    )
    elapsed = perf_counter() - t0

    # 9. Metrics artifact + display
    metrics = {
        "run_id": run_id,
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "total_tokens": total_input_tokens + total_output_tokens,
        "tool_calls": total_tool_calls,
        "executor_attempts": retry_count + 1,
        "elapsed_s": round(elapsed, 2),
        "phase_timings_s": {k: round(v, 2) for k, v in phase_timings.items()},
    }
    writer.write_metrics(metrics)
    writer.write_json("run.json", record)

    print_pr_summary(work_branch, base_branch, pr_url)
    print_metrics_summary(
        input_tokens=total_input_tokens,
        output_tokens=total_output_tokens,
        tool_calls=total_tool_calls,
        attempts=retry_count + 1,
        elapsed_s=elapsed,
        phase_timings=phase_timings,
    )

    _log("Done", f"run folder {run_dir.name} — elapsed {elapsed:.2f}s")

    return run_dir

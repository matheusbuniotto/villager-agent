from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import typer

from app.schemas import RunRecord


cli = typer.Typer(help="Villager command-line interface.", no_args_is_help=True)


@cli.callback()
def app_callback() -> None:
    """Villager command group."""


def _default_runs_dir() -> Path:
    return Path.cwd() / "runs"


def _build_stub_run_record(jira_key: str) -> RunRecord:
    now = datetime.now(UTC)
    run_id = f"run-{uuid4().hex[:12]}"
    return RunRecord(
        run_id=run_id,
        task_id=jira_key,
        repo_name="unknown",
        state="INTAKE",
        created_at=now,
        updated_at=now,
    )


def _write_run_record(run_record: RunRecord, runs_dir: Path | None = None) -> Path:
    target_dir = (runs_dir or _default_runs_dir()) / run_record.run_id
    target_dir.mkdir(parents=True, exist_ok=True)

    record_data = asdict(run_record)
    record_data["created_at"] = run_record.created_at.isoformat()
    record_data["updated_at"] = run_record.updated_at.isoformat()

    record_path = target_dir / "run.json"
    record_path.write_text(json.dumps(record_data, indent=2) + "\n", encoding="utf-8")
    return record_path


@cli.command("run")
def run_command(
    jira: Annotated[str, typer.Option("--jira", help="JIRA issue key to execute.", metavar="KEY")],
) -> None:
    """Create a stub run record for a JIRA issue."""
    run_record = _build_stub_run_record(jira)
    record_path = _write_run_record(run_record)
    typer.echo(f"Started stub run {run_record.run_id} for {jira}")
    typer.echo(f"Run record: {record_path}")


def main() -> None:
    """Villager CLI entrypoint."""
    cli()


if __name__ == "__main__":
    main()

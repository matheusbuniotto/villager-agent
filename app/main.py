from __future__ import annotations

from typing import Annotated

import typer

from app.intake import fetch_task
from app.orchestrator import run_end_to_end

cli = typer.Typer(help="Villager command-line interface.", no_args_is_help=True)


@cli.callback()
def app_callback() -> None:
    """Villager command group."""


@cli.command("run")
def run_command(
    jira: Annotated[str, typer.Option("--jira", help="JIRA issue key to execute.", metavar="KEY")],
    repo: Annotated[
        str | None,
        typer.Option(
            "--repo", help="Repo profile name (overrides JIRA description).", metavar="NAME"
        ),
    ] = None,
) -> None:
    """Run the end-to-end flow for a JIRA issue."""
    task = fetch_task(jira)
    repo_name = repo or (task.repo if task.repo != "unknown" else None) or "example"

    if repo_name == "example" and not repo:
        typer.secho(
            "Warning: no repo found in JIRA issue and --repo not set; using 'example'",
            fg=typer.colors.YELLOW,
        )

    run_dir = run_end_to_end(jira_key=jira, repo_name=repo_name)
    typer.echo(f"Run complete: {run_dir}")


def main() -> None:
    """Villager CLI entrypoint."""
    cli()


if __name__ == "__main__":
    main()

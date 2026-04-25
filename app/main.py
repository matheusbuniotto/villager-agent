from __future__ import annotations

from typing import Annotated

import typer

from app.orchestrator import run_end_to_end

cli = typer.Typer(help="Villager command-line interface.", no_args_is_help=True)


@cli.callback()
def app_callback() -> None:
    """Villager command group."""


@cli.command("run")
def run_command(
    jira: Annotated[str, typer.Option("--jira", help="JIRA issue key to execute.", metavar="KEY")],
    repo: Annotated[
        str,
        typer.Option("--repo", help="Repo profile name.", metavar="NAME"),
    ] = "example",
) -> None:
    """Run the stub end-to-end flow for a JIRA issue."""
    run_dir = run_end_to_end(jira_key=jira, repo_name=repo)
    typer.echo(f"Run complete: {run_dir}")


def main() -> None:
    """Villager CLI entrypoint."""
    cli()


if __name__ == "__main__":
    main()

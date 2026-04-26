from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Generator

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from app.schemas import ExecutionSpec, ValidationReport

console = Console()


def log(phase: str, detail: str = "") -> None:
    ts = datetime.now(UTC).strftime("%H:%M:%S")
    phase_text = Text(f"[{ts}] ▸ {phase}", style="bold cyan")
    if detail:
        phase_text.append(f" — {detail}", style="white")
    console.print(phase_text)


@contextmanager
def spinner(message: str) -> Generator[None, None, None]:
    """Show a spinner with a message while the block runs."""
    with Live(
        Spinner("dots", text=Text(message, style="cyan")),
        console=console,
        transient=True,
        refresh_per_second=10,
    ):
        yield


def print_spec_summary(spec: ExecutionSpec) -> None:
    lines: list[str] = []
    lines.append(f"[bold]Problem:[/bold] {spec.problem_statement}")

    if spec.scope_in:
        lines.append(f"[bold]Scope in:[/bold]  {', '.join(spec.scope_in)}")
    if spec.scope_out:
        lines.append(f"[bold]Scope out:[/bold] {', '.join(spec.scope_out)}")
    if spec.acceptance_criteria:
        lines.append(f"[bold]AC:[/bold] {len(spec.acceptance_criteria)} criteria")

    console.print(
        Panel(
            "\n".join(lines),
            title="[bold cyan]Execution Spec[/bold cyan]",
            border_style="cyan",
            padding=(0, 1),
        )
    )


def print_validation_table(validation: ValidationReport, attempt: int) -> None:
    table = Table(
        title=f"Validation — attempt {attempt}",
        show_header=True,
        header_style="bold",
        border_style="dim",
        padding=(0, 1),
    )
    table.add_column("Check", style="white")
    table.add_column("Status", justify="center")
    table.add_column("Detail", style="dim")

    status_style = {
        "pass": "[green]✓ pass[/green]",
        "fail": "[red]✗ fail[/red]",
        "warning": "[yellow]⚠ warning[/yellow]",
        "skipped": "[dim]– skip[/dim]",
    }

    all_checks = (
        validation.mechanical_checks
        + validation.policy_checks
        + validation.spec_alignment_checks
    )
    for check in all_checks:
        table.add_row(
            check.name,
            status_style.get(check.status, check.status),
            check.reason or "",
        )

    console.print(table)

    decision_style = {
        "accept": "bold green",
        "retry": "bold yellow",
        "escalate": "bold red",
        "wait_human": "bold magenta",
    }
    decision = validation.recommended_decision or "—"
    style = decision_style.get(decision, "white")
    console.print(
        f"  Summary: {validation.summary}  →  decision: [{style}]{decision}[/{style}]"
    )


def print_metrics_summary(
    input_tokens: int,
    output_tokens: int,
    tool_calls: int,
    attempts: int,
    elapsed_s: float,
    phase_timings: dict[str, float],
) -> None:
    table = Table(
        title="Run Metrics",
        show_header=True,
        header_style="bold",
        border_style="dim",
        padding=(0, 1),
    )
    table.add_column("Metric", style="white")
    table.add_column("Value", justify="right", style="bold cyan")

    table.add_row("Tokens in", f"{input_tokens:,}")
    table.add_row("Tokens out", f"{output_tokens:,}")
    table.add_row("Tokens total", f"{input_tokens + output_tokens:,}")
    table.add_row("Tool calls", str(tool_calls))
    table.add_row("Executor attempts", str(attempts))
    table.add_row("Total elapsed", f"{elapsed_s:.1f}s")

    if phase_timings:
        table.add_section()
        for phase, secs in phase_timings.items():
            table.add_row(f"  {phase}", f"{secs:.1f}s")

    console.print(table)


def print_pr_summary(branch: str, base: str, pr_url: str | None) -> None:
    lines = [
        f"[bold]Branch:[/bold] {branch}",
        f"[bold]Base:[/bold]   {base}",
    ]
    if pr_url:
        lines.append(f"[bold]PR:[/bold]     [link={pr_url}]{pr_url}[/link]")
    else:
        lines.append("[dim]PR URL not available (no GitHub config or push failed)[/dim]")

    console.print(
        Panel(
            "\n".join(lines),
            title="[bold green]Draft PR[/bold green]",
            border_style="green",
            padding=(0, 1),
        )
    )

from __future__ import annotations

from app.schemas import ExecutionSpec, TaskPacket, ValidationReport


def compose_pr(
    task: TaskPacket,
    spec: ExecutionSpec,
    validation: ValidationReport | None = None,
) -> tuple[str, str]:
    """Return (title, body) for a draft PR.

    Validation is optional — the sandbox teardown happens before validation
    runs, so the orchestrator passes None until that lifecycle is wired up.
    """
    title = f"[{task.source_issue_key}] {task.title}"

    ac_lines = "\n".join(f"- [ ] {ac}" for ac in spec.acceptance_criteria) or "- (none defined)"

    validation_section: str
    if validation is None:
        validation_section = "Validation: not run"
    else:
        check_lines = "\n".join(
            f"- {c.name}: **{c.status}**" + (f" — {c.reason}" if c.reason else "")
            for c in (validation.mechanical_checks + validation.policy_checks)
        )
        validation_section = (
            f"Status: **{validation.status}**\n\n"
            f"Summary: {validation.summary}\n\n"
            f"{check_lines or '(no checks recorded)'}"
        )

    body = f"""\
## Summary

{task.description}

**Repo:** {task.repo}
**Priority:** {task.priority}
**Risk:** {task.risk_level}

## Acceptance Criteria

{ac_lines}

## Validation

{validation_section}

## Notes

{chr(10).join(f"- {note}" for note in spec.implementation_notes) or "- (none)"}
"""

    return title, body

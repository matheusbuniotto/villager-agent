from __future__ import annotations

from typing import Literal

from app.schemas import ExecutionSpec, RepoProfile, TaskPacket

TaskType = Literal["bug_fix", "feature", "refactor", "migration", "dependency_change", "unknown"]


class SpecBuildError(ValueError):
    """Raised when a task cannot be safely converted to an ExecutionSpec."""


def classify_task_type(task: TaskPacket) -> TaskType:
    """Classify task type from title and description keywords."""
    text = f"{task.title} {task.description}".lower()

    migration_keywords = ["migration", "migrate", "schema change", "database migration"]
    if any(kw in text for kw in migration_keywords):
        return "migration"

    dep_keywords = [
        "upgrade",
        "bump",
        "update package",
        "dependency",
        "requirements",
        "lockfile",
        "package.json",
        "pyproject.toml",
    ]
    if any(kw in text for kw in dep_keywords):
        return "dependency_change"

    bug_keywords = ["bug", "fix", "broken", "error", "crash", "exception", "null", "fails"]
    if any(kw in text for kw in bug_keywords):
        return "bug_fix"

    refactor_keywords = ["refactor", "cleanup", "clean up", "simplify", "restructure"]
    if any(kw in text for kw in refactor_keywords):
        return "refactor"

    feature_keywords = ["add", "implement", "support", "new", "feature", "create", "introduce"]
    if any(kw in text for kw in feature_keywords):
        return "feature"

    return "unknown"


def assess_ambiguity(task: TaskPacket) -> tuple[bool, list[str]]:
    """Return (is_ambiguous, list_of_flags)."""
    flags: list[str] = []

    if len(task.description.strip()) < 30:
        flags.append("description_too_short")

    generic_titles = ["fix bug", "update", "improve", "issue"]
    title_lower = task.title.lower()
    if any(title_lower.startswith(g) or title_lower == g for g in generic_titles):
        flags.append("generic_title")

    return (bool(flags), flags)


def _infer_target_areas(task: TaskPacket, profile: RepoProfile) -> list[str]:
    """Try to guess which owned paths are relevant from the description."""
    text = f"{task.title} {task.description}".lower()
    areas: list[str] = []
    for path in profile.paths.owned:
        # e.g., "app/" -> check for "app" in text
        clean = path.strip("/")
        if clean and clean in text:
            areas.append(path)
    return areas or profile.paths.owned


def _stop_conditions(task_type: TaskType, profile: RepoProfile) -> list[str]:
    conditions: list[str] = ["needs migration", "touches sensitive paths"]
    if profile.rules.block_dependency_changes_without_reason:
        conditions.append("dependency changes without reason")
    if profile.rules.require_human_approval_for_migrations:
        conditions.append("migration requires human approval")
    return conditions


def _escalation_conditions(task: TaskPacket) -> list[str]:
    conditions = ["high risk level", "missing acceptance criteria"]
    if task.priority in ("high", "critical"):
        conditions.append("high priority — extra scrutiny")
    return conditions


def _suggested_plan(task_type: TaskType) -> list[str]:
    base = ["Run tests", "Make changes", "Validate", "Draft PR"]
    if task_type == "bug_fix":
        return ["Reproduce issue", "Add regression test", *base]
    if task_type == "feature":
        return ["Understand current flow", "Add tests for new behavior", *base]
    if task_type == "refactor":
        return ["Review existing tests", "Refactor safely", "Verify no behavior change", *base]
    return base


def _synthesize_acceptance_criteria(task: TaskPacket, task_type: TaskType) -> list[str]:
    """Generate minimal ACs from description when the task has none."""
    base = [f"Implement: {task.title}"]
    if task_type == "bug":
        base.append("Bug no longer reproduces")
    elif task_type == "feature":
        base.append("New behavior is covered by at least one test")
    elif task_type == "refactor":
        base.append("No change in external behavior; existing tests pass")
    base.append("Lint and tests pass")
    return base


def build_spec(task: TaskPacket, profile: RepoProfile) -> ExecutionSpec:
    """Build an ExecutionSpec from a TaskPacket and RepoProfile.

    Raises SpecBuildError if the task is too ambiguous or unsupported.
    """
    task_type = classify_task_type(task)

    # Fail closed on unsupported scope
    if task_type == "migration" and profile.rules.require_human_approval_for_migrations:
        raise SpecBuildError(
            "Task classified as migration and require_human_approval_for_migrations is enabled. "
            "Escalate to human."
        )

    if task_type == "dependency_change" and profile.rules.block_dependency_changes_without_reason:
        raise SpecBuildError(
            "Task classified as dependency change and block_dependency_changes_without_reason "
            "is enabled. Escalate to human."
        )

    is_ambiguous, ambiguity_flags = assess_ambiguity(task)
    if is_ambiguous:
        raise SpecBuildError(
            f"Task is ambiguous: {', '.join(ambiguity_flags)}. "
            "Add acceptance criteria or clarify description before proceeding."
        )

    acceptance_criteria = task.acceptance_criteria or _synthesize_acceptance_criteria(task, task_type)

    return ExecutionSpec(
        spec_id=f"spec-{task.task_id}",
        task_id=task.task_id,
        problem_statement=f"[{task_type}] {task.title}",
        scope_in=[profile.language, profile.build_system, task_type],
        scope_out=["infrastructure", "unrelated services", "production deployment"],
        target_areas=_infer_target_areas(task, profile),
        acceptance_criteria=acceptance_criteria,
        validation_steps=[profile.commands.test, profile.commands.lint],
        artifacts_required=["validation_report", "draft_pr_body"],
        stop_conditions=_stop_conditions(task_type, profile),
        escalation_conditions=_escalation_conditions(task),
        implementation_notes=profile.agent_instructions,
        assumptions=["repo profile is current", f"task type: {task_type}"],
        risk_notes=profile.known_gotchas,
        suggested_plan=_suggested_plan(task_type),
        test_expectations=["All existing tests pass", "New behavior has coverage"],
        review_focus=["Correctness", "Test coverage", "Scope adherence"],
    )

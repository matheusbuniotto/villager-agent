from __future__ import annotations

from app.schemas import ExecutionSpec, RepoProfile, TaskPacket


def build_spec(task: TaskPacket, profile: RepoProfile) -> ExecutionSpec:
    """Stub spec builder: create an ExecutionSpec from task + profile."""
    return ExecutionSpec(
        spec_id=f"spec-{task.task_id}",
        task_id=task.task_id,
        problem_statement=task.title,
        scope_in=[profile.language, profile.build_system],
        scope_out=["infrastructure", "unrelated services"],
        target_areas=profile.paths.owned,
        acceptance_criteria=task.acceptance_criteria,
        validation_steps=[profile.commands.test, profile.commands.lint],
        artifacts_required=["validation_report", "draft_pr_body"],
        stop_conditions=["needs migration", "touches sensitive paths"],
        escalation_conditions=["high risk level", "missing acceptance criteria"],
        implementation_notes=profile.agent_instructions,
        assumptions=["repo profile is current"],
        risk_notes=profile.known_gotchas,
        suggested_plan=["Run tests", "Make changes", "Validate", "Draft PR"],
        test_expectations=["All existing tests pass"],
        review_focus=["Correctness", "Test coverage"],
    )

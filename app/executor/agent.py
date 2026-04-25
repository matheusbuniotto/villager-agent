from __future__ import annotations

from dataclasses import dataclass, field

from langchain_core.language_models.chat_models import BaseChatModel

from app.executor.docker_backend import DockerExecBackend
from app.schemas import ExecutionSpec, RepoProfile

from deepagents import create_deep_agent


WORKDIR = "/workspace/repo"


@dataclass
class ExecutorResult:
    summary: str
    changed_files: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _build_system_prompt(spec: ExecutionSpec, profile: RepoProfile) -> str:
    ac_lines = "\n".join(f"- {ac}" for ac in spec.acceptance_criteria)
    scope_in = ", ".join(spec.scope_in)
    notes = "\n".join(f"- {n}" for n in spec.implementation_notes) or "- none"
    return f"""\
You are a coding agent working inside a Docker sandbox at {WORKDIR}.

## Task
{spec.problem_statement}

## Acceptance criteria
{ac_lines}

## Scope
In: {scope_in}
Out: {", ".join(spec.scope_out)}

## Repo: {profile.repo_name}
Language: {profile.language}
Test command: {profile.commands.test}
Lint command: {profile.commands.lint}

## Implementation notes
{notes}

Work only within {WORKDIR}. When finished, summarize what you changed.
"""


def run_executor(
    spec: ExecutionSpec,
    profile: RepoProfile,
    container_name: str,
    model: BaseChatModel,
) -> ExecutorResult:
    """Run the deepagents executor against a live Docker container."""
    backend = DockerExecBackend(container_name, workdir=WORKDIR)
    system_prompt = _build_system_prompt(spec, profile)

    agent = create_deep_agent(
        model=model,
        backend=backend,
        system_prompt=system_prompt,
    )

    result = agent.invoke({"messages": [{"role": "user", "content": spec.problem_statement}]})

    # extract summary from the last assistant message
    messages = result.get("messages", [])
    summary = next(
        (m.content for m in reversed(messages) if hasattr(m, "content") and m.content),
        "No summary produced.",
    )

    # get changed files via git diff in the container
    diff_result = backend.execute("git diff --name-only HEAD")
    changed_files = [f for f in diff_result.output.splitlines() if f.strip()]

    return ExecutorResult(summary=str(summary), changed_files=changed_files)

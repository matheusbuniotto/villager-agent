from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
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
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0


class _StreamingCallback(BaseCallbackHandler):
    """Pipes agent tool calls and token chunks to a caller-supplied sink."""

    def __init__(self, on_tool: Any, on_token: Any) -> None:
        super().__init__()
        self._on_tool = on_tool
        self._on_token = on_token

    def on_tool_start(self, serialized: dict[str, Any], input_str: str, **kwargs: Any) -> None:
        name = serialized.get("name", "tool")
        self._on_tool(name, input_str)

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        self._on_token(token)


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
    instruction: str | None = None,
    on_tool: Any = None,
    on_token: Any = None,
) -> ExecutorResult:
    """Run the deepagents executor against a live Docker container."""
    backend = DockerExecBackend(container_name, workdir=WORKDIR)
    system_prompt = _build_system_prompt(spec, profile)

    agent = create_deep_agent(
        model=model,
        backend=backend,
        system_prompt=system_prompt,
    )

    user_prompt = spec.problem_statement
    if instruction:
        user_prompt = (
            f"{spec.problem_statement}\n\n"
            "Address the validation issues from the previous attempt before you stop.\n\n"
            f"{instruction}"
        )

    config: dict[str, Any] = {}
    if on_tool or on_token:
        config["callbacks"] = [
            _StreamingCallback(
                on_tool=on_tool or (lambda *_: None),
                on_token=on_token or (lambda *_: None),
            )
        ]

    result = agent.invoke({"messages": [{"role": "user", "content": user_prompt}]}, config)

    messages = result.get("messages", [])

    # extract summary from the last assistant message
    summary = next(
        (m.content for m in reversed(messages) if hasattr(m, "content") and m.content),
        "No summary produced.",
    )

    # accumulate token usage from all AI messages
    input_tokens = 0
    output_tokens = 0
    for msg in messages:
        usage = getattr(msg, "usage_metadata", None)
        if usage:
            input_tokens += usage.get("input_tokens", 0)
            output_tokens += usage.get("output_tokens", 0)

    # count tool invocations (one ToolMessage per tool call result)
    from langchain_core.messages import ToolMessage
    tool_calls = sum(1 for m in messages if isinstance(m, ToolMessage))

    # get changed files via git diff in the container
    diff_result = backend.execute("git diff --name-only HEAD")
    changed_files = [f for f in diff_result.output.splitlines() if f.strip()]

    return ExecutorResult(
        summary=str(summary),
        changed_files=changed_files,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        tool_calls=tool_calls,
    )

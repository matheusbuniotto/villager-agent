"""Integration test for executor agent. Requires Docker. Uses fake model — no LLM API needed."""
from __future__ import annotations

import subprocess
import uuid
from pathlib import Path
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.executor.agent import WORKDIR, ExecutorResult, run_executor
from app.schemas import ExecutionSpec, RepoCommands, RepoPaths, RepoProfile, RepoRules, PRSettings


def docker_available() -> bool:
    try:
        subprocess.run(["docker", "info"], check=True, capture_output=True, timeout=5)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


pytestmark = pytest.mark.skipif(not docker_available(), reason="Docker not available")


class FakeWriteFileThenDoneModel(BaseChatModel):
    """Fake model: writes one file via deepagents write_file tool, then terminates."""

    call_count: int = 0
    target_path: str = f"{WORKDIR}/villager_test_output.txt"

    @property
    def _llm_type(self) -> str:
        return "fake-write-then-done"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "FakeWriteFileThenDoneModel":
        return self

    def _generate(
        self, messages: list[BaseMessage], stop: Any = None, **kwargs: Any
    ) -> ChatResult:
        self.call_count += 1
        if self.call_count == 1:
            msg = AIMessage(
                content="",
                tool_calls=[{
                    "name": "write_file",
                    "args": {"file_path": self.target_path, "content": "written by fake agent"},
                    "id": "call_1",
                    "type": "tool_call",
                }],
            )
        else:
            msg = AIMessage(content="Task complete. Wrote villager_test_output.txt.")
        return ChatResult(generations=[ChatGeneration(message=msg)])


@pytest.fixture(scope="module")
def container():
    name = f"villager-executor-test-{uuid.uuid4().hex[:8]}"
    repo = Path(__file__).parent.parent
    subprocess.run(
        ["docker", "run", "-d", "--name", name, "-v", f"{repo}:/hostrepo:ro",
         "python:3.12-slim", "sleep", "120"],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["docker", "exec", name, "sh", "-lc",
         "apt-get update -qq && apt-get install -y -qq git >/dev/null 2>&1 && "
         "git clone /hostrepo /workspace/repo && "
         "cd /workspace/repo && git config user.email test@test.com && git config user.name Test"],
        check=True, capture_output=True,
    )
    yield name
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)


def _make_spec() -> ExecutionSpec:
    return ExecutionSpec(
        spec_id="spec-TEST-1",
        task_id="TEST-1",
        problem_statement="Add a test output file",
        scope_in=["python", "pytest"],
        scope_out=["infrastructure"],
        acceptance_criteria=["villager_test_output.txt exists"],
    )


def _make_profile() -> RepoProfile:
    return RepoProfile(
        repo_name="villager",
        team_name="test",
        language="python",
        build_system="uv",
        commands=RepoCommands(install="uv sync", lint="ruff check .", test="pytest"),
        paths=RepoPaths(owned=["app/"], sensitive=[], forbidden=[]),
        rules=RepoRules(),
        pr=PRSettings(template="default"),
    )


def test_executor_runs_and_returns_result(container: str) -> None:
    model = FakeWriteFileThenDoneModel()
    result = run_executor(_make_spec(), _make_profile(), container, model)

    assert isinstance(result, ExecutorResult)
    assert result.summary  # non-empty summary from last agent message
    assert "Task complete" in result.summary


def test_executor_fake_model_writes_file_via_backend(container: str) -> None:
    model = FakeWriteFileThenDoneModel()
    run_executor(_make_spec(), _make_profile(), container, model)

    # verify file exists in the container
    check = subprocess.run(
        ["docker", "exec", container, "sh", "-lc",
         f"test -f {WORKDIR}/villager_test_output.txt && echo exists"],
        capture_output=True, text=True,
    )
    assert "exists" in check.stdout

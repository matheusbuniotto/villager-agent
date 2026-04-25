from __future__ import annotations

import json
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


DEFAULT_SANDBOX_IMAGE = "python:3.12-bookworm"


class SandboxError(RuntimeError):
    """Raised when sandbox setup or teardown fails."""


@dataclass(slots=True)
class SandboxHappyPathResult:
    run_id: str
    jira_key: str
    image: str
    container_name: str
    work_branch: str
    repo_source: Path
    artifact_dir: Path


class CommandRunner(Protocol):
    def run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        """Execute a command and return its completed process."""


class SubprocessCommandRunner:
    def run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(command, check=True, capture_output=True, text=True)


class DockerSandboxManager:
    def __init__(
        self,
        runner: CommandRunner | None = None,
        runs_dir: str | Path | None = None,
        image: str = DEFAULT_SANDBOX_IMAGE,
    ) -> None:
        self._runner = runner or SubprocessCommandRunner()
        self._runs_dir = Path(runs_dir) if runs_dir is not None else Path.cwd() / "runs"
        self._image = image

    def run_happy_path(
        self, repo_source: str | Path, jira_key: str, run_id: str
    ) -> SandboxHappyPathResult:
        repo_path = Path(repo_source).resolve()
        if not (repo_path / ".git").is_dir():
            raise SandboxError(f"Repo source must be a git repository: {repo_path}")

        result = SandboxHappyPathResult(
            run_id=run_id,
            jira_key=jira_key,
            image=self._image,
            container_name=self._container_name(run_id),
            work_branch=self._work_branch(jira_key),
            repo_source=repo_path,
            artifact_dir=self._runs_dir / run_id / "sandbox",
        )
        result.artifact_dir.mkdir(parents=True, exist_ok=True)

        started = False
        try:
            self._docker_run(
                [
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    result.container_name,
                    "-v",
                    f"{repo_path}:/hostrepo:ro",
                    self._image,
                    "sh",
                    "-lc",
                    "mkdir -p /workspace/artifacts && sleep infinity",
                ]
            )
            started = True

            self._docker_exec(
                result.container_name,
                "git --version >/dev/null 2>&1 || (apt-get update && apt-get install -y git >/dev/null)",
            )
            self._docker_exec(
                result.container_name,
                "mkdir -p /workspace && git clone /hostrepo /workspace/repo",
            )
            self._docker_exec(
                result.container_name,
                f"cd /workspace/repo && git checkout -b {shlex.quote(result.work_branch)}",
            )
            self._docker_exec(
                result.container_name,
                self._summary_artifact_command(result),
            )
            self._docker_run(
                [
                    "docker",
                    "cp",
                    f"{result.container_name}:/workspace/artifacts/.",
                    str(result.artifact_dir),
                ]
            )
        except subprocess.CalledProcessError as exc:
            raise SandboxError(self._command_failure_message(exc)) from exc
        finally:
            if started:
                self._destroy_container(result.container_name)

        return result

    def _docker_exec(self, container_name: str, shell_command: str) -> None:
        self._docker_run(["docker", "exec", container_name, "sh", "-lc", shell_command])

    def _docker_run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        return self._runner.run(command)

    def _destroy_container(self, container_name: str) -> None:
        try:
            self._docker_run(["docker", "rm", "-f", container_name])
        except subprocess.CalledProcessError as exc:
            raise SandboxError(self._command_failure_message(exc)) from exc

    def _summary_artifact_command(self, result: SandboxHappyPathResult) -> str:
        payload = {
            "run_id": result.run_id,
            "jira_key": result.jira_key,
            "image": result.image,
            "work_branch": result.work_branch,
            "repo_source": str(result.repo_source),
        }
        json_payload = json.dumps(payload, indent=2)
        return "python -c " + shlex.quote(
            "from pathlib import Path; "
            "Path('/workspace/artifacts').mkdir(parents=True, exist_ok=True); "
            f"Path('/workspace/artifacts/sandbox-summary.json').write_text({json_payload!r} + '\\n', encoding='utf-8')"
        )

    @staticmethod
    def _container_name(run_id: str) -> str:
        safe_run_id = re.sub(r"[^a-zA-Z0-9_.-]+", "-", run_id).strip("-") or "run"
        return f"villager-{safe_run_id.lower()}"

    @staticmethod
    def _work_branch(jira_key: str) -> str:
        safe_key = re.sub(r"[^a-zA-Z0-9._-]+", "-", jira_key).strip("-") or "task"
        return f"villager/{safe_key.lower()}"

    @staticmethod
    def _command_failure_message(exc: subprocess.CalledProcessError) -> str:
        command_text = " ".join(str(part) for part in exc.cmd)
        details = exc.stderr.strip() or exc.stdout.strip() or f"exit code {exc.returncode}"
        return f"Sandbox command failed: {command_text}: {details}"

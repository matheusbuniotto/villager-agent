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
class SandboxSession:
    """A running sandbox — container is alive and ready for exec."""

    run_id: str
    jira_key: str
    image: str
    container_name: str
    work_branch: str
    repo_source: Path
    artifact_dir: Path
    repo_url: str | None = None


# keep old name as alias so existing code using SandboxHappyPathResult still works
SandboxHappyPathResult = SandboxSession


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

    def _check_docker_alive(self) -> None:
        try:
            self._docker_run(["docker", "info", "--format", "{{.ServerVersion}}"])
        except subprocess.CalledProcessError as exc:
            raise SandboxError(
                "Docker daemon is not reachable. Start Docker Desktop (or `colima start`) and retry. "
                f"Underlying error: {exc.stderr.strip() or exc.stdout.strip() or exc}"
            ) from exc
        except FileNotFoundError as exc:
            raise SandboxError("`docker` CLI not found on PATH. Install Docker Desktop or colima.") from exc

    def _check_image_available(self, image: str) -> None:
        # Only enforce local presence for images that can't be pulled from a registry.
        # Standard images (e.g. golang:*, python:*) are auto-pulled by docker run.
        # Local-only images (those without a registry host and not on Docker Hub naming)
        # are identified by a "villager" prefix convention.
        if "villager" not in image:
            return
        try:
            self._docker_run(["docker", "image", "inspect", image])
        except subprocess.CalledProcessError:
            raise SandboxError(
                f"Sandbox image '{image}' not found locally. "
                f"Build it with: docker build -t {image} docker/villager-base"
            )

    def start_sandbox(
        self,
        repo_source: str | Path,
        jira_key: str,
        run_id: str,
        repo_url: str | None = None,
        github_pat: str | None = None,
        install_cmd: str | None = None,
    ) -> SandboxSession:
        """Start a container and clone the repo. Container stays alive — caller must call teardown_sandbox.

        If repo_url is given, clones from the remote URL (using github_pat if provided).
        Otherwise mounts repo_source as a local volume and clones from /hostrepo.
        """
        self._check_docker_alive()
        self._check_image_available(self._image)

        repo_path = Path(repo_source).resolve()

        session = SandboxSession(
            run_id=run_id,
            jira_key=jira_key,
            image=self._image,
            container_name=self._container_name(run_id),
            work_branch=self._work_branch(jira_key),
            repo_source=repo_path,
            artifact_dir=self._runs_dir / run_id / "sandbox",
            repo_url=repo_url,
        )
        session.artifact_dir.mkdir(parents=True, exist_ok=True)

        try:
            docker_run_cmd: list[str]
            if repo_url:
                docker_run_cmd = [
                    "docker", "run", "-d",
                    "--name", session.container_name,
                    self._image,
                    "sh", "-lc", "mkdir -p /workspace/artifacts && sleep infinity",
                ]
            else:
                if not (repo_path / ".git").is_dir():
                    raise SandboxError(f"Repo source must be a git repository: {repo_path}")
                docker_run_cmd = [
                    "docker", "run", "-d",
                    "--name", session.container_name,
                    "-v", f"{repo_path}:/hostrepo:ro",
                    self._image,
                    "sh", "-lc", "mkdir -p /workspace/artifacts && sleep infinity",
                ]

            self._docker_run(docker_run_cmd)
            self._docker_exec(
                session.container_name,
                "git --version >/dev/null 2>&1 || (apt-get update && apt-get install -y git >/dev/null)",
            )

            if repo_url:
                # Inject PAT into URL for private repos: https://pat@github.com/org/repo
                clone_url = repo_url
                if github_pat and "github.com" in repo_url:
                    clone_url = repo_url.replace("https://", f"https://{github_pat}@")
                self._docker_exec(
                    session.container_name,
                    f"mkdir -p /workspace && git clone {shlex.quote(clone_url)} /workspace/repo",
                )
            else:
                self._docker_exec(
                    session.container_name,
                    "mkdir -p /workspace && git clone /hostrepo /workspace/repo",
                )

            self._docker_exec(
                session.container_name,
                f"cd /workspace/repo && git checkout -b {shlex.quote(session.work_branch)}",
            )

            if install_cmd:
                self._docker_exec(
                    session.container_name,
                    f"cd /workspace/repo && {install_cmd}",
                )
        except subprocess.CalledProcessError as exc:
            self._destroy_container(session.container_name)
            raise SandboxError(self._command_failure_message(exc)) from exc

        return session

    def commit_and_push(
        self,
        session: SandboxSession,
        commit_message: str,
        github_pat: str | None = None,
    ) -> None:
        """Stage all changes, commit, and push the work branch to origin.

        Configures a throwaway git identity inside the container so the commit
        succeeds even in a fresh Docker image without any git config.
        """
        try:
            self._docker_exec(
                session.container_name,
                "cd /workspace/repo && git config user.email 'villager@bot' && git config user.name 'Villager'",
            )
            self._docker_exec(
                session.container_name,
                f"cd /workspace/repo && git add -A && git commit -m {shlex.quote(commit_message)}",
            )
            # Git strips credentials from the stored remote URL for security,
            # so we must re-inject the PAT explicitly before pushing.
            if github_pat and session.repo_url and "github.com" in session.repo_url:
                base_url = session.repo_url
                if not base_url.endswith(".git"):
                    base_url += ".git"
                authed_url = base_url.replace("https://", f"https://{github_pat}@")
                self._docker_exec(
                    session.container_name,
                    f"cd /workspace/repo && git remote set-url origin {shlex.quote(authed_url)}",
                )
            push_cmd = f"cd /workspace/repo && git push origin {shlex.quote(session.work_branch)}"
            self._docker_exec(session.container_name, push_cmd)
        except subprocess.CalledProcessError as exc:
            msg = self._command_failure_message(exc)
            if "403" in msg or "denied to" in msg:
                raise SandboxError(
                    f"git push was denied by GitHub (403). The PAT likely lacks `contents:write` on this repo. "
                    f"Branch: {session.work_branch}. Original error: {msg}"
                ) from exc
            raise SandboxError(msg) from exc

    def teardown_sandbox(self, session: SandboxSession) -> None:
        """Copy artifacts out and destroy the container."""
        try:
            self._docker_run(
                ["docker", "cp", f"{session.container_name}:/workspace/artifacts/.", str(session.artifact_dir)]
            )
        except subprocess.CalledProcessError:
            pass  # best-effort artifact copy — always destroy
        self._destroy_container(session.container_name)

    def run_happy_path(
        self, repo_source: str | Path, jira_key: str, run_id: str
    ) -> SandboxSession:
        """Start sandbox, write summary artifact, teardown. Preserves original single-shot behaviour."""
        session = self.start_sandbox(repo_source, jira_key, run_id)
        try:
            self._docker_exec(session.container_name, self._summary_artifact_command(session))
        except subprocess.CalledProcessError as exc:
            raise SandboxError(self._command_failure_message(exc)) from exc
        finally:
            self.teardown_sandbox(session)
        return session

    def _docker_exec(self, container_name: str, shell_command: str) -> None:
        # Prepend common toolchain paths so language runtimes (Go, Node, etc.)
        # are available even when the base image uses sh instead of bash.
        patched = (
            "export PATH=/usr/local/go/bin:/usr/local/bin:"
            "/root/.cargo/bin:/root/.nvm/versions/node/*/bin:$PATH && "
            + shell_command
        )
        self._docker_run(["docker", "exec", container_name, "sh", "-lc", patched])

    def _docker_run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        return self._runner.run(command)

    def _destroy_container(self, container_name: str) -> None:
        try:
            self._docker_run(["docker", "rm", "-f", container_name])
        except subprocess.CalledProcessError as exc:
            raise SandboxError(self._command_failure_message(exc)) from exc

    def _summary_artifact_command(self, session: SandboxSession) -> str:
        payload = {
            "run_id": session.run_id,
            "jira_key": session.jira_key,
            "image": session.image,
            "work_branch": session.work_branch,
            "repo_source": str(session.repo_source),
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

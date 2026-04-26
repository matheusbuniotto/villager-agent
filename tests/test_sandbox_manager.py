from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.sandbox import DEFAULT_SANDBOX_IMAGE, DockerSandboxManager, SandboxError, SandboxSession


class FakeCommandRunner:
    """Captures commands instead of running them."""

    def __init__(self) -> None:
        self.commands: list[list[str]] = []
        self._cp_outputs: dict[str, subprocess.CompletedProcess[str]] = {}

    def run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        key = " ".join(command)
        if key in self._cp_outputs:
            return self._cp_outputs[key]
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    def set_fail(self, command_prefix: str) -> None:
        def fail(cmd: list[str]) -> subprocess.CompletedProcess[str]:
            raise subprocess.CalledProcessError(
                returncode=1,
                cmd=cmd,
                stderr=f"fake failure for {command_prefix}",
            )

        self._cp_outputs[command_prefix] = fail([])  # type: ignore[arg-type]


def _make_git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    return repo


def test_happy_path_builds_result_and_runs_docker_commands(tmp_path: Path) -> None:
    repo = _make_git_repo(tmp_path)
    runner = FakeCommandRunner()
    mgr = DockerSandboxManager(runner=runner, runs_dir=tmp_path / "runs")

    result = mgr.run_happy_path(repo, jira_key="VIL-004", run_id="run-abc")

    assert result.run_id == "run-abc"
    assert result.jira_key == "VIL-004"
    assert result.image == DEFAULT_SANDBOX_IMAGE
    assert result.container_name == "villager-run-abc"
    assert result.work_branch == "villager/vil-004"
    assert result.repo_source == repo
    assert result.artifact_dir.exists()

    # Should issue: docker info, docker run, exec (git install), exec (clone),
    # exec (checkout), exec (artifact), docker cp, docker rm -f
    # (no docker image inspect — skipped for non-villager images that can be auto-pulled)
    assert len(runner.commands) == 8
    assert runner.commands[0][0:2] == ["docker", "info"]
    assert runner.commands[1][0:2] == ["docker", "run"]
    assert runner.commands[-2][0:2] == ["docker", "cp"]
    assert runner.commands[-1] == ["docker", "rm", "-f", "villager-run-abc"]


def test_non_git_repo_raises_error(tmp_path: Path) -> None:
    runner = FakeCommandRunner()
    mgr = DockerSandboxManager(runner=runner, runs_dir=tmp_path / "runs")

    with pytest.raises(SandboxError, match="must be a git repository"):
        mgr.run_happy_path(tmp_path / "not-a-repo", jira_key="VIL-004", run_id="run-1")


def test_docker_failure_raises_sandbox_error(tmp_path: Path) -> None:
    repo = _make_git_repo(tmp_path)

    class FailingRunner:
        def run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
            raise subprocess.CalledProcessError(
                returncode=1,
                cmd=command,
                stderr="no such image",
            )

    mgr = DockerSandboxManager(runner=FailingRunner(), runs_dir=tmp_path / "runs")

    with pytest.raises(SandboxError, match="no such image"):
        mgr.run_happy_path(repo, jira_key="VIL-004", run_id="run-1")


def test_container_destroyed_even_on_failure(tmp_path: Path) -> None:
    repo = _make_git_repo(tmp_path)
    runner = FakeCommandRunner()

    call_count = 0
    original_run = runner.run

    def counting_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        nonlocal call_count
        call_count += 1
        if call_count == 4:  # fail on the fourth command (clone exec, after docker info/run/git-install)
            raise subprocess.CalledProcessError(
                returncode=1,
                cmd=command,
                stderr="clone failed",
            )
        return original_run(command)

    runner.run = counting_run  # type: ignore[method-assign]
    mgr = DockerSandboxManager(runner=runner, runs_dir=tmp_path / "runs")

    with pytest.raises(SandboxError, match="clone failed"):
        mgr.run_happy_path(repo, jira_key="VIL-004", run_id="run-1")

    # Should still have issued docker rm -f as the last command
    assert runner.commands[-1] == ["docker", "rm", "-f", "villager-run-1"]


def test_container_name_sanitization() -> None:
    mgr = DockerSandboxManager()
    assert mgr._container_name("run_123") == "villager-run_123"
    assert mgr._container_name("run@123") == "villager-run-123"
    assert mgr._container_name("!!!") == "villager-run"


def test_work_branch_sanitization() -> None:
    mgr = DockerSandboxManager()
    assert mgr._work_branch("PROJ-123") == "villager/proj-123"
    assert mgr._work_branch("PROJ@123") == "villager/proj-123"
    assert mgr._work_branch("!!!") == "villager/task"


def test_summary_artifact_command_writes_json(tmp_path: Path) -> None:
    repo = _make_git_repo(tmp_path)
    runner = FakeCommandRunner()
    mgr = DockerSandboxManager(runner=runner, runs_dir=tmp_path / "runs")

    result = mgr.run_happy_path(repo, jira_key="VIL-004", run_id="run-abc")

    # Find the artifact exec command
    artifact_cmd = next(
        c for c in runner.commands if any("sandbox-summary.json" in part for part in c)
    )
    assert any("python -c" in part for part in artifact_cmd)

    # Verify the artifact directory was created locally
    assert result.artifact_dir.exists()


# --- Preflight checks ---

def test_docker_down_raises_clear_error(tmp_path: Path) -> None:
    repo = _make_git_repo(tmp_path)

    class DockerDownRunner:
        def run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
            if command[:2] == ["docker", "info"]:
                raise subprocess.CalledProcessError(
                    returncode=1, cmd=command, stderr="Cannot connect to the Docker daemon"
                )
            return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    mgr = DockerSandboxManager(runner=DockerDownRunner(), runs_dir=tmp_path / "runs")
    with pytest.raises(SandboxError, match="Docker daemon is not reachable"):
        mgr.start_sandbox(repo, jira_key="VIL-001", run_id="run-1")


def test_docker_cli_not_found_raises_clear_error(tmp_path: Path) -> None:
    repo = _make_git_repo(tmp_path)

    class NoCLIRunner:
        def run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
            if command[:2] == ["docker", "info"]:
                raise FileNotFoundError("docker not on PATH")
            return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    mgr = DockerSandboxManager(runner=NoCLIRunner(), runs_dir=tmp_path / "runs")
    with pytest.raises(SandboxError, match="docker.*CLI not found"):
        mgr.start_sandbox(repo, jira_key="VIL-001", run_id="run-1")


def test_missing_image_raises_clear_error(tmp_path: Path) -> None:
    # Only villager-prefixed images are checked locally (public images are auto-pulled by docker run)
    repo = _make_git_repo(tmp_path)

    class ImageMissingRunner:
        def run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
            if command[:3] == ["docker", "image", "inspect"]:
                raise subprocess.CalledProcessError(
                    returncode=1, cmd=command, stderr="No such image"
                )
            return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    mgr = DockerSandboxManager(runner=ImageMissingRunner(), image="villager-base:latest", runs_dir=tmp_path / "runs")
    with pytest.raises(SandboxError, match="not found locally"):
        mgr.start_sandbox(repo, jira_key="VIL-001", run_id="run-1")


def test_missing_villager_image_includes_build_hint(tmp_path: Path) -> None:
    repo = _make_git_repo(tmp_path)

    class ImageMissingRunner:
        def run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
            if command[:3] == ["docker", "image", "inspect"]:
                raise subprocess.CalledProcessError(
                    returncode=1, cmd=command, stderr="No such image"
                )
            return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    mgr = DockerSandboxManager(runner=ImageMissingRunner(), image="villager-base:latest", runs_dir=tmp_path / "runs")
    with pytest.raises(SandboxError, match="docker build"):
        mgr.start_sandbox(repo, jira_key="VIL-001", run_id="run-1")


def test_push_403_raises_friendly_error(tmp_path: Path) -> None:
    session = SandboxSession(
        run_id="run-1",
        jira_key="VIL-001",
        image="python:3.12-bookworm",
        container_name="villager-run-1",
        work_branch="villager/vil-001",
        repo_source=tmp_path,
        artifact_dir=tmp_path,
        repo_url="https://github.com/acme/repo",
    )

    class Push403Runner:
        def run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
            cmd_str = " ".join(command)
            if "git push" in cmd_str:
                raise subprocess.CalledProcessError(
                    returncode=1,
                    cmd=command,
                    stderr="remote: Permission to acme/repo.git denied to bot. The requested URL returned error: 403",
                )
            return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    mgr = DockerSandboxManager(runner=Push403Runner(), runs_dir=tmp_path / "runs")
    with pytest.raises(SandboxError, match="403.*contents:write"):
        mgr.commit_and_push(session, "VIL-001: fix something", github_pat="fake-token")


# --- Lifecycle tests (require Docker) ---

def _docker_available() -> bool:
    try:
        subprocess.run(["docker", "info"], check=True, capture_output=True, timeout=5)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _container_running(name: str) -> bool:
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", name],
        capture_output=True, text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


@pytest.mark.skipif(not _docker_available(), reason="Docker not available")
def test_start_sandbox_leaves_container_alive(tmp_path: Path) -> None:
    # needs a real git repo — use the project itself
    repo = Path(__file__).parent.parent
    mgr = DockerSandboxManager(runs_dir=tmp_path / "runs")
    session = mgr.start_sandbox(repo, jira_key="VIL-011", run_id="run-lifecycle-test")

    try:
        assert isinstance(session, SandboxSession)
        assert _container_running(session.container_name), "container should be running after start_sandbox"
        # executor can exec into it
        result = subprocess.run(
            ["docker", "exec", session.container_name, "sh", "-lc", "echo alive"],
            capture_output=True, text=True,
        )
        assert "alive" in result.stdout
    finally:
        mgr.teardown_sandbox(session)

    assert not _container_running(session.container_name), "container should be gone after teardown"

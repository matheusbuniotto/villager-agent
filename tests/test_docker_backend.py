"""Integration test — requires Docker running. Skipped if Docker unavailable."""
from __future__ import annotations

import subprocess
import uuid

import pytest

from app.executor.docker_backend import DockerExecBackend


def docker_available() -> bool:
    try:
        subprocess.run(["docker", "info"], check=True, capture_output=True, timeout=5)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


pytestmark = pytest.mark.skipif(not docker_available(), reason="Docker not available")


@pytest.fixture(scope="module")
def container():
    name = f"villager-test-{uuid.uuid4().hex[:8]}"
    subprocess.run(
        ["docker", "run", "-d", "--name", name, "python:3.12-slim", "sleep", "60"],
        check=True, capture_output=True,
    )
    # create workdir
    subprocess.run(
        ["docker", "exec", name, "mkdir", "-p", "/workspace/repo"],
        check=True, capture_output=True,
    )
    yield name
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)


def test_execute_simple_command(container: str) -> None:
    backend = DockerExecBackend(container)
    result = backend.execute("echo hello")
    assert result.exit_code == 0
    assert "hello" in result.output


def test_execute_captures_stderr(container: str) -> None:
    backend = DockerExecBackend(container)
    result = backend.execute("echo err >&2")
    assert "err" in result.output


def test_execute_nonzero_exit_on_failure(container: str) -> None:
    backend = DockerExecBackend(container)
    result = backend.execute("exit 1")
    assert result.exit_code != 0


def test_upload_and_download_file(container: str) -> None:
    backend = DockerExecBackend(container)
    content = b"hello from upload"
    path = "/workspace/repo/test_upload.txt"

    uploads = backend.upload_files([(path, content)])
    assert uploads[0].error is None

    downloads = backend.download_files([path])
    assert downloads[0].error is None
    assert downloads[0].content == content


def test_read_via_inherited_method(container: str) -> None:
    # BaseSandbox.read() is built on execute() — validates the full chain
    backend = DockerExecBackend(container)
    backend.upload_files([("/workspace/repo/hello.txt", b"world")])
    result = backend.read("/workspace/repo/hello.txt")
    assert result.error is None
    assert result.file_data is not None
    assert "world" in result.file_data["content"]

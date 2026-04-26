from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from deepagents.backends.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
)
from deepagents.backends.sandbox import BaseSandbox


_MAX_OUTPUT_CHARS = 8_000
_TRUNCATION_NOTICE = "\n\n[Output truncated to 8000 chars. Use grep/read with offset to see more.]"


class DockerExecBackend(BaseSandbox):
    """deepagents BaseSandbox backed by a running Docker container.

    All file ops (read, write, edit, grep, glob) are inherited from BaseSandbox
    and implemented via execute() — so only these 3 methods are needed.
    """

    def __init__(self, container_name: str, workdir: str = "/workspace/repo") -> None:
        self._container = container_name
        self._workdir = workdir

    @property
    def id(self) -> str:
        return self._container

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        result = subprocess.run(
            ["docker", "exec", self._container, "sh", "-lc", f"cd {self._workdir} && {command}"],
            capture_output=True,
            text=True,
            timeout=timeout or 120,
        )
        output = (result.stdout + result.stderr).strip()
        if len(output) > _MAX_OUTPUT_CHARS:
            output = output[:_MAX_OUTPUT_CHARS] + _TRUNCATION_NOTICE
        return ExecuteResponse(output=output, exit_code=result.returncode)

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        responses: list[FileUploadResponse] = []
        for path, content in files:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            try:
                subprocess.run(
                    ["docker", "cp", tmp_path, f"{self._container}:{path}"],
                    check=True,
                    capture_output=True,
                )
                responses.append(FileUploadResponse(path=path))
            except subprocess.CalledProcessError:
                responses.append(FileUploadResponse(path=path, error="permission_denied"))
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        return responses

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        responses: list[FileDownloadResponse] = []
        for path in paths:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp_path = tmp.name
            try:
                subprocess.run(
                    ["docker", "cp", f"{self._container}:{path}", tmp_path],
                    check=True,
                    capture_output=True,
                )
                responses.append(FileDownloadResponse(path=path, content=Path(tmp_path).read_bytes()))
            except subprocess.CalledProcessError:
                responses.append(FileDownloadResponse(path=path, error="file_not_found"))
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        return responses

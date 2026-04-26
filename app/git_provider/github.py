from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx


class HttpClient(Protocol):
    def post(
        self,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        """Send a POST request."""


@dataclass(slots=True)
class PullRequestRequest:
    repo_owner: str
    repo_name: str
    title: str
    body: str
    head_branch: str
    base_branch: str
    draft: bool = True


class GitHubPullRequestProvider:
    def __init__(self, token: str, client: HttpClient | None = None) -> None:
        self._token = token
        self._client = client or httpx.Client()

    def create_draft_pr(self, request: PullRequestRequest) -> dict[str, Any]:
        response = self._client.post(
            f"https://api.github.com/repos/{request.repo_owner}/{request.repo_name}/pulls",
            json={
                "title": request.title,
                "body": request.body,
                "head": request.head_branch,
                "base": request.base_branch,
                "draft": request.draft,
            },
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()


def verify_push_access(
    token: str,
    repo_owner: str,
    repo_name: str,
    client: HttpClient | None = None,
) -> None:
    """Raise PermissionError if the token cannot write to the repo's contents.

    Uses POST /git/blobs as a write-capability probe. Fine-grained PATs that
    lack `contents:write` return 403 even when the user has push role on the repo
    (a common gotcha: `permissions.push` in GET /repos reflects user role, not token scope).
    Any orphaned blob is harmless — GitHub garbage-collects unreferenced objects.
    """
    http = client or httpx.Client()
    response = http.post(
        f"https://api.github.com/repos/{repo_owner}/{repo_name}/git/blobs",
        json={"content": "dmlsbGFnZXItcHJlZmxpZ2h0", "encoding": "base64"},
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=15.0,
    )
    if response.status_code in (200, 201):
        return
    if response.status_code in (401, 403):
        message = response.json().get("message", response.text) if response.content else str(response.status_code)
        raise PermissionError(
            f"GITHUB_PAT cannot write to {repo_owner}/{repo_name}. "
            "Regenerate a fine-grained PAT with `Contents: Read and write` and "
            f"`Pull requests: Read and write`. GitHub said: {message}"
        )
    response.raise_for_status()


def parse_github_repo(repo_url: str) -> tuple[str, str]:
    normalized = repo_url
    if normalized.startswith("git@github.com:"):
        normalized = normalized.replace("git@github.com:", "https://github.com/", 1)

    parsed = urlparse(normalized)
    if parsed.netloc not in {"github.com", "www.github.com"}:
        raise ValueError(f"Unsupported GitHub URL: {repo_url}")

    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) < 2:
        raise ValueError(f"Could not determine GitHub repo from URL: {repo_url}")

    owner, repo = path_parts[0], path_parts[1].removesuffix(".git")
    return owner, repo

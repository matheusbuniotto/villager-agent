from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.git_provider import GitHubPullRequestProvider, PullRequestRequest, parse_github_repo, verify_push_access


class FakeHttpClient:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    def post(
        self,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        self.requests.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        request = httpx.Request("POST", url)
        return httpx.Response(
            201,
            request=request,
            json={
                "html_url": "https://github.com/acme/repo/pull/123",
                "number": 123,
                "draft": True,
            },
        )


def test_parse_github_repo_from_https_url() -> None:
    assert parse_github_repo("https://github.com/acme/repo.git") == ("acme", "repo")


def test_parse_github_repo_from_ssh_url() -> None:
    assert parse_github_repo("git@github.com:acme/repo.git") == ("acme", "repo")


def test_parse_github_repo_rejects_non_github_url() -> None:
    with pytest.raises(ValueError, match="Unsupported GitHub URL"):
        parse_github_repo("https://gitlab.com/acme/repo")


def test_create_draft_pr_posts_expected_payload() -> None:
    client = FakeHttpClient()
    provider = GitHubPullRequestProvider("secret-token", client=client)

    response = provider.create_draft_pr(
        PullRequestRequest(
            repo_owner="acme",
            repo_name="repo",
            title="[VIL-014] Add provider integration",
            body="PR body",
            head_branch="villager/vil-014",
            base_branch="main",
        )
    )

    assert response["number"] == 123
    request = client.requests[0]
    assert request["url"] == "https://api.github.com/repos/acme/repo/pulls"
    assert request["json"] == {
        "title": "[VIL-014] Add provider integration",
        "body": "PR body",
        "head": "villager/vil-014",
        "base": "main",
        "draft": True,
    }
    assert request["headers"] is not None
    assert request["headers"]["Authorization"] == "Bearer secret-token"


class FakeHttpClientWithStatus:
    """Returns a configurable HTTP status for POST requests."""

    def __init__(self, status_code: int, body: dict[str, Any] | None = None) -> None:
        self._status_code = status_code
        self._body = body or {}

    def post(
        self,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        request = httpx.Request("POST", url)
        return httpx.Response(self._status_code, request=request, json=self._body)


def test_verify_push_access_succeeds_on_201() -> None:
    client = FakeHttpClientWithStatus(201, {"sha": "abc123"})
    # Should not raise
    verify_push_access("valid-token", "acme", "repo", client=client)


def test_verify_push_access_raises_on_403() -> None:
    client = FakeHttpClientWithStatus(
        403,
        {"message": "Resource not accessible by personal access token"},
    )
    with pytest.raises(PermissionError, match="GITHUB_PAT cannot write to acme/repo"):
        verify_push_access("readonly-token", "acme", "repo", client=client)


def test_verify_push_access_raises_on_401() -> None:
    client = FakeHttpClientWithStatus(401, {"message": "Bad credentials"})
    with pytest.raises(PermissionError, match="Bad credentials"):
        verify_push_access("bad-token", "acme", "repo", client=client)


def test_verify_push_access_error_message_names_repo() -> None:
    client = FakeHttpClientWithStatus(403, {"message": "Not authorized"})
    with pytest.raises(PermissionError, match="acme/my-repo"):
        verify_push_access("token", "acme", "my-repo", client=client)


def test_verify_push_access_error_mentions_pat_fix() -> None:
    client = FakeHttpClientWithStatus(403, {"message": "Forbidden"})
    with pytest.raises(PermissionError, match="Contents: Read and write"):
        verify_push_access("token", "acme", "repo", client=client)

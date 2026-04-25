from __future__ import annotations

import base64
import os
from typing import Any

import httpx


class JiraConfigError(ValueError):
    """Raised when JIRA configuration is missing or invalid."""


class JiraApiError(RuntimeError):
    """Raised when a JIRA API call fails."""


class JiraClient:
    """Minimal JIRA Cloud REST API client."""

    def __init__(
        self,
        base_url: str | None = None,
        email: str | None = None,
        api_token: str | None = None,
    ) -> None:
        self._base_url = (base_url or os.environ.get("VILLAGER_JIRA_BASE_URL", "")).rstrip("/")
        self._email = email or os.environ.get("VILLAGER_JIRA_EMAIL", "")
        self._api_token = api_token or os.environ.get("VILLAGER_JIRA_API_TOKEN", "")

        if not self._base_url:
            raise JiraConfigError(
                "VILLAGER_JIRA_BASE_URL is required (e.g., https://yourdomain.atlassian.net)"
            )
        if not self._email:
            raise JiraConfigError("VILLAGER_JIRA_EMAIL is required")
        if not self._api_token:
            raise JiraConfigError("VILLAGER_JIRA_API_TOKEN is required")

    def _auth_header(self) -> str:
        credentials = base64.b64encode(f"{self._email}:{self._api_token}".encode()).decode()
        return f"Basic {credentials}"

    def get_issue(self, issue_key: str) -> dict[str, Any]:
        url = f"{self._base_url}/rest/api/2/issue/{issue_key}"
        headers = {
            "Authorization": self._auth_header(),
            "Accept": "application/json",
        }
        try:
            response = httpx.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            detail = exc.response.text[:200]
            raise JiraApiError(f"JIRA API error for {issue_key}: HTTP {status} — {detail}") from exc
        except httpx.RequestError as exc:
            raise JiraApiError(f"JIRA request failed for {issue_key}: {exc}") from exc

        return response.json()

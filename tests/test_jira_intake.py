from __future__ import annotations

import os
from typing import Any
from unittest.mock import patch

import pytest

from app.intake import JiraApiError, JiraClient, JiraConfigError, fetch_task, normalize_issue
from app.schemas import TaskPacket


class TestJiraClient:
    def test_missing_base_url_raises(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(JiraConfigError, match="VILLAGER_JIRA_BASE_URL"):
                JiraClient()

    def test_missing_email_raises(self) -> None:
        with patch.dict(
            os.environ, {"VILLAGER_JIRA_BASE_URL": "https://x.atlassian.net"}, clear=True
        ):
            with pytest.raises(JiraConfigError, match="VILLAGER_JIRA_EMAIL"):
                JiraClient()

    def test_missing_token_raises(self) -> None:
        with patch.dict(
            os.environ,
            {"VILLAGER_JIRA_BASE_URL": "https://x.atlassian.net", "VILLAGER_JIRA_EMAIL": "a@b.com"},
            clear=True,
        ):
            with pytest.raises(JiraConfigError, match="VILLAGER_JIRA_API_TOKEN"):
                JiraClient()

    def test_get_issue_success(self) -> None:
        client = JiraClient(
            base_url="https://x.atlassian.net",
            email="a@b.com",
            api_token="tok",
        )
        mock_response: dict[str, Any] = {"key": "VIL-006", "fields": {"summary": "Test"}}

        with patch("app.intake.jira_client.httpx.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = mock_response
            mock_get.return_value.raise_for_status = lambda: None

            result = client.get_issue("VIL-006")

        assert result["key"] == "VIL-006"
        mock_get.assert_called_once()
        url = mock_get.call_args[0][0]
        assert "rest/api/2/issue/VIL-006" in url

    def test_get_issue_http_error(self) -> None:
        client = JiraClient(
            base_url="https://x.atlassian.net",
            email="a@b.com",
            api_token="tok",
        )

        with patch("app.intake.jira_client.httpx.get") as mock_get:
            from httpx import Request, Response

            request = Request("GET", "https://x.atlassian.net/rest/api/2/issue/VIL-006")
            response = Response(404, text="Issue not found", request=request)
            mock_get.return_value = response
            mock_get.return_value.raise_for_status = response.raise_for_status

            with pytest.raises(JiraApiError, match="VIL-006"):
                client.get_issue("VIL-006")


class TestNormalizer:
    def test_normalize_basic_issue(self) -> None:
        issue = {
            "key": "VIL-006",
            "fields": {
                "summary": "Implement JIRA adapter",
                "description": "Fetch and normalize JIRA issues.",
                "priority": {"name": "High"},
                "assignee": {"displayName": "Alice"},
                "reporter": {"displayName": "Bob"},
                "labels": ["backend", "villager"],
                "components": [{"name": "api"}],
            },
        }

        packet = normalize_issue(issue)

        assert isinstance(packet, TaskPacket)
        assert packet.source_issue_key == "VIL-006"
        assert packet.title == "Implement JIRA adapter"
        assert packet.priority == "high"
        assert packet.assignee == "Alice"
        assert packet.reporter == "Bob"
        assert packet.labels == ["backend", "villager"]
        assert packet.linked_services == ["api"]

    def test_extract_repo_from_description(self) -> None:
        issue = {
            "key": "VIL-006",
            "fields": {
                "summary": "Test",
                "description": "Fix bug.\n\nRepo: example",
            },
        }

        packet = normalize_issue(issue)
        assert packet.repo == "example"

    def test_extract_repo_from_github_url(self) -> None:
        issue = {
            "key": "VIL-006",
            "fields": {
                "summary": "Test",
                "description": "See https://github.com/acme/billing-service for context.",
            },
        }

        packet = normalize_issue(issue)
        assert packet.repo == "billing-service"

    def test_extract_repo_from_github_url_with_git_suffix(self) -> None:
        issue = {
            "key": "VIL-006",
            "fields": {
                "summary": "Test",
                "description": "Clone git@github.com:acme/payments.git",
            },
        }

        packet = normalize_issue(issue)
        assert packet.repo == "payments"

    def test_extract_repo_from_jira_smart_link(self) -> None:
        issue = {
            "key": "VIL-006",
            "fields": {
                "summary": "Test",
                "description": "repo [https://github.com/acme/billing|https://github.com/acme/billing|smart-link]",
            },
        }

        packet = normalize_issue(issue)
        assert packet.repo == "billing"

    def test_extract_acceptance_criteria(self) -> None:
        issue = {
            "key": "VIL-006",
            "fields": {
                "summary": "Test",
                "description": (
                    "Do something.\n\n"
                    "Acceptance Criteria:\n"
                    "- First thing\n"
                    "- Second thing\n\n"
                    "Notes: extra"
                ),
            },
        }

        packet = normalize_issue(issue)
        assert packet.acceptance_criteria == ["First thing", "Second thing"]

    def test_extract_repo_from_adf_inline_card(self) -> None:
        issue = {
            "key": "VIL-006",
            "fields": {
                "summary": "Test",
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {"type": "text", "text": "Repo: "},
                                {
                                    "type": "inlineCard",
                                    "attrs": {"url": "https://github.com/acme/my-service"},
                                },
                            ],
                        }
                    ],
                },
            },
        }

        packet = normalize_issue(issue)
        assert packet.repo == "my-service"

    def test_normalize_adf_description(self) -> None:
        issue = {
            "key": "VIL-006",
            "fields": {
                "summary": "Test",
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": "Hello world"}],
                        }
                    ],
                },
            },
        }

        packet = normalize_issue(issue)
        assert "Hello world" in packet.description

    def test_missing_fields_use_defaults(self) -> None:
        issue = {"key": "VIL-006", "fields": {}}

        packet = normalize_issue(issue)
        assert packet.title == "Issue VIL-006"
        assert packet.priority == "medium"
        assert packet.assignee is None
        assert packet.repo == "unknown"


class TestFetchTask:
    def test_fallback_to_stub_without_credentials(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            packet = fetch_task("VIL-006")

        assert packet.source_issue_key == "VIL-006"
        assert packet.title == "Stub task for VIL-006"

    def test_uses_jira_when_configured(self) -> None:
        with patch.dict(
            os.environ,
            {
                "VILLAGER_JIRA_BASE_URL": "https://x.atlassian.net",
                "VILLAGER_JIRA_EMAIL": "a@b.com",
                "VILLAGER_JIRA_API_TOKEN": "tok",
            },
            clear=True,
        ):
            with patch("app.intake.jira_client.httpx.get") as mock_get:
                mock_get.return_value.status_code = 200
                mock_get.return_value.json.return_value = {
                    "key": "VIL-006",
                    "fields": {"summary": "Real issue"},
                }
                mock_get.return_value.raise_for_status = lambda: None

                packet = fetch_task("VIL-006")

        assert packet.title == "Real issue"

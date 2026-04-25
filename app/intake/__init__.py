"""Intake module."""

from app.intake.jira_client import JiraApiError, JiraClient, JiraConfigError
from app.intake.normalizer import normalize_issue
from app.intake.stub import fetch_task as _stub_fetch_task
from app.schemas import TaskPacket

__all__ = [
    "JiraApiError",
    "JiraClient",
    "JiraConfigError",
    "fetch_task",
    "normalize_issue",
]


def fetch_task(jira_key: str) -> TaskPacket:
    """Fetch a JIRA issue and normalize it to a TaskPacket.

    Falls back to the stub if JIRA credentials are not configured.
    """
    try:
        client = JiraClient()
    except JiraConfigError:
        return _stub_fetch_task(jira_key)

    issue = client.get_issue(jira_key)
    return normalize_issue(issue)

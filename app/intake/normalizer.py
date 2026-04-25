from __future__ import annotations

import re
from typing import Any, cast

from app.schemas import Priority, TaskPacket


def _extract_text_from_adf(node: Any) -> str:
    """Flatten an Atlassian Document Format description into plain text."""
    if isinstance(node, str):
        return node
    if not isinstance(node, dict):
        return ""

    text_parts: list[str] = []
    content = node.get("content", [])
    for child in content:
        text_parts.append(_extract_text_from_adf(child))

    if node.get("type") == "text":
        text = node.get("text", "")
        if node.get("marks"):
            text = f"*{text}*"
        text_parts.append(text)

    return "\n".join(part for part in text_parts if part)


def _plain_description(description: Any) -> str:
    """Convert JIRA description field to plain text."""
    if isinstance(description, str):
        return description
    if isinstance(description, dict):
        return _extract_text_from_adf(description)
    return ""


_GITHUB_URL_RE = re.compile(r"github\.com[/:](?:[^/\s]+/)?([^/\s|]+)")


def _extract_repo(description_text: str) -> str | None:
    """Look for 'Repo: <name>', 'Repository: <name>', or github.com URL in description."""
    for pattern in (r"Repo:\s*(\S+)", r"Repository:\s*(\S+)"):
        match = re.search(pattern, description_text, re.IGNORECASE)
        if match:
            return match.group(1)

    url_match = _GITHUB_URL_RE.search(description_text)
    if url_match:
        repo = url_match.group(1)
        return repo.removesuffix(".git")

    return None


def _extract_acceptance_criteria(description_text: str) -> list[str]:
    """Look for an 'Acceptance Criteria' section and extract bullet items."""
    lines = description_text.splitlines()
    in_section = False
    criteria: list[str] = []
    for line in lines:
        stripped = line.strip()
        if re.match(r"^#{0,2}\s*Acceptance Criteria", stripped, re.IGNORECASE):
            in_section = True
            continue
        if in_section:
            if not stripped or stripped.startswith("#"):
                break
            if stripped.startswith(("-", "*")):
                criteria.append(stripped.lstrip("-* ").strip())
            elif stripped[0].isdigit() and "." in stripped[:3]:
                criteria.append(stripped.split(".", 1)[1].strip())
    return criteria


def _map_priority(jira_priority: str | None) -> Priority:
    mapping = {
        "highest": "critical",
        "high": "high",
        "medium": "medium",
        "low": "low",
        "lowest": "low",
    }
    return cast(Priority, mapping.get((jira_priority or "").lower(), "medium"))


def normalize_issue(issue: dict[str, Any]) -> TaskPacket:
    """Convert a JIRA issue JSON dict into a TaskPacket."""
    fields = issue.get("fields", {})
    key = issue.get("key", "UNKNOWN")

    description_raw = fields.get("description")
    description_text = _plain_description(description_raw)

    repo = _extract_repo(description_text) or "unknown"
    acceptance_criteria = _extract_acceptance_criteria(description_text)

    priority_name: str | None = None
    priority_field = fields.get("priority")
    if isinstance(priority_field, dict):
        priority_name = priority_field.get("name")

    assignee: str | None = None
    assignee_field = fields.get("assignee")
    if isinstance(assignee_field, dict):
        assignee = assignee_field.get("displayName")

    reporter: str | None = None
    reporter_field = fields.get("reporter")
    if isinstance(reporter_field, dict):
        reporter = reporter_field.get("displayName")

    labels: list[str] = []
    raw_labels = fields.get("labels", [])
    if isinstance(raw_labels, list):
        labels = [str(label) for label in raw_labels]

    components: list[str] = []
    raw_components = fields.get("components", [])
    if isinstance(raw_components, list):
        for comp in raw_components:
            if isinstance(comp, dict):
                name = comp.get("name")
                if name:
                    components.append(str(name))

    return TaskPacket(
        task_id=f"task-{key.lower()}",
        source="jira",
        source_issue_key=key,
        title=fields.get("summary", f"Issue {key}"),
        description=description_text or "No description provided.",
        repo=repo,
        requested_outcome="Implement the requested change.",
        priority=_map_priority(priority_name),
        risk_level="low",
        labels=labels,
        acceptance_criteria=acceptance_criteria,
        assignee=assignee,
        reporter=reporter,
        linked_services=components,
    )

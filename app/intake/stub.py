from __future__ import annotations

from app.schemas import TaskPacket


def fetch_task(jira_key: str) -> TaskPacket:
    """Stub intake: build a TaskPacket from a JIRA key."""
    return TaskPacket(
        task_id=f"task-{jira_key.lower()}",
        source="jira",
        source_issue_key=jira_key,
        title=f"Stub task for {jira_key}",
        description="This is a stub intake response. Replace with real JIRA adapter.",
        repo="unknown",
        requested_outcome="Implement the requested change.",
        priority="medium",
        risk_level="low",
        labels=["villager", "stub"],
        acceptance_criteria=["Stub criterion: behavior works"],
    )

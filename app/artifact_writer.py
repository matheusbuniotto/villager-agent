from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from app.schemas import (
    ExecutionSpec,
    RunRecord,
    TaskPacket,
    ValidationReport,
)


class ArtifactWriter:
    """Write run artifacts to a local run folder."""

    def __init__(self, run_dir: str | Path) -> None:
        self._run_dir = Path(run_dir)
        self._run_dir.mkdir(parents=True, exist_ok=True)

    def write_json(self, filename: str, obj: object) -> Path:
        """Serialize a dataclass to indented JSON."""
        path = self._run_dir / filename
        data = asdict(obj)  # type: ignore[arg-type]
        for key, value in list(data.items()):
            if isinstance(value, datetime):
                data[key] = value.isoformat()
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return path

    def write_text(self, filename: str, content: str) -> Path:
        """Write plain text to a file."""
        path = self._run_dir / filename
        path.write_text(content + "\n", encoding="utf-8")
        return path

    def write_metrics(self, data: dict[str, object]) -> Path:
        """Write metrics.json to the run folder."""
        path = self._run_dir / "metrics.json"
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return path

    def write_summary_md(
        self,
        run_record: RunRecord,
        task: TaskPacket,
        spec: ExecutionSpec,
        validation: ValidationReport | None = None,
    ) -> Path:
        """Write a human-readable summary markdown file."""
        lines: list[str] = [
            f"# Run {run_record.run_id}",
            "",
            f"- **JIRA:** {run_record.task_id}",
            f"- **Repo:** {run_record.repo_name}",
            f"- **State:** {run_record.state}",
            f"- **Started:** {run_record.created_at.isoformat()}",
            "",
            "## Task",
            "",
            f"**Title:** {task.title}",
            "",
            f"**Description:** {task.description}",
            "",
            f"**Priority:** {task.priority}",
            "",
            "## Spec",
            "",
            f"**Type:** {spec.problem_statement}",
            "",
            "**Target areas:**",
            *(f"- {area}" for area in spec.target_areas),
            "",
            "**Acceptance criteria:**",
            *(f"- {ac}" for ac in spec.acceptance_criteria),
            "",
        ]

        if validation:
            lines.extend(
                [
                    "## Validation",
                    "",
                    f"**Status:** {validation.status}",
                    f"**Summary:** {validation.summary}",
                    "",
                    "**Mechanical checks:**",
                    *(f"- {c.name}: {c.status}" for c in validation.mechanical_checks),
                    "",
                    "**Policy checks:**",
                    *(f"- {c.name}: {c.status}" for c in validation.policy_checks),
                    "",
                ]
            )

        content = "\n".join(lines)
        return self.write_text("summary.md", content)

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, cast

from app.schemas import RunRecord, RunStateTransition


class StateStore(Protocol):
    def write_run(self, record: RunRecord) -> Path:
        """Persist the latest snapshot for a run."""
        ...

    def append_transition(self, transition: RunStateTransition) -> Path:
        """Append a state transition event."""
        ...

    def get_run(self, run_id: str) -> RunRecord | None:
        """Return the latest stored snapshot for a run."""
        ...

    def list_transitions(self, run_id: str) -> list[RunStateTransition]:
        """Return stored transitions for a run in append order."""
        ...


class JsonlStateStore:
    """Persist run state as append-only JSONL files."""

    def __init__(self, root_dir: str | Path) -> None:
        self._root_dir = Path(root_dir)
        self._root_dir.mkdir(parents=True, exist_ok=True)
        self._run_records_path = self._root_dir / "run-records.jsonl"
        self._run_transitions_path = self._root_dir / "run-transitions.jsonl"

    @property
    def run_records_path(self) -> Path:
        return self._run_records_path

    @property
    def run_transitions_path(self) -> Path:
        return self._run_transitions_path

    def write_run(self, record: RunRecord) -> Path:
        self._append_jsonl(self._run_records_path, _to_jsonable(record))
        return self._run_records_path

    def append_transition(self, transition: RunStateTransition) -> Path:
        self._append_jsonl(self._run_transitions_path, _to_jsonable(transition))
        return self._run_transitions_path

    def get_run(self, run_id: str) -> RunRecord | None:
        latest: RunRecord | None = None
        for payload in self._iter_jsonl(self._run_records_path):
            if payload.get("run_id") == run_id:
                latest = _run_record_from_dict(payload)
        return latest

    def list_transitions(self, run_id: str) -> list[RunStateTransition]:
        transitions: list[RunStateTransition] = []
        for payload in self._iter_jsonl(self._run_transitions_path):
            if payload.get("run_id") == run_id:
                transitions.append(_run_transition_from_dict(payload))
        return transitions

    @staticmethod
    def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")

    @staticmethod
    def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return _to_jsonable(asdict(cast(Any, value)))
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    return value


def _run_record_from_dict(payload: dict[str, Any]) -> RunRecord:
    return RunRecord(
        run_id=payload["run_id"],
        task_id=payload["task_id"],
        repo_name=payload["repo_name"],
        state=payload["state"],
        created_at=datetime.fromisoformat(payload["created_at"]),
        updated_at=datetime.fromisoformat(payload["updated_at"]),
        retry_count=payload.get("retry_count", 0),
        task_packet_ref=payload.get("task_packet_ref"),
        profile_ref=payload.get("profile_ref"),
        spec_ref=payload.get("spec_ref"),
        validation_report_ref=payload.get("validation_report_ref"),
        review_decision_ref=payload.get("review_decision_ref"),
        artifact_bundle_ref=payload.get("artifact_bundle_ref"),
        summary_ref=payload.get("summary_ref"),
        pr_ref=payload.get("pr_ref"),
        pr_url=payload.get("pr_url"),
        final_outcome=payload.get("final_outcome"),
    )


def _run_transition_from_dict(payload: dict[str, Any]) -> RunStateTransition:
    return RunStateTransition(
        run_id=payload["run_id"],
        from_state=payload.get("from_state"),
        to_state=payload["to_state"],
        occurred_at=datetime.fromisoformat(payload["occurred_at"]),
        reason=payload.get("reason"),
    )

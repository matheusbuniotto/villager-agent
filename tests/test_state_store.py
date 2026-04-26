from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.schemas import RunRecord, RunStateTransition
from app.state_store import JsonlStateStore


def test_jsonl_state_store_round_trips_latest_run_snapshot(tmp_path: Path) -> None:
    store = JsonlStateStore(tmp_path)
    first = RunRecord(
        run_id="run-001",
        task_id="VIL-013",
        repo_name="example",
        state="INTAKE",
        created_at=datetime(2026, 4, 25, 23, 0, tzinfo=UTC),
        updated_at=datetime(2026, 4, 25, 23, 0, tzinfo=UTC),
    )
    second = RunRecord(
        run_id="run-001",
        task_id="VIL-013",
        repo_name="example",
        state="DONE",
        created_at=first.created_at,
        updated_at=datetime(2026, 4, 25, 23, 5, tzinfo=UTC),
        validation_report_ref="runs/run-001/validation.json",
        summary_ref="runs/run-001/summary.md",
        pr_ref="runs/run-001/pr.md",
    )

    store.write_run(first)
    store.write_run(second)

    latest = store.get_run("run-001")

    assert latest is not None
    assert latest.state == "DONE"
    assert latest.validation_report_ref == "runs/run-001/validation.json"
    assert latest.summary_ref == "runs/run-001/summary.md"
    assert latest.pr_ref == "runs/run-001/pr.md"


def test_jsonl_state_store_lists_run_transitions(tmp_path: Path) -> None:
    store = JsonlStateStore(tmp_path)
    store.append_transition(
        RunStateTransition(
            run_id="run-001",
            from_state=None,
            to_state="INTAKE",
            occurred_at=datetime(2026, 4, 25, 23, 0, tzinfo=UTC),
        )
    )
    store.append_transition(
        RunStateTransition(
            run_id="run-001",
            from_state="INTAKE",
            to_state="SPEC_READY",
            occurred_at=datetime(2026, 4, 25, 23, 1, tzinfo=UTC),
            reason="spec built",
        )
    )

    transitions = store.list_transitions("run-001")

    assert [transition.to_state for transition in transitions] == ["INTAKE", "SPEC_READY"]
    assert transitions[1].reason == "spec built"

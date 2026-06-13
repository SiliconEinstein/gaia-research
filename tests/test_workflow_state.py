"""Report workflow state contract tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gaia_research.workflow_state import (
    ReportRunState,
    create_report_run,
    read_state,
    record_event,
    resume_report_run,
    write_state,
)


def test_create_report_run_writes_expected_research_run_directories(tmp_path: Path) -> None:
    workspace = tmp_path / "aspirin-workspace"

    handle, state = create_report_run(
        workspace,
        topic="aspirin primary prevention",
        profile="fast",
        run_id="aspirin-fast",
    )

    assert handle.workspace == workspace.resolve()
    assert handle.run_id == "aspirin-fast"
    assert handle.run_dir == workspace.resolve() / ".gaia" / "research" / "runs" / "aspirin-fast"
    assert handle.state_path == handle.run_dir / "state.json"
    assert handle.events_path == handle.run_dir / "events.ndjson"
    assert handle.landscape_dir == handle.run_dir / "landscape"
    assert handle.field_map_dir == handle.run_dir / "field_map"
    assert handle.focuses_dir == handle.run_dir / "focuses"
    assert handle.assessments_dir == handle.run_dir / "assessments"
    assert handle.materialization_dir == handle.run_dir / "materialization"
    assert handle.reports_dir == handle.run_dir / "reports"

    for directory in (
        handle.landscape_dir,
        handle.field_map_dir,
        handle.focuses_dir,
        handle.assessments_dir,
        handle.materialization_dir,
        handle.reports_dir,
    ):
        assert directory.is_dir()

    assert state.run_id == "aspirin-fast"
    assert state.topic == "aspirin primary prevention"
    assert state.profile == "fast"
    assert state.status == "running"
    assert state.phase == "setup"
    assert state.artifacts == {
        "landscape": str(handle.landscape_dir),
        "field_map": str(handle.field_map_dir),
        "focuses": str(handle.focuses_dir),
        "assessments": str(handle.assessments_dir),
        "materialization": str(handle.materialization_dir),
        "reports": str(handle.reports_dir),
    }

    persisted = json.loads(handle.state_path.read_text(encoding="utf-8"))
    assert persisted["schema_version"] == 1
    assert persisted["run_id"] == "aspirin-fast"
    assert persisted["topic"] == "aspirin primary prevention"
    assert persisted["profile"] == "fast"
    assert persisted["status"] == "running"
    assert persisted["phase"] == "setup"
    assert persisted["artifacts"] == state.artifacts


def test_write_and_read_state_round_trip(tmp_path: Path) -> None:
    handle, state = create_report_run(
        tmp_path / "workspace",
        topic="dqcp landscape",
        profile="review",
        run_id="dqcp-review",
    )
    updated = ReportRunState(
        run_id=state.run_id,
        topic=state.topic,
        profile=state.profile,
        status="completed",
        phase="report",
        created_at=state.created_at,
        updated_at="2026-06-13T00:00:00Z",
        artifacts={**state.artifacts, "final_report": str(handle.reports_dir / "final.md")},
    )

    write_state(handle, updated)

    assert read_state(handle) == updated


def test_record_event_appends_one_json_line_per_event(tmp_path: Path) -> None:
    handle, _state = create_report_run(
        tmp_path / "workspace",
        topic="mendel inheritance",
        profile="fast",
        run_id="mendel-fast",
    )

    first = record_event(handle, "landscape.started", phase="landscape")
    second = record_event(
        handle,
        "landscape.completed",
        phase="landscape",
        payload={"paper_leads": 3},
    )

    events = [
        json.loads(line) for line in handle.events_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [event["type"] for event in events] == [
        "run.created",
        "landscape.started",
        "landscape.completed",
    ]
    assert first["run_id"] == "mendel-fast"
    assert second["paper_leads"] == 3


def test_resume_report_run_rejects_missing_state(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        resume_report_run(tmp_path / "workspace", "missing-run")

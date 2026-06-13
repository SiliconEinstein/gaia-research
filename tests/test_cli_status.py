"""CLI tests for report workflow run status."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gaia_research import cli
from gaia_research.workflow_state import create_report_run, record_event


def test_review_command_is_not_registered(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["review"])

    assert exc_info.value.code == 2
    assert "invalid choice: 'review'" in capsys.readouterr().err


def test_status_command_reads_report_workflow_state(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = tmp_path / "workspace"
    create_report_run(
        workspace,
        topic="aspirin primary prevention",
        profile="fast",
        run_id="aspirin-fast",
    )
    record_event(
        create_report_run(
            workspace,
            topic="secondary run",
            profile="fast",
            run_id="secondary-run",
        )[0],
        "landscape.started",
        phase="landscape",
    )

    exit_code = cli.main(["status", "--path", str(workspace), "--run-id", "aspirin-fast"])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "report run: aspirin-fast" in out
    assert "status: running" in out
    assert "phase: setup" in out
    assert "events: 1" in out


def test_status_command_can_emit_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = tmp_path / "workspace"
    handle, _state = create_report_run(
        workspace,
        topic="dqcp",
        profile="fast",
        run_id="dqcp-fast",
    )
    record_event(handle, "landscape.started", phase="landscape")

    exit_code = cli.main(["status", "--path", str(workspace), "--run-id", "dqcp-fast", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "run_id": "dqcp-fast",
        "status": "running",
        "phase": "setup",
        "run_dir": str(handle.run_dir),
        "events": 2,
        "artifacts": {
            "landscape": str(handle.landscape_dir),
            "field_map": str(handle.field_map_dir),
            "focuses": str(handle.focuses_dir),
            "assessments": str(handle.assessments_dir),
            "materialization": str(handle.materialization_dir),
            "reports": str(handle.reports_dir),
        },
    }

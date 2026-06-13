"""Gaia CLI plugin contracts for gaia-research."""

from __future__ import annotations

import json
from importlib import metadata
from pathlib import Path

import typer
from typer.testing import CliRunner

from gaia_research.workflow_state import create_report_run, record_event


def test_distribution_exposes_gaia_cli_plugin_entry_point() -> None:
    entry_points = metadata.distribution("gaia-research").entry_points
    matches = [
        entry_point
        for entry_point in entry_points
        if entry_point.group == "gaia.cli_plugins" and entry_point.name == "research"
    ]

    assert len(matches) == 1
    assert matches[0].value == "gaia_research.plugin:register"


def test_plugin_review_command_is_not_registered() -> None:
    from gaia_research import plugin

    root_app = typer.Typer(name="gaia")
    plugin.register(root_app)

    result = CliRunner().invoke(root_app, ["research", "review"])

    assert result.exit_code != 0
    assert "No such command" in result.output


def test_plugin_report_command_is_not_registered() -> None:
    from gaia_research import plugin

    root_app = typer.Typer(name="gaia")
    plugin.register(root_app)

    result = CliRunner().invoke(root_app, ["research", "report"])

    assert result.exit_code != 0
    assert "No such command" in result.output


def test_plugin_status_command_reads_report_workflow_state(tmp_path: Path) -> None:
    from gaia_research import plugin

    workspace = tmp_path / "workspace"
    handle, _state = create_report_run(
        workspace,
        topic="dqcp",
        profile="fast",
        run_id="dqcp-fast",
    )
    record_event(handle, "landscape.started", phase="landscape")

    root_app = typer.Typer(name="gaia")
    plugin.register(root_app)
    result = CliRunner().invoke(
        root_app,
        ["research", "status", str(workspace), "--run-id", "dqcp-fast"],
    )

    assert result.exit_code == 0
    assert "report run: dqcp-fast" in result.stdout
    assert "status: running" in result.stdout
    assert "phase: setup" in result.stdout
    assert "events: 2" in result.stdout


def test_plugin_status_command_can_emit_json(tmp_path: Path) -> None:
    from gaia_research import plugin

    workspace = tmp_path / "workspace"
    handle, _state = create_report_run(
        workspace,
        topic="aspirin",
        profile="fast",
        run_id="aspirin-fast",
    )

    root_app = typer.Typer(name="gaia")
    plugin.register(root_app)
    result = CliRunner().invoke(
        root_app,
        ["research", "status", str(workspace), "--run-id", "aspirin-fast", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == {
        "run_id": "aspirin-fast",
        "status": "running",
        "phase": "setup",
        "run_dir": str(handle.run_dir),
        "events": 1,
        "artifacts": {
            "landscape": str(handle.landscape_dir),
            "field_map": str(handle.field_map_dir),
            "focuses": str(handle.focuses_dir),
            "assessments": str(handle.assessments_dir),
            "materialization": str(handle.materialization_dir),
            "reports": str(handle.reports_dir),
        },
    }

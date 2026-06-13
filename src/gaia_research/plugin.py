"""Gaia CLI plugin registration for the external research package."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from gaia_research.contracts import CORE_PUBLIC_SURFACES, verify_core_contract
from gaia_research.workflow_state import read_events, resume_report_run

research_app = typer.Typer(
    name="research",
    help="Gaia Research workflows shipped by the gaia-research package.",
    no_args_is_help=True,
)
_PATH_ARGUMENT = typer.Argument(Path("."), help="Gaia package path.")
_STATUS_RUN_ID_OPTION = typer.Option(None, "--run-id", help="Report workflow run id.")
_JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")


@research_app.command(name="doctor")
def doctor_command() -> None:
    """Check that gaia-research can see the Gaia core surfaces it needs."""
    surfaces = verify_core_contract()
    typer.echo("gaia-research doctor OK")
    for surface in surfaces:
        typer.echo(f"- {surface}")


@research_app.command(name="status")
def status_command(
    path: Path = _PATH_ARGUMENT,
    run_id: str | None = _STATUS_RUN_ID_OPTION,
    json_out: bool = _JSON_OPTION,
) -> None:
    """Report bootstrap status for the package-local research namespace."""
    if run_id is not None:
        try:
            payload = _report_run_status_payload(path, run_id)
        except (FileNotFoundError, ValueError) as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(1) from exc
        if json_out:
            typer.echo(json.dumps(payload, indent=2))
        else:
            _echo_report_run_status(payload)
        return

    research_dir = path / ".gaia" / "research"
    typer.echo(f"research namespace: {research_dir}")
    typer.echo(f"core surfaces: {len(CORE_PUBLIC_SURFACES)}")


def _echo_report_run_status(payload: dict[str, object]) -> None:
    typer.echo(f"report run: {payload['run_id']}")
    typer.echo(f"status: {payload['status']}")
    typer.echo(f"phase: {payload['phase']}")
    typer.echo(f"run_dir: {payload['run_dir']}")
    typer.echo(f"events: {payload['events']}")


def _report_run_status_payload(path: Path, run_id: str) -> dict[str, object]:
    handle, state = resume_report_run(path, run_id)
    return {
        "run_id": handle.run_id,
        "status": state.status,
        "phase": state.phase,
        "run_dir": str(handle.run_dir),
        "events": len(read_events(handle)),
        "artifacts": dict(state.artifacts),
    }


def register(root_app: typer.Typer) -> None:
    """Register the external ``gaia research`` command group."""
    root_app.add_typer(research_app, name="research")

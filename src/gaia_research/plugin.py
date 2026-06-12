"""Gaia CLI plugin registration for the external research package."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from gaia_research.contracts import CORE_PUBLIC_SURFACES, verify_core_contract
from gaia_research.review import ReviewRunError, read_review_run
from gaia_research.runner import ReviewRunnerError, run_package_review

research_app = typer.Typer(
    name="research",
    help="Gaia Research workflows shipped by the gaia-research package.",
    no_args_is_help=True,
)
_PATH_ARGUMENT = typer.Argument(Path("."), help="Gaia package path.")
_PATH_OPTION = typer.Option(Path("."), "--path", help="Gaia package path.")
_TOPIC_OPTION = typer.Option(..., "--topic", help="Review-run topic.")
_PROFILE_OPTION = typer.Option("quick", "--profile", help="Review profile label.")
_RUN_ID_OPTION = typer.Option(None, "--run-id", help="Stable run id.")
_LANGUAGE_OPTION = typer.Option("zh", "--language", help="Run language metadata.")
_FOCUS_OPTION = typer.Option(None, "--focus", help="Inquiry focus override.")
_MODE_OPTION = typer.Option("auto", "--mode", help="Gaia inquiry review mode.")
_NO_INFER_OPTION = typer.Option(False, "--no-infer", help="Skip inference.")
_DEPTH_OPTION = typer.Option(0, "--depth", help="Dependency depth for review.")
_SINCE_OPTION = typer.Option(None, "--since", help="Baseline review id.")
_STRICT_OPTION = typer.Option(False, "--strict", help="Enable strict review mode.")
_STATUS_RUN_ID_OPTION = typer.Option(None, "--run-id", help="Review run id.")
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
            snapshot = read_review_run(path, run_id)
        except (FileNotFoundError, ReviewRunError) as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(1) from exc
        if json_out:
            typer.echo(json.dumps(_review_run_status_payload(snapshot), indent=2))
        else:
            _echo_review_run_status(snapshot)
        return

    research_dir = path / ".gaia" / "research"
    typer.echo(f"research namespace: {research_dir}")
    typer.echo(f"core surfaces: {len(CORE_PUBLIC_SURFACES)}")


def _echo_review_run_status(snapshot: Any) -> None:
    payload = _review_run_status_payload(snapshot)
    typer.echo(f"review run: {payload['run_id']}")
    typer.echo(f"status: {payload['status']}")
    typer.echo(f"phase: {payload['phase']}")
    typer.echo(f"run_dir: {payload['run_dir']}")
    typer.echo(f"report: {payload['report']}")
    typer.echo(f"events: {payload['events']}")


def _review_run_status_payload(snapshot: Any) -> dict[str, object]:
    handle = snapshot.handle
    state = snapshot.state
    events = snapshot.events
    return {
        "run_id": handle.run_id,
        "status": state.get("status", "(unknown)"),
        "phase": state.get("phase", "(unknown)"),
        "run_dir": str(handle.run_dir),
        "report": str(handle.report_path),
        "events": len(events),
    }


@research_app.command(name="review")
def review_command(
    path: Path = _PATH_OPTION,
    topic: str = _TOPIC_OPTION,
    profile: str = _PROFILE_OPTION,
    run_id: str | None = _RUN_ID_OPTION,
    language: str = _LANGUAGE_OPTION,
    focus_override: str | None = _FOCUS_OPTION,
    mode: str = _MODE_OPTION,
    no_infer: bool = _NO_INFER_OPTION,
    depth: int = _DEPTH_OPTION,
    since: str | None = _SINCE_OPTION,
    strict: bool = _STRICT_OPTION,
) -> None:
    """Run Gaia inquiry review into the external research run envelope."""
    try:
        result = run_package_review(
            path,
            topic=topic,
            profile=profile,
            run_id=run_id,
            language=language,
            focus_override=focus_override,
            mode=mode,
            no_infer=no_infer,
            depth=depth,
            since=since,
            strict=strict,
        )
    except ReviewRunnerError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc

    typer.echo(f"review run completed: {result.handle.run_id}")
    typer.echo(f"run_dir: {result.handle.run_dir}")
    typer.echo(f"report: {result.handle.report_path}")


def register(root_app: typer.Typer) -> None:
    """Register the external ``gaia research`` command group."""
    root_app.add_typer(research_app, name="research")

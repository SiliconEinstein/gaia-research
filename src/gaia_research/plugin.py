"""Gaia CLI plugin registration for the external research package."""

from __future__ import annotations

from pathlib import Path

import typer

from gaia_research.contracts import CORE_PUBLIC_SURFACES, verify_core_contract

research_app = typer.Typer(
    name="research",
    help="Gaia Research workflows shipped by the gaia-research package.",
    no_args_is_help=True,
)
_PATH_ARGUMENT = typer.Argument(Path("."), help="Gaia package path.")


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
) -> None:
    """Report bootstrap status for the package-local research namespace."""
    research_dir = path / ".gaia" / "research"
    typer.echo(f"research namespace: {research_dir}")
    typer.echo(f"core surfaces: {len(CORE_PUBLIC_SURFACES)}")


def register(root_app: typer.Typer) -> None:
    """Register the external ``gaia research`` command group."""
    root_app.add_typer(research_app, name="research")

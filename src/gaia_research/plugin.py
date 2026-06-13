"""Gaia CLI plugin registration for the external research package."""

from __future__ import annotations

import typer

from gaia_research.research_cli import research_app


def register(root_app: typer.Typer) -> None:
    """Register the external ``gaia research`` command group."""
    root_app.add_typer(research_app, name="research")

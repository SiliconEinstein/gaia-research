"""Gaia CLI plugin contracts for gaia-research."""

from __future__ import annotations

from importlib import metadata

import typer


def test_distribution_exposes_gaia_cli_plugin_entry_point() -> None:
    entry_points = metadata.distribution("gaia-research").entry_points
    matches = [
        entry_point
        for entry_point in entry_points
        if entry_point.group == "gaia.cli_plugins" and entry_point.name == "research"
    ]

    assert len(matches) == 1
    assert matches[0].value == "gaia_research.plugin:register"


def test_cli_plugin_registers_research_subcommand() -> None:
    entry_points = metadata.distribution("gaia-research").entry_points
    entry_point = next(
        entry_point
        for entry_point in entry_points
        if entry_point.group == "gaia.cli_plugins" and entry_point.name == "research"
    )

    root_app = typer.Typer(name="gaia")
    plugin = entry_point.load()
    plugin(root_app)

    registered_groups = {group.name for group in root_app.registered_groups}
    assert "research" in registered_groups

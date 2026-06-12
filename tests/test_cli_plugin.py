"""Gaia CLI plugin contracts for gaia-research."""

from __future__ import annotations

from importlib import metadata
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import typer
from typer.testing import CliRunner


def test_distribution_exposes_gaia_cli_plugin_entry_point() -> None:
    entry_points = metadata.distribution("gaia-research").entry_points
    matches = [
        entry_point
        for entry_point in entry_points
        if entry_point.group == "gaia.cli_plugins" and entry_point.name == "research"
    ]

    assert len(matches) == 1
    assert matches[0].value == "gaia_research.plugin:register"


def test_plugin_review_command_calls_review_runner(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    from gaia_research import plugin

    pkg = tmp_path / "demo-gaia"
    pkg.mkdir()
    calls: dict[str, Any] = {}

    def fake_run_package_review(path: str | Path, **kwargs: Any) -> Any:
        calls["path"] = Path(path)
        calls["kwargs"] = kwargs
        handle = SimpleNamespace(
            run_id="plugin-run",
            run_dir=pkg / ".gaia" / "research" / "runs" / "plugin-run",
            report_path=pkg / ".gaia" / "research" / "runs" / "plugin-run" / "final_report.md",
        )
        return SimpleNamespace(handle=handle)

    monkeypatch.setattr(plugin, "run_package_review", fake_run_package_review)

    root_app = typer.Typer(name="gaia")
    plugin.register(root_app)
    result = CliRunner().invoke(
        root_app,
        [
            "research",
            "review",
            "--path",
            str(pkg),
            "--topic",
            "dqcp",
            "--profile",
            "quick",
            "--run-id",
            "plugin-run",
            "--focus",
            "neel-vbs",
            "--no-infer",
        ],
    )

    assert result.exit_code == 0
    assert calls == {
        "path": pkg,
        "kwargs": {
            "topic": "dqcp",
            "profile": "quick",
            "run_id": "plugin-run",
            "language": "zh",
            "focus_override": "neel-vbs",
            "mode": "auto",
            "no_infer": True,
            "depth": 0,
            "since": None,
            "strict": False,
        },
    }
    assert "review run completed: plugin-run" in result.stdout
    assert "final_report.md" in result.stdout

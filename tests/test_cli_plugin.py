"""Gaia CLI plugin contracts for gaia-research."""

from __future__ import annotations

import json
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


def test_plugin_status_command_reads_review_run_state(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    from gaia_research import plugin

    pkg = tmp_path / "demo-gaia"
    pkg.mkdir()
    calls: dict[str, Any] = {}

    def fake_read_review_run(path: str | Path, run_id: str) -> Any:
        calls["path"] = Path(path)
        calls["run_id"] = run_id
        handle = SimpleNamespace(
            run_id=run_id,
            run_dir=pkg / ".gaia" / "research" / "runs" / run_id,
            report_path=pkg / ".gaia" / "research" / "runs" / run_id / "final_report.md",
        )
        return SimpleNamespace(
            handle=handle,
            state={"status": "failed", "phase": "core_review"},
            events=[{"type": "run.created"}, {"type": "core_review.failed"}],
        )

    monkeypatch.setattr(plugin, "read_review_run", fake_read_review_run)

    root_app = typer.Typer(name="gaia")
    plugin.register(root_app)
    result = CliRunner().invoke(
        root_app,
        ["research", "status", str(pkg), "--run-id", "failed-run"],
    )

    assert result.exit_code == 0
    assert calls == {"path": pkg, "run_id": "failed-run"}
    assert "review run: failed-run" in result.stdout
    assert "status: failed" in result.stdout
    assert "phase: core_review" in result.stdout
    assert "events: 2" in result.stdout


def test_plugin_status_command_can_emit_json(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    from gaia_research import plugin

    pkg = tmp_path / "demo-gaia"
    pkg.mkdir()

    def fake_read_review_run(path: str | Path, run_id: str) -> Any:
        handle = SimpleNamespace(
            run_id=run_id,
            run_dir=pkg / ".gaia" / "research" / "runs" / run_id,
            report_path=pkg / ".gaia" / "research" / "runs" / run_id / "final_report.md",
        )
        return SimpleNamespace(
            handle=handle,
            state={"status": "failed", "phase": "core_review"},
            events=[{"type": "run.created"}, {"type": "core_review.failed"}],
        )

    monkeypatch.setattr(plugin, "read_review_run", fake_read_review_run)

    root_app = typer.Typer(name="gaia")
    plugin.register(root_app)
    result = CliRunner().invoke(
        root_app,
        ["research", "status", str(pkg), "--run-id", "failed-run", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == {
        "run_id": "failed-run",
        "status": "failed",
        "phase": "core_review",
        "run_dir": str(pkg / ".gaia" / "research" / "runs" / "failed-run"),
        "report": str(pkg / ".gaia" / "research" / "runs" / "failed-run" / "final_report.md"),
        "events": 2,
    }

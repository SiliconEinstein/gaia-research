"""CLI tests for gaia-research review runs."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from gaia_research import cli
from gaia_research.runner import ReviewRunnerError


def test_review_command_runs_package_review_and_prints_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pkg = tmp_path / "demo-gaia"
    pkg.mkdir()
    calls: dict[str, Any] = {}

    def fake_run_package_review(path: str | Path, **kwargs: Any) -> Any:
        calls["path"] = Path(path)
        calls["kwargs"] = kwargs
        handle = SimpleNamespace(
            run_id="demo-run",
            run_dir=pkg / ".gaia" / "research" / "runs" / "demo-run",
            report_path=pkg / ".gaia" / "research" / "runs" / "demo-run" / "final_report.md",
        )
        return SimpleNamespace(handle=handle)

    monkeypatch.setattr(cli, "run_package_review", fake_run_package_review)

    exit_code = cli.main(
        [
            "review",
            "--path",
            str(pkg),
            "--topic",
            "aspirin primary prevention",
            "--profile",
            "quick",
            "--run-id",
            "demo-run",
            "--focus",
            "primary-prevention",
            "--mode",
            "auto",
            "--no-infer",
            "--depth",
            "1",
        ]
    )

    assert exit_code == 0
    assert calls == {
        "path": pkg,
        "kwargs": {
            "topic": "aspirin primary prevention",
            "profile": "quick",
            "run_id": "demo-run",
            "language": "zh",
            "focus_override": "primary-prevention",
            "mode": "auto",
            "no_infer": True,
            "depth": 1,
            "since": None,
            "strict": False,
        },
    }
    out = capsys.readouterr().out
    assert "review run completed: demo-run" in out
    assert "final_report.md" in out


def test_review_command_returns_nonzero_when_runner_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pkg = tmp_path / "demo-gaia"
    pkg.mkdir()

    def fake_run_package_review(path: str | Path, **kwargs: Any) -> Any:
        raise ReviewRunnerError("compile exploded")

    monkeypatch.setattr(cli, "run_package_review", fake_run_package_review)

    exit_code = cli.main(
        [
            "review",
            "--path",
            str(pkg),
            "--topic",
            "dqcp",
            "--profile",
            "quick",
        ]
    )

    assert exit_code == 1
    assert "Error: compile exploded" in capsys.readouterr().err

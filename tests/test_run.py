"""Tests for UI-observable research run envelopes."""

from __future__ import annotations

import json
from pathlib import Path

from gaia_research.artifacts import load_research_package
from gaia_research.run import start_research_run


def _write_research_package(pkg_dir: Path) -> None:
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "research-demo-gaia"\nversion = "0.1.0"\n\n'
        '[tool.gaia]\nnamespace = "research_demo"\ntype = "knowledge-package"\n',
        encoding="utf-8",
    )
    src = pkg_dir / "src" / "research_demo"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text(
        "from gaia.engine.lang import question\n\n"
        'seed = question("Seed research question.")\n'
        '__all__ = ["seed"]\n',
        encoding="utf-8",
    )


def test_start_research_run_resumes_existing_run_without_duplicate_created_event(
    tmp_path: Path,
) -> None:
    _write_research_package(tmp_path / "workspace")
    pkg = load_research_package(tmp_path / "workspace")

    first = start_research_run(
        pkg,
        topic="aspirin primary prevention",
        mode="fast-package-native",
        language="zh",
        profile="fast",
        run_id="aspirin-fast",
    )
    second = start_research_run(
        pkg,
        topic="aspirin primary prevention",
        mode="fast-package-native",
        language="zh",
        profile="fast",
        run_id="aspirin-fast",
    )

    assert first.resumed is False
    assert second.resumed is True
    assert [event["type"] for event in second.events] == ["run.resumed"]
    events = [
        json.loads(line)
        for line in second.events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [event["type"] for event in events].count("run.created") == 1
    assert events[-1]["type"] == "run.resumed"

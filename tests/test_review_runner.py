"""Review runner tests for the Gaia inquiry-review bridge."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from gaia_research.runner import ReviewRunnerError, run_package_review


def _write_gaia_package(root: Path) -> Path:
    pkg = root / "demo-gaia"
    (pkg / "src" / "demo_gaia").mkdir(parents=True)
    (pkg / "src" / "demo_gaia" / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "demo-gaia"',
                'version = "0.1.0"',
                "",
                "[tool.gaia]",
                'type = "knowledge-package"',
                'namespace = "demo"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    return pkg


def _events(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_run_package_review_calls_gaia_inquiry_and_writes_research_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pkg = _write_gaia_package(tmp_path)
    calls: dict[str, Any] = {}

    def fake_run_review(path: str | Path, **kwargs: Any) -> Any:
        calls["path"] = Path(path)
        calls["kwargs"] = kwargs
        return SimpleNamespace(
            review_id="review-demo-auto",
            compile_status="ok",
            counts={"knowledge": 2, "strategies": 1, "operators": 0},
            mode=kwargs["mode"],
        )

    def fake_render_markdown(report: Any) -> str:
        return f"# Inquiry review\n\nreview={report.review_id}\n"

    monkeypatch.setattr("gaia_research.runner.run_review", fake_run_review)
    monkeypatch.setattr("gaia_research.runner.render_markdown", fake_render_markdown)

    result = run_package_review(
        pkg,
        topic="aspirin primary prevention",
        profile="quick",
        run_id="aspirin-review",
        focus_override="primary-prevention",
        mode="auto",
        no_infer=True,
        depth=1,
    )

    assert calls == {
        "path": pkg,
        "kwargs": {
            "focus_override": "primary-prevention",
            "mode": "auto",
            "no_infer": True,
            "depth": 1,
            "since": None,
            "strict": False,
        },
    }
    assert result.handle.run_dir == pkg / ".gaia" / "research" / "runs" / "aspirin-review"
    assert result.markdown == "# Inquiry review\n\nreview=review-demo-auto\n"
    assert result.snapshot.report_path.read_text(encoding="utf-8") == result.markdown

    state = json.loads(result.handle.state_path.read_text(encoding="utf-8"))
    assert state["status"] == "completed"
    assert state["phase"] == "report"
    assert state["core_review"] == {
        "review_id": "review-demo-auto",
        "compile_status": "ok",
        "counts": {"knowledge": 2, "strategies": 1, "operators": 0},
        "mode": "auto",
    }

    event_types = [event["type"] for event in _events(result.handle.events_path)]
    assert event_types == [
        "run.created",
        "checkpoint.created",
        "run.waiting_for_input",
        "core_review.started",
        "core_review.completed",
        "run.completed",
    ]


def test_run_package_review_records_failure_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pkg = _write_gaia_package(tmp_path)

    def fake_run_review(path: str | Path, **kwargs: Any) -> Any:
        raise RuntimeError("compile exploded")

    monkeypatch.setattr("gaia_research.runner.run_review", fake_run_review)

    with pytest.raises(ReviewRunnerError, match="compile exploded"):
        run_package_review(
            pkg,
            topic="dqcp",
            profile="quick",
            run_id="dqcp-review",
        )

    run_dir = pkg / ".gaia" / "research" / "runs" / "dqcp-review"
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert state["status"] == "failed"
    assert state["phase"] == "core_review"
    assert state["error"] == "compile exploded"

    event_types = [event["type"] for event in _events(run_dir / "events.ndjson")]
    assert event_types[-2:] == ["core_review.started", "core_review.failed"]

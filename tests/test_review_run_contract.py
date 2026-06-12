"""Review-run disk contract tests for gaia-research."""

from __future__ import annotations

import json
from pathlib import Path

from gaia_research.review import complete_review_run, read_review_run, start_review_run


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


def test_start_review_run_writes_observable_state_events_and_checkpoint(tmp_path: Path) -> None:
    pkg = _write_gaia_package(tmp_path)

    run = start_review_run(
        pkg,
        topic="aspirin primary prevention",
        profile="quick",
        run_id="aspirin-quick",
    )

    assert run.run_id == "aspirin-quick"
    assert run.run_dir == pkg / ".gaia" / "research" / "runs" / "aspirin-quick"
    assert run.state_path == run.run_dir / "state.json"
    assert run.events_path == run.run_dir / "events.ndjson"
    assert run.report_path == run.run_dir / "final_report.md"
    assert run.checkpoint_path == run.run_dir / "checkpoints" / "query_plan.request.json"
    assert not (pkg / ".gaia" / "research_loop").exists()

    state = json.loads(run.state_path.read_text(encoding="utf-8"))
    assert state["schema_version"] == 1
    assert state["run_id"] == "aspirin-quick"
    assert state["status"] == "waiting_for_input"
    assert state["phase"] == "query_plan"
    assert state["topic"] == "aspirin primary prevention"
    assert state["artifacts"]["final_report"] == str(run.report_path)

    events = [
        json.loads(line)
        for line in run.events_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [event["type"] for event in events] == [
        "run.created",
        "checkpoint.created",
        "run.waiting_for_input",
    ]

    loaded = read_review_run(pkg, "aspirin-quick")
    assert loaded.state == state
    assert loaded.events == events


def test_complete_review_run_marks_state_and_report_path(tmp_path: Path) -> None:
    pkg = _write_gaia_package(tmp_path)
    run = start_review_run(pkg, topic="dqcp evidence", profile="quick", run_id="dqcp")

    completed = complete_review_run(run, "# Evidence report\n\nGrounded summary.")

    assert completed.report_path.read_text(encoding="utf-8").startswith("# Evidence report")
    assert completed.state["status"] == "completed"
    assert completed.state["phase"] == "report"
    assert completed.state["artifacts"]["final_report"] == str(run.report_path)
    assert completed.events[-1]["type"] == "run.completed"

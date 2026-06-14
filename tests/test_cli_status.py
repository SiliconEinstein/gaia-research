"""CLI tests for report workflow run status."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gaia_research import cli
from gaia_research.workflow_state import create_report_run, record_event


def _write_research_package(pkg_dir: Path) -> Path:
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
    return pkg_dir


def _write_checkpoint_config(path: Path) -> Path:
    path.write_text(json.dumps({"llm": {"provider": "checkpoint"}}), encoding="utf-8")
    return path


def test_review_command_is_not_registered(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["review"])

    assert exc_info.value.code == 2
    assert "No such command" in capsys.readouterr().err


def test_report_command_is_not_registered(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["report"])

    assert exc_info.value.code == 2
    assert "No such command" in capsys.readouterr().err


def test_status_command_reads_report_workflow_state(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = tmp_path / "workspace"
    create_report_run(
        workspace,
        topic="aspirin primary prevention",
        profile="fast",
        run_id="aspirin-fast",
    )
    record_event(
        create_report_run(
            workspace,
            topic="secondary run",
            profile="fast",
            run_id="secondary-run",
        )[0],
        "landscape.started",
        phase="landscape",
    )

    exit_code = cli.main(["status", "--path", str(workspace), "--run-id", "aspirin-fast"])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "report run: aspirin-fast" in out
    assert "status: running" in out
    assert "phase: setup" in out
    assert "events: 1" in out


def test_status_command_can_emit_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = tmp_path / "workspace"
    handle, _state = create_report_run(
        workspace,
        topic="dqcp",
        profile="fast",
        run_id="dqcp-fast",
    )
    record_event(handle, "landscape.started", phase="landscape")

    exit_code = cli.main(["status", "--path", str(workspace), "--run-id", "dqcp-fast", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert {
        key: value for key, value in payload.items() if key != "recent_events"
    } == {
        "run_id": "dqcp-fast",
        "status": "running",
        "phase": "setup",
        "run_dir": str(handle.run_dir),
        "events": 2,
        "artifacts": {
            "landscape": str(handle.landscape_dir),
            "field_map": str(handle.field_map_dir),
            "focuses": str(handle.focuses_dir),
            "assessments": str(handle.assessments_dir),
            "materialization": str(handle.materialization_dir),
            "reports": str(handle.reports_dir),
        },
    }
    assert [event["type"] for event in payload["recent_events"]] == [
        "run.created",
        "landscape.started",
    ]
    assert payload["recent_events"][0]["run_id"] == "dqcp-fast"
    assert payload["recent_events"][1]["phase"] == "landscape"


def test_run_command_accepts_topic_workspace_and_fast_profile(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = _write_research_package(tmp_path / "workspace")
    config = _write_checkpoint_config(tmp_path / "checkpoint.json")

    exit_code = cli.main(
        [
            "run",
            str(workspace),
            "--topic",
            "aspirin primary prevention",
            "--profile",
            "fast",
            "--config",
            str(config),
            "--run-id",
            "aspirin-fast",
            "--json",
        ]
    )

    assert exit_code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["run_id"] == "aspirin-fast"
    assert out["status"] == "waiting_for_input"
    assert out["phase"] == "query_plan"
    assert out["profile"] == "fast"
    assert out["topic"] == "aspirin primary prevention"
    assert out["report"] is None
    assert Path(out["state_path"]).exists()
    assert Path(out["events_path"]).exists()

    state_path = workspace / ".gaia" / "research" / "runs" / "aspirin-fast" / "state.json"
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert payload["profile"] == "fast"
    assert payload["topic"] == "aspirin primary prevention"


def test_run_command_resumes_query_plan_with_default_topic_query(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = _write_research_package(tmp_path / "workspace")
    config = _write_checkpoint_config(tmp_path / "checkpoint.json")
    captured: dict[str, object] = {}
    search_json = tmp_path / "search.json"
    search_json.write_text('{"items": []}\n', encoding="utf-8")

    assert (
        cli.main(
            [
                "run",
                str(workspace),
                "--topic",
                "aspirin primary prevention",
                "--profile",
                "fast",
                "--config",
                str(config),
                "--run-id",
                "aspirin-fast",
                "--json",
            ]
        )
        == 0
    )
    capsys.readouterr()

    def fake_execute_live_searches(
        *_args: object, queries: list[str], **_kwargs: object
    ) -> list[str]:
        captured["queries"] = list(queries)
        return [str(search_json)]

    def fake_execute_file_provider_run(*_args: object, **_kwargs: object) -> None:
        captured["file_provider_called"] = True

    monkeypatch.setattr(
        "gaia_research.research_cli.execute_live_searches",
        fake_execute_live_searches,
    )
    monkeypatch.setattr(
        "gaia_research.research_cli.execute_file_provider_run",
        fake_execute_file_provider_run,
    )

    assert (
        cli.main(
            [
                "run",
                str(workspace),
                "--topic",
                "aspirin primary prevention",
                "--profile",
                "fast",
                "--config",
                str(config),
                "--run-id",
                "aspirin-fast",
                "--json",
            ]
        )
        == 0
    )

    assert captured == {
        "queries": ["aspirin primary prevention"],
        "file_provider_called": True,
    }


def test_run_command_resumes_query_plan_from_response_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = _write_research_package(tmp_path / "workspace")
    config = _write_checkpoint_config(tmp_path / "checkpoint.json")
    captured: dict[str, object] = {}
    search_json = tmp_path / "search.json"
    search_json.write_text('{"items": []}\n', encoding="utf-8")

    assert (
        cli.main(
            [
                "run",
                str(workspace),
                "--topic",
                "aspirin primary prevention",
                "--profile",
                "fast",
                "--config",
                str(config),
                "--run-id",
                "aspirin-fast",
                "--json",
            ]
        )
        == 0
    )
    first = json.loads(capsys.readouterr().out)
    response_path = Path(first["pending_checkpoint"]).with_name("query_plan.response.json")
    response_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "checkpoint_id": "query_plan_001",
                "action": "continue",
                "queries": ["manual aspirin query"],
            }
        ),
        encoding="utf-8",
    )

    def fake_execute_live_searches(
        *_args: object, queries: list[str], **_kwargs: object
    ) -> list[str]:
        captured["queries"] = list(queries)
        return [str(search_json)]

    def fake_execute_file_provider_run(*_args: object, **_kwargs: object) -> None:
        captured["file_provider_called"] = True

    monkeypatch.setattr(
        "gaia_research.research_cli.execute_live_searches",
        fake_execute_live_searches,
    )
    monkeypatch.setattr(
        "gaia_research.research_cli.execute_file_provider_run",
        fake_execute_file_provider_run,
    )

    assert (
        cli.main(
            [
                "run",
                str(workspace),
                "--topic",
                "aspirin primary prevention",
                "--profile",
                "fast",
                "--config",
                str(config),
                "--run-id",
                "aspirin-fast",
                "--json",
            ]
        )
        == 0
    )

    assert captured == {
        "queries": ["manual aspirin query"],
        "file_provider_called": True,
    }


def test_render_command_renders_existing_artifact_without_llm(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = _write_research_package(tmp_path / "workspace")
    artifact = tmp_path / "focus.json"
    artifact.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "focus_synthesis",
                "language": "zh",
                "focuses": [
                    {
                        "id": "elderly_net_benefit",
                        "question": "老年人一级预防净获益是否为正?",
                        "priority": "high",
                        "readiness": "ready_for_assess",
                        "status": "candidate",
                        "rationale": "ASPREE 同时涉及无心血管获益和出血增加。",
                        "coverage": {"items": 4, "paper_leads": 2},
                        "evidence_refs": [{"kind": "variable", "id": "v1"}],
                        "suggested_queries": ["aspirin elderly bleeding"],
                    }
                ],
                "coverage_gaps": [],
                "notes": [],
            }
        ),
        encoding="utf-8",
    )

    exit_code = cli.main(["render", str(workspace), "--artifact", str(artifact)])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "# Research Focus Synthesis" in out
    assert "elderly_net_benefit" in out

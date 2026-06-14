"""Agent-platform contracts for EvidenceMaster deployments."""

from __future__ import annotations

import json
from importlib import metadata, resources
from pathlib import Path

import pytest

from gaia_research import cli
from gaia_research.workflow_state import create_report_run


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


def test_doctor_can_emit_agent_readable_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("GAIA_LKM_ACCESS_KEY", "bohrium-secret-value")
    monkeypatch.setenv("GAIA_RESEARCH_LLM_MODEL", "openai/gpt-4.1-mini")
    monkeypatch.setenv("GAIA_RESEARCH_LLM_API_BASE", "https://llm.example/v1")
    monkeypatch.setenv("GAIA_RESEARCH_LLM_API_KEY", "llm-secret-value")

    exit_code = cli.main(["doctor", "--for-agent", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["package"] == "gaia-research"
    assert payload["plugin_entry_point"] == "gaia_research.plugin:register"
    assert "gaia.lkm.client" in payload["core_surfaces"]
    assert (
        "gaia research run <pkg> --topic <topic> --profile fast --json-stream"
        in payload["required_gaia_cli"]
    )
    assert payload["missing"] == []


def test_doctor_reports_external_credential_readiness_without_secret_values(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("GAIA_LKM_ACCESS_KEY", "bohrium-secret-value")
    monkeypatch.setenv("GAIA_RESEARCH_LLM_MODEL", "openai/gpt-4.1-mini")
    monkeypatch.setenv("GAIA_RESEARCH_LLM_API_BASE", "https://llm.example/v1/chat/completions")
    monkeypatch.setenv("GAIA_RESEARCH_LLM_API_KEY", "llm-secret-value")

    assert cli.main(["doctor", "--for-agent", "--json"]) == 0

    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["credentials"]["lkm_access_key"]["ready"] is True
    assert payload["credentials"]["lkm_access_key"]["accepted_env"] == [
        "GAIA_LKM_ACCESS_KEY",
        "LKM_ACCESS_KEY",
    ]
    assert payload["credentials"]["llm_provider"]["ready"] is True
    assert payload["credentials"]["llm_provider"]["model_env"] == "GAIA_RESEARCH_LLM_MODEL"
    assert "bohrium-secret-value" not in out
    assert "llm-secret-value" not in out


def test_doctor_requires_explicit_gaia_research_llm_namespace(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("GAIA_LKM_ACCESS_KEY", "bohrium-secret-value")
    monkeypatch.delenv("GAIA_RESEARCH_LLM_MODEL", raising=False)
    monkeypatch.delenv("GAIA_RESEARCH_LLM_API_BASE", raising=False)
    monkeypatch.delenv("GAIA_RESEARCH_LLM_API_KEY", raising=False)
    monkeypatch.setenv("LITELLM_PROXY_API_BASE", "https://legacy.example/v1")
    monkeypatch.setenv("LITELLM_PROXY_API_KEY", "legacy-proxy-key")
    monkeypatch.setenv("OPENAI_API_KEY", "provider-native-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "provider-native-key")

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["doctor", "--for-agent", "--json"])
    assert exc_info.value.code == 1

    out = capsys.readouterr().out
    payload = json.loads(out)
    llm_status = payload["credentials"]["llm_provider"]
    assert payload["ok"] is False
    assert payload["missing"] == ["llm_model", "llm_api_base", "llm_api_key"]
    assert llm_status["ready"] is False
    assert llm_status["accepted_env"] == {
        "model": ["GAIA_RESEARCH_LLM_MODEL"],
        "api_base": ["GAIA_RESEARCH_LLM_API_BASE"],
        "api_key": ["GAIA_RESEARCH_LLM_API_KEY"],
    }
    assert "legacy-proxy-key" not in out
    assert "provider-native-key" not in out


def test_doctor_can_load_explicit_llm_namespace_from_env_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("GAIA_LKM_ACCESS_KEY", "bohrium-secret-value")
    monkeypatch.delenv("GAIA_RESEARCH_LLM_MODEL", raising=False)
    monkeypatch.delenv("GAIA_RESEARCH_LLM_API_BASE", raising=False)
    monkeypatch.delenv("GAIA_RESEARCH_LLM_API_KEY", raising=False)
    env_file = tmp_path / "research.env"
    env_file.write_text(
        "\n".join(
            [
                "GAIA_RESEARCH_LLM_MODEL=openai/test",
                "GAIA_RESEARCH_LLM_API_BASE=https://llm.example/v1",
                "GAIA_RESEARCH_LLM_API_KEY=env-file-secret",
            ]
        ),
        encoding="utf-8",
    )

    assert cli.main(["doctor", "--for-agent", "--env-file", str(env_file), "--json"]) == 0

    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["credentials"]["llm_provider"]["ready"] is True
    assert "env-file-secret" not in out


def test_capabilities_json_describes_evidence_master_surface(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main(["capabilities", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["agent_name"] == "EvidenceMaster"
    assert payload["workflow"] == [
        "topic",
        "landscape",
        "field_map",
        "focus_selection",
        "assessment",
        "materialization_decision",
        "report",
    ]
    assert "doctor" in payload["commands"]
    assert "artifacts" in payload["commands"]
    assert payload["agent_skills"] == [
        "gaia-research-bootstrap",
        "gaia-research-run",
        "gaia-research-status",
        "gaia-research-artifacts",
    ]
    assert payload["commands"]["run"]["agent_form"] == (
        'gaia research run <pkg> --topic "<topic>" '
        "--profile fast --env-file <env-file> --json-stream"
    )


def test_run_help_exposes_profile_config_surface_not_legacy_overrides(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(["run", "--help"]) == 0

    out = capsys.readouterr().out
    for expected in ("--topic", "--profile", "--config", "--env-file", "--json"):
        assert expected in out
    for legacy_override in (
        "--search-limit",
        "--analysis-provider",
        "--model",
        "--focus-count",
        "--evidence-max-items",
        "--assess-analysis-json",
        "--targeted-query",
    ):
        assert legacy_override not in out


def test_hidden_run_overrides_remain_backward_compatible(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pkg = _write_research_package(tmp_path / "workspace")

    assert (
        cli.main(
            [
                "run",
                str(pkg),
                "--topic",
                "compatibility smoke",
                "--profile",
                "fast",
                "--analysis-provider",
                "checkpoint",
                "--run-id",
                "compat-smoke",
                "--search-limit",
                "5",
                "--focus-count",
                "1",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["run_id"] == "compat-smoke"


def test_artifacts_command_indexes_report_run_outputs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    handle, _state = create_report_run(
        tmp_path,
        topic="aspirin primary prevention",
        profile="fast",
        run_id="aspirin-fast",
    )
    report = handle.reports_dir / "report.md"
    report.write_text("# Report\n", encoding="utf-8")

    exit_code = cli.main(["artifacts", str(tmp_path), "--run-id", "aspirin-fast", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["run_id"] == "aspirin-fast"
    assert payload["status"] == "running"
    assert payload["phase"] == "setup"
    assert payload["artifact_root"] == str(handle.run_dir)
    assert payload["artifact_dirs"]["reports"] == str(handle.reports_dir)
    assert {
        "kind": "reports",
        "name": "report.md",
        "path": str(report),
        "size_bytes": 9,
    } in payload["files"]


def test_status_and_artifacts_read_state_created_by_run_command(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pkg = _write_research_package(tmp_path / "workspace")
    config = _write_checkpoint_config(tmp_path / "checkpoint.json")

    assert (
        cli.main(
            [
                "run",
                str(pkg),
                "--topic",
                "local EvidenceMaster smoke",
                "--profile",
                "fast",
                "--config",
                str(config),
                "--run-id",
                "local-smoke",
                "--json",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert cli.main(["status", str(pkg), "--run-id", "local-smoke", "--json"]) == 0
    status_payload = json.loads(capsys.readouterr().out)
    assert status_payload["run_id"] == "local-smoke"
    assert status_payload["status"] == "waiting_for_input"
    assert status_payload["phase"] == "query_plan"
    assert status_payload["events"] == 3
    assert status_payload["recent_events"][-1]["type"] == "run.waiting_for_input"

    assert cli.main(["artifacts", str(pkg), "--run-id", "local-smoke", "--json"]) == 0
    artifacts_payload = json.loads(capsys.readouterr().out)
    assert artifacts_payload["run_id"] == "local-smoke"
    assert artifacts_payload["artifact_root"].endswith("/.gaia/research/runs/local-smoke")
    assert any(item["name"] == "query_plan.request.json" for item in artifacts_payload["files"])


def test_distribution_exposes_gaia_skill_entry_point() -> None:
    entry_points = metadata.distribution("gaia-research").entry_points
    matches = [
        entry_point
        for entry_point in entry_points
        if entry_point.group == "gaia.skills" and entry_point.name == "gaia-research"
    ]

    assert len(matches) == 1
    assert matches[0].value == "gaia_research.skills"


def test_agent_skills_are_packaged_as_gaia_skill_tree() -> None:
    root = resources.files("gaia_research.skills")

    for name in (
        "gaia-research-bootstrap",
        "gaia-research-run",
        "gaia-research-status",
        "gaia-research-artifacts",
    ):
        skill = root / name / "SKILL.md"
        assert skill.is_file()
        text = skill.read_text(encoding="utf-8")
        assert text.startswith("---\nname: ")
        assert "description: Use when" in text


def test_bootstrap_skill_names_lkm_and_llm_setup() -> None:
    text = (
        resources.files("gaia_research.skills")
        .joinpath("gaia-research-bootstrap", "SKILL.md")
        .read_text(encoding="utf-8")
    )

    assert "GAIA_LKM_ACCESS_KEY" in text
    assert "gaia search lkm auth login" in text
    assert "GAIA_RESEARCH_LLM_MODEL" in text
    assert "GAIA_RESEARCH_LLM_API_BASE" in text
    assert "GAIA_RESEARCH_LLM_API_KEY" in text
    assert "LITELLM_PROXY_API_KEY" not in text

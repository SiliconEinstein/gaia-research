"""Unit tests for engine-level research workflow orchestration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from gaia.engine.inquiry.state import load_state

from gaia_research import (
    ResearchOrchestratorPaused,
    ResearchPackage,
    ResearchSyncResult,
    append_research_event,
    sync_assessment_artifact,
    write_research_artifact,
)
from gaia_research.orchestrator import execute_file_provider_run
from gaia_research.run import ResearchRunStart, start_research_run


def _write_research_package(pkg_dir: Path) -> ResearchPackage:
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "research-demo-gaia"\nversion = "0.1.0"\n\n'
        '[tool.gaia]\nnamespace = "research_demo"\ntype = "knowledge-package"\n',
        encoding="utf-8",
    )
    src = pkg_dir / "src" / "research_demo"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text(
        "from gaia.engine.lang import claim\n\n"
        'seed = claim("Seed claim for research orchestrator tests.")\n'
        '__all__ = ["seed"]\n',
        encoding="utf-8",
    )
    return ResearchPackage(
        path=pkg_dir,
        project_name="research-demo-gaia",
        import_name="research_demo",
        namespace="research_demo",
    )


def _search_json(path: Path) -> Path:
    payload = {
        "schema_version": 1,
        "query": {"text": "aspirin evidence", "provider": "lkm", "kind": "knowledge"},
        "results": [
            {
                "id": "lkm:bohrium:var_aspree",
                "kind": "claim",
                "title": "Claim from ASPREE",
                "content": "ASPREE reported no cardiovascular benefit.",
                "gaia": {"qid": None},
                "source": {
                    "provider_id": "var_aspree",
                    "paper_id": "P_ASPREE",
                    "paper_title": "ASPREE trial",
                    "doi": "10.1/aspree",
                    "index_id": "bohrium",
                },
                "rank": {"score": 0.9},
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _focus_analysis_json(path: Path) -> Path:
    payload = {
        "focuses": [
            {
                "id": "aspree_net_benefit",
                "kind": "research_focus",
                "status": "candidate",
                "question": "Does aspirin primary prevention show net benefit in older adults?",
                "rationale": "ASPREE evidence raises a net-benefit uncertainty.",
                "priority": "high",
                "readiness": "ready_for_assess",
                "scope": {"population": "older adults"},
                "coverage": {"items": 1, "missing": []},
                "evidence_refs": [{"kind": "variable", "id": "var_aspree"}],
                "suggested_queries": [],
            }
        ],
        "coverage_gaps": [],
        "notes": [],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _focus_analysis_with_workflow_gaps_json(path: Path) -> Path:
    payload = {
        "focuses": [
            {
                "id": "aspree_net_benefit",
                "kind": "research_focus",
                "status": "candidate",
                "question": "Does aspirin primary prevention show net benefit in older adults?",
                "rationale": "ASPREE evidence raises a net-benefit uncertainty.",
                "priority": "high",
                "readiness": "ready_for_assess",
                "scope": {"population": "older adults"},
                "coverage": {"items": 1, "missing": []},
                "evidence_refs": [{"kind": "variable", "id": "var_aspree"}],
                "suggested_queries": [],
            },
            {
                "id": "bleeding_tradeoff",
                "kind": "research_focus",
                "status": "candidate",
                "question": "How do bleeding harms change the net-benefit judgment?",
                "rationale": "The benefit-harm tradeoff remains unresolved.",
                "priority": "medium",
                "readiness": "ready_for_assess",
                "scope": {"population": "older adults"},
                "coverage": {"items": 1, "missing": []},
                "evidence_refs": [{"kind": "variable", "id": "var_aspree"}],
                "suggested_queries": [],
            },
            {
                "id": "subgroup_evidence",
                "kind": "research_focus",
                "status": "candidate",
                "question": "Which subgroups, if any, have different evidence?",
                "rationale": "Subgroup evidence is thin.",
                "priority": "low",
                "readiness": "needs_expand",
                "scope": {"population": "older adults"},
                "coverage": {"items": 0, "missing": ["subgroups"]},
                "evidence_refs": [{"kind": "variable", "id": "var_aspree"}],
                "suggested_queries": ["aspirin primary prevention subgroup evidence"],
            },
        ],
        "coverage_gaps": [
            {
                "id": "missing_harms",
                "kind": "coverage_gap",
                "description": "Bleeding-harm evidence is not yet covered.",
                "evidence_refs": [{"kind": "variable", "id": "var_aspree"}],
            }
        ],
        "notes": [],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _focus_analysis_with_expand_only_json(path: Path) -> Path:
    payload = {
        "focuses": [
            {
                "id": "aspree_net_benefit",
                "kind": "research_focus",
                "status": "candidate",
                "question": "Does aspirin primary prevention show net benefit in older adults?",
                "rationale": "ASPREE evidence raises a net-benefit uncertainty.",
                "priority": "high",
                "readiness": "ready_for_assess",
                "scope": {"population": "older adults"},
                "coverage": {"items": 1, "missing": []},
                "evidence_refs": [{"kind": "variable", "id": "var_aspree"}],
                "suggested_queries": [],
            },
            {
                "id": "subgroup_evidence",
                "kind": "research_focus",
                "status": "candidate",
                "question": "Which subgroups, if any, have different evidence?",
                "rationale": "Subgroup evidence is thin.",
                "priority": "low",
                "readiness": "needs_expand",
                "scope": {"population": "older adults"},
                "coverage": {"items": 0, "missing": ["subgroups"]},
                "evidence_refs": [{"kind": "variable", "id": "var_aspree"}],
                "suggested_queries": ["aspirin primary prevention subgroup evidence"],
            },
        ],
        "coverage_gaps": [],
        "notes": [],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _focus_analysis_with_coverage_gap_json(path: Path) -> Path:
    payload = {
        "focuses": [
            {
                "id": "aspree_net_benefit",
                "kind": "research_focus",
                "status": "candidate",
                "question": "Does aspirin primary prevention show net benefit in older adults?",
                "rationale": "ASPREE evidence raises a net-benefit uncertainty.",
                "priority": "high",
                "readiness": "ready_for_assess",
                "scope": {"population": "older adults"},
                "coverage": {"items": 1, "missing": []},
                "evidence_refs": [{"kind": "variable", "id": "var_aspree"}],
                "suggested_queries": [],
            }
        ],
        "coverage_gaps": [
            {
                "id": "missing_harms",
                "kind": "coverage_gap",
                "description": "Bleeding-harm evidence is not yet covered.",
                "evidence_refs": [{"kind": "variable", "id": "var_aspree"}],
            }
        ],
        "notes": [],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _assess_analysis_with_hydrated_ref_json(path: Path) -> Path:
    payload = {
        "new_claims": [
            {
                "id": "aspree_no_net_benefit",
                "claim": "ASPREE does not show net benefit for routine aspirin use.",
                "category": "answer_candidate",
                "rationale": "The materialized ASPREE claim reports no cardiovascular benefit.",
                "answers_question": "aspree_net_benefit",
                "source_refs": [{"kind": "package_ref", "id": "lkm:aspree_pkg::net_benefit"}],
            },
            {
                "id": "aspree_bleeding_tradeoff_matters",
                "claim": "Bleeding harms are material to the ASPREE net-benefit judgment.",
                "category": "synthesis",
                "rationale": "The ASPREE result requires benefit and harm to be compared.",
                "answers_question": "aspree_net_benefit",
                "source_refs": [{"kind": "package_ref", "id": "lkm:aspree_pkg::net_benefit"}],
            }
        ],
        "relations": [
            {
                "type": "supports",
                "claim": "The ASPREE claim supports the no-net-benefit candidate.",
                "rationale": "The materialized paper claim reports no cardiovascular benefit.",
                "epistemic_status": "candidate",
                "source_refs": [{"kind": "package_ref", "id": "lkm:aspree_pkg::net_benefit"}],
                "claim_refs": ["lkm:aspree_pkg::net_benefit", "aspree_no_net_benefit"],
            }
        ],
        "candidate_obligations": [],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _assess_analysis_empty_json(path: Path) -> Path:
    payload: dict[str, object] = {
        "new_claims": [],
        "relations": [],
        "candidate_obligations": [],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _assess_analysis_with_obligation_json(path: Path) -> Path:
    payload = {
        "new_claims": [],
        "relations": [],
        "candidate_obligations": [
            {
                "kind": "needs_more_evidence",
                "target": {"kind": "claim", "ref": "aspree_no_net_benefit"},
                "action_type": "search_more_evidence",
                "action": "Find direct counter-evidence for the aspirin net-benefit claim.",
                "content": "The current evidence leaves the adverse-event tradeoff unresolved.",
                "source_refs": [{"kind": "variable", "id": "var_aspree"}],
                "actionable": True,
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class _Runtime:
    def update_run_state(self, run: ResearchRunStart, payload: dict[str, object]) -> None:
        state = json.loads(run.state_path.read_text(encoding="utf-8"))
        state.update(payload)
        run.state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    def read_search_json(self, ref: str) -> tuple[dict[str, object], str]:
        path = Path(ref)
        return json.loads(path.read_text(encoding="utf-8")), str(path)

    def read_json_object_ref(self, ref: str, *, label: str) -> dict[str, object]:
        _ = label
        payload = json.loads(Path(ref).read_text(encoding="utf-8"))
        assert isinstance(payload, dict)
        return payload

    def write_json_file(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def write_text_file(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def write_artifact(
        self,
        research_pkg: ResearchPackage,
        category: str,
        stem: str,
        payload: dict[str, Any],
    ) -> Path:
        return write_research_artifact(research_pkg, category, stem, payload)

    def append_research_event(
        self,
        research_pkg: ResearchPackage,
        event: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return append_research_event(research_pkg, event, payload)

    def emit_run_event(
        self,
        run: ResearchRunStart,
        *,
        event_type: str,
        phase: str,
        json_stream: bool,
        payload: dict[str, object],
    ) -> None:
        _ = json_stream
        with run.events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"type": event_type, "phase": phase, **payload}) + "\n")

    def record_trace(
        self,
        research_pkg: ResearchPackage,
        run: ResearchRunStart,
        *,
        start: float,
        name: str,
        kind: str,
        mode: str,
        inputs: list[str],
        outputs: list[str],
        metrics: dict[str, object] | None = None,
        status: str = "ok",
    ) -> None:
        _ = research_pkg, start, kind, mode, inputs, outputs, metrics, status
        trace_dir = run.run_dir / "trace"
        trace_dir.mkdir(parents=True, exist_ok=True)
        with (trace_dir / "trace.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"name": name, "status": status}) + "\n")

    def record_cli_trace(
        self,
        research_pkg: ResearchPackage,
        run: ResearchRunStart,
        *,
        start: float,
        name: str,
        mode: str,
        inputs: list[str],
        outputs: list[str],
        metrics: dict[str, object] | None = None,
    ) -> None:
        self.record_trace(
            research_pkg,
            run,
            start=start,
            name=name,
            kind="cli",
            mode=mode,
            inputs=inputs,
            outputs=outputs,
            metrics=metrics,
        )

    def sync_landscape_artifact(
        self,
        research_pkg: ResearchPackage,
        landscape: dict[str, Any],
        *,
        dry_run: bool,
    ) -> ResearchSyncResult:
        _ = research_pkg, landscape
        return ResearchSyncResult(dry_run=dry_run)

    def sync_focus_artifact(
        self,
        research_pkg: ResearchPackage,
        focus_artifact: dict[str, Any],
        *,
        max_questions: int,
        dry_run: bool,
    ) -> ResearchSyncResult:
        _ = research_pkg, focus_artifact, max_questions
        return ResearchSyncResult(dry_run=dry_run)

    def sync_assessment_artifact(
        self,
        research_pkg: ResearchPackage,
        assessment: dict[str, Any],
        *,
        dry_run: bool,
    ) -> ResearchSyncResult:
        _ = research_pkg, assessment
        return ResearchSyncResult(dry_run=dry_run)

    def write_benchmark_summary(self, research_pkg: ResearchPackage, trace_dir: Path) -> Path:
        _ = research_pkg
        path = trace_dir / "summary.json"
        self.write_json_file(path, {"schema_version": 1})
        return path

    def resolve_litellm_model(self, model: str | None) -> str:
        return model or "test-model"

    def maybe_run_sectioned_report_writing(
        self,
        research_pkg: ResearchPackage,
        run: ResearchRunStart,
        *,
        topic: str,
        language: str,
        analysis_provider: str,
        research_mode: str,
        model: str | None,
        assess_model: str | None,
        focus: str,
        field_map_path: Path | None,
        focus_path: Path,
        landscape_paths: list[Path],
        selected_evidence_paths: list[Path],
        assessment_paths: list[Path],
        llm_temperature: float,
        llm_timeout: float,
        llm_max_retries: int,
        llm_max_tokens: int | None,
        report_section_concurrency: int,
        json_stream: bool,
    ) -> tuple[str | None, list[str]]:
        _ = (
            research_pkg,
            run,
            topic,
            language,
            analysis_provider,
            research_mode,
            model,
            assess_model,
            focus,
            field_map_path,
            focus_path,
            landscape_paths,
            selected_evidence_paths,
            assessment_paths,
            llm_temperature,
            llm_timeout,
            llm_max_retries,
            llm_max_tokens,
            report_section_concurrency,
            json_stream,
        )
        return None, []

    def search_lkm(
        self,
        query: str,
        *,
        index: str,
        limit: int,
        reasoning_only: bool,
    ) -> dict[str, object]:
        _ = query, index, limit, reasoning_only
        return {"schema_version": 1, "results": []}

    def run_command_provider(self, *_args: object, **_kwargs: object) -> str:
        raise AssertionError("command provider should not run")

    def run_litellm_provider(self, *_args: object, **_kwargs: object) -> str:
        raise AssertionError("litellm provider should not run")

    def materialize_landscape_sources(
        self,
        research_pkg: ResearchPackage,
        landscape: dict[str, Any],
        *,
        landscape_artifact: Path,
        dry_run: bool,
    ) -> dict[str, object]:
        _ = research_pkg, landscape, landscape_artifact, dry_run
        return {"source_packages_added": [], "source_packages_skipped": []}

    def materialize_lkm_deep_evidence(
        self,
        research_pkg: ResearchPackage,
        *,
        paper_ids: list[str],
        claim_ids: list[str],
        chain_claim_ids: list[str],
        lkm_index: str,
        dry_run: bool,
    ) -> dict[str, object]:
        _ = research_pkg, paper_ids, claim_ids, chain_claim_ids, lkm_index, dry_run
        return {
            "lkm_materialize_requests": [],
            "lkm_packages_materialized": [],
            "lkm_chains_materialized": [],
        }


class _HydratingRuntime(_Runtime):
    def materialize_lkm_deep_evidence(
        self,
        research_pkg: ResearchPackage,
        *,
        paper_ids: list[str],
        claim_ids: list[str],
        chain_claim_ids: list[str],
        lkm_index: str,
        dry_run: bool,
    ) -> dict[str, object]:
        _ = research_pkg, claim_ids, chain_claim_ids, lkm_index, dry_run
        assert paper_ids == ["P_ASPREE"]
        return {
            "lkm_materialize_requests": ["P_ASPREE"],
            "lkm_packages_materialized": [
                {
                    "source_ref": "lkm:bohrium:paper:P_ASPREE",
                    "import_name": "aspree_pkg",
                    "symbol_refs": [
                        {
                            "node_id": "var_aspree",
                            "kind": "claim",
                            "symbol": "net_benefit",
                            "ref": "lkm:aspree_pkg::net_benefit",
                        }
                    ],
                }
            ],
            "lkm_chains_materialized": [],
        }


class _UnresolvedAnchorRuntime(_Runtime):
    def materialize_lkm_deep_evidence(
        self,
        research_pkg: ResearchPackage,
        *,
        paper_ids: list[str],
        claim_ids: list[str],
        chain_claim_ids: list[str],
        lkm_index: str,
        dry_run: bool,
    ) -> dict[str, object]:
        _ = research_pkg, paper_ids, claim_ids, chain_claim_ids, lkm_index, dry_run
        return {
            "lkm_materialize_requests": ["P_ASPREE"],
            "lkm_packages_materialized": [],
            "lkm_chains_materialized": [],
        }


class _ObligationRuntime(_Runtime):
    def sync_assessment_artifact(
        self,
        research_pkg: ResearchPackage,
        assessment: dict[str, Any],
        *,
        dry_run: bool,
    ) -> ResearchSyncResult:
        return sync_assessment_artifact(
            research_pkg,
            assessment,
            source_writes=False,
            dry_run=dry_run,
        )


class _RecordingSearchRuntime(_ObligationRuntime):
    def __init__(self) -> None:
        self.queries: list[str] = []

    def search_lkm(
        self,
        query: str,
        *,
        index: str,
        limit: int,
        reasoning_only: bool,
    ) -> dict[str, object]:
        self.queries.append(query)
        return super().search_lkm(
            query,
            index=index,
            limit=limit,
            reasoning_only=reasoning_only,
        )


class _DeferredCoverageRuntime(_RecordingSearchRuntime):
    def sync_landscape_artifact(
        self,
        research_pkg: ResearchPackage,
        landscape: dict[str, Any],
        *,
        dry_run: bool,
    ) -> ResearchSyncResult:
        _ = research_pkg, landscape
        result = ResearchSyncResult(dry_run=dry_run)
        result.obligations_deferred.append(
            {
                "target": {"kind": "question", "id": "research_coverage"},
                "target_qid": "research_coverage",
                "action_type": "close_coverage_gap",
                "action": "Close coverage gap missing_harms: Bleeding-harm evidence is thin.",
                "content": "Bleeding-harm evidence is thin.",
                "diagnostic_kind": "focus_weakness",
                "anchor": {
                    "kind": "landscape_gap",
                    "gaia_research": {
                        "obligation_type": "workflow",
                        "action_type": "close_coverage_gap",
                        "target": {"kind": "question", "id": "research_coverage"},
                        "auto_closeable": True,
                        "blocking": False,
                        "budget_class": "coverage",
                        "source": "landscape",
                    },
                },
            }
        )
        return result


class _PolicyRuntime(_RecordingSearchRuntime):
    def __init__(self, policy: dict[str, Any]) -> None:
        super().__init__()
        self.policy = policy
        self.policy_inputs: list[dict[str, object]] = []

    def run_litellm_provider(self, *_args: object, **kwargs: object) -> str:
        run = cast(ResearchRunStart, _args[1])
        phase = cast(str, kwargs["phase"])
        input_payload = cast(dict[str, object], kwargs["input_payload"])
        output_name = cast(str, kwargs["output_name"])
        assert phase == "obligation_policy"
        self.policy_inputs.append(input_payload)
        output_path = run.run_dir / "analysis" / f"{output_name}.output.json"
        self.write_json_file(output_path, self.policy)
        return str(output_path)


class _GraphAssetRuntime(_HydratingRuntime):
    def sync_assessment_artifact(
        self,
        research_pkg: ResearchPackage,
        assessment: dict[str, Any],
        *,
        dry_run: bool,
    ) -> ResearchSyncResult:
        return sync_assessment_artifact(research_pkg, assessment, dry_run=dry_run)


def test_checkpoint_assess_pause_uses_typed_engine_signal(tmp_path: Path) -> None:
    research_pkg = _write_research_package(tmp_path / "research-demo-gaia")
    run = start_research_run(
        research_pkg,
        topic="aspirin evidence",
        mode="fast-package-native",
        language="en",
        profile="fast",
        run_id="typed-pause",
        wait_for_query_plan=False,
    )

    with pytest.raises(ResearchOrchestratorPaused) as exc_info:
        execute_file_provider_run(
            research_pkg,
            run,
            topic="aspirin evidence",
            mode="fast-package-native",
            language="en",
            search_json=[str(_search_json(tmp_path / "search.json"))],
            focus_analysis_json=str(_focus_analysis_json(tmp_path / "focus.json")),
            targeted_search_json=[],
            targeted_query=[],
            focus=None,
            focus_count=1,
            assess_analysis_json=None,
            analysis_provider="checkpoint",
            model=None,
            focus_model=None,
            assess_model=None,
            llm_temperature=0.0,
            llm_timeout=30.0,
            llm_max_retries=0,
            llm_max_tokens=None,
            report_section_concurrency=1,
            search_index="bohrium",
            search_limit=20,
            reasoning_only=True,
            evidence_selection_mode="off",
            evidence_max_items=8,
            evidence_max_papers=5,
            evidence_max_chains=3,
            focus_analysis_command=None,
            assess_analysis_command=None,
            json_stream=False,
            runtime=_Runtime(),
        )

    assert exc_info.value.phase == "assess_analysis"
    state = json.loads(run.state_path.read_text(encoding="utf-8"))
    assert state["status"] == "waiting_for_input"
    assert state["phase"] == "assess_analysis"
    assert "error" not in state


def test_deep_expand_hydrates_selected_evidence_refs_before_assessment(
    tmp_path: Path,
) -> None:
    research_pkg = _write_research_package(tmp_path / "research-demo-gaia")
    run = start_research_run(
        research_pkg,
        topic="aspirin evidence",
        mode="fast-package-native",
        language="en",
        profile="fast",
        run_id="hydrate-anchors",
        wait_for_query_plan=False,
    )

    execute_file_provider_run(
        research_pkg,
        run,
        topic="aspirin evidence",
        mode="fast-package-native",
        language="en",
        search_json=[str(_search_json(tmp_path / "search.json"))],
        focus_analysis_json=str(_focus_analysis_json(tmp_path / "focus.json")),
        targeted_search_json=[],
        targeted_query=[],
        focus=None,
        focus_count=1,
        assess_analysis_json=str(_assess_analysis_with_hydrated_ref_json(tmp_path / "assess.json")),
        analysis_provider="checkpoint",
        model=None,
        focus_model=None,
        assess_model=None,
        llm_temperature=0.0,
        llm_timeout=30.0,
        llm_max_retries=0,
        llm_max_tokens=None,
        report_section_concurrency=1,
        search_index="bohrium",
        search_limit=20,
        reasoning_only=True,
        evidence_selection_mode="fast",
        evidence_max_items=8,
        evidence_max_papers=5,
        evidence_max_chains=3,
        focus_analysis_command=None,
        assess_analysis_command=None,
        json_stream=False,
        runtime=_HydratingRuntime(),
    )

    state = json.loads(run.state_path.read_text(encoding="utf-8"))
    selected_evidence_path = Path(state["artifacts"]["selected_evidence"])
    selected_evidence = json.loads(selected_evidence_path.read_text(encoding="utf-8"))
    assert "materialization_result" not in selected_evidence
    materialization_manifest_path = Path(selected_evidence["materialization_manifest"])
    materialization_manifest = json.loads(
        materialization_manifest_path.read_text(encoding="utf-8")
    )
    assert materialization_manifest["kind"] == "evidence_materialization"
    assert materialization_manifest["materialization_result"]["lkm_packages_materialized"][0][
        "import_name"
    ] == "aspree_pkg"
    assert selected_evidence["anchors"][0]["ref"] == "lkm:aspree_pkg::net_benefit"
    assert selected_evidence["evidence_packet"]["items"][0]["package_ref"]["ref"] == (
        "lkm:aspree_pkg::net_benefit"
    )


def test_graph_assets_summary_records_package_anchors_claims_relations_and_matrix(
    tmp_path: Path,
) -> None:
    research_pkg = _write_research_package(tmp_path / "research-demo-gaia")
    run = start_research_run(
        research_pkg,
        topic="aspirin evidence",
        mode="fast-package-native",
        language="en",
        profile="fast",
        run_id="graph-assets",
        wait_for_query_plan=False,
        output_contracts=["gaia_graph_assets"],
    )

    execute_file_provider_run(
        research_pkg,
        run,
        topic="aspirin evidence",
        mode="fast-package-native",
        language="en",
        search_json=[str(_search_json(tmp_path / "search.json"))],
        focus_analysis_json=str(_focus_analysis_json(tmp_path / "focus.json")),
        targeted_search_json=[],
        targeted_query=[],
        focus=None,
        focus_count=1,
        assess_analysis_json=str(_assess_analysis_with_hydrated_ref_json(tmp_path / "assess.json")),
        analysis_provider="checkpoint",
        model=None,
        focus_model=None,
        assess_model=None,
        llm_temperature=0.0,
        llm_timeout=30.0,
        llm_max_retries=0,
        llm_max_tokens=None,
        report_section_concurrency=1,
        search_index="bohrium",
        search_limit=20,
        reasoning_only=True,
        evidence_selection_mode="fast",
        evidence_max_items=8,
        evidence_max_papers=5,
        evidence_max_chains=3,
        focus_analysis_command=None,
        assess_analysis_command=None,
        json_stream=False,
        runtime=_GraphAssetRuntime(),
    )

    state = json.loads(run.state_path.read_text(encoding="utf-8"))
    assert "final_report" not in state["artifacts"]
    assert not (run.run_dir / "trace" / "final_report.md").exists()
    assert "scoped_question" in state["artifacts"]
    graph_assets_path = Path(state["artifacts"]["graph_assets"])
    graph_assets = json.loads(graph_assets_path.read_text(encoding="utf-8"))
    assert graph_assets["success_evaluation"]["success"] is True
    assert graph_assets["corpus"] == {
        "focuses": 1,
        "candidate_items": 1,
        "unique_candidate_items": 1,
        "candidate_paper_leads": 1,
        "candidate_papers": 1,
        "materialization_policy": "all_candidate_papers",
        "materialization_candidate_papers": 1,
        "selected_items": 1,
        "selected_unique_papers": 1,
        "package_refs": ["lkm:bohrium:paper:P_ASPREE"],
        "by_focus": [
            {
                "focus": "aspree_net_benefit",
                "candidate_items": 1,
                "unique_candidate_items": 1,
                "candidate_papers": 1,
                "materialization_candidate_papers": 1,
                "selected_items": 1,
                "selected_unique_papers": 1,
            }
        ],
    }
    assert graph_assets["anchors"][0]["ref"] == "lkm:aspree_pkg::net_benefit"
    assert len(graph_assets["claims"]) == 2
    assert graph_assets["candidate_relations"][0]["dsl_valid"] is True
    assert graph_assets["evidence_matrix"][0]["relation_id"].startswith("candidate_relation_")
    authored_source = (
        research_pkg.path / "src" / "research_demo" / "authored" / "__init__.py"
    ).read_text(encoding="utf-8")
    assert "claim(" in authored_source
    assert "candidate_relation(" in authored_source


def test_assessment_obligations_are_planned_before_report(tmp_path: Path) -> None:
    research_pkg = _write_research_package(tmp_path / "research-demo-gaia")
    run = start_research_run(
        research_pkg,
        topic="aspirin evidence",
        mode="fast-package-native",
        language="en",
        profile="fast",
        run_id="obligations-plan",
        wait_for_query_plan=False,
    )

    execute_file_provider_run(
        research_pkg,
        run,
        topic="aspirin evidence",
        mode="fast-package-native",
        language="en",
        search_json=[str(_search_json(tmp_path / "search.json"))],
        focus_analysis_json=str(_focus_analysis_json(tmp_path / "focus.json")),
        targeted_search_json=[],
        targeted_query=[],
        focus=None,
        focus_count=1,
        assess_analysis_json=str(_assess_analysis_with_obligation_json(tmp_path / "assess.json")),
        analysis_provider="checkpoint",
        model=None,
        focus_model=None,
        assess_model=None,
        llm_temperature=0.0,
        llm_timeout=30.0,
        llm_max_retries=0,
        llm_max_tokens=None,
        report_section_concurrency=1,
        search_index="bohrium",
        search_limit=20,
        reasoning_only=True,
        evidence_selection_mode="off",
        evidence_max_items=8,
        evidence_max_papers=5,
        evidence_max_chains=3,
        focus_analysis_command=None,
        assess_analysis_command=None,
        json_stream=False,
        runtime=_ObligationRuntime(),
    )

    state = json.loads(run.state_path.read_text(encoding="utf-8"))
    obligations_path = Path(state["artifacts"]["obligations"])
    obligations = json.loads(obligations_path.read_text(encoding="utf-8"))
    assert obligations["decision"] == "defer"
    assert obligations["open_obligations"][0]["target"] == {
        "kind": "claim",
        "ref": "aspree_no_net_benefit",
    }
    assert obligations["open_obligations"][0]["action_type"] == "search_more_evidence"
    assert obligations["deferred_obligations"][0]["action"] == (
        "Find direct counter-evidence for the aspirin net-benefit claim."
    )


def test_obligation_loop_executes_search_more_evidence_action(tmp_path: Path) -> None:
    research_pkg = _write_research_package(tmp_path / "research-demo-gaia")
    run = start_research_run(
        research_pkg,
        topic="aspirin evidence",
        mode="fast-package-native",
        language="en",
        profile="fast",
        run_id="obligations-schedule",
        wait_for_query_plan=False,
    )

    execute_file_provider_run(
        research_pkg,
        run,
        topic="aspirin evidence",
        mode="fast-package-native",
        language="en",
        search_json=[str(_search_json(tmp_path / "search.json"))],
        focus_analysis_json=str(_focus_analysis_json(tmp_path / "focus.json")),
        targeted_search_json=[],
        targeted_query=[],
        focus=None,
        focus_count=1,
        assess_analysis_json=str(_assess_analysis_with_obligation_json(tmp_path / "assess.json")),
        analysis_provider="checkpoint",
        model=None,
        focus_model=None,
        assess_model=None,
        llm_temperature=0.0,
        llm_timeout=30.0,
        llm_max_retries=0,
        llm_max_tokens=None,
        report_section_concurrency=1,
        search_index="bohrium",
        search_limit=20,
        reasoning_only=True,
        evidence_selection_mode="off",
        evidence_max_items=8,
        evidence_max_papers=5,
        evidence_max_chains=3,
        obligation_iterations=1,
        focus_analysis_command=None,
        assess_analysis_command=None,
        json_stream=False,
        runtime=_ObligationRuntime(),
    )

    state = json.loads(run.state_path.read_text(encoding="utf-8"))
    obligations_path = Path(state["artifacts"]["obligations"])
    obligations = json.loads(obligations_path.read_text(encoding="utf-8"))
    assert obligations["decision"] == "defer"
    assert obligations["budget"]["obligation_iterations"] == 1
    assert obligations["executions"][0]["action_type"] == "search_more_evidence"
    assert obligations["executions"][0]["status"] == "completed"
    assert obligations["executions"][0]["landscape_path"]
    assert obligations["schedule"]["decision"] == "defer"
    assert all(
        item["action_type"] != "search_more_evidence"
        for item in obligations["open_obligations"]
    )


def test_obligation_loop_executes_assess_focus_action(tmp_path: Path) -> None:
    research_pkg = _write_research_package(tmp_path / "research-demo-gaia")
    run = start_research_run(
        research_pkg,
        topic="aspirin evidence",
        mode="fast-package-native",
        language="en",
        profile="fast",
        run_id="obligations-assess-focus",
        wait_for_query_plan=False,
    )

    execute_file_provider_run(
        research_pkg,
        run,
        topic="aspirin evidence",
        mode="fast-package-native",
        language="en",
        search_json=[str(_search_json(tmp_path / "search.json"))],
        focus_analysis_json=str(_focus_analysis_with_workflow_gaps_json(tmp_path / "focus.json")),
        targeted_search_json=[],
        targeted_query=[],
        focus=None,
        focus_count=1,
        assess_analysis_json=str(_assess_analysis_empty_json(tmp_path / "assess.json")),
        analysis_provider="checkpoint",
        model=None,
        focus_model=None,
        assess_model=None,
        llm_temperature=0.0,
        llm_timeout=30.0,
        llm_max_retries=0,
        llm_max_tokens=None,
        report_section_concurrency=1,
        search_index="bohrium",
        search_limit=20,
        reasoning_only=True,
        evidence_selection_mode="off",
        evidence_max_items=8,
        evidence_max_papers=5,
        evidence_max_chains=3,
        obligation_iterations=1,
        focus_analysis_command=None,
        assess_analysis_command=None,
        json_stream=False,
        runtime=_ObligationRuntime(),
    )

    state = json.loads(run.state_path.read_text(encoding="utf-8"))
    assert len(state["artifacts"]["assessments"]) == 2
    obligations = json.loads(Path(state["artifacts"]["obligations"]).read_text(encoding="utf-8"))
    assert obligations["executions"][0]["action_type"] == "assess_focus"
    assert obligations["executions"][0]["target_qid"] == "bleeding_tradeoff"
    assert obligations["executions"][0]["assessment_path"]
    assert all(
        not (
            item["action_type"] == "assess_focus"
            and item.get("target_qid") == "bleeding_tradeoff"
        )
        for item in obligations["open_obligations"]
    )


def test_obligation_loop_executes_expand_focus_action(tmp_path: Path) -> None:
    research_pkg = _write_research_package(tmp_path / "research-demo-gaia")
    run = start_research_run(
        research_pkg,
        topic="aspirin evidence",
        mode="fast-package-native",
        language="en",
        profile="fast",
        run_id="obligations-expand-focus",
        wait_for_query_plan=False,
    )
    runtime = _RecordingSearchRuntime()

    execute_file_provider_run(
        research_pkg,
        run,
        topic="aspirin evidence",
        mode="fast-package-native",
        language="en",
        search_json=[str(_search_json(tmp_path / "search.json"))],
        focus_analysis_json=str(_focus_analysis_with_expand_only_json(tmp_path / "focus.json")),
        targeted_search_json=[],
        targeted_query=[],
        focus=None,
        focus_count=1,
        assess_analysis_json=str(_assess_analysis_with_obligation_json(tmp_path / "assess.json")),
        analysis_provider="checkpoint",
        model=None,
        focus_model=None,
        assess_model=None,
        llm_temperature=0.0,
        llm_timeout=30.0,
        llm_max_retries=0,
        llm_max_tokens=None,
        report_section_concurrency=1,
        search_index="bohrium",
        search_limit=20,
        reasoning_only=True,
        evidence_selection_mode="off",
        evidence_max_items=8,
        evidence_max_papers=5,
        evidence_max_chains=3,
        obligation_iterations=1,
        focus_analysis_command=None,
        assess_analysis_command=None,
        json_stream=False,
        runtime=runtime,
    )

    state = json.loads(run.state_path.read_text(encoding="utf-8"))
    obligations = json.loads(Path(state["artifacts"]["obligations"]).read_text(encoding="utf-8"))
    assert runtime.queries == ["aspirin primary prevention subgroup evidence"]
    assert obligations["executions"][0]["action_type"] == "expand_focus"
    landscape = json.loads(
        Path(obligations["executions"][0]["landscape_path"]).read_text(encoding="utf-8")
    )
    assert landscape["action"] == "obligation.expand_focus"
    assert landscape["target"] == {"kind": "question", "id": "subgroup_evidence"}


def test_obligation_loop_executes_close_coverage_gap_action(tmp_path: Path) -> None:
    research_pkg = _write_research_package(tmp_path / "research-demo-gaia")
    run = start_research_run(
        research_pkg,
        topic="aspirin evidence",
        mode="fast-package-native",
        language="en",
        profile="fast",
        run_id="obligations-close-coverage",
        wait_for_query_plan=False,
    )
    runtime = _RecordingSearchRuntime()

    execute_file_provider_run(
        research_pkg,
        run,
        topic="aspirin evidence",
        mode="fast-package-native",
        language="en",
        search_json=[str(_search_json(tmp_path / "search.json"))],
        focus_analysis_json=str(_focus_analysis_with_coverage_gap_json(tmp_path / "focus.json")),
        targeted_search_json=[],
        targeted_query=[],
        focus=None,
        focus_count=1,
        assess_analysis_json=str(_assess_analysis_empty_json(tmp_path / "assess.json")),
        analysis_provider="checkpoint",
        model=None,
        focus_model=None,
        assess_model=None,
        llm_temperature=0.0,
        llm_timeout=30.0,
        llm_max_retries=0,
        llm_max_tokens=None,
        report_section_concurrency=1,
        search_index="bohrium",
        search_limit=20,
        reasoning_only=True,
        evidence_selection_mode="off",
        evidence_max_items=8,
        evidence_max_papers=5,
        evidence_max_chains=3,
        obligation_iterations=1,
        focus_analysis_command=None,
        assess_analysis_command=None,
        json_stream=False,
        runtime=runtime,
    )

    state = json.loads(run.state_path.read_text(encoding="utf-8"))
    obligations = json.loads(Path(state["artifacts"]["obligations"]).read_text(encoding="utf-8"))
    assert runtime.queries == [
        "Close coverage gap missing_harms: Bleeding-harm evidence is not yet covered."
    ]
    assert obligations["executions"][0]["action_type"] == "close_coverage_gap"
    landscape = json.loads(
        Path(obligations["executions"][0]["landscape_path"]).read_text(encoding="utf-8")
    )
    assert landscape["action"] == "obligation.close_coverage_gap"
    assert landscape["target"] == {"kind": "question", "id": "research_coverage"}


def test_obligation_loop_executes_supported_deferred_workflow_action(
    tmp_path: Path,
) -> None:
    research_pkg = _write_research_package(tmp_path / "research-demo-gaia")
    run = start_research_run(
        research_pkg,
        topic="aspirin evidence",
        mode="fast-package-native",
        language="en",
        profile="fast",
        run_id="obligations-deferred-coverage",
        wait_for_query_plan=False,
    )
    runtime = _DeferredCoverageRuntime()

    execute_file_provider_run(
        research_pkg,
        run,
        topic="aspirin evidence",
        mode="fast-package-native",
        language="en",
        search_json=[str(_search_json(tmp_path / "search.json"))],
        focus_analysis_json=str(_focus_analysis_json(tmp_path / "focus.json")),
        targeted_search_json=[],
        targeted_query=[],
        focus=None,
        focus_count=1,
        assess_analysis_json=str(_assess_analysis_empty_json(tmp_path / "assess.json")),
        analysis_provider="checkpoint",
        model=None,
        focus_model=None,
        assess_model=None,
        llm_temperature=0.0,
        llm_timeout=30.0,
        llm_max_retries=0,
        llm_max_tokens=None,
        report_section_concurrency=1,
        search_index="bohrium",
        search_limit=20,
        reasoning_only=True,
        evidence_selection_mode="off",
        evidence_max_items=8,
        evidence_max_papers=5,
        evidence_max_chains=3,
        obligation_iterations=1,
        focus_analysis_command=None,
        assess_analysis_command=None,
        json_stream=False,
        runtime=runtime,
    )

    state = json.loads(run.state_path.read_text(encoding="utf-8"))
    obligations = json.loads(Path(state["artifacts"]["obligations"]).read_text(encoding="utf-8"))
    assert runtime.queries == [
        "Close coverage gap missing_harms: Bleeding-harm evidence is thin."
    ]
    assert obligations["remaining_obligation_iterations"] == 0
    assert obligations["executions"][0]["action_type"] == "close_coverage_gap"
    assert obligations["executions"][0]["status"] == "completed"
    assert all(
        item["action_type"] != "close_coverage_gap"
        for item in obligations["deferred_obligations"]
    )


def test_obligation_loop_uses_litellm_policy_to_order_supported_actions(
    tmp_path: Path,
) -> None:
    research_pkg = _write_research_package(tmp_path / "research-demo-gaia")
    run = start_research_run(
        research_pkg,
        topic="aspirin evidence",
        mode="fast-package-native",
        language="en",
        profile="fast",
        run_id="obligations-policy",
        wait_for_query_plan=False,
    )
    runtime = _PolicyRuntime(
        {
            "schema_version": 1,
            "kind": "research_obligation_policy",
            "rankings": [
                {
                    "target_qid": "research_coverage",
                    "action_type": "close_coverage_gap",
                    "score": 0.99,
                    "reason": "Bleeding-harm coverage changes the review conclusion.",
                    "report_impact": "high",
                    "uncertainty_reduction": "high",
                }
            ],
        }
    )

    execute_file_provider_run(
        research_pkg,
        run,
        topic="aspirin evidence",
        mode="fast-package-native",
        language="en",
        search_json=[str(_search_json(tmp_path / "search.json"))],
        focus_analysis_json=str(_focus_analysis_with_workflow_gaps_json(tmp_path / "focus.json")),
        targeted_search_json=[],
        targeted_query=[],
        focus=None,
        focus_count=1,
        assess_analysis_json=str(_assess_analysis_empty_json(tmp_path / "assess.json")),
        analysis_provider="litellm",
        model="test-model",
        focus_model=None,
        assess_model=None,
        llm_temperature=0.0,
        llm_timeout=30.0,
        llm_max_retries=0,
        llm_max_tokens=None,
        report_section_concurrency=1,
        search_index="bohrium",
        search_limit=20,
        reasoning_only=True,
        evidence_selection_mode="off",
        evidence_max_items=8,
        evidence_max_papers=5,
        evidence_max_chains=3,
        obligation_iterations=1,
        focus_analysis_command=None,
        assess_analysis_command=None,
        json_stream=False,
        runtime=runtime,
    )

    state = json.loads(run.state_path.read_text(encoding="utf-8"))
    obligations = json.loads(Path(state["artifacts"]["obligations"]).read_text(encoding="utf-8"))
    assert runtime.policy_inputs
    contract = runtime.policy_inputs[0]["contract"]
    assert isinstance(contract, dict)
    assert contract["contract"] == "gaia.research.obligation_policy"
    assert runtime.queries == [
        "Close coverage gap missing_harms: Bleeding-harm evidence is not yet covered."
    ]
    assert obligations["executions"][0]["action_type"] == "close_coverage_gap"
    assert obligations["executions"][0]["policy_selection"]["reason"] == (
        "Bleeding-harm coverage changes the review conclusion."
    )


def test_workflow_obligations_are_collected_before_report(tmp_path: Path) -> None:
    research_pkg = _write_research_package(tmp_path / "research-demo-gaia")
    run = start_research_run(
        research_pkg,
        topic="aspirin evidence",
        mode="fast-package-native",
        language="en",
        profile="fast",
        run_id="workflow-obligations",
        wait_for_query_plan=False,
    )

    execute_file_provider_run(
        research_pkg,
        run,
        topic="aspirin evidence",
        mode="fast-package-native",
        language="en",
        search_json=[str(_search_json(tmp_path / "search.json"))],
        focus_analysis_json=str(_focus_analysis_with_workflow_gaps_json(tmp_path / "focus.json")),
        targeted_search_json=[],
        targeted_query=[],
        focus=None,
        focus_count=1,
        assess_analysis_json=str(_assess_analysis_with_obligation_json(tmp_path / "assess.json")),
        analysis_provider="checkpoint",
        model=None,
        focus_model=None,
        assess_model=None,
        llm_temperature=0.0,
        llm_timeout=30.0,
        llm_max_retries=0,
        llm_max_tokens=None,
        report_section_concurrency=1,
        search_index="bohrium",
        search_limit=20,
        reasoning_only=True,
        evidence_selection_mode="off",
        evidence_max_items=8,
        evidence_max_papers=5,
        evidence_max_chains=3,
        focus_analysis_command=None,
        assess_analysis_command=None,
        json_stream=False,
        runtime=_ObligationRuntime(),
    )

    state = json.loads(run.state_path.read_text(encoding="utf-8"))
    obligations_path = Path(state["artifacts"]["obligations"])
    obligations = json.loads(obligations_path.read_text(encoding="utf-8"))
    action_types = [item["action_type"] for item in obligations["open_obligations"]]
    assert "assess_focus" in action_types
    assert "expand_focus" in action_types
    assert "close_coverage_gap" in action_types
    for item in obligations["open_obligations"]:
        if item["action_type"] in {"assess_focus", "expand_focus", "close_coverage_gap"}:
            assert item["diagnostic_kind"] == "focus_weakness"
            assert item["anchor"]["gaia_research"]["obligation_type"] == "workflow"


def test_unresolved_anchor_obligations_are_synced_to_inquiry_state(tmp_path: Path) -> None:
    research_pkg = _write_research_package(tmp_path / "research-demo-gaia")
    run = start_research_run(
        research_pkg,
        topic="aspirin evidence",
        mode="fast-package-native",
        language="en",
        profile="fast",
        run_id="anchor-obligations",
        wait_for_query_plan=False,
        output_contracts=["gaia_graph_assets"],
    )

    execute_file_provider_run(
        research_pkg,
        run,
        topic="aspirin evidence",
        mode="fast-package-native",
        language="en",
        search_json=[str(_search_json(tmp_path / "search.json"))],
        focus_analysis_json=str(_focus_analysis_json(tmp_path / "focus.json")),
        targeted_search_json=[],
        targeted_query=[],
        focus=None,
        focus_count=1,
        assess_analysis_json=str(_assess_analysis_with_obligation_json(tmp_path / "assess.json")),
        analysis_provider="checkpoint",
        model=None,
        focus_model=None,
        assess_model=None,
        llm_temperature=0.0,
        llm_timeout=30.0,
        llm_max_retries=0,
        llm_max_tokens=None,
        report_section_concurrency=1,
        search_index="bohrium",
        search_limit=20,
        reasoning_only=True,
        evidence_selection_mode="fast",
        evidence_max_items=8,
        evidence_max_papers=5,
        evidence_max_chains=3,
        focus_analysis_command=None,
        assess_analysis_command=None,
        json_stream=False,
        runtime=_UnresolvedAnchorRuntime(),
    )

    obligations = load_state(research_pkg.path).synthetic_obligations
    assert any(
        obligation.diagnostic_kind == "structural_hole"
        and obligation.anchor["gaia_research"]["action_type"] == "resolve_anchor"
        for obligation in obligations
    )

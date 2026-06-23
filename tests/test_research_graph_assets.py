"""Tests for Gaia-native research graph assets and run surface."""

from __future__ import annotations

import json
from pathlib import Path

from gaia_research.artifacts import load_research_package
from gaia_research.graph_assets import evaluate_graph_asset_success, project_evidence_matrix_rows
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


def test_every_run_surface_records_graph_asset_goal_and_scoped_question(
    tmp_path: Path,
) -> None:
    _write_research_package(tmp_path / "workspace")
    pkg = load_research_package(tmp_path / "workspace")

    run = start_research_run(
        pkg,
        topic="deconfined criticality",
        focus="Is deconfined criticality continuous or weakly first-order?",
        mode="fast-package-native",
        language="en",
        profile="fast",
        run_id="dqc-fast",
        wait_for_query_plan=False,
    )

    state = json.loads(run.state_path.read_text(encoding="utf-8"))
    assert state["mode"] == "fast-package-native"
    assert state["output_contract"] == "gaia_graph_assets"
    assert state["output_contracts"] == ["gaia_graph_assets", "research_report"]
    assert "requires_report" not in state
    assert state["phase"] == "graph_scope"
    assert state["input_kind"] == "focus"
    assert "final_report" not in state["artifacts"]

    scoped_question_path = Path(state["artifacts"]["scoped_question"])
    scoped_question = json.loads(scoped_question_path.read_text(encoding="utf-8"))
    assert scoped_question == {
        "kind": "scoped_question",
        "id": "dqc-fast_question",
        "question": "Is deconfined criticality continuous or weakly first-order?",
        "metadata": {"gaia_research": {"kind": "research_question"}},
    }


def test_run_can_skip_report_but_still_uses_graph_assets(
    tmp_path: Path,
) -> None:
    _write_research_package(tmp_path / "workspace")
    pkg = load_research_package(tmp_path / "workspace")

    run = start_research_run(
        pkg,
        topic="deconfined criticality",
        mode="fast-package-native",
        language="en",
        profile="fast",
        run_id="dqc-mvp",
        wait_for_query_plan=False,
        output_contracts=["gaia_graph_assets"],
    )

    state = json.loads(run.state_path.read_text(encoding="utf-8"))
    assert state["output_contract"] == "gaia_graph_assets"
    assert state["output_contracts"] == ["gaia_graph_assets"]
    assert "requires_report" not in state
    assert state["phase"] == "graph_scope"
    assert "scoped_question" in state["artifacts"]


def test_graph_asset_success_validator_requires_core_assets_and_obligation_decision() -> None:
    artifact = evaluate_graph_asset_success(
        {
            "scoped_question": {"id": "q1", "question": "What is the evidence?"},
            "anchors": [
                {
                    "id": "a1",
                    "kind": "claim",
                    "source_ref": "lkm:default:paper:P1",
                    "import_name": "paper_p1",
                    "symbol": "claim_a",
                    "ref": "paper_p1.claim_a",
                }
            ],
            "claims": [
                {"id": "c1", "gaia_object_type": "claim"},
                {"id": "c2", "gaia_object_type": "claim"},
            ],
            "candidate_relations": [
                {"id": "r1", "claim_refs": ["paper_p1.claim_a", "c1"], "dsl_valid": True}
            ],
            "evidence_matrix": [{"relation_id": "r1"}],
            "open_obligations": [
                {
                    "target": {"kind": "claim", "ref": "c1"},
                    "action_type": "search_more_evidence",
                    "action": "Find direct contradicting evidence.",
                }
            ],
            "obligation_decision": "continue",
        }
    )

    assert artifact["kind"] == "gaia_native_research_graph_asset_success"
    assert artifact["success"] is True
    assert artifact["missing"] == []


def test_graph_asset_success_validator_requires_decision_for_open_obligations() -> None:
    artifact = evaluate_graph_asset_success(
        {
            "scoped_question": {"id": "q1", "question": "What is the evidence?"},
            "anchors": [
                {
                    "id": "a1",
                    "kind": "claim",
                    "source_ref": "lkm:default:paper:P1",
                    "import_name": "paper_p1",
                    "symbol": "claim_a",
                    "ref": "paper_p1.claim_a",
                }
            ],
            "claims": [
                {"id": "c1", "gaia_object_type": "claim"},
                {"id": "c2", "gaia_object_type": "claim"},
            ],
            "candidate_relations": [
                {"id": "r1", "claim_refs": ["paper_p1.claim_a", "c1"], "dsl_valid": True}
            ],
            "evidence_matrix": [{"relation_id": "r1"}],
            "open_obligations": [
                {
                    "target": {"kind": "claim", "ref": "c1"},
                    "action_type": "search_more_evidence",
                    "action": "Find direct contradicting evidence.",
                }
            ],
        }
    )

    assert artifact["success"] is False
    assert "obligation_decision" in artifact["missing"]


def test_graph_asset_success_allows_unresolved_anchors_when_obligated() -> None:
    artifact = evaluate_graph_asset_success(
        {
            "scoped_question": {"id": "q1", "question": "What is the evidence?"},
            "anchors": [
                {
                    "id": "resolved_a",
                    "kind": "claim",
                    "source_ref": "lkm:default:paper:P1",
                    "import_name": "paper_p1",
                    "symbol": "claim_a",
                    "ref": "lkm:paper_p1::claim_a",
                    "status": "resolved",
                },
                {
                    "id": "missing_b",
                    "kind": "claim",
                    "source_ref": "lkm:default:paper:P2",
                    "import_name": None,
                    "symbol": None,
                    "ref": None,
                    "status": "unresolved",
                },
            ],
            "claims": [
                {"id": "c1", "gaia_object_type": "claim"},
                {"id": "c2", "gaia_object_type": "claim"},
            ],
            "candidate_relations": [
                {"id": "r1", "claim_refs": ["lkm:paper_p1::claim_a", "c1"], "dsl_valid": True}
            ],
            "evidence_matrix": [{"relation_id": "r1"}],
            "open_obligations": [],
            "deferred_obligations": [
                {
                    "target": {"kind": "claim", "id": "missing_b"},
                    "action_type": "resolve_anchor",
                    "action": "Resolve missing anchor.",
                }
            ],
        }
    )

    assert artifact["success"] is True
    assert artifact["checks"]["resolved_anchors"] is True
    assert artifact["checks"]["unresolved_anchor_obligations"] is True


def test_evidence_matrix_projection_uses_only_candidate_relation_metadata() -> None:
    rows = project_evidence_matrix_rows(
        [
            {
                "id": "candidate_relation_drift_supports_candidate",
                "claims": ["paper_pkg__claim_drift", "research_claim_weak_first_order"],
                "pattern": None,
                "rationale": "Finite-size drift supports the weak first-order candidate.",
                "metadata": {
                    "gaia_research": {
                        "kind": "candidate_relation",
                        "scope_question": "dqc-order",
                        "relation_type": "supports",
                        "strength": "moderate",
                        "epistemic_status": "scaffolded",
                        "system": "lattice deconfined criticality models",
                        "condition": "finite-size regimes",
                        "method": "finite-size scaling",
                        "observable": "drift in scaling observables",
                        "certainty": "moderate",
                        "scope_note": "Applies only to the studied regimes.",
                        "source_refs": [{"kind": "lkm_anchor", "id": "claim_drift"}],
                    }
                },
            },
            {
                "id": "unjudged_search_hit",
                "claims": ["paper_pkg__claim_noise", "research_claim_weak_first_order"],
                "metadata": {"gaia_research": {"kind": "evidence_context"}},
            },
        ]
    )

    assert rows == [
        {
            "relation_id": "candidate_relation_drift_supports_candidate",
            "source_claim_id": "paper_pkg__claim_drift",
            "target_claim_id": "research_claim_weak_first_order",
            "claim_ids": ["paper_pkg__claim_drift", "research_claim_weak_first_order"],
            "pattern": None,
            "relation_type": "supports",
            "strength": "moderate",
            "scope_question": "dqc-order",
            "rationale": "Finite-size drift supports the weak first-order candidate.",
            "epistemic_status": "scaffolded",
            "system": "lattice deconfined criticality models",
            "condition": "finite-size regimes",
            "method": "finite-size scaling",
            "observable": "drift in scaling observables",
            "certainty": "moderate",
            "scope_note": "Applies only to the studied regimes.",
            "source_refs": [{"kind": "lkm_anchor", "id": "claim_drift"}],
        }
    ]

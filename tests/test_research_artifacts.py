"""Unit tests for research artifact persistence."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest
from gaia.engine.inquiry.state import load_state

from gaia_research.artifacts import (
    ResearchPackage,
    append_research_event,
    ensure_research_manifest,
    write_research_artifact,
)
from gaia_research.sync import (
    ResearchSyncSourceError,
    sync_assessment_artifact,
    sync_focus_artifact,
    sync_landscape_artifact,
)


def _pkg(path: Path) -> ResearchPackage:
    return ResearchPackage(
        path=path,
        project_name="research-demo-gaia",
        import_name="research_demo",
        namespace="research_demo",
    )


def _assessment_with_obligation(*, actionable: bool | None = None) -> dict[str, object]:
    obligation: dict[str, object] = {
        "kind": "needs_more_evidence",
        "content": "需要更深的纸面核查。",
        "source_refs": [{"kind": "variable", "id": "v1"}],
    }
    if actionable is not None:
        obligation["actionable"] = actionable
    return {
        "kind": "assessment",
        "focus": {"kind": "focus", "id": "focus_1"},
        "relations": [],
        "candidate_obligations": [obligation],
    }


def test_research_manifest_updates_use_atomic_replace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_write_text = Path.write_text

    def guarded_write_text(self: Path, *args: Any, **kwargs: Any) -> int:
        if self.name == "manifest.json":
            raise AssertionError("manifest.json must be updated through atomic replace")
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", guarded_write_text)
    pkg = _pkg(tmp_path)

    manifest = ensure_research_manifest(pkg)
    append_research_event(pkg, "demo.event", {"ok": True})
    artifact_path = write_research_artifact(pkg, "demos", "demo", {"kind": "demo"})

    manifest_path = tmp_path / ".gaia" / "research" / "manifest.json"
    persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert persisted["events"]["last_event"] == "demo.event"
    assert persisted["artifacts"][-1]["path"] == str(artifact_path)


def test_assessment_obligations_default_to_deferred_gaps(tmp_path: Path) -> None:
    result = sync_assessment_artifact(
        _pkg(tmp_path),
        _assessment_with_obligation(),
        source_writes=False,
    )

    assert result.obligations_added == []
    assert len(result.obligations_deferred) == 1
    assert load_state(tmp_path).synthetic_obligations == []


def test_actionable_assessment_obligation_writes_open_inquiry_item(tmp_path: Path) -> None:
    result = sync_assessment_artifact(
        _pkg(tmp_path),
        _assessment_with_obligation(actionable=True),
        source_writes=False,
    )

    assert len(result.obligations_added) == 1
    assert result.obligations_deferred == []
    obligations = load_state(tmp_path).synthetic_obligations
    assert len(obligations) == 1
    assert obligations[0].target_qid == "focus_1"


def test_actionable_assessment_obligation_can_target_claim_with_action(tmp_path: Path) -> None:
    assessment = {
        "kind": "assessment",
        "focus": {"kind": "focus", "id": "focus_1"},
        "relations": [],
        "candidate_obligations": [
            {
                "kind": "needs_more_evidence",
                "target": {"kind": "claim", "ref": "research_claim_weak_first_order"},
                "action_type": "search_more_evidence",
                "action": "Find direct counter-evidence for the weak first-order claim.",
                "content": "Need stronger adversarial evidence before treating this as stable.",
                "source_refs": [{"kind": "package_ref", "id": "lkm:paper_pkg::claim_drift"}],
                "actionable": True,
            }
        ],
    }

    result = sync_assessment_artifact(_pkg(tmp_path), assessment, source_writes=False)

    assert result.open_obligations == [
        {
            "qid": result.obligations_added[0],
            "target": {"kind": "claim", "ref": "research_claim_weak_first_order"},
            "target_qid": "research_claim_weak_first_order",
            "action_type": "search_more_evidence",
            "action": "Find direct counter-evidence for the weak first-order claim.",
            "content": (
                "action_type=search_more_evidence; action=Find direct counter-evidence "
                "for the weak first-order claim.; note=Need stronger adversarial "
                "evidence before treating this as stable."
            ),
            "diagnostic_kind": "support_weak",
            "anchor": {
                "kind": "assessment_obligation",
                "source_refs": [{"kind": "package_ref", "id": "lkm:paper_pkg::claim_drift"}],
                "gaia_research": {
                    "obligation_type": "workflow",
                    "action_type": "search_more_evidence",
                    "target": {"kind": "claim", "ref": "research_claim_weak_first_order"},
                    "auto_closeable": True,
                    "blocking": True,
                    "budget_class": "evidence",
                    "source": "assessment",
                },
            },
            "source_refs": [{"kind": "package_ref", "id": "lkm:paper_pkg::claim_drift"}],
        }
    ]
    obligations = load_state(tmp_path).synthetic_obligations
    assert obligations[0].target_qid == "research_claim_weak_first_order"
    assert obligations[0].content.startswith("action_type=search_more_evidence")
    assert obligations[0].anchor["gaia_research"]["obligation_type"] == "workflow"


def test_duplicate_actionable_obligation_still_returns_existing_open_item(
    tmp_path: Path,
) -> None:
    assessment = {
        "kind": "assessment",
        "focus": {"kind": "focus", "id": "focus_1"},
        "relations": [],
        "candidate_obligations": [
            {
                "kind": "needs_more_evidence",
                "target": {"kind": "claim", "ref": "research_claim_weak_first_order"},
                "action_type": "search_more_evidence",
                "action": "Find direct counter-evidence for the weak first-order claim.",
                "content": "Need stronger adversarial evidence before treating this as stable.",
                "source_refs": [{"kind": "package_ref", "id": "lkm:paper_pkg::claim_drift"}],
                "actionable": True,
            }
        ],
    }

    first = sync_assessment_artifact(_pkg(tmp_path), assessment, source_writes=False)
    second = sync_assessment_artifact(_pkg(tmp_path), assessment, source_writes=False)

    assert len(first.obligations_added) == 1
    assert second.obligations_added == []
    assert second.obligations_skipped == 1
    assert second.open_obligations[0]["qid"] == first.obligations_added[0]
    assert len(load_state(tmp_path).synthetic_obligations) == 1


def test_deferred_assessment_obligation_preserves_target_and_action(tmp_path: Path) -> None:
    assessment = {
        "kind": "assessment",
        "focus": {"kind": "focus", "id": "focus_1"},
        "relations": [],
        "candidate_obligations": [
            {
                "kind": "needs_method_check",
                "target": {"kind": "relation", "ref": "candidate_relation_drift"},
                "action_type": "check_method_scope",
                "action": "Check whether finite-size scaling assumptions match the relation.",
                "content": "The method scope is unresolved.",
                "source_refs": [{"kind": "package_ref", "id": "lkm:paper_pkg::claim_drift"}],
            }
        ],
    }

    result = sync_assessment_artifact(_pkg(tmp_path), assessment, source_writes=False)

    assert result.obligations_added == []
    assert result.obligations_deferred == [
        {
            "target": {"kind": "relation", "ref": "candidate_relation_drift"},
            "target_qid": "candidate_relation_drift",
            "action_type": "check_method_scope",
            "action": "Check whether finite-size scaling assumptions match the relation.",
            "content": (
                "action_type=check_method_scope; action=Check whether finite-size "
                "scaling assumptions match the relation.; note=The method scope is unresolved."
            ),
            "diagnostic_kind": "other",
            "anchor": {
                "kind": "assessment_obligation",
                "source_refs": [{"kind": "package_ref", "id": "lkm:paper_pkg::claim_drift"}],
                "gaia_research": {
                    "obligation_type": "future_research",
                    "action_type": "check_method_scope",
                    "target": {"kind": "relation", "ref": "candidate_relation_drift"},
                    "auto_closeable": False,
                    "blocking": False,
                    "budget_class": "research",
                    "source": "assessment",
                },
            },
            "source_refs": [{"kind": "package_ref", "id": "lkm:paper_pkg::claim_drift"}],
        }
    ]


def test_focus_sync_coverage_gap_uses_research_obligation_metadata(tmp_path: Path) -> None:
    focus_artifact = {
        "kind": "focus_synthesis",
        "focuses": [
            {
                "id": "focus_1",
                "kind": "research_focus",
                "status": "candidate",
                "question": "What evidence is missing?",
                "rationale": "The field map found a thin area.",
                "priority": "high",
                "readiness": "needs_expand",
                "scope": {},
                "coverage": {},
                "evidence_refs": [{"kind": "variable", "id": "v1"}],
                "suggested_queries": [],
            }
        ],
        "coverage_gaps": [
            {
                "id": "missing_experiment",
                "kind": "coverage_gap",
                "description": "Experimental evidence is missing.",
                "evidence_refs": [{"kind": "variable", "id": "v1"}],
            }
        ],
        "notes": [],
    }

    result = sync_focus_artifact(_pkg(tmp_path), focus_artifact, source_writes=False)

    assert result.obligations_deferred[0]["action_type"] == "close_coverage_gap"
    assert result.obligations_deferred[0]["diagnostic_kind"] == "focus_weakness"
    metadata = result.obligations_deferred[0]["anchor"]["gaia_research"]
    assert metadata["obligation_type"] == "workflow"
    assert metadata["auto_closeable"] is True
    assert metadata["source"] == "focus_artifact"


def test_landscape_sync_coverage_gap_uses_research_obligation_metadata(tmp_path: Path) -> None:
    landscape = {
        "kind": "research_landscape",
        "target": {"kind": "topic", "id": "topic_1"},
        "candidate_coverage_gaps": [
            {
                "id": "thin_bucket",
                "description": "Field-theory evidence is thin.",
                "evidence_refs": [{"kind": "variable", "id": "v1"}],
            }
        ],
    }

    result = sync_landscape_artifact(_pkg(tmp_path), landscape)

    assert result.obligations_deferred[0]["action_type"] == "close_coverage_gap"
    assert result.obligations_deferred[0]["diagnostic_kind"] == "focus_weakness"
    metadata = result.obligations_deferred[0]["anchor"]["gaia_research"]
    assert metadata["obligation_type"] == "workflow"
    assert metadata["source"] == "landscape"


def test_assessment_sync_rejects_unparseable_authored_source(tmp_path: Path) -> None:
    assessment = {
        "kind": "assessment",
        "focus": {"kind": "focus", "id": "focus_1"},
        "evidence_packet": {"items": []},
        "relations": [
            {
                "id": "bad_foreign_ref",
                "type": "opposes",
                "claim": "An invalid foreign ref must not leave broken authored source.",
                "claim_refs": ["lkm:bad-module::seed", "seed_alt"],
            }
        ],
        "candidate_obligations": [],
    }

    with pytest.raises(ResearchSyncSourceError, match="authored source is not parseable"):
        sync_assessment_artifact(_pkg(tmp_path), assessment)
    authored_source = (tmp_path / "research_demo" / "authored" / "__init__.py").read_text(
        encoding="utf-8"
    )
    ast.parse(authored_source)
    assert "bad-module" not in authored_source
    assert "candidate_relation(" not in authored_source


def test_assessment_sync_review_note_uses_reader_facing_review_markdown(tmp_path: Path) -> None:
    assessment = {
        "kind": "assessment",
        "focus": {"kind": "focus", "id": "focus_1"},
        "relations": [],
        "review": {
            "language": "en",
            "depth": "review",
            "abstract": "Review abstract [variable:v1].",
            "key_points": ["Key result [variable:v1]."],
            "summary": "Summary keeps reader-facing prose [variable:v1].",
            "sections": [{"title": "Evidence", "body": "Section body [variable:v1]."}],
            "evidence_table": [{"claim": "Table claim [variable:v1]", "direction": "supports"}],
            "limitations": ["Limitation [variable:v1]."],
            "next_queries": ["follow-up query [variable:v1]"],
        },
        "candidate_obligations": [],
    }

    result = sync_assessment_artifact(_pkg(tmp_path), assessment)

    assert len(result.notes_written) == 1
    authored_source = (tmp_path / "research_demo" / "authored" / "__init__.py").read_text(
        encoding="utf-8"
    )
    assert "[variable:v1]" not in authored_source
    assert "Review abstract" in authored_source
    assert "Key result" in authored_source
    assert "Table claim" in authored_source
    assert "follow-up query" in authored_source


def test_assessment_sync_authors_new_claims_before_candidate_relations(
    tmp_path: Path,
) -> None:
    assessment = {
        "kind": "assessment",
        "focus": {"kind": "focus", "id": "dqc-order"},
        "new_claims": [
            {
                "id": "dqc_weak_first_order",
                "claim": "Deconfined criticality is weakly first-order in the studied regimes.",
                "rationale": "Finite-size drift and histogram evidence motivate this candidate.",
                "answers_question": "dqc-order",
                "source_refs": [{"kind": "lkm_anchor", "id": "claim_drift"}],
            }
        ],
        "relations": [
            {
                "id": "drift_supports_candidate",
                "type": "supports",
                "claim_refs": ["lkm:paper_pkg::claim_drift", "dqc_weak_first_order"],
                "rationale": "The drift claim supports the newly authored candidate claim.",
                "epistemic_status": "scaffolded",
                "system": "lattice deconfined criticality models",
                "condition": "finite-size simulation regimes",
                "method": "finite-size scaling",
                "observable": "drift in scaling observables",
                "certainty": "moderate",
                "scope_note": "Applies only to the studied regimes.",
                "source_refs": [{"kind": "lkm_anchor", "id": "claim_drift"}],
            }
        ],
        "candidate_obligations": [],
    }

    result = sync_assessment_artifact(_pkg(tmp_path), assessment)

    assert len(result.claims_written) == 1
    assert len(result.candidate_relations_written) == 1
    assert result.evidence_matrix_rows == [
        {
            "relation_id": result.candidate_relations_written[0],
            "source_claim_id": "paper_pkg__claim_drift",
            "target_claim_id": result.claims_written[0],
            "claim_ids": ["paper_pkg__claim_drift", result.claims_written[0]],
            "pattern": None,
            "relation_type": "supports",
            "scope_question": "dqc-order",
            "rationale": "The drift claim supports the newly authored candidate claim.",
            "epistemic_status": "scaffolded",
            "system": "lattice deconfined criticality models",
            "condition": "finite-size simulation regimes",
            "method": "finite-size scaling",
            "observable": "drift in scaling observables",
            "certainty": "moderate",
            "scope_note": "Applies only to the studied regimes.",
            "source_refs": [{"kind": "lkm_anchor", "id": "claim_drift"}],
        }
    ]
    authored_path = tmp_path / "research_demo" / "authored" / "__init__.py"
    authored_source = authored_path.read_text(encoding="utf-8")
    ast.parse(authored_source)
    assert "claim(" in authored_source
    assert "candidate_relation(" in authored_source
    assert "kind': 'research_claim'" in authored_source
    assert "'status': 'candidate'" in authored_source
    assert "kind': 'candidate_relation'" in authored_source
    assert "paper_pkg__claim_drift" in authored_source
    assert "dqc_weak_first_order" in authored_source
    assert f"from research_demo import {result.claims_written[0]}" not in authored_source
    assert "gaia author" not in authored_source


def test_assessment_sync_completes_partial_relation_claim_refs_from_package_sources(
    tmp_path: Path,
) -> None:
    assessment = {
        "kind": "assessment",
        "focus": {"kind": "focus", "id": "dqc-order"},
        "new_claims": [
            {
                "id": "dqc_continuous_scaling",
                "claim": "Some deconfined-criticality simulations exhibit continuous scaling.",
                "source_refs": [{"kind": "package_ref", "id": "lkm:paper_pkg::claim_scaling"}],
            }
        ],
        "relations": [
            {
                "id": "scaling_supports_candidate",
                "type": "supports",
                "claim_refs": ["dqc_continuous_scaling"],
                "source_refs": [
                    {"kind": "package_ref", "id": "lkm:paper_pkg::claim_scaling"}
                ],
                "rationale": "The grounded scaling claim supports the new candidate claim.",
            }
        ],
        "candidate_obligations": [],
    }

    result = sync_assessment_artifact(_pkg(tmp_path), assessment)

    assert result.candidate_relations_skipped == []
    assert len(result.candidate_relations_written) == 1
    assert result.evidence_matrix_rows[0]["claim_ids"] == [
        "paper_pkg__claim_scaling",
        result.claims_written[0],
    ]
    authored_source = (tmp_path / "research_demo" / "authored" / "__init__.py").read_text(
        encoding="utf-8"
    )
    ast.parse(authored_source)
    assert "candidate_relation(" in authored_source
    assert "paper_pkg__claim_scaling" in authored_source


def test_assessment_sync_reuses_existing_research_claim_by_normalized_text(
    tmp_path: Path,
) -> None:
    first_assessment = {
        "kind": "assessment",
        "focus": {"kind": "focus", "id": "focus_a"},
        "new_claims": [
            {
                "id": "shared_candidate_a",
                "claim": "Deconfined criticality is weakly first-order in studied regimes.",
                "rationale": "Initial assessment proposed this synthesis claim.",
                "answers_question": "focus_a",
                "source_refs": [{"kind": "package_ref", "id": "lkm:paper_pkg::claim_drift"}],
            }
        ],
        "relations": [],
        "candidate_obligations": [],
    }
    first = sync_assessment_artifact(_pkg(tmp_path), first_assessment)
    existing_binding = first.claims_written[0]

    second_assessment = {
        "kind": "assessment",
        "focus": {"kind": "focus", "id": "focus_b"},
        "new_claims": [
            {
                "id": "shared_candidate_b",
                "claim": "  Deconfined   criticality is weakly first-order in studied regimes. ",
                "rationale": "A later focus produced the same candidate claim.",
                "answers_question": "focus_b",
                "source_refs": [{"kind": "package_ref", "id": "lkm:paper_pkg::claim_drift"}],
            }
        ],
        "relations": [
            {
                "id": "drift_supports_reused_candidate",
                "type": "supports",
                "claim_refs": ["lkm:paper_pkg::claim_drift", "shared_candidate_b"],
                "rationale": "The drift claim supports the reused candidate claim.",
                "source_refs": [{"kind": "package_ref", "id": "lkm:paper_pkg::claim_drift"}],
            }
        ],
        "candidate_obligations": [],
    }
    second = sync_assessment_artifact(_pkg(tmp_path), second_assessment)

    assert second.claims_written == []
    assert second.claims_skipped == [f"shared_candidate_b -> {existing_binding}"]
    assert second.evidence_matrix_rows[0]["target_claim_id"] == existing_binding
    authored_source = (tmp_path / "research_demo" / "authored" / "__init__.py").read_text(
        encoding="utf-8"
    )
    ast.parse(authored_source)
    assert authored_source.count("claim(") == 1

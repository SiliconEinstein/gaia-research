"""Tests for resolving LKM anchors after paper package materialization."""

from __future__ import annotations

from gaia_research.evidence_selection import (
    hydrate_selected_evidence_with_anchor_resolution,
    resolve_materialized_anchors,
)


def test_resolve_materialized_anchors_fills_symbol_refs_and_defers_unresolved_hits() -> None:
    result = resolve_materialized_anchors(
        anchors=[
            {
                "id": "claim_a",
                "hit_id": "lkm:bohrium:claim_a",
                "node_id": "claim_a",
                "kind": "claim",
                "paper_id": "P1",
                "source_ref": "lkm:bohrium:paper:P1",
                "import_name": None,
                "symbol": None,
                "ref": None,
                "status": "pending_materialization",
            },
            {
                "id": "claim_missing",
                "hit_id": "lkm:bohrium:claim_missing",
                "node_id": "claim_missing",
                "kind": "claim",
                "paper_id": "P1",
                "source_ref": "lkm:bohrium:paper:P1",
                "import_name": None,
                "symbol": None,
                "ref": None,
                "status": "pending_materialization",
            },
        ],
        materialized_packages=[
            {
                "source_ref": "lkm:bohrium:paper:P1",
                "import_name": "paper_p1",
                "symbol_refs": [
                    {
                        "node_id": "claim_a",
                        "kind": "claim",
                        "symbol": "claim_a",
                        "ref": "lkm:paper_p1::claim_a",
                    }
                ],
            }
        ],
    )

    assert result["anchors"][0] == {
        "id": "claim_a",
        "hit_id": "lkm:bohrium:claim_a",
        "node_id": "claim_a",
        "kind": "claim",
        "paper_id": "P1",
        "source_ref": "lkm:bohrium:paper:P1",
        "import_name": "paper_p1",
        "symbol": "claim_a",
        "ref": "lkm:paper_p1::claim_a",
        "status": "resolved",
    }
    assert result["anchors"][1]["status"] == "unresolved"
    assert result["deferred_obligations"] == [
        {
                "target": {"kind": "claim", "id": "claim_missing"},
                "target_qid": "claim_missing",
                "action_type": "resolve_anchor",
            "action": (
                "Resolve LKM claim anchor claim_missing inside "
                "lkm:bohrium:paper:P1 before authoring candidate relations."
            ),
            "content": (
                "Resolve LKM claim anchor claim_missing inside "
                "lkm:bohrium:paper:P1 before authoring candidate relations."
            ),
            "diagnostic_kind": "structural_hole",
            "anchor": {
                "kind": "anchor_resolution",
                "gaia_research": {
                    "obligation_type": "workflow",
                    "action_type": "resolve_anchor",
                    "target": {"kind": "claim", "id": "claim_missing"},
                    "auto_closeable": True,
                    "blocking": True,
                    "budget_class": "materialization",
                    "source": "anchor_resolution",
                    "anchor_id": "claim_missing",
                    "source_ref": "lkm:bohrium:paper:P1",
                },
            },
            "source_refs": [{"kind": "lkm_anchor", "id": "claim_missing"}],
            "actionable": True,
        }
    ]


def test_hydrate_selected_evidence_with_anchor_resolution_adds_package_refs() -> None:
    selected_evidence = {
        "kind": "selected_evidence",
        "evidence_packet": {
            "items": [
                {
                    "kind": "variable",
                    "id": "claim_a",
                    "variable_type": "claim",
                    "content": "Claim A.",
                    "source": {"paper_id": "P1", "paper_title": "Paper"},
                },
                {
                    "kind": "variable",
                    "id": "claim_missing",
                    "variable_type": "claim",
                    "content": "Missing claim.",
                    "source": {"paper_id": "P1", "paper_title": "Paper"},
                },
            ],
            "paper_leads": [],
        },
        "anchors": [
            {
                "id": "claim_a",
                "hit_id": "lkm:bohrium:claim_a",
                "node_id": "claim_a",
                "kind": "claim",
                "paper_id": "P1",
                "source_ref": "lkm:bohrium:paper:P1",
                "status": "pending_materialization",
            },
            {
                "id": "claim_missing",
                "hit_id": "lkm:bohrium:claim_missing",
                "node_id": "claim_missing",
                "kind": "claim",
                "paper_id": "P1",
                "source_ref": "lkm:bohrium:paper:P1",
                "status": "pending_materialization",
            },
        ],
    }

    hydrated = hydrate_selected_evidence_with_anchor_resolution(
        selected_evidence,
        materialized_packages=[
            {
                "source_ref": "lkm:bohrium:paper:P1",
                "import_name": "paper_p1",
                "symbol_refs": [
                    {
                        "node_id": "claim_a",
                        "kind": "claim",
                        "symbol": "claim_a",
                        "ref": "lkm:paper_p1::claim_a",
                    }
                ],
            }
        ],
    )

    items = hydrated["evidence_packet"]["items"]
    assert items[0]["package_ref"] == {
        "ref": "lkm:paper_p1::claim_a",
        "value_type": "claim",
        "source_ref": "lkm:bohrium:paper:P1",
        "import_name": "paper_p1",
        "symbol": "claim_a",
        "anchor_id": "claim_a",
    }
    assert "package_ref" not in items[1]
    assert hydrated["anchors"][0]["status"] == "resolved"
    assert hydrated["anchors"][1]["status"] == "unresolved"
    assert hydrated["deferred_obligations"][0]["action_type"] == "resolve_anchor"

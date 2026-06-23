"""Tests for research obligation continuation decisions."""

from __future__ import annotations

from gaia_research.budgets import ResearchRunBudget
from gaia_research.graph_assets import plan_obligation_decision
from gaia_research.obligations import derive_workflow_obligations


def test_obligation_decision_continues_when_budget_remains() -> None:
    decision = plan_obligation_decision(
        open_obligations=[
            {
                "target": {"kind": "claim", "ref": "c1"},
                "action_type": "search_more_evidence",
                "action": "Find contradicting evidence.",
            }
        ],
        deferred_obligations=[],
        budget=ResearchRunBudget(obligation_iterations=1),
    )

    assert decision == {
        "decision": "continue",
        "next_obligation": {
            "target": {"kind": "claim", "ref": "c1"},
            "action_type": "search_more_evidence",
            "action": "Find contradicting evidence.",
        },
        "deferred_obligations": [],
    }


def test_obligation_decision_defers_when_budget_is_exhausted() -> None:
    decision = plan_obligation_decision(
        open_obligations=[
            {
                "target": {"kind": "relation", "ref": "r1"},
                "action_type": "check_method_scope",
                "action": "Check method scope.",
            }
        ],
        deferred_obligations=[
            {
                "target": {"kind": "claim", "ref": "c2"},
                "action_type": "resolve_anchor",
                "action": "Resolve anchor.",
            }
        ],
        budget=ResearchRunBudget(obligation_iterations=0),
    )

    assert decision == {
        "decision": "defer",
        "next_obligation": None,
        "deferred_obligations": [
            {
                "target": {"kind": "relation", "ref": "r1"},
                "action_type": "check_method_scope",
                "action": "Check method scope.",
            },
            {
                "target": {"kind": "claim", "ref": "c2"},
                "action_type": "resolve_anchor",
                "action": "Resolve anchor.",
            },
        ],
    }


def test_workflow_obligations_cover_unassessed_and_underexpanded_focuses() -> None:
    obligations = derive_workflow_obligations(
        focus_artifact={
            "kind": "focus_synthesis",
            "focuses": [
                {
                    "id": "ready_focus",
                    "status": "candidate",
                    "question": "Is the transition continuous?",
                    "priority": "high",
                    "readiness": "ready_for_assess",
                    "evidence_refs": [{"kind": "variable", "id": "v1"}],
                },
                {
                    "id": "thin_focus",
                    "status": "candidate",
                    "question": "What experiments constrain the claim?",
                    "priority": "medium",
                    "readiness": "needs_expand",
                    "evidence_refs": [{"kind": "variable", "id": "v2"}],
                    "suggested_queries": ["experimental deconfined criticality evidence"],
                },
            ],
            "coverage_gaps": [
                {
                    "id": "missing_experiment",
                    "description": "Experimental systems are thinly covered.",
                    "evidence_refs": [{"kind": "variable", "id": "v3"}],
                }
            ],
        },
        assessed_focus_ids=set(),
    )

    assert [item["action_type"] for item in obligations] == [
        "assess_focus",
        "expand_focus",
        "close_coverage_gap",
    ]
    assert {item["diagnostic_kind"] for item in obligations} == {"focus_weakness"}
    assert {item["anchor"]["gaia_research"]["obligation_type"] for item in obligations} == {
        "workflow"
    }
    assert all(item["anchor"]["gaia_research"]["auto_closeable"] is True for item in obligations)
    assert obligations[0]["target"] == {"kind": "question", "id": "ready_focus"}


def test_human_review_focus_is_manual_assessment_obligation_not_review_action() -> None:
    obligations = derive_workflow_obligations(
        focus_artifact={
            "kind": "focus_synthesis",
            "focuses": [
                {
                    "id": "manual_focus",
                    "status": "candidate",
                    "question": "Should a human inspect this focus before assessment?",
                    "priority": "medium",
                    "readiness": "needs_human_review",
                    "evidence_refs": [{"kind": "variable", "id": "v4"}],
                }
            ],
            "coverage_gaps": [],
        },
        assessed_focus_ids=set(),
    )

    assert [item["action_type"] for item in obligations] == ["assess_focus"]
    assert obligations[0]["anchor"]["gaia_research"]["auto_closeable"] is False
    assert obligations[0]["anchor"]["gaia_research"]["budget_class"] == "assessment"
    assert "review_focus" not in str(obligations[0])

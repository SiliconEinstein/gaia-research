"""Tests for obligation-loop scheduling decisions."""

from __future__ import annotations

from typing import Any

from gaia_research.budgets import ResearchRunBudget
from gaia_research.scheduler import plan_obligation_schedule


def _workflow_obligation(
    action_type: str,
    *,
    target_id: str,
    obligation_type: str = "workflow",
    auto_closeable: bool = True,
    blocking: bool = True,
) -> dict[str, Any]:
    return {
        "target": {"kind": "question", "id": target_id},
        "target_qid": target_id,
        "diagnostic_kind": "focus_weakness",
        "action_type": action_type,
        "action": f"{action_type} action for {target_id}",
        "content": f"{action_type} content for {target_id}",
        "anchor": {
            "kind": "research_obligation",
            "gaia_research": {
                "obligation_type": obligation_type,
                "action_type": action_type,
                "auto_closeable": auto_closeable,
                "blocking": blocking,
                "budget_class": "assessment",
                "source": "test",
            },
        },
    }


def test_schedule_prioritizes_supported_workflow_obligations() -> None:
    schedule = plan_obligation_schedule(
        open_obligations=[
            _workflow_obligation("close_coverage_gap", target_id="coverage"),
            _workflow_obligation("search_more_evidence", target_id="thin_claim"),
            _workflow_obligation("expand_focus", target_id="thin_focus"),
            _workflow_obligation("assess_focus", target_id="ready_focus"),
        ],
        deferred_obligations=[],
        budget=ResearchRunBudget(obligation_iterations=1),
    )

    assert schedule["decision"] == "execute"
    assert schedule["selected_action_type"] == "assess_focus"
    assert schedule["selected_obligation"]["target_qid"] == "ready_focus"
    assert schedule["remaining_iterations"] == 0
    assert schedule["supported_action_types"] == [
        "assess_focus",
        "expand_focus",
        "search_more_evidence",
        "close_coverage_gap",
    ]
    assert schedule["guardrails"]["max_assessed_claims_per_focus"] == 20


def test_run_budget_defaults_match_unified_per_action_guardrails() -> None:
    budget = ResearchRunBudget()

    assert budget.focus_count == 1
    assert budget.evidence_items_per_focus == 20
    assert budget.evidence_papers_per_focus == 20
    assert budget.evidence_chains_per_focus == 20


def test_schedule_defers_when_obligation_loop_budget_is_exhausted() -> None:
    open_obligation = _workflow_obligation("assess_focus", target_id="ready_focus")

    schedule = plan_obligation_schedule(
        open_obligations=[open_obligation],
        deferred_obligations=[],
        budget=ResearchRunBudget(obligation_iterations=0),
    )

    assert schedule["decision"] == "defer"
    assert schedule["selected_obligation"] is None
    assert schedule["deferred_obligations"] == [open_obligation]


def test_schedule_uses_supported_deferred_workflow_when_open_has_no_candidate() -> None:
    deferred_supported = _workflow_obligation(
        "close_coverage_gap",
        target_id="research_coverage",
        blocking=False,
    )

    schedule = plan_obligation_schedule(
        open_obligations=[_workflow_obligation("check_method_scope", target_id="method_scope")],
        deferred_obligations=[deferred_supported],
        budget=ResearchRunBudget(obligation_iterations=1),
    )

    assert schedule["decision"] == "execute"
    assert schedule["selected_action_type"] == "close_coverage_gap"
    assert schedule["selected_obligation"] == deferred_supported
    assert schedule["remaining_iterations"] == 0


def test_schedule_uses_policy_score_for_supported_candidates() -> None:
    coverage = _workflow_obligation(
        "close_coverage_gap",
        target_id="research_coverage",
        blocking=False,
    )
    ready_focus = _workflow_obligation("assess_focus", target_id="ready_focus")

    schedule = plan_obligation_schedule(
        open_obligations=[ready_focus, coverage],
        deferred_obligations=[],
        budget=ResearchRunBudget(obligation_iterations=1),
        policy={
            "rankings": [
                {
                    "target_qid": "research_coverage",
                    "action_type": "close_coverage_gap",
                    "score": 0.95,
                    "reason": "Coverage gap changes the review conclusion more than another focus.",
                }
            ]
        },
    )

    assert schedule["decision"] == "execute"
    assert schedule["selected_action_type"] == "close_coverage_gap"
    assert schedule["selected_obligation"] == coverage
    assert schedule["policy_selection"] == {
        "target_qid": "research_coverage",
        "action_type": "close_coverage_gap",
        "score": 0.95,
        "reason": "Coverage gap changes the review conclusion more than another focus.",
    }


def test_schedule_ignores_policy_for_missing_candidate() -> None:
    ready_focus = _workflow_obligation("assess_focus", target_id="ready_focus")
    coverage = _workflow_obligation(
        "close_coverage_gap",
        target_id="research_coverage",
        blocking=False,
    )

    schedule = plan_obligation_schedule(
        open_obligations=[ready_focus, coverage],
        deferred_obligations=[],
        budget=ResearchRunBudget(obligation_iterations=1),
        policy={
            "rankings": [
                {
                    "target_qid": "does_not_exist",
                    "action_type": "close_coverage_gap",
                    "score": 1.0,
                    "reason": "This policy entry should not match anything.",
                }
            ]
        },
    )

    assert schedule["decision"] == "execute"
    assert schedule["selected_action_type"] == "assess_focus"
    assert schedule["selected_obligation"] == ready_focus
    assert schedule["policy_selection"] is None


def test_schedule_ignores_policy_with_non_executable_action_type() -> None:
    ready_focus = _workflow_obligation("assess_focus", target_id="ready_focus")
    coverage = _workflow_obligation(
        "close_coverage_gap",
        target_id="research_coverage",
        blocking=False,
    )

    schedule = plan_obligation_schedule(
        open_obligations=[ready_focus, coverage],
        deferred_obligations=[],
        budget=ResearchRunBudget(obligation_iterations=1),
        policy={
            "rankings": [
                {
                    "target_qid": "ready_focus",
                    "action_type": "review_focus",
                    "mapped_executable_action": "assess_focus",
                    "score": 1.0,
                    "reason": "Legacy review action must not steer the new scheduler.",
                }
            ]
        },
    )

    assert schedule["decision"] == "execute"
    assert schedule["selected_action_type"] == "assess_focus"
    assert schedule["selected_obligation"] == ready_focus
    assert schedule["policy_selection"] is None


def test_schedule_ignores_policy_mapped_executable_action_field() -> None:
    ready_focus = _workflow_obligation("assess_focus", target_id="ready_focus")
    coverage = _workflow_obligation(
        "close_coverage_gap",
        target_id="research_coverage",
        blocking=False,
    )

    schedule = plan_obligation_schedule(
        open_obligations=[coverage, ready_focus],
        deferred_obligations=[],
        budget=ResearchRunBudget(obligation_iterations=1),
        policy={
            "rankings": [
                {
                    "target_qid": "research_coverage",
                    "mapped_executable_action": "close_coverage_gap",
                    "score": 1.0,
                    "reason": "Mapped action is no longer part of the policy contract.",
                }
            ]
        },
    )

    assert schedule["decision"] == "execute"
    assert schedule["selected_action_type"] == "assess_focus"
    assert schedule["selected_obligation"] == ready_focus
    assert schedule["policy_selection"] is None


def test_schedule_ignores_future_research_and_unsupported_actions() -> None:
    future_research = _workflow_obligation(
        "check_method_scope",
        target_id="later",
        obligation_type="future_research",
    )
    unsupported = _workflow_obligation("resolve_anchor", target_id="anchor")
    not_auto_closeable = _workflow_obligation(
        "assess_focus",
        target_id="manual_review",
        auto_closeable=False,
    )

    schedule = plan_obligation_schedule(
        open_obligations=[future_research, unsupported, not_auto_closeable],
        deferred_obligations=[],
        budget=ResearchRunBudget(obligation_iterations=3),
    )

    assert schedule["decision"] == "defer"
    assert schedule["selected_obligation"] is None
    assert schedule["unsupported_obligations"] == [unsupported]
    assert schedule["future_research_obligations"] == [future_research]
    assert schedule["manual_obligations"] == [not_auto_closeable]

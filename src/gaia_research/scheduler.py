"""Obligation-loop scheduling primitives for Gaia-native research runs."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

from gaia_research.budgets import ResearchRunBudget

SUPPORTED_OBLIGATION_ACTIONS: tuple[str, ...] = (
    "assess_focus",
    "expand_focus",
    "search_more_evidence",
    "close_coverage_gap",
)

ACTION_PRIORITY: dict[str, int] = {
    action_type: index for index, action_type in enumerate(SUPPORTED_OBLIGATION_ACTIONS)
}


@dataclass(frozen=True)
class ResearchActionGuardrails:
    """Uniform per-action limits shared by all workflow profiles."""

    max_queries_per_obligation: int = 4
    max_search_results_per_query: int = 10
    max_assessed_claims_per_focus: int = 20
    max_materialized_papers_per_focus: int = 20
    max_materialized_chains_per_focus: int = 20
    max_new_claims_per_assessment: int = 8
    max_candidate_relations_per_assessment: int = 16


DEFAULT_ACTION_GUARDRAILS = ResearchActionGuardrails()


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _has_text(payload: dict[str, Any], key: str) -> bool:
    value = payload.get(key)
    return isinstance(value, str) and bool(value.strip())


def _research_metadata(obligation: dict[str, Any]) -> dict[str, Any]:
    anchor = _as_dict(obligation.get("anchor"))
    return _as_dict(anchor.get("gaia_research"))


def _action_type(obligation: dict[str, Any]) -> str | None:
    action_type = obligation.get("action_type")
    if isinstance(action_type, str) and action_type.strip():
        return action_type.strip()
    metadata_action_type = _research_metadata(obligation).get("action_type")
    if isinstance(metadata_action_type, str) and metadata_action_type.strip():
        return metadata_action_type.strip()
    return None


def _target_qid(obligation: dict[str, Any]) -> str | None:
    target = _as_dict(obligation.get("target"))
    for value in (
        obligation.get("target_qid"),
        target.get("ref"),
        target.get("id"),
    ):
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _is_future_research(obligation: dict[str, Any]) -> bool:
    return _research_metadata(obligation).get("obligation_type") == "future_research"


def _is_auto_closeable(obligation: dict[str, Any]) -> bool:
    metadata = _research_metadata(obligation)
    if "auto_closeable" not in metadata:
        return True
    return metadata.get("auto_closeable") is True


def _is_explicit_auto_closeable(obligation: dict[str, Any]) -> bool:
    return _research_metadata(obligation).get("auto_closeable") is True


def _is_blocking(obligation: dict[str, Any]) -> bool:
    metadata = _research_metadata(obligation)
    if "blocking" not in metadata:
        return True
    return metadata.get("blocking") is True


def _is_actionable_shape(obligation: dict[str, Any]) -> bool:
    return bool(_as_dict(obligation.get("target"))) and _has_text(obligation, "action")


def _valid_dicts(values: Sequence[object]) -> list[dict[str, Any]]:
    return [value for value in values if isinstance(value, dict)]


def _classify_obligations(
    obligations: Sequence[object],
) -> tuple[
    list[tuple[int, dict[str, Any]]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    candidates: list[tuple[int, dict[str, Any]]] = []
    unsupported: list[dict[str, Any]] = []
    future_research: list[dict[str, Any]] = []
    manual: list[dict[str, Any]] = []
    for index, raw in enumerate(obligations):
        if not isinstance(raw, dict) or not _is_actionable_shape(raw):
            continue
        if _is_future_research(raw):
            future_research.append(raw)
            continue
        if not _is_auto_closeable(raw):
            manual.append(raw)
            continue
        action_type = _action_type(raw)
        if action_type not in ACTION_PRIORITY:
            unsupported.append(raw)
            continue
        candidates.append((index, raw))
    return candidates, unsupported, future_research, manual


def _candidate_sort_key(candidate: tuple[int, dict[str, Any]]) -> tuple[int, int, int]:
    index, obligation = candidate
    action_type = _action_type(obligation) or ""
    return (
        0 if _is_blocking(obligation) else 1,
        ACTION_PRIORITY.get(action_type, len(ACTION_PRIORITY)),
        index,
    )


def _policy_rankings(policy: object) -> list[dict[str, Any]]:
    payload = policy if isinstance(policy, dict) else {}
    rankings = payload.get("rankings")
    if not isinstance(rankings, list):
        return []
    return [item for item in rankings if isinstance(item, dict)]


def _numeric_score(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _policy_entry_matches(
    entry: dict[str, Any],
    obligation: dict[str, Any],
) -> bool:
    action_type = entry.get("action_type") or entry.get("mapped_executable_action")
    if not isinstance(action_type, str) or action_type.strip() != _action_type(obligation):
        return False

    entry_qid = entry.get("target_qid") or entry.get("target_id")
    if isinstance(entry_qid, str) and entry_qid.strip():
        return entry_qid.strip() == _target_qid(obligation)

    entry_obligation_id = entry.get("obligation_id") or entry.get("qid")
    if isinstance(entry_obligation_id, str) and entry_obligation_id.strip():
        return entry_obligation_id.strip() == obligation.get("qid")

    return False


def _policy_selection_payload(entry: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in (
        "obligation_id",
        "qid",
        "target_qid",
        "target_id",
        "action_type",
        "mapped_executable_action",
        "score",
        "reason",
        "report_impact",
        "uncertainty_reduction",
        "coverage_gain",
        "cost",
    ):
        value = entry.get(key)
        if value is not None:
            payload[key] = value
    return payload


def _select_policy_candidate(
    candidates: list[tuple[int, dict[str, Any]]],
    *,
    policy: object,
) -> tuple[tuple[int, dict[str, Any]] | None, dict[str, Any] | None]:
    scored: list[tuple[float, tuple[int, dict[str, Any]], dict[str, Any]]] = []
    for entry in _policy_rankings(policy):
        score = _numeric_score(entry.get("score"))
        if score is None:
            continue
        for candidate in candidates:
            if _policy_entry_matches(entry, candidate[1]):
                scored.append((score, candidate, _policy_selection_payload(entry)))
    if not scored:
        return None, None
    _, candidate, selection = sorted(
        scored,
        key=lambda item: (-item[0], _candidate_sort_key(item[1])),
    )[0]
    return candidate, selection


def plan_obligation_schedule(
    *,
    open_obligations: Sequence[object],
    deferred_obligations: Sequence[object],
    budget: ResearchRunBudget,
    guardrails: ResearchActionGuardrails = DEFAULT_ACTION_GUARDRAILS,
    policy: object | None = None,
) -> dict[str, Any]:
    """Select the next obligation-loop action within the remaining run budget."""
    open_items = _valid_dicts(open_obligations)
    deferred_items = _valid_dicts(deferred_obligations)
    candidates, unsupported, future_research, manual = _classify_obligations(open_items)
    deferred_candidates, deferred_unsupported, deferred_future_research, deferred_manual = (
        _classify_obligations(deferred_items)
    )
    deferred_candidates = [
        candidate
        for candidate in deferred_candidates
        if _is_explicit_auto_closeable(candidate[1])
    ]
    unsupported = [*unsupported, *deferred_unsupported]
    future_research = [*future_research, *deferred_future_research]
    manual = [*manual, *deferred_manual]

    selected: dict[str, Any] | None = None
    selected_action_type: str | None = None
    policy_selection: dict[str, Any] | None = None
    selection_pool = candidates or deferred_candidates
    if budget.obligation_iterations > 0 and selection_pool:
        selected_candidate, policy_selection = _select_policy_candidate(
            selection_pool,
            policy=policy,
        )
        if selected_candidate is None:
            selected_candidate = sorted(selection_pool, key=_candidate_sort_key)[0]
        _, selected = selected_candidate
        selected_action_type = _action_type(selected)

    if selected is None:
        deferred = [*open_items, *deferred_items]
        remaining_iterations = max(0, budget.obligation_iterations)
        decision = "defer"
    else:
        deferred = [item for item in [*open_items, *deferred_items] if item is not selected]
        remaining_iterations = max(0, budget.obligation_iterations - 1)
        decision = "execute"

    return {
        "schema_version": 1,
        "kind": "research_obligation_schedule",
        "decision": decision,
        "selected_obligation": selected,
        "selected_action_type": selected_action_type,
        "policy_selection": policy_selection,
        "remaining_iterations": remaining_iterations,
        "supported_action_types": list(SUPPORTED_OBLIGATION_ACTIONS),
        "guardrails": asdict(guardrails),
        "deferred_obligations": deferred,
        "unsupported_obligations": unsupported,
        "future_research_obligations": future_research,
        "manual_obligations": manual,
    }


__all__ = [
    "DEFAULT_ACTION_GUARDRAILS",
    "SUPPORTED_OBLIGATION_ACTIONS",
    "ResearchActionGuardrails",
    "plan_obligation_schedule",
]

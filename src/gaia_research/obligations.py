"""Research obligation normalization helpers.

Gaia core owns the diagnostic kind vocabulary. Gaia research stores workflow
semantics in ``anchor.gaia_research`` so schedulers can act on them without
inventing new Gaia obligation kinds.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from gaia.engine.inquiry.state import VALID_OBLIGATION_KINDS

JsonDict = dict[str, Any]


def _clean_text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _list_of_dicts(value: object) -> list[JsonDict]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _source_refs(value: object) -> list[JsonDict]:
    return [dict(item) for item in _list_of_dicts(value)]


def research_obligation_anchor(
    *,
    source_kind: str,
    obligation_type: str,
    action_type: str,
    target: JsonDict,
    auto_closeable: bool,
    blocking: bool,
    budget_class: str,
    source: str,
    extra: JsonDict | None = None,
) -> JsonDict:
    """Build the Gaia-research metadata envelope for a synthetic obligation."""
    metadata: JsonDict = {
        "obligation_type": obligation_type,
        "action_type": action_type,
        "target": dict(target),
        "auto_closeable": auto_closeable,
        "blocking": blocking,
        "budget_class": budget_class,
        "source": source,
    }
    if extra:
        metadata.update(extra)
    return {
        "kind": source_kind,
        "gaia_research": metadata,
    }


def make_research_obligation(
    *,
    target: JsonDict,
    action_type: str,
    action: str,
    content: str,
    diagnostic_kind: str,
    obligation_type: str,
    auto_closeable: bool,
    blocking: bool,
    budget_class: str,
    source: str,
    source_kind: str = "research_obligation",
    source_refs: object = None,
    extra_anchor: JsonDict | None = None,
    actionable: bool | None = None,
) -> JsonDict:
    """Create the common obligation record used by sync, traces, and graph assets."""
    clean_action_type = _clean_text(action_type)
    clean_action = _clean_text(action)
    clean_content = _clean_text(content)
    if clean_action_type is None:
        raise ValueError("action_type must be non-empty")
    if clean_action is None:
        raise ValueError("action must be non-empty")
    if clean_content is None:
        clean_content = clean_action
    if diagnostic_kind not in VALID_OBLIGATION_KINDS:
        raise ValueError(
            f"invalid diagnostic_kind {diagnostic_kind!r}; "
            f"allowed: {sorted(VALID_OBLIGATION_KINDS)}"
        )
    target_qid = _clean_text(target.get("ref")) or _clean_text(target.get("id"))
    if target_qid is None:
        target_qid = "research_obligation"
    record: JsonDict = {
        "target": dict(target),
        "target_qid": target_qid,
        "action_type": clean_action_type,
        "action": clean_action,
        "content": clean_content,
        "diagnostic_kind": diagnostic_kind,
        "anchor": research_obligation_anchor(
            source_kind=source_kind,
            obligation_type=obligation_type,
            action_type=clean_action_type,
            target=target,
            auto_closeable=auto_closeable,
            blocking=blocking,
            budget_class=budget_class,
            source=source,
            extra=extra_anchor,
        ),
    }
    refs = _source_refs(source_refs)
    if refs:
        record["source_refs"] = refs
    if actionable is not None:
        record["actionable"] = actionable
    return record


def _focus_action_for_readiness(focus: JsonDict) -> tuple[str, str, str, bool] | None:
    focus_id = _clean_text(focus.get("id"))
    readiness = _clean_text(focus.get("readiness"))
    if focus_id is None or readiness is None:
        return None
    if readiness == "needs_expand":
        suggested_queries = [
            query
            for query in focus.get("suggested_queries", [])
            if isinstance(query, str) and query.strip()
        ]
        query_note = (
            f" Suggested query: {suggested_queries[0].strip()}" if suggested_queries else ""
        )
        return (
            "expand_focus",
            f"Expand focus {focus_id} before assessment.{query_note}",
            "expansion",
            True,
        )
    if readiness == "needs_human_review":
        return (
            "review_focus",
            f"Review focus {focus_id} before automatic assessment.",
            "focus_review",
            True,
        )
    return None


def derive_workflow_obligations(
    *,
    focus_artifact: JsonDict | None,
    assessed_focus_ids: Iterable[str],
) -> list[JsonDict]:
    """Derive workflow obligations from focus readiness and coverage gaps."""
    if not isinstance(focus_artifact, dict):
        return []
    assessed = {focus_id for focus_id in assessed_focus_ids if isinstance(focus_id, str)}
    obligations: list[JsonDict] = []
    seen: set[tuple[str, str, str]] = set()

    def append_once(obligation: JsonDict) -> None:
        key = (
            str(obligation.get("target_qid") or ""),
            str(obligation.get("action_type") or ""),
            str(obligation.get("content") or ""),
        )
        if key in seen:
            return
        seen.add(key)
        obligations.append(obligation)

    focuses = _list_of_dicts(focus_artifact.get("focuses"))
    for focus in focuses:
        focus_id = _clean_text(focus.get("id"))
        if focus_id is None:
            continue
        status = _clean_text(focus.get("status"))
        if status == "defer":
            continue
        target = {"kind": "question", "id": focus_id}
        if focus.get("readiness") == "ready_for_assess" and focus_id not in assessed:
            action_type = "assess_focus"
            action = f"Assess ready focus {focus_id} before downstream synthesis."
            append_once(
                make_research_obligation(
                    target=target,
                    action_type=action_type,
                    action=action,
                    content=action,
                    diagnostic_kind="focus_weakness",
                    obligation_type="workflow",
                    auto_closeable=True,
                    blocking=True,
                    budget_class="assessment",
                    source="focus_artifact",
                    source_refs=focus.get("evidence_refs"),
                    extra_anchor={"focus_readiness": focus.get("readiness")},
                    actionable=True,
                )
            )
            continue
        readiness_action = _focus_action_for_readiness(focus)
        if readiness_action is None:
            continue
        action_type, action, budget_class, blocking = readiness_action
        append_once(
            make_research_obligation(
                target=target,
                action_type=action_type,
                action=action,
                content=action,
                diagnostic_kind="focus_weakness",
                obligation_type="workflow",
                auto_closeable=True,
                blocking=blocking,
                budget_class=budget_class,
                source="focus_artifact",
                source_refs=focus.get("evidence_refs"),
                extra_anchor={"focus_readiness": focus.get("readiness")},
                actionable=True,
            )
        )

    for gap in _list_of_dicts(focus_artifact.get("coverage_gaps")):
        description = _clean_text(gap.get("description")) or _clean_text(gap.get("suggestion"))
        if description is None:
            continue
        gap_id = _clean_text(gap.get("id")) or "coverage_gap"
        focus_ids = [
            value
            for value in gap.get("focus_ids", [])
            if isinstance(value, str) and value.strip()
        ]
        target_id = focus_ids[0].strip() if focus_ids else "research_coverage"
        target = {"kind": "question", "id": target_id}
        action = f"Close coverage gap {gap_id}: {description}"
        append_once(
            make_research_obligation(
                target=target,
                action_type="close_coverage_gap",
                action=action,
                content=description,
                diagnostic_kind="focus_weakness",
                obligation_type="workflow",
                auto_closeable=True,
                blocking=False,
                budget_class="coverage",
                source="focus_artifact",
                source_refs=gap.get("evidence_refs"),
                extra_anchor={"coverage_gap_id": gap_id},
                actionable=True,
            )
        )
    return obligations


__all__ = [
    "derive_workflow_obligations",
    "make_research_obligation",
    "research_obligation_anchor",
]

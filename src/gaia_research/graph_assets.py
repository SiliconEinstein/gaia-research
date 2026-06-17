"""Validation and projections for Gaia-native research graph assets."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from gaia_research.budgets import ResearchRunBudget
from gaia_research.scheduler import plan_obligation_schedule

GRAPH_ASSET_SUCCESS_SCHEMA_VERSION = 1
OBLIGATION_DECISIONS = {"continue", "defer"}


def _utcnow() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _has_text(payload: dict[str, Any], key: str) -> bool:
    value = payload.get(key)
    return isinstance(value, str) and bool(value.strip())


def _has_scoped_question(assets: dict[str, Any]) -> bool:
    question = _as_dict(assets.get("scoped_question"))
    return _has_text(question, "id") and _has_text(question, "question")


def _anchor_is_resolved(anchor: object) -> bool:
    payload = _as_dict(anchor)
    return all(
        _has_text(payload, key)
        for key in ("id", "kind", "source_ref", "import_name", "symbol", "ref")
    )


def _has_resolved_anchors(assets: dict[str, Any]) -> bool:
    anchors = _as_list(assets.get("anchors"))
    return any(_anchor_is_resolved(anchor) for anchor in anchors)


def _unresolved_anchor_ids(assets: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for anchor in _as_list(assets.get("anchors")):
        payload = _as_dict(anchor)
        if _anchor_is_resolved(payload):
            continue
        anchor_id = payload.get("id")
        if isinstance(anchor_id, str) and anchor_id:
            ids.add(anchor_id)
    return ids


def _obligation_anchor_ids(obligation: object) -> set[str]:
    payload = _as_dict(obligation)
    ids: set[str] = set()
    target = _as_dict(payload.get("target"))
    target_id = target.get("id") or target.get("ref")
    if isinstance(target_id, str) and target_id:
        ids.add(target_id)
    for source_ref in _as_list(payload.get("source_refs")):
        ref_payload = _as_dict(source_ref)
        if ref_payload.get("kind") != "lkm_anchor":
            continue
        ref_id = ref_payload.get("id")
        if isinstance(ref_id, str) and ref_id:
            ids.add(ref_id)
    return ids


def _unresolved_anchors_are_obligated(assets: dict[str, Any]) -> bool:
    unresolved = _unresolved_anchor_ids(assets)
    if not unresolved:
        return True
    obligations = [
        *_as_list(assets.get("open_obligations")),
        *_as_list(assets.get("deferred_obligations")),
    ]
    obligated: set[str] = set()
    for obligation in obligations:
        obligated.update(_obligation_anchor_ids(obligation))
    return unresolved <= obligated


def _claim_is_gaia_claim(claim: object) -> bool:
    payload = _as_dict(claim)
    return _has_text(payload, "id") and payload.get("gaia_object_type") == "claim"


def _has_claims(assets: dict[str, Any]) -> bool:
    claims = _as_list(assets.get("claims"))
    return len(claims) >= 2 and all(_claim_is_gaia_claim(claim) for claim in claims)


def _candidate_relation_is_valid(relation: object) -> bool:
    payload = _as_dict(relation)
    claim_refs = [ref for ref in _as_list(payload.get("claim_refs")) if isinstance(ref, str)]
    return _has_text(payload, "id") and len(claim_refs) >= 2 and payload.get("dsl_valid") is True


def _valid_relation_ids(assets: dict[str, Any]) -> set[str]:
    return {
        str(_as_dict(relation).get("id"))
        for relation in _as_list(assets.get("candidate_relations"))
        if _candidate_relation_is_valid(relation)
    }


def _has_candidate_relations(assets: dict[str, Any]) -> bool:
    return bool(_valid_relation_ids(assets))


def _has_evidence_matrix(assets: dict[str, Any]) -> bool:
    relation_ids = _valid_relation_ids(assets)
    rows = _as_list(assets.get("evidence_matrix"))
    if not rows:
        return False
    for row in rows:
        relation_id = _as_dict(row).get("relation_id")
        if isinstance(relation_id, str) and relation_id in relation_ids:
            return True
    return False


def _obligation_is_actionable(obligation: object) -> bool:
    payload = _as_dict(obligation)
    return (
        bool(_as_dict(payload.get("target")))
        and _has_text(payload, "action_type")
        and _has_text(payload, "action")
    )


def _obligations_are_valid(assets: dict[str, Any]) -> bool:
    obligations = [
        *_as_list(assets.get("open_obligations")),
        *_as_list(assets.get("deferred_obligations")),
    ]
    return all(_obligation_is_actionable(obligation) for obligation in obligations)


def _has_required_obligation_when_gap_remains(assets: dict[str, Any]) -> bool:
    if assets.get("important_gaps_remain") is not True:
        return True
    obligations = [
        *_as_list(assets.get("open_obligations")),
        *_as_list(assets.get("deferred_obligations")),
    ]
    return bool(obligations)


def _has_obligation_decision(assets: dict[str, Any]) -> bool:
    open_obligations = _as_list(assets.get("open_obligations"))
    if not open_obligations:
        return True
    return assets.get("obligation_decision") in OBLIGATION_DECISIONS


def evaluate_graph_asset_success(assets: dict[str, Any]) -> dict[str, Any]:
    """Evaluate whether one run produced the required Gaia-native graph assets."""
    checks = {
        "scoped_question": _has_scoped_question(assets),
        "resolved_anchors": _has_resolved_anchors(assets),
        "unresolved_anchor_obligations": _unresolved_anchors_are_obligated(assets),
        "claims": _has_claims(assets),
        "candidate_relations": _has_candidate_relations(assets),
        "evidence_matrix": _has_evidence_matrix(assets),
        "obligations": _obligations_are_valid(assets)
        and _has_required_obligation_when_gap_remains(assets),
        "obligation_decision": _has_obligation_decision(assets),
    }
    missing = [key for key, passed in checks.items() if not passed]
    return {
        "schema_version": GRAPH_ASSET_SUCCESS_SCHEMA_VERSION,
        "kind": "gaia_native_research_graph_asset_success",
        "generated_at": _utcnow(),
        "success": not missing,
        "checks": checks,
        "missing": missing,
    }


def _actionable_obligations(obligations: Sequence[object]) -> list[dict[str, Any]]:
    return [
        obligation
        for obligation in obligations
        if isinstance(obligation, dict) and _obligation_is_actionable(obligation)
    ]


def plan_obligation_decision(
    *,
    open_obligations: Sequence[object],
    deferred_obligations: Sequence[object],
    budget: ResearchRunBudget,
) -> dict[str, Any]:
    """Choose whether this run should continue into an open obligation or defer it."""
    schedule = plan_obligation_schedule(
        open_obligations=open_obligations,
        deferred_obligations=deferred_obligations,
        budget=budget,
    )
    next_obligation = schedule.get("selected_obligation")
    if isinstance(next_obligation, dict) and schedule.get("decision") == "execute":
        return {
            "decision": "continue",
            "next_obligation": next_obligation,
            "deferred_obligations": [
                item for item in schedule.get("deferred_obligations", []) if isinstance(item, dict)
            ],
        }
    return {
        "decision": "defer",
        "next_obligation": None,
        "deferred_obligations": [
            item
            for item in [*open_obligations, *deferred_obligations]
            if isinstance(item, dict)
        ],
    }


def _relation_claim_ids(relation: dict[str, Any]) -> list[str]:
    raw_claims = relation.get("claims", relation.get("claim_refs"))
    return [claim for claim in _as_list(raw_claims) if isinstance(claim, str) and claim.strip()]


def _relation_research_metadata(relation: dict[str, Any]) -> dict[str, Any]:
    metadata = _as_dict(relation.get("metadata"))
    return _as_dict(metadata.get("gaia_research"))


def project_evidence_matrix_rows(relations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Project inspection rows from authored candidate relation metadata."""
    rows: list[dict[str, Any]] = []
    for relation in relations:
        if not isinstance(relation, dict):
            continue
        metadata = _relation_research_metadata(relation)
        if metadata.get("kind") != "candidate_relation":
            continue
        claim_ids = _relation_claim_ids(relation)
        if len(claim_ids) < 2:
            continue
        relation_id = relation.get("id") or metadata.get("id")
        if not isinstance(relation_id, str) or not relation_id.strip():
            continue

        row: dict[str, Any] = {
            "relation_id": relation_id.strip(),
            "source_claim_id": claim_ids[0],
            "target_claim_id": claim_ids[1],
            "claim_ids": claim_ids,
            "pattern": relation.get("pattern"),
            "relation_type": metadata.get("relation_type") or relation.get("relation_type"),
        }
        rationale = relation.get("rationale")
        if isinstance(rationale, str) and rationale.strip():
            row["rationale"] = rationale.strip()
        for key in (
            "strength",
            "scope_question",
            "epistemic_status",
            "system",
            "condition",
            "method",
            "observable",
            "certainty",
            "scope_note",
            "source_refs",
        ):
            value = metadata.get(key)
            if value is not None:
                row[key] = value
        rows.append(row)
    return rows


__all__ = [
    "GRAPH_ASSET_SUCCESS_SCHEMA_VERSION",
    "evaluate_graph_asset_success",
    "plan_obligation_decision",
    "project_evidence_matrix_rows",
]

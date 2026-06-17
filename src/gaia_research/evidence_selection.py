"""Select compact deep-evidence packets from broad research landscapes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from gaia_research.obligations import make_research_obligation

SELECTED_EVIDENCE_SCHEMA_VERSION = 1


def _utcnow() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def build_selected_evidence_artifact(
    *,
    focus: dict[str, Any],
    landscapes: list[dict[str, Any]],
    selection_mode: str = "fast",
    lkm_index: str = "bohrium",
    max_items: int = 12,
    max_papers: int = 6,
    max_chains: int = 6,
    max_omitted: int = 20,
) -> dict[str, Any]:
    """Build a compact evidence packet and deep-materialization plan for assessment."""
    packet = _evidence_packet_from_landscapes(landscapes)
    candidate_items = _dedupe_items(packet["items"])
    candidate_paper_ids = _candidate_paper_ids(
        paper_leads=packet["paper_leads"],
        candidate_items=candidate_items,
    )
    ranked_items = sorted(
        candidate_items,
        key=lambda item: _item_rank(item, focus=focus),
    )
    selected_items = _select_items(
        ranked_items,
        max_items=max_items,
        max_papers=max_papers,
        selection_mode=selection_mode,
    )
    selected_item_ids = {_stable_item_id(item, fallback="") for item in selected_items}
    omitted_items = [
        item for item in ranked_items if _stable_item_id(item, fallback="") not in selected_item_ids
    ][:max_omitted]
    selected_paper_leads = _paper_leads_for_items(
        packet["paper_leads"],
        selected_items=selected_items,
        max_papers=max_papers,
    )
    evidence_packet = {
        "landscapes": packet["landscapes"],
        "items": selected_items,
        "paper_leads": selected_paper_leads,
    }
    materialization_plan = _materialization_plan(
        candidate_paper_ids=candidate_paper_ids,
        lkm_index=lkm_index,
    )
    anchors = _anchors_for_items(selected_items, lkm_index=lkm_index)
    return {
        "schema_version": SELECTED_EVIDENCE_SCHEMA_VERSION,
        "kind": "selected_evidence",
        "created_at": _utcnow(),
        "focus": dict(focus),
        "selection_policy": {
            "mode": selection_mode,
            "max_items": max_items,
            "max_papers": max_papers,
            "max_chains": max_chains,
            "max_omitted": max_omitted,
            "materialization_policy": "all_candidate_papers",
        },
        "corpus": {
            "candidate_items": len(packet["items"]),
            "unique_candidate_items": len(candidate_items),
            "candidate_paper_leads": len(packet["paper_leads"]),
            "candidate_papers": len(candidate_paper_ids),
            "materialization_policy": "all_candidate_papers",
            "materialization_candidate_papers": len(candidate_paper_ids),
        },
        "evidence_packet": evidence_packet,
        "materialization_plan": materialization_plan,
        "anchors": anchors,
        "selection": {
            "items_considered": len(packet["items"]),
            "unique_items_considered": len(candidate_items),
            "duplicate_items_considered": len(packet["items"]) - len(candidate_items),
            "items_selected": len(selected_items),
            "paper_leads_considered": len(packet["paper_leads"]),
            "paper_leads_selected": len(selected_paper_leads),
            "selected_unique_papers": len(_paper_ids_from_items(selected_items)),
            "selection_rate_unique": round(
                len(selected_items) / len(candidate_items),
                4,
            )
            if candidate_items
            else 0.0,
        },
        "coverage_audit": _coverage_audit(
            focus=focus,
            selected_items=selected_items,
            candidate_items=candidate_items,
        ),
        "omitted_relevant_evidence": [_item_summary(item) for item in omitted_items],
    }


def resolve_materialized_anchors(
    *,
    anchors: list[dict[str, Any]],
    materialized_packages: list[dict[str, Any]],
) -> dict[str, Any]:
    """Resolve selected LKM anchors against materialized paper package symbol refs."""
    symbol_refs = _symbol_refs_by_anchor(materialized_packages)
    resolved_anchors: list[dict[str, Any]] = []
    deferred_obligations: list[dict[str, Any]] = []
    for anchor in anchors:
        resolved = dict(anchor)
        key = _anchor_resolution_key(resolved)
        symbol_ref = symbol_refs.get(key)
        if symbol_ref is not None:
            resolved["import_name"] = symbol_ref["import_name"]
            resolved["symbol"] = symbol_ref["symbol"]
            resolved["ref"] = symbol_ref["ref"]
            resolved["status"] = "resolved"
        else:
            resolved["status"] = "unresolved"
            deferred_obligations.append(_anchor_resolution_obligation(resolved))
        resolved_anchors.append(resolved)
    return {"anchors": resolved_anchors, "deferred_obligations": deferred_obligations}


def hydrate_selected_evidence_with_anchor_resolution(
    selected_evidence: dict[str, Any],
    *,
    materialized_packages: list[dict[str, Any]],
) -> dict[str, Any]:
    """Attach resolved Gaia refs from materialized package anchors to selected evidence."""
    hydrated = dict(selected_evidence)
    anchors = [
        dict(anchor)
        for anchor in selected_evidence.get("anchors", [])
        if isinstance(anchor, dict)
    ]
    resolution = resolve_materialized_anchors(
        anchors=anchors,
        materialized_packages=materialized_packages,
    )
    resolved_anchors = [
        dict(anchor) for anchor in resolution["anchors"] if isinstance(anchor, dict)
    ]
    hydrated["anchors"] = resolved_anchors
    hydrated["deferred_obligations"] = resolution["deferred_obligations"]

    evidence_packet = selected_evidence.get("evidence_packet")
    if isinstance(evidence_packet, dict):
        hydrated["evidence_packet"] = _evidence_packet_with_anchor_refs(
            evidence_packet,
            anchors=resolved_anchors,
        )
    return hydrated


def _materialization_plan(
    *,
    candidate_paper_ids: list[str],
    lkm_index: str,
) -> dict[str, list[str]]:
    return {
        "paper_ids": candidate_paper_ids,
        "claim_ids": [],
        "chain_claim_ids": [],
        "package_refs": [
            _lkm_paper_source_ref(lkm_index, paper_id)
            for paper_id in candidate_paper_ids
        ],
    }


def _evidence_packet_from_landscapes(landscapes: list[dict[str, Any]]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    paper_leads: list[dict[str, Any]] = []
    landscape_refs: list[dict[str, Any]] = []
    for landscape_index, landscape in enumerate(landscapes):
        action = landscape.get("action")
        is_new = action == "explore.expand"
        landscape_refs.append(
            {
                "index": landscape_index,
                "kind": landscape.get("kind"),
                "action": action,
                "target": landscape.get("target"),
            }
        )
        for raw_item in landscape.get("items", []):
            if not isinstance(raw_item, dict):
                continue
            item = dict(raw_item)
            item.setdefault("item_id", _stable_item_id(item, fallback=f"item_{len(items)}"))
            item.setdefault("display_index", len(items))
            item["landscape_index"] = landscape_index
            item["source_landscape_action"] = action
            item["is_new"] = is_new
            items.append(item)
        for raw_lead in landscape.get("paper_leads", []):
            if not isinstance(raw_lead, dict):
                continue
            lead = dict(raw_lead)
            lead["landscape_index"] = landscape_index
            lead["source_landscape_action"] = action
            lead["is_new"] = is_new
            paper_leads.append(lead)
    return {"landscapes": landscape_refs, "items": items, "paper_leads": paper_leads}


def _dedupe_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        key = _stable_item_id(item, fallback=f"item_{len(deduped)}")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _stable_item_id(item: dict[str, Any], *, fallback: str) -> str:
    kind = item.get("kind")
    source_id = item.get("id")
    if isinstance(kind, str) and kind != "item" and isinstance(source_id, str) and source_id:
        return source_id
    item_id = item.get("item_id")
    if isinstance(item_id, str) and item_id:
        return item_id
    source = item.get("source")
    paper_id = source.get("paper_id") if isinstance(source, dict) else None
    return paper_id if isinstance(paper_id, str) and paper_id else fallback


def _item_rank(item: dict[str, Any], *, focus: dict[str, Any]) -> tuple[int, int, str]:
    text = " ".join(
        str(value)
        for value in [
            item.get("id"),
            item.get("title"),
            item.get("content"),
            _paper_title(item),
        ]
        if value
    ).lower()
    focus_terms = _focus_terms(focus)
    matched_terms = sum(1 for term in focus_terms if term in text)
    has_claim = item.get("kind") == "variable" and item.get("variable_type") == "claim"
    display_index = item.get("display_index")
    order = display_index if isinstance(display_index, int) else 0
    return (-matched_terms, 0 if has_claim else 1, f"{order:08d}")


def _select_items(
    ranked_items: list[dict[str, Any]],
    *,
    max_items: int,
    max_papers: int,
    selection_mode: str,
) -> list[dict[str, Any]]:
    if selection_mode != "review":
        return ranked_items[:max_items]

    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    selected_papers: set[str] = set()
    for item in ranked_items:
        paper_id = _item_paper_id(item)
        if paper_id is None or paper_id in selected_papers:
            continue
        _append_selected_item(item, selected=selected, selected_ids=selected_ids)
        selected_papers.add(paper_id)
        if len(selected) >= min(max_items, max_papers):
            break

    for item in ranked_items:
        _append_selected_item(item, selected=selected, selected_ids=selected_ids)
        if len(selected) >= max_items:
            break
    return selected


def _append_selected_item(
    item: dict[str, Any],
    *,
    selected: list[dict[str, Any]],
    selected_ids: set[str],
) -> None:
    item_id = _stable_item_id(item, fallback=f"item_{len(selected)}")
    if item_id in selected_ids:
        return
    selected_ids.add(item_id)
    selected.append(item)


def _focus_terms(focus: dict[str, Any]) -> list[str]:
    text = " ".join(
        str(value) for value in [focus.get("id"), focus.get("title"), focus.get("content")] if value
    )
    terms: list[str] = []
    for raw in text.replace("-", " ").replace("_", " ").split():
        term = raw.strip().lower()
        if len(term) >= 4 and term not in terms:
            terms.append(term)
    return terms


def _paper_title(item: dict[str, Any]) -> str | None:
    source = item.get("source")
    title = source.get("paper_title") if isinstance(source, dict) else None
    return title if isinstance(title, str) else None


def _item_paper_id(item: dict[str, Any]) -> str | None:
    source = item.get("source")
    paper_id = source.get("paper_id") if isinstance(source, dict) else None
    return paper_id if isinstance(paper_id, str) and paper_id else None


def _lkm_paper_source_ref(lkm_index: str, paper_id: str) -> str:
    return f"lkm:{lkm_index}:paper:{paper_id}"


def _item_anchor_kind(item: dict[str, Any]) -> str | None:
    kind = item.get("kind")
    variable_type = item.get("variable_type")
    if kind == "variable" and variable_type in {"claim", "question"}:
        return str(variable_type)
    if kind in {"claim", "question"}:
        return str(kind)
    return None


def _item_hit_id(item: dict[str, Any], *, fallback: str) -> str:
    provenance = item.get("provenance")
    result_id = provenance.get("result_id") if isinstance(provenance, dict) else None
    if isinstance(result_id, str) and result_id:
        return result_id
    item_id = item.get("id")
    return item_id if isinstance(item_id, str) and item_id else fallback


def _anchors_for_items(items: list[dict[str, Any]], *, lkm_index: str) -> list[dict[str, Any]]:
    anchors: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        paper_id = _item_paper_id(item)
        anchor_kind = _item_anchor_kind(item)
        node_id = item.get("id")
        if (
            paper_id is None
            or anchor_kind is None
            or not isinstance(node_id, str)
            or not node_id
        ):
            continue
        key = (paper_id, node_id)
        if key in seen:
            continue
        seen.add(key)
        anchors.append(
            {
                "id": node_id,
                "hit_id": _item_hit_id(item, fallback=node_id),
                "node_id": node_id,
                "kind": anchor_kind,
                "paper_id": paper_id,
                "source_ref": _lkm_paper_source_ref(lkm_index, paper_id),
                "import_name": None,
                "symbol": None,
                "ref": None,
                "status": "pending_materialization",
                "landscape_index": item.get("landscape_index"),
            }
        )
    return anchors


def _anchor_resolution_key(anchor: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(anchor.get("source_ref") or ""),
        str(anchor.get("kind") or ""),
        str(anchor.get("node_id") or anchor.get("id") or ""),
    )


def _symbol_refs_by_anchor(
    materialized_packages: list[dict[str, Any]],
) -> dict[tuple[str, str, str], dict[str, str]]:
    refs: dict[tuple[str, str, str], dict[str, str]] = {}
    for package in materialized_packages:
        source_ref = package.get("source_ref")
        import_name = package.get("import_name")
        if not isinstance(source_ref, str) or not isinstance(import_name, str):
            continue
        symbol_refs = package.get("symbol_refs")
        if not isinstance(symbol_refs, list):
            continue
        for raw_symbol_ref in symbol_refs:
            if not isinstance(raw_symbol_ref, dict):
                continue
            node_id = raw_symbol_ref.get("node_id") or raw_symbol_ref.get("id")
            kind = raw_symbol_ref.get("kind")
            symbol = raw_symbol_ref.get("symbol")
            ref = raw_symbol_ref.get("ref")
            if not all(isinstance(value, str) and value for value in (node_id, kind, symbol, ref)):
                continue
            symbol_payload = {
                "import_name": import_name,
                "symbol": str(symbol),
                "ref": str(ref),
            }
            for raw_id in (node_id, raw_symbol_ref.get("local_id"), raw_symbol_ref.get("id")):
                if isinstance(raw_id, str) and raw_id:
                    refs[(source_ref, str(kind), raw_id)] = symbol_payload
    return refs


def _evidence_packet_with_anchor_refs(
    evidence_packet: dict[str, Any],
    *,
    anchors: list[dict[str, Any]],
) -> dict[str, Any]:
    packet = dict(evidence_packet)
    resolved_by_id = _resolved_anchors_by_item_id(anchors)
    items: list[dict[str, Any]] = []
    for item in evidence_packet.get("items", []):
        if not isinstance(item, dict):
            continue
        hydrated_item = dict(item)
        anchor = resolved_by_id.get(_stable_item_id(hydrated_item, fallback=""))
        if anchor is not None:
            hydrated_item["package_ref"] = {
                "ref": anchor["ref"],
                "value_type": anchor["kind"],
                "source_ref": anchor["source_ref"],
                "import_name": anchor["import_name"],
                "symbol": anchor["symbol"],
                "anchor_id": anchor["id"],
            }
        items.append(hydrated_item)
    packet["items"] = items
    return packet


def _resolved_anchors_by_item_id(anchors: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    resolved: dict[str, dict[str, Any]] = {}
    for anchor in anchors:
        if anchor.get("status") != "resolved":
            continue
        if not all(
            isinstance(anchor.get(key), str) and anchor.get(key)
            for key in ("id", "kind", "source_ref", "import_name", "symbol", "ref")
        ):
            continue
        for raw_id in (anchor.get("node_id"), anchor.get("id"), anchor.get("hit_id")):
            if isinstance(raw_id, str) and raw_id:
                resolved[raw_id] = anchor
    return resolved


def _anchor_resolution_obligation(anchor: dict[str, Any]) -> dict[str, Any]:
    kind = str(anchor.get("kind") or "claim")
    anchor_id = str(anchor.get("id") or anchor.get("node_id") or "unknown")
    source_ref = str(anchor.get("source_ref") or "unknown source")
    target = {"kind": kind, "id": anchor_id}
    action = (
        f"Resolve LKM {kind} anchor {anchor_id} inside {source_ref} before "
        "authoring candidate relations."
    )
    return make_research_obligation(
        target=target,
        action_type="resolve_anchor",
        action=action,
        content=action,
        diagnostic_kind="structural_hole",
        obligation_type="workflow",
        auto_closeable=True,
        blocking=True,
        budget_class="materialization",
        source="anchor_resolution",
        source_kind="anchor_resolution",
        source_refs=[{"kind": "lkm_anchor", "id": anchor_id}],
        extra_anchor={"anchor_id": anchor_id, "source_ref": source_ref},
        actionable=True,
    )


def _paper_leads_for_items(
    paper_leads: list[dict[str, Any]],
    *,
    selected_items: list[dict[str, Any]],
    max_papers: int,
) -> list[dict[str, Any]]:
    selected_papers = _paper_ids_from_items(selected_items)
    by_id = {
        lead.get("paper_id"): lead
        for lead in paper_leads
        if isinstance(lead.get("paper_id"), str) and lead.get("paper_id")
    }
    leads: list[dict[str, Any]] = []
    for paper_id in selected_papers:
        lead = by_id.get(paper_id)
        if lead is not None:
            leads.append(dict(lead))
        if len(leads) >= max_papers:
            break
    return leads


def _paper_ids_from_items(items: list[dict[str, Any]]) -> list[str]:
    paper_ids: list[str] = []
    for item in items:
        source = item.get("source")
        paper_id = source.get("paper_id") if isinstance(source, dict) else None
        if isinstance(paper_id, str) and paper_id and paper_id not in paper_ids:
            paper_ids.append(paper_id)
    return paper_ids


def _candidate_paper_ids(
    *,
    paper_leads: list[dict[str, Any]],
    candidate_items: list[dict[str, Any]],
) -> list[str]:
    paper_ids: list[str] = []
    for lead in paper_leads:
        paper_id = lead.get("paper_id")
        if isinstance(paper_id, str) and paper_id and paper_id not in paper_ids:
            paper_ids.append(paper_id)
    for paper_id in _paper_ids_from_items(candidate_items):
        if paper_id not in paper_ids:
            paper_ids.append(paper_id)
    return paper_ids


def _paper_ids(leads: list[dict[str, Any]], *, limit: int) -> list[str]:
    ids: list[str] = []
    for lead in leads:
        paper_id = lead.get("paper_id")
        if isinstance(paper_id, str) and paper_id and paper_id not in ids:
            ids.append(paper_id)
        if len(ids) >= limit:
            break
    return ids


def _claim_ids(items: list[dict[str, Any]], *, limit: int) -> list[str]:
    ids: list[str] = []
    for item in items:
        if item.get("kind") != "variable" or item.get("variable_type") != "claim":
            continue
        claim_id = item.get("id")
        if isinstance(claim_id, str) and claim_id and claim_id not in ids:
            ids.append(claim_id)
        if len(ids) >= limit:
            break
    return ids


def _ref_key(ref: object) -> tuple[str, str] | None:
    if isinstance(ref, str) and ref:
        return ("paper", ref) if ref.isdigit() else ("variable", ref)
    if not isinstance(ref, dict):
        return None
    ref_id = ref.get("id") or ref.get("paper_id") or ref.get("ref")
    if isinstance(ref_id, int):
        ref_id = str(ref_id)
    kind = ref.get("kind") or ("paper" if ref.get("paper_id") else None)
    if isinstance(kind, str) and isinstance(ref_id, str) and ref_id:
        return kind, ref_id
    return None


def _item_ref_keys(item: dict[str, Any]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    item_id = item.get("id")
    kind = item.get("kind")
    if isinstance(kind, str) and isinstance(item_id, str) and item_id:
        keys.add((kind, item_id))
        if kind == "variable":
            keys.add(("item", item_id))
    stable_id = item.get("item_id")
    if isinstance(stable_id, str) and stable_id:
        keys.add(("item", stable_id))
        keys.add(("variable", stable_id))
    paper_id = _item_paper_id(item)
    if paper_id:
        keys.add(("paper", paper_id))
    return keys


def _coverage_audit(
    *,
    focus: dict[str, Any],
    selected_items: list[dict[str, Any]],
    candidate_items: list[dict[str, Any]],
) -> dict[str, Any]:
    selected_keys = set().union(*[_item_ref_keys(item) for item in selected_items])
    candidate_keys = set().union(*[_item_ref_keys(item) for item in candidate_items])
    focus_refs = focus.get("evidence_refs")
    focus_ref_keys = (
        [key for ref in focus_refs if (key := _ref_key(ref)) is not None]
        if isinstance(focus_refs, list)
        else []
    )
    covered_focus_refs = [key for key in focus_ref_keys if key in selected_keys]
    candidate_focus_refs = [key for key in focus_ref_keys if key in candidate_keys]
    selected_by_landscape = _count_by_field(selected_items, "landscape_index")
    candidate_by_landscape = _count_by_field(candidate_items, "landscape_index")
    return {
        "focus_refs_total": len(focus_ref_keys),
        "focus_refs_available": len(candidate_focus_refs),
        "focus_refs_selected": len(covered_focus_refs),
        "focus_ref_selection_rate": round(
            len(covered_focus_refs) / len(focus_ref_keys),
            4,
        )
        if focus_ref_keys
        else None,
        "candidate_unique_papers": len(_paper_ids_from_items(candidate_items)),
        "selected_unique_papers": len(_paper_ids_from_items(selected_items)),
        "candidate_by_landscape_index": candidate_by_landscape,
        "selected_by_landscape_index": selected_by_landscape,
        "selected_claims": sum(
            1
            for item in selected_items
            if item.get("kind") == "variable" and item.get("variable_type") == "claim"
        ),
    }


def _count_by_field(items: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = item.get(field)
        key = str(value) if value is not None else "unknown"
        counts[key] = counts.get(key, 0) + 1
    return counts


def _item_summary(item: dict[str, Any]) -> dict[str, Any]:
    source = item.get("source")
    source_payload = source if isinstance(source, dict) else {}
    content = item.get("content")
    content_text = content if isinstance(content, str) else None
    return {
        "kind": item.get("kind"),
        "id": item.get("id") or item.get("item_id"),
        "title": item.get("title"),
        "content_preview": content_text[:240] if content_text else None,
        "paper_id": source_payload.get("paper_id"),
        "paper_title": source_payload.get("paper_title"),
        "landscape_index": item.get("landscape_index"),
    }

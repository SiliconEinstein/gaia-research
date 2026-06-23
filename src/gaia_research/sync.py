"""Sync research artifacts into Gaia package source and inquiry state.

``.gaia/research`` is an audit/cache layer. This module is the narrow bridge
that takes review artifacts produced by ``gaia research`` and records durable
state in the existing package-native surfaces:

* authored DSL source for questions, notes, scaffold relations, materializations;
* ``.gaia/inquiry`` for active focus, synthetic hypotheses, and obligations.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from gaia.engine.authoring import append_statement, ensure_authored_submodule, split_csv_refs
from gaia.engine.inquiry.state import (
    SyntheticHypothesis,
    SyntheticObligation,
    append_tactic_event,
    load_state,
    mint_qid,
    save_state,
)

from gaia_research.artifacts import ResearchPackage
from gaia_research.graph_assets import project_evidence_matrix_rows
from gaia_research.obligations import research_obligation_anchor
from gaia_research.report import render_assessment_review_note_markdown

JsonDict = dict[str, Any]

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SLUG_RE = re.compile(r"[^A-Za-z0-9_]+")
_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
_READINESS_ORDER = {
    "ready_for_assess": 0,
    "needs_expand": 1,
    "needs_human_review": 2,
    "defer": 3,
}


class ResearchSyncSourceError(RuntimeError):
    """Raised when research sync would leave authored source invalid."""


@dataclass
class ResearchSyncResult:
    """Summary of package/inquiry writes performed for one research action."""

    dry_run: bool = False
    source_writes_enabled: bool = True
    questions_written: list[str] = field(default_factory=list)
    questions_skipped: list[str] = field(default_factory=list)
    notes_written: list[str] = field(default_factory=list)
    notes_skipped: list[str] = field(default_factory=list)
    claims_written: list[str] = field(default_factory=list)
    claims_skipped: list[str] = field(default_factory=list)
    candidate_relations_written: list[str] = field(default_factory=list)
    candidate_relations_skipped: list[str] = field(default_factory=list)
    evidence_matrix_rows: list[JsonDict] = field(default_factory=list)
    materializations_written: list[str] = field(default_factory=list)
    materializations_skipped: list[str] = field(default_factory=list)
    obligations_added: list[str] = field(default_factory=list)
    open_obligations: list[JsonDict] = field(default_factory=list)
    obligations_deferred: list[JsonDict] = field(default_factory=list)
    obligations_skipped: int = 0
    hypotheses_added: list[str] = field(default_factory=list)
    hypotheses_skipped: int = 0
    focus_set: str | None = None

    @property
    def writes_source(self) -> bool:
        """Whether this sync is allowed to write package source."""
        return self.source_writes_enabled and not self.dry_run

    @property
    def writes_inquiry(self) -> bool:
        """Whether this sync is allowed to mutate inquiry state."""
        return not self.dry_run

    def to_payload(self) -> JsonDict:
        """Return a JSON-compatible summary for research events."""
        return {
            "dry_run": self.dry_run,
            "writes_source": self.writes_source,
            "writes_inquiry": self.writes_inquiry,
            "questions_written": list(self.questions_written),
            "questions_skipped": list(self.questions_skipped),
            "notes_written": list(self.notes_written),
            "notes_skipped": list(self.notes_skipped),
            "claims_written": list(self.claims_written),
            "claims_skipped": list(self.claims_skipped),
            "candidate_relations_written": list(self.candidate_relations_written),
            "candidate_relations_skipped": list(self.candidate_relations_skipped),
            "evidence_matrix_rows": list(self.evidence_matrix_rows),
            "materializations_written": list(self.materializations_written),
            "materializations_skipped": list(self.materializations_skipped),
            "obligations_added": list(self.obligations_added),
            "open_obligations": list(self.open_obligations),
            "obligations_deferred": list(self.obligations_deferred),
            "obligations_skipped": self.obligations_skipped,
            "hypotheses_added": list(self.hypotheses_added),
            "hypotheses_skipped": self.hypotheses_skipped,
            "focus_set": self.focus_set,
        }


def _source_root(pkg: ResearchPackage) -> Path:
    src_root = pkg.path / "src" / pkg.import_name
    if src_root.exists():
        return src_root
    return pkg.path / pkg.import_name


def _authored_init_path(pkg: ResearchPackage) -> Path:
    source_root = _source_root(pkg)
    return cast(Path, ensure_authored_submodule(source_root, source_root / "__init__.py"))


def _short_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:8]


def _slug(value: object, *, max_len: int = 56) -> str:
    text = str(value or "").strip().lower()
    text = _SLUG_RE.sub("_", text).strip("_")
    if not text:
        text = "item"
    if text[0].isdigit():
        text = f"r_{text}"
    return text[:max_len].strip("_") or "item"


def _binding(prefix: str, seed: object) -> str:
    base = _slug(seed)
    return f"{prefix}_{base}_{_short_hash(seed)}"


def _binding_exists(path: Path, binding: str) -> bool:
    if not path.exists():
        return False
    source = path.read_text(encoding="utf-8")
    return re.search(rf"^\s*{re.escape(binding)}\s*=", source, flags=re.MULTILINE) is not None


@dataclass(frozen=True)
class _AuthoredClaim:
    binding: str
    text: str
    source_claim_id: str | None


def _normalized_claim_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _keyword_literal(call: ast.Call, name: str) -> object:
    for keyword in call.keywords:
        if keyword.arg != name:
            continue
        try:
            return ast.literal_eval(keyword.value)
        except (ValueError, TypeError):
            return None
    return None


def _authored_claims(path: Path) -> list[_AuthoredClaim]:
    if not path.exists():
        return []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return []
    claims: list[_AuthoredClaim] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        call = node.value
        if _call_name(call.func) != "claim":
            continue
        target = node.targets[0] if node.targets else None
        if not isinstance(target, ast.Name):
            continue
        if not call.args:
            continue
        try:
            claim_text = ast.literal_eval(call.args[0])
        except (ValueError, TypeError):
            continue
        if not isinstance(claim_text, str) or not claim_text.strip():
            continue
        metadata = _keyword_literal(call, "metadata")
        research_metadata = (
            metadata.get("gaia_research") if isinstance(metadata, dict) else None
        )
        source_claim_id = (
            research_metadata.get("source_claim_id")
            if isinstance(research_metadata, dict)
            else None
        )
        claims.append(
            _AuthoredClaim(
                binding=target.id,
                text=claim_text.strip(),
                source_claim_id=source_claim_id if isinstance(source_claim_id, str) else None,
            )
        )
    return claims


def _assert_parseable_authored_source(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    try:
        ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        line = f" line {exc.lineno}" if exc.lineno is not None else ""
        raise ResearchSyncSourceError(
            f"authored source is not parseable after research sync: {path}:{line}: {exc.msg}"
        ) from exc


def _research_metadata(kind: str, payload: JsonDict) -> JsonDict:
    return {"gaia_research": {"kind": kind, **payload}}


def _append_statement_once(
    pkg: ResearchPackage,
    *,
    binding: str,
    generated_code: str,
    required_imports: tuple[str, ...],
    result_list: list[str],
    skip_list: list[str],
    export: bool = False,
    sibling_imports: tuple[tuple[str, str], ...] = (),
    foreign_imports: tuple[tuple[str, str, str], ...] = (),
    source_writes: bool,
) -> None:
    target = _authored_init_path(pkg)
    if _binding_exists(target, binding):
        skip_list.append(binding)
        return
    if not source_writes:
        skip_list.append(binding)
        return
    before_source = target.read_text(encoding="utf-8")
    append_statement(
        target,
        generated_code,
        new_label=binding,
        required_imports=required_imports,
        sibling_imports=sibling_imports,
        foreign_imports=foreign_imports,
        import_package_name=pkg.import_name,
        export=export,
    )
    try:
        _assert_parseable_authored_source(target)
    except ResearchSyncSourceError:
        target.write_text(before_source, encoding="utf-8")
        raise
    result_list.append(binding)


def _add_hypothesis_once(
    pkg: ResearchPackage,
    *,
    content: str,
    scope_qid: str | None,
    anchor: JsonDict,
    result: ResearchSyncResult,
) -> None:
    if not result.writes_inquiry:
        result.hypotheses_skipped += 1
        return
    state = load_state(pkg.path)
    for existing in state.synthetic_hypotheses:
        if existing.content == content and existing.scope_qid == scope_qid:
            result.hypotheses_skipped += 1
            return
    hypothesis = SyntheticHypothesis(qid=mint_qid("hyp"), content=content, scope_qid=scope_qid)
    state.synthetic_hypotheses.append(hypothesis)
    save_state(pkg.path, state)
    append_tactic_event(
        pkg.path,
        "research.hypothesis.added",
        {"qid": hypothesis.qid, "scope_qid": scope_qid, "anchor": anchor},
    )
    result.hypotheses_added.append(hypothesis.qid)


def _clean_text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _obligation_record(
    *,
    target_qid: str,
    content: str,
    diagnostic_kind: str,
    target: JsonDict | None,
    action_type: str | None,
    action: str | None,
    anchor: JsonDict,
    source_refs: object,
    qid: str | None = None,
) -> JsonDict:
    record: JsonDict = {}
    if qid is not None:
        record["qid"] = qid
    record["target"] = target if target is not None else {"kind": "question", "id": target_qid}
    record["target_qid"] = target_qid
    record["action_type"] = action_type or diagnostic_kind
    record["action"] = action or content
    record["content"] = content
    record["diagnostic_kind"] = diagnostic_kind
    if anchor:
        record["anchor"] = anchor
    if isinstance(source_refs, list):
        record["source_refs"] = source_refs
    return record


def _obligation_target(payload: JsonDict, *, default_qid: str) -> JsonDict:
    target = payload.get("target")
    if isinstance(target, dict):
        kind = _clean_text(target.get("kind"))
        ref = _clean_text(target.get("ref"))
        target_id = _clean_text(target.get("id"))
        if kind is not None and (ref is not None or target_id is not None):
            normalized: JsonDict = {"kind": kind}
            if ref is not None:
                normalized["ref"] = ref
            if target_id is not None:
                normalized["id"] = target_id
            return normalized
    return {"kind": "question", "id": default_qid}


def _target_qid(target: JsonDict) -> str:
    for key in ("ref", "id"):
        value = _clean_text(target.get(key))
        if value is not None:
            return value
    return "research_obligation"


def _obligation_action_type(payload: JsonDict, *, raw_kind: str) -> str:
    return _clean_text(payload.get("action_type")) or raw_kind


def _obligation_action(payload: JsonDict, *, fallback: str | None) -> str | None:
    return _clean_text(payload.get("action")) or fallback


def _obligation_content(payload: JsonDict, *, action_type: str, action: str) -> str:
    note = _clean_text(payload.get("content"))
    has_structured_action = (
        _clean_text(payload.get("action_type")) is not None
        or _clean_text(payload.get("action")) is not None
    )
    if not has_structured_action:
        return note or action
    parts = [f"action_type={action_type}", f"action={action}"]
    if note is not None and note != action:
        parts.append(f"note={note}")
    return "; ".join(parts)


def _add_obligation_once(
    pkg: ResearchPackage,
    *,
    target_qid: str,
    target: JsonDict | None = None,
    content: str,
    diagnostic_kind: str,
    anchor: JsonDict,
    action_type: str | None = None,
    action: str | None = None,
    source_refs: object = None,
    result: ResearchSyncResult,
) -> None:
    if not result.writes_inquiry:
        result.obligations_skipped += 1
        return
    state = load_state(pkg.path)
    for existing in state.synthetic_obligations:
        if (
            existing.target_qid == target_qid
            and existing.content == content
            and existing.diagnostic_kind == diagnostic_kind
        ):
            result.obligations_skipped += 1
            result.open_obligations.append(
                _obligation_record(
                    qid=existing.qid,
                    target=target,
                    target_qid=target_qid,
                    action_type=action_type,
                    action=action,
                    content=content,
                    diagnostic_kind=diagnostic_kind,
                    anchor=anchor,
                    source_refs=source_refs,
                )
            )
            return
    obligation = SyntheticObligation(
        qid=mint_qid("oblig"),
        target_qid=target_qid,
        content=content,
        diagnostic_kind=diagnostic_kind,
        anchor=anchor,
    )
    state.synthetic_obligations.append(obligation)
    save_state(pkg.path, state)
    append_tactic_event(
        pkg.path,
        "research.obligation.added",
        {
            "qid": obligation.qid,
            "target_qid": target_qid,
            "diagnostic_kind": diagnostic_kind,
            "anchor": anchor,
        },
    )
    result.obligations_added.append(obligation.qid)
    result.open_obligations.append(
        _obligation_record(
            qid=obligation.qid,
            target=target,
            target_qid=target_qid,
            action_type=action_type,
            action=action,
            content=content,
            diagnostic_kind=diagnostic_kind,
            anchor=anchor,
            source_refs=source_refs,
        )
    )


def _defer_obligation(
    *,
    target_qid: str,
    target: JsonDict | None = None,
    content: str,
    diagnostic_kind: str,
    anchor: JsonDict,
    action_type: str | None = None,
    action: str | None = None,
    source_refs: object = None,
    result: ResearchSyncResult,
) -> None:
    result.obligations_deferred.append(
        _obligation_record(
            target=target,
            target_qid=target_qid,
            action_type=action_type,
            action=action,
            content=content,
            diagnostic_kind=diagnostic_kind,
            anchor=anchor,
            source_refs=source_refs,
        )
    )


def _is_actionable_obligation(payload: JsonDict) -> bool:
    for key in ("actionable", "blocking", "write_obligation"):
        value = payload.get(key)
        if isinstance(value, bool):
            return value
    status = payload.get("status")
    return isinstance(status, str) and status in {"actionable", "blocking"}


def _diagnostic_kind_for_obligation(*, raw_kind: str, action_type: str) -> str:
    if raw_kind in {
        "prior_hole",
        "structural_hole",
        "support_weak",
        "focus_weakness",
        "other",
    }:
        return raw_kind
    if raw_kind == "needs_more_evidence" or action_type in {
        "search_more_evidence",
        "assess_claim",
    }:
        return "support_weak"
    if action_type in {"resolve_anchor", "materialize_package", "repair_relation", "repair_refs"}:
        return "structural_hole"
    if action_type in {"assess_focus", "expand_focus", "close_coverage_gap"}:
        return "focus_weakness"
    return "other"


def _obligation_budget_class(action_type: str) -> str:
    if action_type in {"search_more_evidence", "assess_claim"}:
        return "evidence"
    if action_type in {"resolve_anchor", "materialize_package"}:
        return "materialization"
    if action_type in {"repair_relation", "repair_refs"}:
        return "graph_repair"
    if action_type in {"assess_focus"}:
        return "assessment"
    if action_type in {"expand_focus"}:
        return "expansion"
    if action_type in {"close_coverage_gap"}:
        return "coverage"
    return "research"


def _set_focus(pkg: ResearchPackage, *, focus: str, kind: str, result: ResearchSyncResult) -> None:
    if not result.writes_inquiry:
        return
    state = load_state(pkg.path)
    if state.focus == focus and state.focus_kind == kind:
        result.focus_set = focus
        return
    if state.focus is not None:
        state.focus_stack.append(
            {
                "focus": state.focus,
                "focus_kind": state.focus_kind,
                "focus_resolved_id": state.focus_resolved_id,
            }
        )
    state.focus = focus
    state.focus_kind = kind
    state.focus_resolved_id = None
    save_state(pkg.path, state)
    append_tactic_event(pkg.path, "research.focus.set", {"focus": focus, "kind": kind})
    result.focus_set = focus


def _focus_sort_key(focus: JsonDict) -> tuple[int, int, str]:
    return (
        _PRIORITY_ORDER.get(str(focus.get("priority", "low")), 99),
        _READINESS_ORDER.get(str(focus.get("readiness", "defer")), 99),
        str(focus.get("id", "")),
    )


def _focuses_from_artifact(artifact: JsonDict) -> list[JsonDict]:
    raw_focuses = artifact.get("focuses", [])
    return [item for item in raw_focuses if isinstance(item, dict)]


def _accepted_focuses(focuses: list[JsonDict], *, max_questions: int) -> list[JsonDict]:
    accepted = [focus for focus in focuses if focus.get("status") == "accepted"]
    return sorted(accepted, key=_focus_sort_key)[:max_questions]


def _sync_accepted_focus_questions(
    pkg: ResearchPackage,
    focuses: list[JsonDict],
    *,
    result: ResearchSyncResult,
) -> list[str]:
    written_or_existing: list[str] = []
    for focus in focuses:
        focus_id = str(focus.get("id") or "focus")
        question = focus.get("question")
        if not isinstance(question, str) or not question.strip():
            continue
        binding = _binding("rq", focus_id)
        metadata = _research_metadata(
            "accepted_focus",
            {
                "focus_id": focus_id,
                "priority": focus.get("priority"),
                "readiness": focus.get("readiness"),
                "scope": focus.get("scope", {}),
                "coverage": focus.get("coverage", {}),
                "evidence_refs": focus.get("evidence_refs", []),
            },
        )
        code = (
            f"{binding} = question({question.strip()!r}, title={focus_id!r}, metadata={metadata!r})"
        )
        before_written = len(result.questions_written)
        _append_statement_once(
            pkg,
            binding=binding,
            generated_code=code,
            required_imports=("question",),
            result_list=result.questions_written,
            skip_list=result.questions_skipped,
            source_writes=result.writes_source,
        )
        if len(result.questions_written) > before_written or binding in result.questions_skipped:
            written_or_existing.append(binding)
    return written_or_existing


def _sync_candidate_focus_hypotheses(
    pkg: ResearchPackage,
    focuses: list[JsonDict],
    *,
    scope_qid: str | None,
    result: ResearchSyncResult,
) -> None:
    for focus in focuses:
        if focus.get("status") == "accepted":
            continue
        question = focus.get("question")
        if not isinstance(question, str) or not question.strip():
            continue
        _add_hypothesis_once(
            pkg,
            content=question.strip(),
            scope_qid=scope_qid,
            anchor={"kind": "candidate_focus", "id": focus.get("id")},
            result=result,
        )


def _sync_focus_coverage_gaps(
    gaps: object,
    *,
    target_qid: str,
    result: ResearchSyncResult,
) -> None:
    if not isinstance(gaps, list):
        return
    for gap in gaps:
        if not isinstance(gap, dict):
            continue
        description = gap.get("description")
        if not isinstance(description, str) or not description.strip():
            continue
        gap_id = str(gap.get("id") or "coverage_gap")
        target = {"kind": "question", "id": target_qid}
        action = f"Close coverage gap {gap_id}: {description.strip()}"
        source_refs = gap.get("evidence_refs")
        anchor = {
            "kind": "focus_coverage_gap",
            "id": gap.get("id"),
            **research_obligation_anchor(
                source_kind="focus_coverage_gap",
                obligation_type="workflow",
                action_type="close_coverage_gap",
                target=target,
                auto_closeable=True,
                blocking=False,
                budget_class="coverage",
                source="focus_artifact",
                extra={"coverage_gap_id": gap_id},
            ),
        }
        _defer_obligation(
            target=target,
            target_qid=target_qid,
            content=description.strip(),
            diagnostic_kind="focus_weakness",
            action_type="close_coverage_gap",
            action=action,
            anchor=anchor,
            source_refs=source_refs,
            result=result,
        )


def sync_landscape_artifact(
    pkg: ResearchPackage,
    landscape: JsonDict,
    *,
    dry_run: bool = False,
) -> ResearchSyncResult:
    """Record broad/targeted landscape discoveries as inquiry scaffolds."""
    result = ResearchSyncResult(
        dry_run=dry_run,
        source_writes_enabled=False,
    )
    if dry_run:
        return result

    target = landscape.get("target")
    if isinstance(target, dict):
        target_qid = str(target.get("id") or "research_landscape")
    else:
        target_qid = "research_landscape"

    focuses = landscape.get("candidate_focuses", [])
    if isinstance(focuses, list):
        for focus in focuses:
            if not isinstance(focus, dict):
                continue
            question = focus.get("question")
            if not isinstance(question, str) or not question.strip():
                continue
            _add_hypothesis_once(
                pkg,
                content=question.strip(),
                scope_qid=target_qid if target_qid != "research_landscape" else None,
                anchor={"kind": "landscape_focus", "id": focus.get("id")},
                result=result,
            )

    gaps = landscape.get("candidate_coverage_gaps", [])
    if isinstance(gaps, list):
        for gap in gaps:
            if not isinstance(gap, dict):
                continue
            description = gap.get("description") or gap.get("suggestion")
            if not isinstance(description, str) or not description.strip():
                continue
            gap_id = str(gap.get("id") or "coverage_gap")
            target = {"kind": "question", "id": target_qid}
            action = f"Close coverage gap {gap_id}: {description.strip()}"
            source_refs = gap.get("evidence_refs")
            anchor = {
                "kind": "landscape_gap",
                "id": gap.get("id"),
                **research_obligation_anchor(
                    source_kind="landscape_gap",
                    obligation_type="workflow",
                    action_type="close_coverage_gap",
                    target=target,
                    auto_closeable=True,
                    blocking=False,
                    budget_class="coverage",
                    source="landscape",
                    extra={"coverage_gap_id": gap_id},
                ),
            }
            _defer_obligation(
                target=target,
                target_qid=target_qid,
                content=description.strip(),
                diagnostic_kind="focus_weakness",
                action_type="close_coverage_gap",
                action=action,
                anchor=anchor,
                source_refs=source_refs,
                result=result,
            )

    return result


def sync_focus_artifact(
    pkg: ResearchPackage,
    artifact: JsonDict,
    *,
    max_questions: int = 3,
    source_writes: bool = True,
    dry_run: bool = False,
) -> ResearchSyncResult:
    """Write accepted focuses as package questions and inquiry state."""
    result = ResearchSyncResult(
        dry_run=dry_run,
        source_writes_enabled=source_writes,
    )

    focuses = _focuses_from_artifact(artifact)
    accepted = _accepted_focuses(focuses, max_questions=max_questions)
    written_or_existing = _sync_accepted_focus_questions(pkg, accepted, result=result)

    if written_or_existing:
        _set_focus(pkg, focus=written_or_existing[0], kind="question", result=result)

    scope_qid = written_or_existing[0] if written_or_existing else None
    _sync_candidate_focus_hypotheses(pkg, focuses, scope_qid=scope_qid, result=result)
    target_qid = written_or_existing[0] if written_or_existing else "research_focus"
    _sync_focus_coverage_gaps(artifact.get("coverage_gaps"), target_qid=target_qid, result=result)

    return result


def _assessment_package_ref_value_types(assessment: JsonDict) -> dict[str, str]:
    evidence_packet = assessment.get("evidence_packet")
    items = evidence_packet.get("items") if isinstance(evidence_packet, dict) else None
    if not isinstance(items, list):
        return {}

    refs: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        package_ref_payload = item.get("package_ref")
        if not isinstance(package_ref_payload, dict):
            continue
        ref = package_ref_payload.get("ref")
        value_type = package_ref_payload.get("value_type")
        if isinstance(ref, str) and ref and isinstance(value_type, str) and value_type:
            refs[ref] = value_type
    return refs


def _relation_claim_refs(
    relation: JsonDict,
    *,
    package_ref_value_types: dict[str, str] | None = None,
    new_claim_refs: dict[str, str] | None = None,
) -> tuple[
    list[str],
    tuple[tuple[str, str], ...],
    tuple[tuple[str, str, str], ...],
    str | None,
]:
    raw_refs = relation.get("claim_refs", relation.get("claims"))
    source_package_refs = _package_ref_source_refs(relation)
    if raw_refs is None:
        raw_refs = source_package_refs
    if not isinstance(raw_refs, list):
        return [], (), (), "claim_refs missing or not a list"
    raw_refs = _repair_partial_claim_refs_from_source_package_refs(
        raw_refs,
        source_package_refs=source_package_refs,
    )
    candidate_refs = new_claim_refs or {}
    refs = [
        candidate_refs.get(str(item).strip(), str(item).strip())
        for item in raw_refs
        if str(item).strip()
    ]
    value_types = package_ref_value_types or {}
    for ref in refs:
        value_type = value_types.get(ref)
        if value_type is not None and value_type != "claim":
            return [], (), (), f"{ref} has value_type={value_type}; expected claim"
    if len(refs) < 2:
        return [], (), (), f"need at least two claim refs; got {len(refs)}"
    tokens, error = split_csv_refs(",".join(refs))
    if error is not None:
        return [], (), (), str(error)
    new_claim_bindings = set(candidate_refs.values())
    sibling = tuple((item, "") for item in tokens.local if item not in new_claim_bindings)
    foreign = tuple((item.module, item.symbol, item.alias) for item in tokens.foreign_imports)
    return tokens.rendered, sibling, foreign, None


def _repair_partial_claim_refs_from_source_package_refs(
    raw_refs: list[object],
    *,
    source_package_refs: list[str],
) -> list[object]:
    # Fallback for partial LLM output; prompts still require complete relation endpoints.
    if len([ref for ref in raw_refs if str(ref).strip()]) >= 2:
        return raw_refs
    refs: list[object] = []
    seen: set[str] = set()
    for ref in [*source_package_refs, *raw_refs]:
        key = str(ref).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        refs.append(ref)
    return refs


def _package_ref_source_refs(relation: JsonDict) -> list[str]:
    source_refs = relation.get("source_refs")
    if not isinstance(source_refs, list):
        return []
    refs: list[str] = []
    for ref in source_refs:
        if not isinstance(ref, dict) or ref.get("kind") != "package_ref":
            continue
        ref_id = ref.get("id")
        if isinstance(ref_id, str) and ref_id.strip():
            refs.append(ref_id.strip())
    return refs


def _candidate_relation_pattern(relation_type: str, claim_refs: list[str]) -> str | None:
    if relation_type in {"opposes", "conflicts"} and len(claim_refs) == 2:
        return "contradict"
    return None


def _relation_type(relation: JsonDict) -> str:
    raw = relation.get("relation_type") or relation.get("type") or "relation"
    return str(raw)


def _new_claim_text(claim: JsonDict) -> str | None:
    for key in ("claim", "text", "content"):
        value = claim.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _sync_assessment_new_claims(
    pkg: ResearchPackage,
    claims: object,
    *,
    focus_id: str,
    result: ResearchSyncResult,
) -> dict[str, str]:
    if not isinstance(claims, list):
        return {}
    bindings: dict[str, str] = {}
    target = _authored_init_path(pkg)
    existing_by_text = {
        _normalized_claim_text(claim.text): claim.binding for claim in _authored_claims(target)
    }
    for claim_payload in claims:
        if not isinstance(claim_payload, dict):
            continue
        claim_text = _new_claim_text(claim_payload)
        claim_id = claim_payload.get("id")
        if not isinstance(claim_id, str) or not claim_id.strip() or claim_text is None:
            result.claims_skipped.append(str(claim_id or claim_payload or "claim"))
            continue
        existing_binding = existing_by_text.get(_normalized_claim_text(claim_text))
        if existing_binding is not None:
            result.claims_skipped.append(f"{claim_id} -> {existing_binding}")
            bindings[claim_id] = existing_binding
            continue
        binding = _binding(
            "research_claim",
            {
                "focus": focus_id,
                "id": claim_id,
                "claim": claim_text,
            },
        )
        metadata = _research_metadata(
            "research_claim",
            {
                "focus": focus_id,
                "source_claim_id": claim_id,
                "category": claim_payload.get("category"),
                "answers_question": claim_payload.get("answers_question") or focus_id,
                "status": claim_payload.get("status") or "candidate",
                "rationale": claim_payload.get("rationale"),
                "source_refs": claim_payload.get("source_refs", []),
            },
        )
        code = f"{binding} = claim({claim_text!r}, title={claim_id!r}, metadata={metadata!r})"
        _append_statement_once(
            pkg,
            binding=binding,
            generated_code=code,
            required_imports=("claim",),
            result_list=result.claims_written,
            skip_list=result.claims_skipped,
            export=True,
            source_writes=result.writes_source,
        )
        bindings[claim_id] = binding
        existing_by_text.setdefault(_normalized_claim_text(claim_text), binding)
    return bindings


def _sync_assessment_review_note(
    pkg: ResearchPackage,
    assessment: JsonDict,
    *,
    focus_id: str,
    result: ResearchSyncResult,
) -> None:
    review = assessment.get("review")
    if not isinstance(review, dict):
        return
    content = render_assessment_review_note_markdown(
        review,
        citations=assessment.get("citations"),
        language=review.get("language") or assessment.get("language"),
    )
    if not content:
        return
    binding = _binding("review", {"focus": focus_id, "summary": review.get("summary")})
    metadata = _research_metadata(
        "assessment_review",
        {"focus": focus_id, "language": review.get("language"), "depth": review.get("depth")},
    )
    code = (
        f"{binding} = note("
        f"{content!r}, title={('Assessment review: ' + focus_id)!r}, metadata={metadata!r})"
    )
    _append_statement_once(
        pkg,
        binding=binding,
        generated_code=code,
        required_imports=("note",),
        result_list=result.notes_written,
        skip_list=result.notes_skipped,
        source_writes=result.writes_source,
    )


def _sync_assessment_relation_hypothesis(
    pkg: ResearchPackage,
    relation: JsonDict,
    *,
    focus_id: str,
    result: ResearchSyncResult,
) -> None:
    claim = relation.get("claim")
    if not isinstance(claim, str) or not claim.strip():
        return
    content = f"{relation.get('type', 'relation')}: {claim.strip()}"
    _add_hypothesis_once(
        pkg,
        content=content,
        scope_qid=focus_id,
        anchor={
            "kind": "assessment_relation",
            "source_refs": relation.get("source_refs"),
        },
        result=result,
    )


def _sync_assessment_candidate_relation(
    pkg: ResearchPackage,
    relation: JsonDict,
    *,
    focus_id: str,
    package_ref_value_types: dict[str, str],
    new_claim_refs: dict[str, str],
    result: ResearchSyncResult,
) -> None:
    claim_refs, sibling_imports, foreign_imports, skip_reason = _relation_claim_refs(
        relation,
        package_ref_value_types=package_ref_value_types,
        new_claim_refs=new_claim_refs,
    )
    if len(claim_refs) < 2:
        label = str(relation.get("id") or relation.get("claim") or "relation")
        if skip_reason:
            label = f"{label}: {skip_reason}"
        result.candidate_relations_skipped.append(label)
        return
    relation_type = _relation_type(relation)
    binding = _binding(
        "candidate_relation",
        {
            "focus": focus_id,
            "type": relation_type,
            "claim_refs": claim_refs,
            "claim": relation.get("claim"),
        },
    )
    pattern = _candidate_relation_pattern(relation_type, claim_refs)
    metadata = _research_metadata(
        "candidate_relation",
        {
            "focus": focus_id,
            "scope_question": relation.get("scope_question") or focus_id,
            "relation_type": relation_type,
            "strength": relation.get("strength"),
            "epistemic_status": relation.get("epistemic_status"),
            "system": relation.get("system"),
            "condition": relation.get("condition"),
            "method": relation.get("method"),
            "observable": relation.get("observable"),
            "certainty": relation.get("certainty"),
            "scope_note": relation.get("scope_note"),
            "source_refs": relation.get("source_refs", []),
        },
    )
    relation_record: JsonDict = {
        "id": binding,
        "claims": claim_refs,
        "pattern": pattern,
        "metadata": metadata,
    }
    kwargs = [f"claims=[{', '.join(claim_refs)}]"]
    if pattern is not None:
        kwargs.append(f"pattern={pattern!r}")
    rationale = relation.get("rationale")
    if isinstance(rationale, str) and rationale.strip():
        rationale_text = rationale.strip()
        relation_record["rationale"] = rationale_text
        kwargs.append(f"rationale={rationale_text!r}")
    kwargs.append(f"metadata={metadata!r}")
    code = f"{binding} = candidate_relation({', '.join(kwargs)})"
    target = _authored_init_path(pkg)
    backed_before = _binding_exists(target, binding)
    _append_statement_once(
        pkg,
        binding=binding,
        generated_code=code,
        required_imports=("candidate_relation",),
        result_list=result.candidate_relations_written,
        skip_list=result.candidate_relations_skipped,
        sibling_imports=sibling_imports,
        foreign_imports=foreign_imports,
        source_writes=result.writes_source,
    )
    if backed_before or _binding_exists(target, binding):
        result.evidence_matrix_rows.extend(project_evidence_matrix_rows([relation_record]))


def _sync_assessment_relations(
    pkg: ResearchPackage,
    relations: object,
    *,
    focus_id: str,
    package_ref_value_types: dict[str, str],
    new_claim_refs: dict[str, str],
    result: ResearchSyncResult,
) -> None:
    if not isinstance(relations, list):
        return
    for relation in relations:
        if not isinstance(relation, dict):
            continue
        _sync_assessment_relation_hypothesis(pkg, relation, focus_id=focus_id, result=result)
        _sync_assessment_candidate_relation(
            pkg,
            relation,
            focus_id=focus_id,
            package_ref_value_types=package_ref_value_types,
            new_claim_refs=new_claim_refs,
            result=result,
        )


def _sync_assessment_obligations(
    pkg: ResearchPackage,
    obligations: object,
    *,
    focus_id: str,
    result: ResearchSyncResult,
) -> None:
    if not isinstance(obligations, list):
        return
    for obligation in obligations:
        if not isinstance(obligation, dict):
            continue
        raw_kind = str(obligation.get("kind") or "other")
        target = _obligation_target(obligation, default_qid=focus_id)
        target_qid = _target_qid(target)
        action_type = _obligation_action_type(obligation, raw_kind=raw_kind)
        diagnostic_kind = _diagnostic_kind_for_obligation(
            raw_kind=raw_kind,
            action_type=action_type,
        )
        action = _obligation_action(obligation, fallback=_clean_text(obligation.get("content")))
        if action is None:
            continue
        content = _obligation_content(obligation, action_type=action_type, action=action)
        source_refs = obligation.get("source_refs")
        actionable = _is_actionable_obligation(obligation)
        anchor = {
            "kind": "assessment_obligation",
            "source_refs": source_refs,
            **research_obligation_anchor(
                source_kind="assessment_obligation",
                obligation_type="workflow" if actionable else "future_research",
                action_type=action_type,
                target=target,
                auto_closeable=actionable,
                blocking=actionable,
                budget_class=_obligation_budget_class(action_type),
                source="assessment",
            ),
        }
        if not actionable:
            _defer_obligation(
                target=target,
                target_qid=target_qid,
                content=content,
                diagnostic_kind=diagnostic_kind,
                action_type=action_type,
                action=action,
                anchor=anchor,
                source_refs=source_refs,
                result=result,
            )
            continue
        _add_obligation_once(
            pkg,
            target=target,
            target_qid=target_qid,
            content=content,
            diagnostic_kind=diagnostic_kind,
            action_type=action_type,
            action=action,
            anchor=anchor,
            source_refs=source_refs,
            result=result,
        )


def sync_assessment_artifact(
    pkg: ResearchPackage,
    assessment: JsonDict,
    *,
    source_writes: bool = True,
    dry_run: bool = False,
) -> ResearchSyncResult:
    """Record assessment review output as package/inquiry scaffolds."""
    result = ResearchSyncResult(
        dry_run=dry_run,
        source_writes_enabled=source_writes,
    )

    focus = assessment.get("focus")
    focus_id = str(focus.get("id") if isinstance(focus, dict) else "research_focus")
    package_ref_value_types = _assessment_package_ref_value_types(assessment)

    _sync_assessment_review_note(pkg, assessment, focus_id=focus_id, result=result)
    new_claim_refs = _sync_assessment_new_claims(
        pkg,
        assessment.get("new_claims"),
        focus_id=focus_id,
        result=result,
    )
    _sync_assessment_relations(
        pkg,
        assessment.get("relations"),
        focus_id=focus_id,
        package_ref_value_types=package_ref_value_types,
        new_claim_refs=new_claim_refs,
        result=result,
    )
    _sync_assessment_obligations(
        pkg,
        assessment.get("candidate_obligations"),
        focus_id=focus_id,
        result=result,
    )
    return result


def sync_research_obligations(
    pkg: ResearchPackage,
    obligations: object,
    *,
    dry_run: bool = False,
) -> ResearchSyncResult:
    """Record normalized research obligations into Gaia inquiry state."""
    result = ResearchSyncResult(
        dry_run=dry_run,
        source_writes_enabled=False,
    )
    if not isinstance(obligations, list):
        return result
    for obligation in obligations:
        if not isinstance(obligation, dict):
            continue
        target = _obligation_target(
            obligation,
            default_qid=str(obligation.get("target_qid") or "research_obligation"),
        )
        target_qid = str(obligation.get("target_qid") or _target_qid(target))
        action_type = _clean_text(obligation.get("action_type")) or "research_action"
        action = _clean_text(obligation.get("action"))
        if action is None:
            continue
        content = _clean_text(obligation.get("content")) or action
        diagnostic_kind = _diagnostic_kind_for_obligation(
            raw_kind=str(obligation.get("diagnostic_kind") or obligation.get("kind") or "other"),
            action_type=action_type,
        )
        source_refs = obligation.get("source_refs")
        raw_anchor = obligation.get("anchor")
        anchor = dict(raw_anchor) if isinstance(raw_anchor, dict) else {}
        if "gaia_research" not in anchor:
            anchor = {
                **anchor,
                **research_obligation_anchor(
                    source_kind=str(anchor.get("kind") or "research_obligation"),
                    obligation_type="workflow"
                    if _is_actionable_obligation(obligation)
                    else "future_research",
                    action_type=action_type,
                    target=target,
                    auto_closeable=_is_actionable_obligation(obligation),
                    blocking=_is_actionable_obligation(obligation),
                    budget_class=_obligation_budget_class(action_type),
                    source="research_obligation",
                ),
            }
        if _is_actionable_obligation(obligation):
            _add_obligation_once(
                pkg,
                target=target,
                target_qid=target_qid,
                content=content,
                diagnostic_kind=diagnostic_kind,
                action_type=action_type,
                action=action,
                anchor=anchor,
                source_refs=source_refs,
                result=result,
            )
            continue
        _defer_obligation(
            target=target,
            target_qid=target_qid,
            content=content,
            diagnostic_kind=diagnostic_kind,
            action_type=action_type,
            action=action,
            anchor=anchor,
            source_refs=source_refs,
            result=result,
        )
    return result


def _source_assessment_focus_id(artifact: JsonDict) -> str:
    source_assessment = artifact.get("source_assessment")
    if isinstance(source_assessment, dict):
        focus_id = source_assessment.get("focus_id") or source_assessment.get("id")
        if isinstance(focus_id, str) and focus_id.strip():
            return focus_id.strip()
    return "research_proposal"


def _accepted_research_question_proposals(
    proposals: object,
    *,
    max_questions: int,
) -> list[JsonDict]:
    if not isinstance(proposals, list):
        return []
    accepted = [
        proposal
        for proposal in proposals
        if isinstance(proposal, dict)
        and proposal.get("status") == "accepted"
        and proposal.get("kind") == "research_question"
    ]
    return sorted(
        accepted,
        key=lambda proposal: (
            _PRIORITY_ORDER.get(str(proposal.get("priority", "low")), 99),
            str(proposal.get("id", "")),
        ),
    )[:max_questions]


def _sync_accepted_proposal_questions(
    pkg: ResearchPackage,
    proposals: list[JsonDict],
    *,
    source_focus_id: str,
    result: ResearchSyncResult,
) -> list[str]:
    written_or_existing: list[str] = []
    for proposal in proposals:
        proposal_id = str(proposal.get("id") or "proposal")
        question_text = proposal.get("question")
        if not isinstance(question_text, str) or not question_text.strip():
            continue
        binding = _binding("rq", proposal_id)
        metadata = _research_metadata(
            "accepted_proposal",
            {
                "proposal_id": proposal_id,
                "proposal_kind": proposal.get("kind"),
                "priority": proposal.get("priority"),
                "source_focus_id": source_focus_id,
                "source_refs": proposal.get("source_refs", []),
            },
        )
        code = (
            f"{binding} = question("
            f"{question_text.strip()!r}, title={proposal_id!r}, metadata={metadata!r})"
        )
        before_written = len(result.questions_written)
        _append_statement_once(
            pkg,
            binding=binding,
            generated_code=code,
            required_imports=("question",),
            result_list=result.questions_written,
            skip_list=result.questions_skipped,
            source_writes=result.writes_source,
        )
        if len(result.questions_written) > before_written or binding in result.questions_skipped:
            written_or_existing.append(binding)
    return written_or_existing


def _sync_proposal_hypotheses(
    pkg: ResearchPackage,
    hypotheses: object,
    *,
    scope_qid: str | None,
    result: ResearchSyncResult,
) -> None:
    if not isinstance(hypotheses, list):
        return
    for hypothesis in hypotheses:
        if not isinstance(hypothesis, dict):
            continue
        content = hypothesis.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        _add_hypothesis_once(
            pkg,
            content=content.strip(),
            scope_qid=scope_qid,
            anchor={
                "kind": "proposal_hypothesis",
                "source_refs": hypothesis.get("source_refs"),
            },
            result=result,
        )


def _sync_unaccepted_proposals_as_hypotheses(
    pkg: ResearchPackage,
    proposals: object,
    *,
    scope_qid: str | None,
    result: ResearchSyncResult,
) -> None:
    if not isinstance(proposals, list):
        return
    for proposal in proposals:
        if not isinstance(proposal, dict) or proposal.get("status") == "accepted":
            continue
        question_text = proposal.get("question")
        if not isinstance(question_text, str) or not question_text.strip():
            continue
        _add_hypothesis_once(
            pkg,
            content=question_text.strip(),
            scope_qid=scope_qid,
            anchor={"kind": "proposal_candidate", "id": proposal.get("id")},
            result=result,
        )


def _sync_proposal_obligations(
    pkg: ResearchPackage,
    obligations: object,
    *,
    target_qid: str,
    result: ResearchSyncResult,
) -> None:
    if not isinstance(obligations, list):
        return
    for obligation in obligations:
        if not isinstance(obligation, dict):
            continue
        raw_kind = str(obligation.get("kind") or "other")
        diagnostic_kind = "support_weak" if raw_kind == "needs_more_evidence" else "other"
        target = _obligation_target(obligation, default_qid=target_qid)
        resolved_target_qid = _target_qid(target)
        action_type = _obligation_action_type(obligation, raw_kind=raw_kind)
        action = _obligation_action(obligation, fallback=_clean_text(obligation.get("content")))
        if action is None:
            continue
        content = _obligation_content(obligation, action_type=action_type, action=action)
        source_refs = obligation.get("source_refs")
        _add_obligation_once(
            pkg,
            target=target,
            target_qid=resolved_target_qid,
            content=content,
            diagnostic_kind=diagnostic_kind,
            action_type=action_type,
            action=action,
            anchor={
                "kind": "proposal_obligation",
                "source_refs": source_refs,
            },
            source_refs=source_refs,
            result=result,
        )


def sync_proposal_artifact(
    pkg: ResearchPackage,
    proposal: JsonDict,
    *,
    max_questions: int = 3,
    source_writes: bool = True,
    dry_run: bool = False,
) -> ResearchSyncResult:
    """Record accepted open-ended proposals as questions and inquiry state."""
    result = ResearchSyncResult(
        dry_run=dry_run,
        source_writes_enabled=source_writes,
    )

    source_focus_id = _source_assessment_focus_id(proposal)
    accepted_questions = _accepted_research_question_proposals(
        proposal.get("proposals"),
        max_questions=max_questions,
    )
    written_or_existing = _sync_accepted_proposal_questions(
        pkg,
        accepted_questions,
        source_focus_id=source_focus_id,
        result=result,
    )
    if written_or_existing:
        _set_focus(pkg, focus=written_or_existing[0], kind="question", result=result)

    scope_qid = written_or_existing[0] if written_or_existing else source_focus_id
    _sync_unaccepted_proposals_as_hypotheses(
        pkg,
        proposal.get("proposals"),
        scope_qid=scope_qid,
        result=result,
    )
    _sync_proposal_hypotheses(
        pkg,
        proposal.get("hypotheses"),
        scope_qid=scope_qid,
        result=result,
    )
    _sync_proposal_obligations(
        pkg,
        proposal.get("candidate_obligations"),
        target_qid=scope_qid,
        result=result,
    )
    return result


def sync_materialization(
    pkg: ResearchPackage,
    *,
    scaffold: str,
    by: list[str],
    rationale: str | None = None,
    source_writes: bool = True,
    dry_run: bool = False,
) -> ResearchSyncResult:
    """Write an explicit ``materialize(...)`` link for a scaffold."""
    result = ResearchSyncResult(
        dry_run=dry_run,
        source_writes_enabled=source_writes,
    )
    if not _IDENTIFIER_RE.match(scaffold):
        result.materializations_skipped.append(scaffold)
        return result
    clean_by = [item for item in by if _IDENTIFIER_RE.match(item)]
    if not clean_by or len(clean_by) != len(by):
        result.materializations_skipped.append(scaffold)
        return result
    binding = _binding("materialization", {"scaffold": scaffold, "by": clean_by})
    metadata = _research_metadata("materialization", {"scaffold": scaffold, "by": clean_by})
    kwargs = [f"by=[{', '.join(clean_by)}]"]
    if rationale:
        kwargs.append(f"rationale={rationale!r}")
    kwargs.append(f"metadata={metadata!r}")
    code = f"{binding} = materialize({scaffold}, {', '.join(kwargs)})"
    _append_statement_once(
        pkg,
        binding=binding,
        generated_code=code,
        required_imports=("materialize",),
        result_list=result.materializations_written,
        skip_list=result.materializations_skipped,
        sibling_imports=tuple((item, "") for item in clean_by),
        source_writes=result.writes_source,
    )
    return result


__all__ = [
    "ResearchSyncResult",
    "ResearchSyncSourceError",
    "sync_assessment_artifact",
    "sync_focus_artifact",
    "sync_landscape_artifact",
    "sync_materialization",
    "sync_proposal_artifact",
    "sync_research_obligations",
]

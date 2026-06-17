"""Tests for packaged Gaia Research prompt assets."""

from __future__ import annotations

import json

from gaia_research.prompt_assets import (
    RESEARCH_PROMPT_PHASES,
    load_research_output_shape,
    load_research_phase_prompt,
    load_research_system_prompt,
)


def test_research_system_prompt_is_packaged() -> None:
    prompt = load_research_system_prompt()

    assert "Return exactly one valid JSON object" in prompt
    assert "source refs and ids" in prompt


def test_every_research_phase_has_prompt_and_shape() -> None:
    assert RESEARCH_PROMPT_PHASES == (
        "query_plan",
        "field_map_analysis",
        "focus_analysis",
        "assess_analysis",
        "report_plan",
        "report_section",
        "report_stitch",
    )

    for phase in RESEARCH_PROMPT_PHASES:
        prompt = load_research_phase_prompt(phase)
        shape = load_research_output_shape(phase)
        json.dumps(shape)
        assert len(prompt.strip()) > 40
        assert shape["required_top_level_keys"]


def test_unknown_research_phase_fails_clearly() -> None:
    try:
        load_research_phase_prompt("unknown")
    except ValueError as exc:
        assert "unknown research prompt phase" in str(exc)
    else:
        raise AssertionError("expected unknown prompt phase to fail")


def test_report_prompts_encode_evidence_obligations_without_fixed_sections() -> None:
    report_plan = load_research_phase_prompt("report_plan")
    report_section = load_research_phase_prompt("report_section")
    report_stitch = load_research_phase_prompt("report_stitch")

    combined = "\n".join([report_plan, report_section, report_stitch])

    for obligation in (
        "current evidence position",
        "scope and coverage",
        "evidence basis",
        "agreement, disagreement, or tension",
        "uncertainty and limitations",
        "next evidence need",
    ):
        assert obligation in combined

    assert "Do not force the report into six fixed sections" in report_plan
    assert "Do not introduce unassessed evidence as a strong conclusion" in report_section
    assert "Do not drop evidence obligations" in report_stitch


def test_prompts_treat_focuses_as_discussion_questions_and_assessment_as_matrix() -> None:
    focus_prompt = load_research_phase_prompt("focus_analysis")
    assess_prompt = load_research_phase_prompt("assess_analysis")
    report_plan = load_research_phase_prompt("report_plan")
    report_section = load_research_phase_prompt("report_section")
    shape = load_research_output_shape("report_plan")

    assert "report-level discussion question" in focus_prompt
    assert "system, condition, method, observable" in assess_prompt
    assert "evidence matrix row" in assess_prompt
    assert "new_claims" in assess_prompt
    assert "existing-existing" in assess_prompt
    assert "existing-new" in assess_prompt
    assert "lkm:<package>::<label>" in assess_prompt
    assert "Synthesize across focuses" in report_plan
    assert "not one section per focus" in report_plan
    assert "relevant focus" in report_section
    assert "focus_ids" in shape["sections_item_keys"]


def test_assessment_prompt_distinguishes_relation_endpoints_from_provenance() -> None:
    assess_prompt = load_research_phase_prompt("assess_analysis")
    shape = load_research_output_shape("assess_analysis")

    assert "claim_refs are relation endpoints" in assess_prompt
    assert "source_refs are provenance" in assess_prompt
    endpoint_rule = (
        "Every candidate relation with concrete endpoints must include at least two claim_refs"
    )
    assert endpoint_rule in assess_prompt
    assert "Do not rely on source_refs to supply missing relation endpoints" in assess_prompt
    assert "Only put a package_ref in claim_refs when that package_ref is a claim endpoint" in (
        assess_prompt
    )
    assert "relations_claim_refs_note" in shape
    assert "source_refs do not replace claim_refs" in shape["relations_claim_refs_note"]

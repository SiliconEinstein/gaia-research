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

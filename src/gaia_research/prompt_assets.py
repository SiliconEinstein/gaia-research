"""Packaged prompt loading helpers."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any, cast

_RESEARCH_PROMPTS_PACKAGE = "gaia_research.prompts.research"

RESEARCH_PROMPT_PHASES = (
    "query_plan",
    "field_map_analysis",
    "focus_analysis",
    "assess_analysis",
    "report_plan",
    "report_section",
    "report_stitch",
)


def load_research_system_prompt() -> str:
    """Load the common system prompt for research JSON compiler calls."""
    return _read_prompt_text("system.md")


def load_research_phase_prompt(phase: str) -> str:
    """Load the phase prompt for one research workflow LLM call."""
    if phase not in RESEARCH_PROMPT_PHASES:
        msg = f"unknown research prompt phase: {phase}"
        raise ValueError(msg)
    return _read_prompt_text(f"{phase}.md")


def load_research_output_shape(phase: str) -> dict[str, Any]:
    """Load compact output-shape hints for one research workflow LLM call."""
    if phase not in RESEARCH_PROMPT_PHASES:
        msg = f"unknown research prompt phase: {phase}"
        raise ValueError(msg)
    payload = json.loads(_read_prompt_text("output_shapes.json"))
    shape = payload.get(phase)
    if not isinstance(shape, dict):
        msg = f"missing output shape for research prompt phase: {phase}"
        raise ValueError(msg)
    return cast(dict[str, Any], shape)


def _read_prompt_text(name: str) -> str:
    resource = files(_RESEARCH_PROMPTS_PACKAGE).joinpath(name)
    return resource.read_text(encoding="utf-8").strip()

"""Shared run-budget primitives for Gaia research workflows."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchRunBudget:
    """Common budget envelope used by workflow scheduling decisions."""

    focus_count: int = 1
    evidence_items_per_focus: int = 20
    evidence_papers_per_focus: int = 20
    evidence_chains_per_focus: int = 20
    obligation_iterations: int = 0
    report_sections: int | None = None
    report_evidence_refs: int | None = None
    report_words: int | None = None


__all__ = ["ResearchRunBudget"]

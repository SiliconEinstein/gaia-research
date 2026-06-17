"""Tests for research CLI option validation."""

from __future__ import annotations

import pytest
import typer

from gaia_research.research_cli import _validate_evidence_selection_limits


def test_research_run_rejects_assessment_worksets_smaller_than_ten() -> None:
    with pytest.raises(typer.Exit) as exc_info:
        _validate_evidence_selection_limits(max_items=9, max_papers=1, max_chains=0)

    assert exc_info.value.exit_code == 2


def test_research_run_accepts_minimum_assessment_workset_size() -> None:
    _validate_evidence_selection_limits(max_items=10, max_papers=1, max_chains=0)

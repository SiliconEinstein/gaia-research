"""Tests for typed research workflow configuration."""

from __future__ import annotations

import json
from pathlib import Path

from gaia_research.run_config import resolve_research_run_config


def test_fast_profile_is_supported_as_product_alias() -> None:
    config = resolve_research_run_config(profile="fast")

    assert config.profile == "fast"
    assert config.llm.provider == "litellm"
    assert config.search.limit == 10
    assert config.focus.count == 1
    assert config.evidence.selection_mode == "fast"


def test_broad_profile_uses_wider_search_and_focus_defaults() -> None:
    config = resolve_research_run_config(profile="broad")

    assert config.profile == "broad"
    assert config.llm.provider == "litellm"
    assert config.search.limit == 20
    assert config.focus.count == 3
    assert config.evidence.selection_mode == "fast"
    assert config.evidence.max_items == 24
    assert config.evidence.max_papers == 10
    assert config.evidence.max_chains == 10


def test_deep_profile_uses_wider_evidence_selection_defaults() -> None:
    config = resolve_research_run_config(profile="deep")

    assert config.profile == "deep"
    assert config.llm.provider == "litellm"
    assert config.search.limit == 20
    assert config.focus.count == 5
    assert config.evidence.selection_mode == "review"
    assert config.evidence.max_items == 48
    assert config.evidence.max_papers == 20
    assert config.evidence.max_chains == 20


def test_legacy_profiles_are_rejected() -> None:
    for profile in ("evidence-assessment", "quick", "review"):
        try:
            resolve_research_run_config(profile=profile)
        except ValueError as exc:
            assert "fast, broad, deep" in str(exc)
        else:  # pragma: no cover - assertion branch
            raise AssertionError(f"{profile} should be rejected")


def test_config_file_and_overrides_deep_merge(tmp_path: Path) -> None:
    config_path = tmp_path / "research.json"
    config_path.write_text(
        json.dumps(
            {
                "profile": "broad",
                "search": {"limit": 7},
                "evidence": {"max_items": 24},
                "llm": {"provider": "litellm", "model": "openai/test"},
            }
        ),
        encoding="utf-8",
    )

    config = resolve_research_run_config(
        profile="fast",
        config_file=config_path,
        overrides={"evidence": {"max_papers": 9}, "report": {"section_concurrency": 2}},
    )

    assert config.profile == "broad"
    assert config.search.limit == 7
    assert config.focus.count == 3
    assert config.evidence.selection_mode == "fast"
    assert config.evidence.max_items == 24
    assert config.evidence.max_papers == 9
    assert config.llm.provider == "litellm"
    assert config.llm.model == "openai/test"
    assert config.report.section_concurrency == 2

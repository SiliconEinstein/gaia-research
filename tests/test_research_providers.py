"""Tests for research analysis provider helpers."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, ClassVar, cast

from gaia_research import research_providers


def test_litellm_messages_use_packaged_prompt_assets() -> None:
    messages = research_providers._litellm_messages(
        phase="query_plan",
        input_payload={"topic": "smoke"},
    )

    assert messages[0]["role"] == "system"
    assert "Return exactly one valid JSON object" in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert "Generate 3-5 broad live-search queries" in messages[1]["content"]
    assert "required_top_level_keys" in messages[1]["content"]


def test_litellm_completion_uses_explicit_gaia_research_endpoint(
    monkeypatch: Any,
) -> None:
    captured: dict[str, object] = {}

    class FakeLiteLLM:
        suppress_debug_info = False
        disable_cost_calc = False
        set_verbose = True
        callbacks: ClassVar[list[object]] = []
        success_callback: ClassVar[list[object]] = []
        failure_callback: ClassVar[list[object]] = []
        _async_success_callback: ClassVar[list[object]] = []
        _async_failure_callback: ClassVar[list[object]] = []
        input_callback: ClassVar[list[object]] = []
        service_callback: ClassVar[list[object]] = []
        post_call_rules: ClassVar[list[object]] = []

        async def acompletion(self, **kwargs: object) -> dict[str, object]:
            captured.update(kwargs)
            return {"choices": [{"message": {"content": "{}"}}]}

    fake_runtime = FakeLiteLLM()

    monkeypatch.setenv(
        "GAIA_RESEARCH_LLM_API_BASE",
        "https://api.deepseek.com/chat/completions",
    )
    monkeypatch.setenv("GAIA_RESEARCH_LLM_API_KEY", "research-key")
    monkeypatch.setenv("LITELLM_PROXY_API_BASE", "https://legacy.example/v1")
    monkeypatch.setenv("LITELLM_PROXY_API_KEY", "legacy-proxy-key")
    monkeypatch.setattr(
        research_providers,
        "import_module",
        lambda name: fake_runtime if name == "litellm" else None,
    )

    asyncio.run(
        research_providers._litellm_completion(
            model="openai/deepseek-chat",
            phase="field_map_analysis",
            input_payload={"artifact_payloads": []},
            temperature=0.0,
            timeout=10.0,
            max_retries=0,
            max_tokens=128,
        )
    )

    assert captured["api_base"] == "https://api.deepseek.com"
    assert captured["api_key"] == "research-key"


def test_litellm_env_kwargs_ignores_legacy_and_provider_native_keys(
    monkeypatch: Any,
) -> None:
    monkeypatch.delenv("GAIA_RESEARCH_LLM_API_BASE", raising=False)
    monkeypatch.delenv("GAIA_RESEARCH_LLM_API_KEY", raising=False)
    monkeypatch.setenv("LITELLM_PROXY_API_BASE", "https://legacy.example/v1")
    monkeypatch.setenv("LITELLM_PROXY_API_KEY", "legacy-proxy-key")
    monkeypatch.setenv("OPENAI_API_KEY", "provider-native-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "provider-native-key")

    assert research_providers._litellm_env_kwargs() == {}


def test_hydrated_selected_evidence_preserves_new_expansion_metadata(
    tmp_path: Path,
) -> None:
    selected_evidence_path = tmp_path / "selected-evidence.json"
    selected_evidence_path.write_text(
        json.dumps(
            {
                "kind": "selected_evidence",
                "schema_version": 1,
                "evidence_packet": {
                    "landscapes": [
                        {
                            "index": 0,
                            "kind": "research_landscape",
                            "action": "explore.expand",
                        }
                    ],
                    "items": [
                        {
                            "kind": "variable",
                            "id": "claim_expand",
                            "variable_type": "claim",
                            "content": "Focused expansion claim.",
                            "source": {
                                "paper_id": "P_EXPAND",
                                "paper_title": "Expand paper",
                            },
                            "source_landscape_action": "explore.expand",
                            "is_new": True,
                        }
                    ],
                    "paper_leads": [
                        {
                            "paper_id": "P_EXPAND",
                            "title": "Expand paper",
                            "variable_ids": ["claim_expand"],
                            "source_landscape_action": "explore.expand",
                            "is_new": True,
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    hydrated = research_providers._hydrate_analysis_provider_input(
        {
            "phase": "assess_analysis",
            "artifacts": [str(selected_evidence_path)],
        }
    )

    artifact_payloads = cast(list[dict[str, Any]], hydrated["artifact_payloads"])
    compact = cast(dict[str, Any], artifact_payloads[0]["json"])
    evidence_packet = cast(dict[str, Any], compact["evidence_packet"])
    items = cast(list[dict[str, Any]], evidence_packet["items"])
    paper_leads = cast(list[dict[str, Any]], evidence_packet["paper_leads"])
    assert items[0]["source_landscape_action"] == "explore.expand"
    assert items[0]["is_new"] is True
    assert paper_leads[0]["source_landscape_action"] == "explore.expand"
    assert paper_leads[0]["is_new"] is True

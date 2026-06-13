"""Tests for research analysis provider helpers."""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

from gaia_research import research_providers


def test_litellm_completion_uses_normalized_proxy_endpoint(
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
        "LITELLM_PROXY_API_BASE",
        "https://api.deepseek.com/chat/completions",
    )
    monkeypatch.setenv("LITELLM_PROXY_API_KEY", "proxy-key")
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
    assert captured["api_key"] == "proxy-key"

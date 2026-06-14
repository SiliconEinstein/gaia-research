"""Analysis provider helpers for the package-native research CLI."""

from __future__ import annotations

import asyncio
import json
import os
import re
import shlex
import subprocess
from importlib import import_module
from pathlib import Path
from time import perf_counter, sleep
from typing import Any, cast

import typer

from gaia_research import ResearchPackage
from gaia_research.prompt_assets import (
    load_research_output_shape,
    load_research_phase_prompt,
    load_research_system_prompt,
)
from gaia_research.research_runtime import (
    _emit_run_event,
    _read_json_object_path,
    _record_run_trace,
    _update_run_state,
)
from gaia_research.run import ResearchRunStart


def _load_research_env_files_or_exit(env_file: list[str] | None) -> None:
    refs = _research_env_file_refs(env_file)
    for ref in refs:
        path = Path(ref).expanduser()
        if not path.exists():
            typer.echo(f"Error: --env-file not found: {ref}", err=True)
            raise typer.Exit(2)
        if not path.is_file():
            typer.echo(f"Error: --env-file is not a file: {ref}", err=True)
            raise typer.Exit(2)
        try:
            assignments = _parse_research_env_file(path)
        except ValueError as exc:
            typer.echo(f"Error: invalid --env-file {ref}: {exc}", err=True)
            raise typer.Exit(2) from exc
        for key, value in assignments.items():
            os.environ.setdefault(key, value)


def _research_env_file_refs(env_file: list[str] | None) -> list[str]:
    refs = [ref for ref in (env_file or []) if ref.strip()]
    if refs:
        return refs
    configured = os.environ.get("GAIA_RESEARCH_ENV_FILE")
    if configured:
        return [ref for ref in configured.split(os.pathsep) if ref.strip()]
    return []


def _parse_research_env_file(path: Path) -> dict[str, str]:
    assignments: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        if "=" not in line:
            raise ValueError(f"line {line_number} must be KEY=VALUE")
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ValueError(f"line {line_number} has invalid key {key!r}")
        assignments[key] = _parse_env_value(value.strip())
    return assignments


def _parse_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    comment_index = value.find(" #")
    if comment_index != -1:
        value = value[:comment_index].rstrip()
    return value


def _run_analysis_provider_command(
    research_pkg: ResearchPackage,
    run: ResearchRunStart,
    *,
    phase: str,
    command: str,
    input_payload: dict[str, object],
    output_name: str,
    json_stream: bool,
) -> str:
    analysis_dir = run.run_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    input_path = analysis_dir / f"{output_name}.input.json"
    output_path = analysis_dir / f"{output_name}.output.json"
    input_path.write_text(
        json.dumps(input_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _emit_run_event(
        run,
        event_type="provider.started",
        phase=phase,
        json_stream=json_stream,
        payload={"provider": "command", "input": str(input_path), "output": str(output_path)},
    )
    args = shlex.split(command)
    if not args:
        typer.echo(f"Error: empty provider command for {phase}.", err=True)
        raise typer.Exit(2)
    env = {
        **os.environ,
        "GAIA_RESEARCH_PHASE": phase,
        "GAIA_RESEARCH_INPUT": str(input_path),
        "GAIA_RESEARCH_OUTPUT": str(output_path),
        "GAIA_RESEARCH_RUN_DIR": str(run.run_dir),
    }
    start = perf_counter()
    completed = subprocess.run(
        args,
        cwd=research_pkg.path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        error = (completed.stderr or completed.stdout or "").strip()
        _record_command_provider_failed_trace(
            research_pkg,
            run,
            start=start,
            phase=phase,
            input_path=input_path,
            output_path=output_path if output_path.exists() else None,
            completed=completed,
            error=error or f"provider command exited {completed.returncode}",
        )
        _update_run_state(
            run,
            {
                "status": "failed",
                "phase": phase,
                "error": error or f"provider command exited {completed.returncode}",
            },
        )
        _emit_run_event(
            run,
            event_type="run.failed",
            phase=phase,
            json_stream=json_stream,
            payload={"provider": "command", "returncode": completed.returncode, "error": error},
        )
        typer.echo(
            f"Error: provider command failed for {phase} with exit code "
            f"{completed.returncode}: {error}",
            err=True,
        )
        raise typer.Exit(2)
    if not output_path.exists():
        error = f"provider command for {phase} did not write {output_path}"
        _record_command_provider_failed_trace(
            research_pkg,
            run,
            start=start,
            phase=phase,
            input_path=input_path,
            output_path=None,
            completed=completed,
            error=error,
        )
        _update_run_state(run, {"status": "failed", "phase": phase, "error": error})
        _emit_run_event(
            run,
            event_type="run.failed",
            phase=phase,
            json_stream=json_stream,
            payload={"provider": "command", "returncode": completed.returncode, "error": error},
        )
        typer.echo(
            f"Error: {error}.",
            err=True,
        )
        raise typer.Exit(2)
    try:
        _read_json_object_path(output_path)
    except typer.Exit as exc:
        error = f"provider command for {phase} wrote invalid JSON: {output_path}"
        _record_command_provider_failed_trace(
            research_pkg,
            run,
            start=start,
            phase=phase,
            input_path=input_path,
            output_path=output_path,
            completed=completed,
            error=error,
        )
        _update_run_state(run, {"status": "failed", "phase": phase, "error": error})
        _emit_run_event(
            run,
            event_type="run.failed",
            phase=phase,
            json_stream=json_stream,
            payload={"provider": "command", "returncode": completed.returncode, "error": error},
        )
        raise typer.Exit(2) from exc
    _record_run_trace(
        research_pkg,
        run,
        start=start,
        name=f"provider.command.{phase}",
        kind="llm",
        mode="command",
        inputs=[str(input_path)],
        outputs=[str(output_path)],
        metrics={
            "provider": "command",
            "phase": phase,
            "returncode": completed.returncode,
            "stdout_chars": len(completed.stdout or ""),
            "stderr_chars": len(completed.stderr or ""),
        },
    )
    _emit_run_event(
        run,
        event_type="provider.completed",
        phase=phase,
        json_stream=json_stream,
        payload={"provider": "command", "input": str(input_path), "output": str(output_path)},
    )
    return str(output_path)


def _record_command_provider_failed_trace(
    research_pkg: ResearchPackage,
    run: ResearchRunStart,
    *,
    start: float,
    phase: str,
    input_path: Path,
    output_path: Path | None,
    completed: subprocess.CompletedProcess[str],
    error: str,
) -> None:
    _record_run_trace(
        research_pkg,
        run,
        start=start,
        name=f"provider.command.{phase}",
        kind="llm",
        mode="command",
        inputs=[str(input_path)],
        outputs=[str(output_path)] if output_path is not None else [],
        metrics={
            "provider": "command",
            "phase": phase,
            "returncode": completed.returncode,
            "stdout_chars": len(completed.stdout or ""),
            "stderr_chars": len(completed.stderr or ""),
            "error": error,
        },
        status="failed",
    )


def _run_analysis_provider_litellm(
    research_pkg: ResearchPackage,
    run: ResearchRunStart,
    *,
    phase: str,
    model: str,
    input_payload: dict[str, object],
    output_name: str,
    temperature: float,
    timeout: float,
    max_retries: int,
    max_tokens: int | None,
    json_stream: bool,
) -> str:
    rate_limit_retry_count = 2
    rate_limit_retry_delay_seconds = 75.0
    analysis_dir = run.run_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    input_path = analysis_dir / f"{output_name}.input.json"
    output_path = analysis_dir / f"{output_name}.output.json"
    raw_path = analysis_dir / f"{output_name}.raw.txt"
    hydrated_payload = _hydrate_analysis_provider_input(input_payload)
    input_path.write_text(
        json.dumps(hydrated_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _emit_run_event(
        run,
        event_type="provider.started",
        phase=phase,
        json_stream=json_stream,
        payload={
            "provider": "litellm",
            "model": model,
            "input": str(input_path),
            "output": str(output_path),
        },
    )
    start = perf_counter()
    response: object | None = None
    retry_count = 0
    retry_wait_seconds = 0.0
    try:
        while True:
            try:
                response = asyncio.run(
                    _litellm_completion(
                        model=model,
                        phase=phase,
                        input_payload=hydrated_payload,
                        temperature=temperature,
                        timeout=timeout,
                        max_retries=max_retries,
                        max_tokens=max_tokens,
                    )
                )
                break
            except Exception as exc:
                if not _is_litellm_rate_limit_error(exc) or retry_count >= rate_limit_retry_count:
                    raise
                retry_count += 1
                retry_wait_seconds += rate_limit_retry_delay_seconds
                _emit_run_event(
                    run,
                    event_type="provider.retrying",
                    phase=phase,
                    json_stream=json_stream,
                    payload={
                        "provider": "litellm",
                        "model": model,
                        "reason": "rate_limit",
                        "attempt": retry_count,
                        "max_attempts": rate_limit_retry_count + 1,
                        "wait_seconds": rate_limit_retry_delay_seconds,
                        "error": str(exc),
                    },
                )
                sleep(rate_limit_retry_delay_seconds)
        content = _litellm_response_content(response)
        raw_path.write_text(content, encoding="utf-8")
        output_payload = _json_object_from_llm_content(content)
    except Exception as exc:
        usage = _litellm_usage_dict(response)
        prompt_tokens = _int_metric(usage.get("prompt_tokens"))
        completion_tokens = _int_metric(usage.get("completion_tokens"))
        _record_run_trace(
            research_pkg,
            run,
            start=start,
            name=f"provider.litellm.{phase}",
            kind="llm",
            mode="litellm",
            inputs=[str(input_path)],
            outputs=[str(raw_path)] if raw_path.exists() else [],
            metrics={
                "provider": "litellm",
                "phase": phase,
                "model": model,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "raw_path": str(raw_path) if raw_path.exists() else None,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": _int_metric(usage.get("total_tokens")),
                "request_id": _litellm_request_id(response),
                "retry_count": retry_count,
                "retry_wait_seconds": retry_wait_seconds,
            },
            model=model,
            token_usage={
                "input_tokens": prompt_tokens,
                "output_tokens": completion_tokens,
            },
            status="failed",
        )
        _update_run_state(run, {"status": "failed", "phase": phase, "error": str(exc)})
        _emit_run_event(
            run,
            event_type="run.failed",
            phase=phase,
            json_stream=json_stream,
            payload={"provider": "litellm", "model": model, "error": str(exc)},
        )
        typer.echo(f"Error: LiteLLM provider failed for {phase}: {exc}", err=True)
        raise typer.Exit(2) from exc
    output_path.write_text(
        json.dumps(output_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    usage = _litellm_usage_dict(response)
    prompt_tokens = _int_metric(usage.get("prompt_tokens"))
    completion_tokens = _int_metric(usage.get("completion_tokens"))
    _record_run_trace(
        research_pkg,
        run,
        start=start,
        name=f"provider.litellm.{phase}",
        kind="llm",
        mode="litellm",
        inputs=[str(input_path)],
        outputs=[str(output_path)],
        metrics={
            "provider": "litellm",
            "phase": phase,
            "model": model,
            "raw_path": str(raw_path),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": _int_metric(usage.get("total_tokens")),
            "request_id": _litellm_request_id(response),
            "retry_count": retry_count,
            "retry_wait_seconds": retry_wait_seconds,
        },
        model=model,
        token_usage={
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
        },
    )
    _emit_run_event(
        run,
        event_type="provider.completed",
        phase=phase,
        json_stream=json_stream,
        payload={
            "provider": "litellm",
            "model": model,
            "input": str(input_path),
            "output": str(output_path),
        },
    )
    return str(output_path)


def _is_litellm_rate_limit_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "ratelimit" in text or "rate limit" in text or "tpm" in text


async def _litellm_completion(
    *,
    model: str,
    phase: str,
    input_payload: dict[str, object],
    temperature: float,
    timeout: float,
    max_retries: int,
    max_tokens: int | None,
) -> object:
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

    litellm_runtime = cast(Any, import_module("litellm"))
    litellm_runtime.suppress_debug_info = True
    litellm_runtime.disable_cost_calc = True
    litellm_runtime.set_verbose = False
    litellm_runtime.callbacks = []
    litellm_runtime.success_callback = []
    litellm_runtime.failure_callback = []
    litellm_runtime._async_success_callback = []
    litellm_runtime._async_failure_callback = []
    litellm_runtime.input_callback = []
    litellm_runtime.service_callback = []
    litellm_runtime.post_call_rules = []
    kwargs: dict[str, object] = {
        "model": model,
        "messages": _litellm_messages(phase=phase, input_payload=input_payload),
        "temperature": temperature,
        "timeout": timeout,
        "max_retries": max_retries,
        "response_format": {"type": "json_object"},
    }
    kwargs.update(_litellm_env_kwargs())
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    return await litellm_runtime.acompletion(**kwargs)


def _litellm_env_kwargs() -> dict[str, object]:
    kwargs: dict[str, object] = {}
    api_base = os.environ.get("GAIA_RESEARCH_LLM_API_BASE")
    api_key = os.environ.get("GAIA_RESEARCH_LLM_API_KEY")
    if api_base and api_base.strip():
        kwargs["api_base"] = _normalize_litellm_api_base(api_base)
    if api_key and api_key.strip():
        kwargs["api_key"] = api_key.strip()
    return kwargs


def _normalize_litellm_api_base(api_base: str) -> str:
    normalized = api_base.strip().rstrip("/")
    suffix = "/chat/completions"
    if normalized.endswith(suffix):
        return normalized[: -len(suffix)].rstrip("/")
    return normalized


def _litellm_messages(
    *,
    phase: str,
    input_payload: dict[str, object],
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": load_research_system_prompt(),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "phase": phase,
                    "instruction": load_research_phase_prompt(phase),
                    "output_shape": load_research_output_shape(phase),
                    "validation_rules": [
                        "Return a single JSON object, not an array or string.",
                        "Do not add explanatory text before or after the JSON.",
                        "Do not add decorative or prose-only keys outside the requested shape.",
                        "Every source_refs entry must use ids present in artifact_payloads.",
                        "If evidence is weak, encode uncertainty inside JSON fields.",
                        "Prefer fewer high-quality grounded items over broad ungrounded output.",
                        (
                            "Keep strings compact; avoid LaTeX commands when Unicode "
                            "text is available."
                        ),
                    ],
                    "input": input_payload,
                },
                indent=2,
                ensure_ascii=False,
            ),
        },
    ]


def _hydrate_analysis_provider_input(payload: dict[str, object]) -> dict[str, object]:
    hydrated = dict(payload)
    artifact_payloads: list[dict[str, object]] = []
    phase = payload.get("phase")
    phase_name = phase if isinstance(phase, str) else ""
    artifacts = payload.get("artifacts")
    if isinstance(artifacts, list):
        for artifact in artifacts:
            if not isinstance(artifact, str):
                continue
            path = Path(artifact)
            if path.exists():
                artifact_json = _read_json_object_path(path)
                artifact_payloads.append(
                    {
                        "path": artifact,
                        "json": _compact_artifact_json(phase_name, artifact_json),
                    }
                )
    hydrated["artifact_payloads"] = artifact_payloads
    return hydrated


def _compact_artifact_json(
    phase: str,
    payload: dict[str, object],
) -> dict[str, object]:
    kind = payload.get("kind")
    if kind == "research_landscape":
        return _compact_research_landscape(payload)
    if kind == "selected_evidence":
        return _compact_selected_evidence(payload)
    if phase.startswith("report_") and kind == "assessment":
        return _compact_assessment(payload)
    return payload


def _compact_research_landscape(payload: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": payload.get("schema_version"),
        "kind": payload.get("kind"),
        "action": payload.get("action"),
        "target": payload.get("target"),
        "created_at": payload.get("created_at"),
        "stats": payload.get("stats"),
        "query_provenance": payload.get("query_provenance"),
        "coverage_map": _compact_coverage_map(payload.get("coverage_map")),
        "candidate_coverage_gaps": payload.get("candidate_coverage_gaps"),
        "candidate_focuses": payload.get("candidate_focuses"),
        "paper_leads": [
            _compact_paper_lead(item) for item in _list_of_dicts(payload.get("paper_leads"))[:20]
        ],
        "items": [
            _compact_landscape_item(item) for item in _list_of_dicts(payload.get("items"))[:25]
        ],
        "notes": payload.get("notes"),
    }


def _compact_selected_evidence(payload: dict[str, object]) -> dict[str, object]:
    evidence_packet = payload.get("evidence_packet")
    packet = evidence_packet if isinstance(evidence_packet, dict) else {}
    materialization_plan = payload.get("materialization_plan")
    materialization_result = payload.get("materialization_result")
    return {
        "schema_version": payload.get("schema_version"),
        "kind": payload.get("kind"),
        "created_at": payload.get("created_at"),
        "focus": payload.get("focus"),
        "selection": payload.get("selection"),
        "materialization_plan": materialization_plan,
        "materialization_summary": _materialization_summary(materialization_result),
        "evidence_packet": {
            "landscapes": packet.get("landscapes"),
            "items": [
                _compact_landscape_item(item) for item in _list_of_dicts(packet.get("items"))[:24]
            ],
            "paper_leads": [
                _compact_paper_lead(item) for item in _list_of_dicts(packet.get("paper_leads"))[:18]
            ],
        },
    }


def _compact_assessment(payload: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": payload.get("schema_version"),
        "kind": payload.get("kind"),
        "created_at": payload.get("created_at"),
        "focus": payload.get("focus"),
        "overall": payload.get("overall"),
        "findings": payload.get("findings"),
        "relations": payload.get("relations"),
        "candidate_relations": payload.get("candidate_relations"),
        "obligations": payload.get("obligations"),
        "limitations": payload.get("limitations"),
        "next_actions": payload.get("next_actions"),
    }


def _compact_coverage_map(value: object) -> object:
    if not isinstance(value, dict):
        return value
    return {
        "query_families": value.get("query_families"),
        "under_covered_regions": value.get("under_covered_regions"),
        "candidate_focus_ids": value.get("candidate_focus_ids"),
        "paper_overlap": value.get("paper_overlap"),
    }


def _compact_paper_lead(item: dict[str, object]) -> dict[str, object]:
    return {
        "paper_id": item.get("paper_id"),
        "title": item.get("title"),
        "doi": item.get("doi"),
        "index_id": item.get("index_id"),
        "queries": item.get("queries"),
        "variable_ids": _list_of_strings(item.get("variable_ids"))[:8],
        "result_count": item.get("result_count"),
    }


def _compact_landscape_item(item: dict[str, object]) -> dict[str, object]:
    source = item.get("source")
    source_payload = source if isinstance(source, dict) else {}
    package_ref = item.get("package_ref")
    return {
        "item_id": item.get("item_id"),
        "id": item.get("id"),
        "kind": item.get("kind"),
        "variable_type": item.get("variable_type"),
        "title": _truncate_text(item.get("title"), 240),
        "content": _truncate_text(item.get("content"), 450),
        "source": {
            "paper_id": source_payload.get("paper_id"),
            "paper_title": source_payload.get("paper_title"),
            "doi": source_payload.get("doi"),
            "index_id": source_payload.get("index_id"),
            "provider_id": source_payload.get("provider_id"),
        },
        "package_ref": package_ref,
        "provenance": item.get("provenance"),
    }


def _materialization_summary(value: object) -> object:
    if not isinstance(value, dict):
        return value
    return {
        "lkm_materialize_requests": value.get("lkm_materialize_requests"),
        "lkm_packages_materialized": [
            _compact_materialized_package(item)
            for item in _list_of_dicts(value.get("lkm_packages_materialized"))
        ],
        "lkm_chains_materialized": [
            _compact_materialized_package(item)
            for item in _list_of_dicts(value.get("lkm_chains_materialized"))
        ],
    }


def _compact_materialized_package(item: dict[str, object]) -> dict[str, object]:
    return {
        "requested_source_ref": item.get("requested_source_ref"),
        "source_ref": item.get("source_ref"),
        "package": item.get("package"),
        "import_name": item.get("import_name"),
        "claim_count": item.get("claim_count"),
        "question_count": item.get("question_count"),
        "chain_count": item.get("chain_count"),
    }


def _list_of_dicts(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _list_of_strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _truncate_text(value: object, limit: int) -> object:
    if not isinstance(value, str) or len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def _json_object_from_llm_content(content: str) -> dict[str, object]:
    text = content.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        repaired_text = _escape_invalid_json_backslashes(text)
        try:
            payload = json.loads(repaired_text)
        except json.JSONDecodeError:
            raise ValueError(f"LiteLLM response was not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("LiteLLM response must be a JSON object.")
    return payload


def _escape_invalid_json_backslashes(text: str) -> str:
    """Preserve LaTeX-style backslashes inside otherwise valid JSON strings."""
    return re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", text)


def _litellm_response_content(response: object) -> str:
    if isinstance(response, dict):
        choices = response.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict):
                    content = message.get("content")
                    return "" if content is None else str(content)
    choices = getattr(response, "choices", None)
    if choices:
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None)
        return "" if content is None else str(content)
    return ""


def _litellm_usage_dict(response: object) -> dict[str, object]:
    usage = (
        response.get("usage") if isinstance(response, dict) else getattr(response, "usage", None)
    )
    if usage is None:
        return {}
    if isinstance(usage, dict):
        return dict(usage)
    if hasattr(usage, "model_dump"):
        dumped = usage.model_dump()
        return dumped if isinstance(dumped, dict) else {}
    try:
        return dict(usage)
    except Exception:
        return {}


def _litellm_request_id(response: object) -> str | None:
    if isinstance(response, dict):
        value = response.get("id") or response.get("request_id")
        return str(value) if value else None
    for attr in ("id", "request_id"):
        value = getattr(response, attr, None)
        if value:
            return str(value)
    return None


def _int_metric(value: object) -> int:
    return int(value) if isinstance(value, int | float) else 0


def _resolve_litellm_model(model: str | None) -> str:
    resolved = model or os.environ.get("GAIA_RESEARCH_LLM_MODEL")
    if resolved and resolved.strip():
        return resolved.strip()
    typer.echo(
        "Error: --analysis-provider litellm requires --model or GAIA_RESEARCH_LLM_MODEL.",
        err=True,
    )
    raise typer.Exit(2)

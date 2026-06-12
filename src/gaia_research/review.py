"""Review-run SDK and disk contract for package-local research runs."""

from __future__ import annotations

import json
import re
import tempfile
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RUN_SCHEMA_VERSION = 1
RESEARCH_NAMESPACE = ".gaia/research"


class ReviewRunError(ValueError):
    """Raised when a review-run target or run id is invalid."""


@dataclass(frozen=True)
class ReviewRunHandle:
    """Observable handles returned to product, CLI, and skill callers."""

    run_id: str
    run_dir: Path
    state_path: Path
    events_path: Path
    report_path: Path
    checkpoint_path: Path


@dataclass(frozen=True)
class ReviewRunSnapshot:
    """Loaded review-run state and event log."""

    handle: ReviewRunHandle
    state: dict[str, Any]
    events: list[dict[str, Any]]
    report_path: Path


def _utcnow() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _utcstamp() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return normalized[:40] or "research"


def _validate_run_id(value: str) -> str:
    if value != _slug(value):
        raise ReviewRunError(
            "run_id must contain only lowercase ASCII letters, digits, and hyphens, "
            "and must not start or end with a hyphen"
        )
    return value


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as f:
            tmp_path = Path(f.name)
            f.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        tmp_path.replace(path)
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink()


def _load_gaia_package(pkg_path: str | Path) -> dict[str, str]:
    path = Path(pkg_path).resolve()
    pyproject = path / "pyproject.toml"
    if not pyproject.exists():
        raise ReviewRunError(f"not a Gaia package: {path}")
    with pyproject.open("rb") as f:
        config = tomllib.load(f)
    gaia = config.get("tool", {}).get("gaia", {})
    if gaia.get("type") != "knowledge-package":
        raise ReviewRunError(f"not a Gaia knowledge package: {path}")
    project = config.get("project", {})
    project_name = project.get("name")
    if not isinstance(project_name, str) or not project_name:
        raise ReviewRunError(f"Gaia package is missing [project].name: {path}")
    import_name = project_name.removesuffix("-gaia").replace("-", "_")
    namespace = gaia.get("namespace")
    if not isinstance(namespace, str) or not namespace:
        namespace = import_name
    return {
        "path": str(path),
        "project_name": project_name,
        "import_name": import_name,
        "namespace": namespace,
    }


def _handle(pkg_path: str | Path, run_id: str) -> ReviewRunHandle:
    pkg = Path(pkg_path).resolve()
    run_dir = pkg / RESEARCH_NAMESPACE / "runs" / run_id
    return ReviewRunHandle(
        run_id=run_id,
        run_dir=run_dir,
        state_path=run_dir / "state.json",
        events_path=run_dir / "events.ndjson",
        report_path=run_dir / "final_report.md",
        checkpoint_path=run_dir / "checkpoints" / "query_plan.request.json",
    )


def _append_event(
    handle: ReviewRunHandle,
    event_type: str,
    *,
    phase: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "schema_version": RUN_SCHEMA_VERSION,
        "type": event_type,
        "run_id": handle.run_id,
        "phase": phase,
        "ts": _utcnow(),
    }
    if payload:
        event.update(payload)
    handle.events_path.parent.mkdir(parents=True, exist_ok=True)
    with handle.events_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def record_review_run_event(
    handle: ReviewRunHandle,
    event_type: str,
    *,
    phase: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append an observable event to a review run."""
    return _append_event(handle, event_type, phase=phase, payload=payload)


def _read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def start_review_run(
    pkg_path: str | Path,
    *,
    topic: str,
    profile: str,
    run_id: str | None = None,
    language: str = "zh",
) -> ReviewRunHandle:
    """Create an observable review-run envelope under ``.gaia/research``."""
    package = _load_gaia_package(pkg_path)
    resolved_run_id = (
        _validate_run_id(run_id) if run_id is not None else f"{_slug(topic)}-{_utcstamp()}"
    )
    handle = _handle(package["path"], resolved_run_id)
    handle.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

    state = {
        "schema_version": RUN_SCHEMA_VERSION,
        "run_id": resolved_run_id,
        "status": "waiting_for_input",
        "phase": "query_plan",
        "mode": "review-run",
        "profile": profile,
        "language": language,
        "topic": topic,
        "package": package,
        "run_dir": str(handle.run_dir),
        "pending_checkpoint": str(handle.checkpoint_path),
        "artifacts": {"final_report": str(handle.report_path)},
    }
    _write_json_atomic(handle.state_path, state)
    _write_json_atomic(
        handle.checkpoint_path,
        {
            "schema_version": RUN_SCHEMA_VERSION,
            "type": "checkpoint.query_plan",
            "phase": "query_plan",
            "default_action": {"action": "continue", "queries": []},
        },
    )
    _append_event(
        handle,
        "run.created",
        phase="setup",
        payload={"topic": topic, "profile": profile, "language": language},
    )
    _append_event(
        handle,
        "checkpoint.created",
        phase="query_plan",
        payload={"path": str(handle.checkpoint_path)},
    )
    _append_event(
        handle,
        "run.waiting_for_input",
        phase="query_plan",
        payload={"pending_checkpoint": str(handle.checkpoint_path)},
    )
    return handle


def read_review_run(pkg_path: str | Path, run_id: str) -> ReviewRunSnapshot:
    """Load state and events for one review run."""
    handle = _handle(pkg_path, _validate_run_id(run_id))
    state = json.loads(handle.state_path.read_text(encoding="utf-8"))
    return ReviewRunSnapshot(
        handle=handle,
        state=state,
        events=_read_events(handle.events_path),
        report_path=handle.report_path,
    )


def complete_review_run(
    handle: ReviewRunHandle,
    markdown: str,
    *,
    state_updates: dict[str, Any] | None = None,
) -> ReviewRunSnapshot:
    """Write the final report and mark the run completed."""
    state = json.loads(handle.state_path.read_text(encoding="utf-8"))
    handle.report_path.parent.mkdir(parents=True, exist_ok=True)
    handle.report_path.write_text(markdown, encoding="utf-8")
    state.update(
        {
            "status": "completed",
            "phase": "report",
            "completed_at": _utcnow(),
        }
    )
    if state_updates:
        state.update(state_updates)
    state.setdefault("artifacts", {})["final_report"] = str(handle.report_path)
    _write_json_atomic(handle.state_path, state)
    _append_event(
        handle,
        "run.completed",
        phase="report",
        payload={"final_report": str(handle.report_path)},
    )
    return ReviewRunSnapshot(
        handle=handle,
        state=state,
        events=_read_events(handle.events_path),
        report_path=handle.report_path,
    )


def fail_review_run(
    handle: ReviewRunHandle,
    error: str,
    *,
    phase: str = "core_review",
) -> ReviewRunSnapshot:
    """Mark a review run failed while preserving its observable event log."""
    state = json.loads(handle.state_path.read_text(encoding="utf-8"))
    state.update(
        {
            "status": "failed",
            "phase": phase,
            "failed_at": _utcnow(),
            "error": error,
        }
    )
    _write_json_atomic(handle.state_path, state)
    _append_event(handle, f"{phase}.failed", phase=phase, payload={"error": error})
    return ReviewRunSnapshot(
        handle=handle,
        state=state,
        events=_read_events(handle.events_path),
        report_path=handle.report_path,
    )

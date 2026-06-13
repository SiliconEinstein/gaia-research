"""Report workflow run state and event contract."""

from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RUN_SCHEMA_VERSION = 1
RESEARCH_NAMESPACE = ".gaia/research"


@dataclass(frozen=True)
class ReportRunHandle:
    """Filesystem handles for one report workflow run."""

    workspace: Path
    run_id: str
    run_dir: Path
    state_path: Path
    events_path: Path
    landscape_dir: Path
    field_map_dir: Path
    focuses_dir: Path
    assessments_dir: Path
    materialization_dir: Path
    reports_dir: Path


@dataclass(frozen=True)
class ReportRunState:
    """Serializable report workflow state."""

    run_id: str
    topic: str
    profile: str
    status: str
    phase: str
    created_at: str
    updated_at: str
    artifacts: dict[str, str]


def _utcnow() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _utcstamp() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return normalized[:40] or "research"


def _validate_run_id(value: str) -> str:
    if value != _slug(value):
        raise ValueError(
            "run_id must contain only lowercase ASCII letters, digits, and hyphens, "
            "and must not start or end with a hyphen"
        )
    return value


def _handle(workspace: str | Path, run_id: str) -> ReportRunHandle:
    resolved_workspace = Path(workspace).resolve()
    run_dir = resolved_workspace / RESEARCH_NAMESPACE / "runs" / run_id
    return ReportRunHandle(
        workspace=resolved_workspace,
        run_id=run_id,
        run_dir=run_dir,
        state_path=run_dir / "state.json",
        events_path=run_dir / "events.ndjson",
        landscape_dir=run_dir / "landscape",
        field_map_dir=run_dir / "field_map",
        focuses_dir=run_dir / "focuses",
        assessments_dir=run_dir / "assessments",
        materialization_dir=run_dir / "materialization",
        reports_dir=run_dir / "reports",
    )


def _state_payload(state: ReportRunState) -> dict[str, Any]:
    return {
        "schema_version": RUN_SCHEMA_VERSION,
        "run_id": state.run_id,
        "topic": state.topic,
        "profile": state.profile,
        "status": state.status,
        "phase": state.phase,
        "created_at": state.created_at,
        "updated_at": state.updated_at,
        "artifacts": dict(state.artifacts),
    }


def _state_from_payload(payload: dict[str, Any]) -> ReportRunState:
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, dict):
        artifacts = {}
    return ReportRunState(
        run_id=str(payload["run_id"]),
        topic=str(payload["topic"]),
        profile=str(payload["profile"]),
        status=str(payload["status"]),
        phase=str(payload["phase"]),
        created_at=str(payload["created_at"]),
        updated_at=str(payload["updated_at"]),
        artifacts={str(key): str(value) for key, value in artifacts.items()},
    )


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


def write_state(handle: ReportRunHandle, state: ReportRunState) -> None:
    """Persist report workflow state atomically."""
    _write_json_atomic(handle.state_path, _state_payload(state))


def read_state(handle: ReportRunHandle) -> ReportRunState:
    """Read report workflow state from disk."""
    payload = json.loads(handle.state_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"state file must contain a JSON object: {handle.state_path}")
    return _state_from_payload(payload)


def record_event(
    handle: ReportRunHandle,
    event_type: str,
    *,
    phase: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append an observable JSON event to the run event log."""
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


def _ensure_run_dirs(handle: ReportRunHandle) -> None:
    for directory in (
        handle.landscape_dir,
        handle.field_map_dir,
        handle.focuses_dir,
        handle.assessments_dir,
        handle.materialization_dir,
        handle.reports_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def _artifact_dirs(handle: ReportRunHandle) -> dict[str, str]:
    return {
        "landscape": str(handle.landscape_dir),
        "field_map": str(handle.field_map_dir),
        "focuses": str(handle.focuses_dir),
        "assessments": str(handle.assessments_dir),
        "materialization": str(handle.materialization_dir),
        "reports": str(handle.reports_dir),
    }


def create_report_run(
    workspace: str | Path,
    *,
    topic: str,
    profile: str,
    run_id: str | None = None,
) -> tuple[ReportRunHandle, ReportRunState]:
    """Create the filesystem envelope for a report workflow run."""
    resolved_run_id = (
        _validate_run_id(run_id) if run_id is not None else f"{_slug(topic)}-{_utcstamp()}"
    )
    handle = _handle(workspace, resolved_run_id)
    _ensure_run_dirs(handle)
    now = _utcnow()
    state = ReportRunState(
        run_id=resolved_run_id,
        topic=topic,
        profile=profile,
        status="running",
        phase="setup",
        created_at=now,
        updated_at=now,
        artifacts=_artifact_dirs(handle),
    )
    write_state(handle, state)
    record_event(
        handle,
        "run.created",
        phase="setup",
        payload={"topic": topic, "profile": profile},
    )
    return handle, state


def resume_report_run(
    workspace: str | Path,
    run_id: str,
) -> tuple[ReportRunHandle, ReportRunState]:
    """Load an existing report workflow run."""
    handle = _handle(workspace, _validate_run_id(run_id))
    if not handle.state_path.exists():
        raise FileNotFoundError(handle.state_path)
    return handle, read_state(handle)


__all__ = [
    "ReportRunHandle",
    "ReportRunState",
    "create_report_run",
    "read_state",
    "record_event",
    "resume_report_run",
    "write_state",
]

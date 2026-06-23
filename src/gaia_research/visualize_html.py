"""Static HTML visualization surface for Gaia Research run artifacts."""

from __future__ import annotations

import json
import tomllib
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote

VISUALIZE_HTML_SCHEMA_VERSION = 1


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_ndjson(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _package_metadata(pkg_path: Path) -> dict[str, Any]:
    pyproject_path = pkg_path / "pyproject.toml"
    payload: dict[str, Any] = {}
    if pyproject_path.exists():
        payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = _as_dict(payload.get("project"))
    tool = _as_dict(payload.get("tool"))
    gaia = _as_dict(tool.get("gaia"))
    uv = _as_dict(tool.get("uv"))
    uv_sources = _as_dict(uv.get("sources"))
    return {
        "path": str(pkg_path),
        "pyproject": str(pyproject_path) if pyproject_path.exists() else None,
        "project_name": project.get("name") or pkg_path.name,
        "namespace": gaia.get("namespace"),
        "package_type": gaia.get("type"),
        "dependencies": [
            item for item in _as_list(project.get("dependencies")) if isinstance(item, str)
        ],
        "uv_sources": {
            str(key): value for key, value in uv_sources.items() if isinstance(key, str)
        },
    }


def _iter_paths(value: object) -> list[Path]:
    paths: list[Path] = []
    if isinstance(value, str) and value:
        paths.append(Path(value))
    elif isinstance(value, list):
        for item in value:
            paths.extend(_iter_paths(item))
    elif isinstance(value, dict):
        for item in value.values():
            paths.extend(_iter_paths(item))
    return paths


def _file_link(path: Path) -> str:
    return f"file://{quote(str(path.resolve()))}"


def _append_file(
    files: list[dict[str, Any]],
    seen: set[Path],
    *,
    kind: str,
    path: Path,
    run_dir: Path,
) -> None:
    if not path.exists() or not path.is_file():
        return
    resolved = path.resolve()
    if resolved in seen:
        return
    seen.add(resolved)
    try:
        relative = str(path.relative_to(run_dir))
    except ValueError:
        relative = path.name
    files.append(
        {
            "kind": kind,
            "name": path.name,
            "path": str(path),
            "relative_path": relative,
            "href": _file_link(path),
            "size_bytes": path.stat().st_size,
        }
    )


def _artifact_file_index(run_dir: Path, artifact_paths: dict[str, object]) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for kind, value in sorted(artifact_paths.items()):
        for root in _iter_paths(value):
            if not root.exists():
                continue
            if root.is_file():
                _append_file(files, seen, kind=kind, path=root, run_dir=run_dir)
                continue
            for path in sorted(root.rglob("*")):
                _append_file(files, seen, kind=kind, path=path, run_dir=run_dir)
    if run_dir.exists():
        for path in sorted(run_dir.rglob("*")):
            if path.name in {"state.json", "events.ndjson"}:
                continue
            if not path.is_file():
                continue
            rel = path.relative_to(run_dir)
            kind = rel.parts[0] if len(rel.parts) > 1 else "run"
            _append_file(files, seen, kind=kind, path=path, run_dir=run_dir)
    return files


def _graph_asset_summary(graph_assets: dict[str, Any]) -> dict[str, Any]:
    anchors = [item for item in _as_list(graph_assets.get("anchors")) if isinstance(item, dict)]
    claims = [item for item in _as_list(graph_assets.get("claims")) if isinstance(item, dict)]
    relations = [
        item for item in _as_list(graph_assets.get("candidate_relations")) if isinstance(item, dict)
    ]
    evidence_matrix = [
        item for item in _as_list(graph_assets.get("evidence_matrix")) if isinstance(item, dict)
    ]
    open_obligations = [
        item for item in _as_list(graph_assets.get("open_obligations")) if isinstance(item, dict)
    ]
    deferred_obligations = [
        item
        for item in _as_list(graph_assets.get("deferred_obligations"))
        if isinstance(item, dict)
    ]
    return {
        "path": graph_assets.get("_path"),
        "success_evaluation": _as_dict(graph_assets.get("success_evaluation")),
        "corpus": _as_dict(graph_assets.get("corpus")),
        "counts": {
            "anchors": len(anchors),
            "claims": len(claims),
            "candidate_relations": len(relations),
            "evidence_matrix_rows": len(evidence_matrix),
            "open_obligations": len(open_obligations),
            "deferred_obligations": len(deferred_obligations),
        },
        "anchors": anchors[:50],
        "claims": claims[:50],
        "candidate_relations": relations[:50],
        "evidence_matrix": evidence_matrix[:50],
        "open_obligations": open_obligations[:50],
        "deferred_obligations": deferred_obligations[:50],
    }


def _selected_evidence_summary(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for file_item in files:
        path = Path(str(file_item.get("path") or ""))
        if file_item.get("kind") not in {"selected_evidence", "selected_evidence_by_focus"}:
            continue
        payload = _read_json(path)
        if payload.get("kind") != "selected_evidence":
            continue
        packet = _as_dict(payload.get("evidence_packet"))
        summaries.append(
            {
                "path": str(path),
                "focus_id": _as_dict(payload.get("focus")).get("id")
                or _as_dict(payload.get("selection")).get("focus_id"),
                "items": len(_as_list(packet.get("items"))),
                "anchors": len(_as_list(payload.get("anchors"))),
                "omitted_relevant_evidence": len(
                    _as_list(payload.get("omitted_relevant_evidence"))
                ),
                "materialization_manifest": payload.get("materialization_manifest"),
                "materialization_summary": _as_dict(payload.get("materialization_summary")),
            }
        )
    return summaries


def _trace_summary(run_dir: Path, events_path: Path) -> dict[str, Any]:
    trace_dir = run_dir / "trace"
    benchmark = _read_json(trace_dir / "benchmark.json")
    obligations = _read_json(trace_dir / "obligations.json")
    return {
        "events_path": str(events_path),
        "events": _read_ndjson(events_path),
        "trace_dir": str(trace_dir),
        "trace_records": _read_ndjson(trace_dir / "trace.jsonl"),
        "benchmark": benchmark,
        "obligations": obligations,
    }


def build_visualization_payload(pkg_path: str | Path, run_id: str) -> dict[str, Any]:
    """Build a compact, renderer-friendly payload for a research run visualization."""
    pkg = Path(pkg_path).resolve()
    run_dir = pkg / ".gaia" / "research" / "runs" / run_id
    state_path = run_dir / "state.json"
    events_path = run_dir / "events.ndjson"
    state = _read_json(state_path)
    if not state:
        raise FileNotFoundError(state_path)
    artifacts = _as_dict(state.get("artifacts"))
    files = _artifact_file_index(run_dir, artifacts)
    graph_assets_path = artifacts.get("graph_assets")
    graph_assets: dict[str, Any] = {}
    if isinstance(graph_assets_path, str):
        graph_assets = _read_json(Path(graph_assets_path))
        if graph_assets:
            graph_assets["_path"] = graph_assets_path
    trace = _trace_summary(run_dir, events_path)
    return {
        "schema_version": VISUALIZE_HTML_SCHEMA_VERSION,
        "kind": "gaia_research_package_visualization",
        "package": _package_metadata(pkg),
        "run": {
            "run_id": state.get("run_id", run_id),
            "topic": state.get("topic"),
            "profile": state.get("profile"),
            "mode": state.get("mode"),
            "status": state.get("status"),
            "phase": state.get("phase"),
            "created_at": state.get("created_at"),
            "updated_at": state.get("updated_at"),
            "run_dir": str(run_dir),
            "state_path": str(state_path),
        },
        "persistent_content": {
            "artifact_dirs": artifacts,
            "files": files,
            "graph_assets": _graph_asset_summary(graph_assets),
            "selected_evidence": _selected_evidence_summary(files),
        },
        "execution_trace": trace,
    }


def _json_block(value: object) -> str:
    return escape(json.dumps(value, ensure_ascii=False, indent=2))


def _text(value: object) -> str:
    return escape("" if value is None else str(value))


def _metric(label: str, value: object) -> str:
    return f'<div class="metric"><span>{escape(label)}</span><strong>{_text(value)}</strong></div>'


def _file_table(files: list[dict[str, Any]]) -> str:
    rows = []
    for item in files[:300]:
        rows.append(
            "<tr>"
            f"<td>{_text(item.get('kind'))}</td>"
            f"<td><a href=\"{_text(item.get('href'))}\">{_text(item.get('relative_path'))}</a></td>"
            f"<td class=\"num\">{_text(item.get('size_bytes'))}</td>"
            "</tr>"
        )
    return (
        '<table><thead><tr><th>Kind</th><th>Path</th><th class="num">Bytes</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _object_list(title: str, items: list[dict[str, Any]], *, key_hint: str) -> str:
    if not items:
        return f"<section><h3>{escape(title)}</h3><p class=\"empty\">None recorded.</p></section>"
    cards = []
    for item in items[:25]:
        heading = item.get(key_hint) or item.get("id") or item.get("ref") or item.get("target_qid")
        cards.append(
            '<article class="record">'
            f"<h4>{_text(heading or title)}</h4>"
            f"<pre>{_json_block(item)}</pre>"
            "</article>"
        )
    return (
        f"<section><h3>{escape(title)}</h3>"
        f'<div class="records">{"".join(cards)}</div></section>'
    )


def _trace_table(records: list[dict[str, Any]]) -> str:
    rows = []
    for item in records[:300]:
        rows.append(
            "<tr>"
            f"<td>{_text(item.get('step') or item.get('type'))}</td>"
            f"<td>{_text(item.get('phase') or item.get('kind'))}</td>"
            f"<td>{_text(item.get('status'))}</td>"
            f"<td class=\"num\">{_text(item.get('wall_seconds'))}</td>"
            f"<td>{_text(item.get('ts') or item.get('ts_end'))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Step</th><th>Phase/Kind</th><th>Status</th>"
        '<th class="num">Seconds</th><th>Time</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render_visualization_html(payload: dict[str, Any]) -> str:
    """Render a self-contained static HTML visualization page."""
    package = _as_dict(payload.get("package"))
    run = _as_dict(payload.get("run"))
    persistent = _as_dict(payload.get("persistent_content"))
    graph = _as_dict(persistent.get("graph_assets"))
    graph_counts = _as_dict(graph.get("counts"))
    trace = _as_dict(payload.get("execution_trace"))
    benchmark = _as_dict(trace.get("benchmark"))
    benchmark_summary = _as_dict(benchmark.get("summary"))
    obligations = _as_dict(trace.get("obligations"))
    files = [item for item in _as_list(persistent.get("files")) if isinstance(item, dict)]
    trace_records = [
        item for item in _as_list(trace.get("trace_records")) if isinstance(item, dict)
    ]
    events = [item for item in _as_list(trace.get("events")) if isinstance(item, dict)]
    selected_evidence_html = _object_list(
        "Selected Evidence",
        [item for item in _as_list(persistent.get("selected_evidence")) if isinstance(item, dict)],
        key_hint="focus_id",
    )
    anchors_html = _object_list(
        "Anchors",
        [item for item in _as_list(graph.get("anchors")) if isinstance(item, dict)],
        key_hint="ref",
    )
    claims_html = _object_list(
        "Claims",
        [item for item in _as_list(graph.get("claims")) if isinstance(item, dict)],
        key_hint="label",
    )
    relations_html = _object_list(
        "Candidate Relations",
        [item for item in _as_list(graph.get("candidate_relations")) if isinstance(item, dict)],
        key_hint="id",
    )
    matrix_html = _object_list(
        "Evidence Matrix",
        [item for item in _as_list(graph.get("evidence_matrix")) if isinstance(item, dict)],
        key_hint="relation_id",
    )
    open_obligations_html = _object_list(
        "Open Obligations",
        [item for item in _as_list(graph.get("open_obligations")) if isinstance(item, dict)],
        key_hint="target_qid",
    )
    obligation_executions_html = _object_list(
        "Obligation Executions",
        [item for item in _as_list(obligations.get("executions")) if isinstance(item, dict)],
        key_hint="action_type",
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Gaia Research Visualization - {_text(run.get('run_id'))}</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #17201b;
      --muted: #617064;
      --line: #c9d5cd;
      --paper: #f7f8f4;
      --panel: #ffffff;
      --accent: #0b6f6a;
      --accent-2: #b33f2f;
      --soft: #e8efea;
      --code: #111815;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--paper);
      color: var(--ink);
      font-family: ui-serif, Georgia, "Times New Roman", serif;
      line-height: 1.45;
    }}
    header {{
      border-bottom: 1px solid var(--line);
      background: linear-gradient(180deg, #fff 0%, var(--paper) 100%);
      padding: 28px clamp(18px, 4vw, 54px) 22px;
    }}
    .eyebrow {{
      color: var(--accent);
      font: 700 12px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
      letter-spacing: 0;
      text-transform: uppercase;
    }}
    h1 {{
      margin: 8px 0 12px;
      font-size: clamp(28px, 5vw, 54px);
      line-height: 1.02;
      letter-spacing: 0;
    }}
    .subline {{
      max-width: 980px;
      color: var(--muted);
      font-size: 16px;
    }}
    main {{ padding: 20px clamp(14px, 3vw, 40px) 44px; }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 8px;
      margin: 18px 0;
    }}
    .metric {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px 12px;
      min-height: 68px;
    }}
    .metric span {{
      display: block;
      color: var(--muted);
      font: 700 11px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace;
      text-transform: uppercase;
    }}
    .metric strong {{
      display: block;
      margin-top: 8px;
      font-size: 22px;
      overflow-wrap: anywhere;
    }}
    .tabs {{
      display: flex;
      gap: 6px;
      border-bottom: 1px solid var(--line);
      margin-top: 22px;
    }}
    .tabs button {{
      appearance: none;
      border: 1px solid var(--line);
      border-bottom: 0;
      background: var(--soft);
      color: var(--ink);
      padding: 10px 14px;
      border-radius: 6px 6px 0 0;
      cursor: pointer;
      font: 700 13px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
    }}
    .tabs button.active {{ background: var(--panel); color: var(--accent); }}
    .tab-panel {{
      display: none;
      background: var(--panel);
      border: 1px solid var(--line);
      border-top: 0;
      padding: 16px;
    }}
    .tab-panel.active {{ display: block; }}
    section {{ margin: 0 0 20px; }}
    h2, h3, h4 {{ letter-spacing: 0; }}
    h2 {{ margin: 4px 0 16px; font-size: 24px; }}
    h3 {{ margin: 16px 0 10px; font-size: 17px; }}
    h4 {{ margin: 0 0 8px; font-size: 15px; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 8px 7px;
      text-align: left;
      vertical-align: top;
      overflow-wrap: anywhere;
    }}
    th {{
      color: var(--muted);
      font: 700 11px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace;
      text-transform: uppercase;
    }}
    .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .records {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 10px;
    }}
    .record {{
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      background: #fbfcf9;
      min-width: 0;
    }}
    pre {{
      margin: 0;
      max-height: 340px;
      overflow: auto;
      color: #dce7df;
      background: var(--code);
      border-radius: 6px;
      padding: 10px;
      font: 12px/1.45 ui-monospace, SFMono-Regular, Menlo, monospace;
      white-space: pre-wrap;
    }}
    a {{ color: var(--accent); text-decoration-thickness: 1px; }}
    .empty {{ color: var(--muted); font-style: italic; }}
    .raw {{
      margin-top: 16px;
      border-top: 1px solid var(--line);
      padding-top: 16px;
    }}
    @media (max-width: 720px) {{
      .tabs {{ overflow-x: auto; }}
      .tabs button {{ white-space: nowrap; }}
      th:nth-child(3), td:nth-child(3) {{ display: none; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="eyebrow">Gaia Research Package Visualization</div>
    <h1>{_text(package.get('project_name'))}</h1>
    <div class="subline">{_text(run.get('topic'))}</div>
    <div class="metrics">
      {_metric('Run', run.get('run_id'))}
      {_metric('Status', run.get('status'))}
      {_metric('Phase', run.get('phase'))}
      {_metric('Profile', run.get('profile'))}
      {_metric('Graph Success', _as_dict(graph.get('success_evaluation')).get('success'))}
      {_metric('Trace Steps', benchmark_summary.get('steps', len(trace_records)))}
    </div>
  </header>
  <main>
    <div class="tabs" role="tablist">
      <button class="active" data-tab="persisted" type="button">Persisted Content</button>
      <button data-tab="trace" type="button">Execution Trace</button>
    </div>
    <div id="persisted" class="tab-panel active">
      <h2>Persisted Content</h2>
      <div class="metrics">
        {_metric('Anchors', graph_counts.get('anchors', 0))}
        {_metric('Claims', graph_counts.get('claims', 0))}
        {_metric('Relations', graph_counts.get('candidate_relations', 0))}
        {_metric('Matrix Rows', graph_counts.get('evidence_matrix_rows', 0))}
        {_metric('Open Obligations', graph_counts.get('open_obligations', 0))}
        {_metric('Deferred Obligations', graph_counts.get('deferred_obligations', 0))}
      </div>
      {selected_evidence_html}
      {anchors_html}
      {claims_html}
      {relations_html}
      {matrix_html}
      {open_obligations_html}
      <section>
        <h3>Artifact Files</h3>
        {_file_table(files)}
      </section>
      <section class="raw">
        <h3>Package Metadata</h3>
        <pre>{_json_block(package)}</pre>
      </section>
    </div>
    <div id="trace" class="tab-panel">
      <h2>Execution Trace</h2>
      <div class="metrics">
        {_metric('Events', len(events))}
        {_metric('Trace Records', len(trace_records))}
        {_metric('Total Seconds', benchmark_summary.get('total_wall_seconds'))}
        {_metric('Input Tokens', benchmark_summary.get('total_input_tokens'))}
        {_metric('Output Tokens', benchmark_summary.get('total_output_tokens'))}
        {_metric('Obligation Executions', len(_as_list(obligations.get('executions'))))}
      </div>
      <section>
        <h3>Trace Records</h3>
        {_trace_table(trace_records)}
      </section>
      <section>
        <h3>Events</h3>
        {_trace_table(events)}
      </section>
      {obligation_executions_html}
      <section class="raw">
        <h3>Obligation Plan</h3>
        <pre>{_json_block(obligations)}</pre>
      </section>
      <section class="raw">
        <h3>Benchmark</h3>
        <pre>{_json_block(benchmark)}</pre>
      </section>
    </div>
  </main>
  <script>
    const buttons = Array.from(document.querySelectorAll('[data-tab]'));
    const panels = Array.from(document.querySelectorAll('.tab-panel'));
    buttons.forEach((button) => {{
      button.addEventListener('click', () => {{
        const id = button.dataset.tab;
        buttons.forEach((item) => item.classList.toggle('active', item === button));
        panels.forEach((panel) => panel.classList.toggle('active', panel.id === id));
      }});
    }});
  </script>
</body>
</html>
"""
    return html


def write_visualization_html(
    pkg_path: str | Path, run_id: str, output_path: str | Path | None
) -> Path:
    """Write the static HTML visualization page and return its path."""
    pkg = Path(pkg_path).resolve()
    if output_path is None:
        output = pkg / ".gaia" / "research" / "runs" / run_id / "visualize.html"
    else:
        output = Path(output_path)
        if not output.is_absolute():
            output = pkg / output
    payload = build_visualization_payload(pkg, run_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_visualization_html(payload), encoding="utf-8")
    return output


__all__ = [
    "build_visualization_payload",
    "render_visualization_html",
    "write_visualization_html",
]

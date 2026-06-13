# gaia-research

Standalone research workflow package for Gaia.

This repository is being migrated toward ownership of Gaia's upper research
workflows. Gaia core remains the language, package, LKM search, authoring,
materialization, inquiry, and plugin substrate. Dependency direction is
intentionally one-way:

```text
gaia-research -> gaia-lang
```

Gaia core must not import `gaia_research`.

## Current Scope And Correction

Implemented in the first bridge milestone:

- package-local run SDK and disk contract;
- `.gaia/research/runs/<run-id>/` state, events, checkpoint, and final report
  artifacts;
- `gaia.cli_plugins` entry point for `gaia research`;
- downstream contract tests against Gaia core public modules;
- CI lint, typecheck, tests, and wheel build.

The earlier `gaia-research review` bridge around Gaia core
`gaia.engine.inquiry.review.run_review` was removed from the active CLI because
it was not the research workflow parity target. The current parity target is the
upper `gaia research ...` workflow from Gaia main, not the inquiry review
bridge.

This bridge milestone is not the completed research module split. The completed
split requires this repository to own the existing upper report workflow that
currently spans Gaia research and `gaia-lkm-explore` surfaces.

Current migration target:

- topic-driven report workflow;
- landscape;
- field map;
- focus selection;
- assessment/report-ready artifact;
- materialization decision;
- report.

Not in the current migration target:

- large-scale graph sessions;
- long-running pause/resume graph expansion;
- deep/broad continuous large-scale expansion policies.

Those graph-session capabilities are follow-up work. The current milestone is
report workflow parity, not graph-session expansion.

Gaia core keeps primitives such as `gaia search lkm`, `gaia add`,
`gaia inquiry`, `gaia author`, materialization, package checks, inference, and
rendering. `gaia-research` owns the upper research workflow built from those
primitives.

## Install For Development

```bash
uv sync --extra dev
```

The package depends on Gaia core as `gaia-lang`.

## Documentation

Workflow foundations live in [docs/foundations](docs/foundations/README.md).
Keep them current with code changes that alter workflow semantics, artifact
schemas, CLI behavior, or engine boundaries. Use
[docs/execution-record.md](docs/execution-record.md) for PR learnings and
tracking, not as the canonical design source.

## Report-Run Status

Inspect a report workflow run:

```bash
uv run gaia-research status \
  --path /path/to/workspace \
  --run-id aspirin-fast
```

Add `--json` for machine-readable status output.

## Report-Run Artifacts

Each report workflow run writes an observable envelope under the workspace:

```text
<workspace>/.gaia/research/runs/<run-id>/
  state.json
  events.ndjson
  landscape/
  field_map/
  focuses/
  assessments/
  materialization/
  reports/
```

`state.json` records status, phase, topic, profile, and artifact directories.
`events.ndjson` records lifecycle events such as `run.created` and later stage
events.

The old `.gaia/research_loop` path is not recreated.

## Contract Checks

Local verifier:

```bash
uv run pytest -q
uv run ruff check src tests
uv run mypy src tests
uv build --wheel --out-dir dist
scripts/smoke_installed_wheel.sh
```

To smoke-test a Gaia core branch before it reaches Gaia main, override the core
dependency used by the installed-wheel verifier:

```bash
GAIA_CORE_SPEC="gaia-lang @ git+https://github.com/SiliconEinstein/Gaia.git@codex/research-plugin-handoff" \
  scripts/smoke_installed_wheel.sh
```

The test suite verifies:

- `gaia-research` can import declared Gaia core public modules;
- Gaia core import does not import `gaia_research`;
- runtime Gaia package dependency metadata names only `gaia-lang`;
- gaia-research source does not statically import Gaia core modules; the bridge
  stays behind declared dynamic public surfaces;
- the CLI plugin entry point is present in package metadata;
- report-run artifacts are written under `.gaia/research/runs/**`.

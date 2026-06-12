# gaia-research

Standalone research package for Gaia.

This repository owns Gaia's external research workflows. Gaia core remains the
language, package, authoring, materialization, inquiry, and plugin substrate.
Dependency direction is intentionally one-way:

```text
gaia-research -> gaia-lang
```

Gaia core must not import `gaia_research`.

## Current Scope

Implemented in this split stack:

- package-local review-run SDK and disk contract;
- `.gaia/research/runs/<run-id>/` state, events, checkpoint, and final report
  artifacts;
- `gaia-research review` standalone CLI;
- `gaia.cli_plugins` entry point for `gaia research`;
- downstream contract tests against Gaia core public modules and review
  callables;
- CI lint, typecheck, tests, and wheel build.

Not implemented here:

- large-scale graph sessions;
- long-running pause/resume graph expansion;
- full explore/assess/propose migration from Gaia core.

Those follow-up capabilities should build on this package boundary without
changing the dependency direction.

## Install For Development

```bash
uv sync --extra dev
```

The package depends on Gaia core as `gaia-lang`.

## Review-Run Usage

Run a Gaia inquiry review through the standalone entry point:

```bash
uv run gaia-research review \
  --path /path/to/example-gaia \
  --topic "aspirin primary prevention" \
  --profile quick \
  --run-id aspirin-review \
  --no-infer
```

The same implementation is exposed to Gaia core through the CLI plugin entry
point:

```bash
gaia research review \
  --path /path/to/example-gaia \
  --topic "aspirin primary prevention" \
  --profile quick \
  --run-id aspirin-review \
  --no-infer
```

The Gaia command requires a Gaia core version that loads `gaia.cli_plugins` and
hands off the legacy `research` group to the installed `gaia-research` plugin.

Add `--json` to either review command when an agent or product caller needs the
completed run id, status, phase, run directory, report path, and event count
without parsing human-readable text.

Inspect a completed or failed run:

```bash
uv run gaia-research status \
  --path /path/to/example-gaia \
  --run-id aspirin-review
```

Add `--json` for machine-readable status output.

## Review-Run Artifacts

Each run writes an observable envelope under the package being reviewed:

```text
<package>/.gaia/research/runs/<run-id>/
  state.json
  events.ndjson
  checkpoints/query_plan.request.json
  final_report.md
```

`state.json` records status, phase, package metadata, pending checkpoint, final
report path, and Gaia core review metadata. `events.ndjson` records lifecycle
events such as `run.created`, `core_review.started`, `core_review.completed`,
`core_review.failed`, and `run.completed`.

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
- the exact Gaia core review callables used by the bridge are callable;
- the CLI plugin entry point is present in package metadata;
- review-run artifacts are written under `.gaia/research/runs/**`.

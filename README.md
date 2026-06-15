# gaia-research

`gaia-research` provides Gaia's upper research workflows as an installable
package and Gaia CLI plugin.

It turns a research topic into auditable artifacts and a report-ready result:

```text
topic
  -> landscape
  -> field map
  -> focus selection
  -> assessment
  -> materialization decision
  -> report
```

Gaia core remains the primitive substrate for package loading, LKM search,
authoring, materialization, inquiry state, checks, inference, and rendering.
This package owns the research workflow orchestration built from those
primitives.

## Install For Development

```bash
uv sync --extra dev
```

The package depends on Gaia core as `gaia-lang`.

## CLI

Run readiness checks:

```bash
uv run gaia-research doctor --for-agent --json
uv run gaia-research capabilities --json
```

Start a research workflow:

```bash
uv run gaia-research run <pkg> \
  --topic "<research topic>" \
  --profile fast \
  --json-stream
```

If credentials live in a local dotenv file, pass it explicitly:

```bash
uv run gaia-research run <pkg> \
  --topic "<research topic>" \
  --profile fast \
  --env-file .env.local \
  --json-stream
```

Inspect a run:

```bash
uv run gaia-research status <pkg> --run-id <run-id> --json
uv run gaia-research artifacts <pkg> --run-id <run-id> --json
```

Render a generated artifact as Markdown:

```bash
uv run gaia-research render <pkg> --artifact <artifact-json>
```

When installed with a Gaia release that supports CLI plugin handoff, the same
commands are available as:

```bash
gaia research doctor --for-agent --json
gaia research capabilities --json
gaia research run <pkg> --topic "<research topic>" --profile fast --json-stream
```

## Runtime Configuration

Research runs that use the LiteLLM provider expect explicit Gaia Research
environment variables:

```text
GAIA_RESEARCH_LLM_MODEL
GAIA_RESEARCH_LLM_API_BASE
GAIA_RESEARCH_LLM_API_KEY
```

LKM access must be available through either stored Gaia credentials or:

```text
GAIA_LKM_ACCESS_KEY
```

`doctor --for-agent --json` reports missing runtime requirements without
printing secret values.

## Artifacts

Each run writes an observable envelope under the Gaia workspace:

```text
<workspace>/.gaia/research/runs/<run-id>/
  state.json
  events.ndjson
  searches/
  analysis/
  trace/
  checkpoints/
  landscape/
  field_map/
  focuses/
  assessments/
  materialization/
  reports/
```

`state.json` records the current status, phase, topic, profile, and artifact
paths. `events.ndjson` records lifecycle and progress events. `status --json`
includes recent events so agents can observe long-running workflows even when
they cannot stream stdout directly.

## Prompts

LLM prompt assets for workflow phases live under:

```text
src/gaia_research/prompts/research/
```

The provider layer loads these assets, combines them with live input payloads
and output-shape hints, and calls the configured LLM provider. Python code
remains responsible for JSON validation, grounding repair, artifact writing, and
rendering.

## Agent Skills

The package exposes a `gaia.skills` entry point with thin agent-facing skills:

```text
gaia-research-bootstrap
gaia-research-run
gaia-research-status
gaia-research-artifacts
```

These skills route agents to the CLI and presentation discipline. They do not
duplicate the workflow engine.

## Documentation

Workflow foundations live in [docs/foundations](docs/foundations/README.md).
Specs, plans, testing notes, and prior-art archives live under `docs/`.

## Verification

Run the local verifier before claiming completion:

```bash
scripts/audit_goal_a.sh
```

Useful focused checks:

```bash
uv run pytest -q
uv run ruff check src tests
uv run mypy src tests
uv build --wheel --out-dir dist
scripts/smoke_installed_wheel.sh dist
```

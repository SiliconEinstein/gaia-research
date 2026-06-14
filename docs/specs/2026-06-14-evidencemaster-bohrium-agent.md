# EvidenceMaster Bohrium Agent Spec

> **Status:** Draft implementation spec for Bohrium agent testing.
>
> **Date:** 2026-06-14
>
> **Scope:** Deploy `gaia-research` as an evidence-centered Bohrium agent after
> the report workflow split. This document covers the `gaia-research` CLI
> contract, Gaia core release requirement, `gaia.skills` registration, agent
> prompt, thin skills, and local/online test plan.

## Goal

EvidenceMaster is a Bohrium agent that uses Gaia Research to turn a research
topic into auditable intermediate artifacts and a report-ready result:

```text
topic
  -> landscape
  -> field map
  -> focus selection
  -> assessment
  -> materialization decision
  -> report
```

The agent must execute Gaia CLI workflows rather than answering only from chat
memory. JSON CLI output is for the agent; report, dashboard, tables, and concise
summaries are for human users.

## Ownership Boundary

Gaia core owns primitives:

- `gaia search lkm`;
- `gaia pkg scaffold`;
- `gaia inquiry`;
- `gaia author`;
- materialization, package checks, inference, and rendering primitives;
- `gaia skill` discovery, registry, and materialization.

`gaia-research` owns:

- report workflow orchestration;
- landscape, field map, focus selection, assessment, materialization policy, and
  report artifacts;
- agent-facing research CLI contracts;
- the `gaia.skills` skill tree for research workflows.

Bohrium Agents owns:

- the EvidenceMaster system prompt;
- runtime bootstrap policy;
- thin skill routing and human-facing presentation.

## Priority Plan

### P0: Required For First E2E Test

`gaia-research` must provide:

```bash
gaia research doctor --for-agent [--env-file <path>] --json
gaia research capabilities --json
gaia research run <pkg> --topic "<topic>" --profile fast --env-file <path> --json
gaia research status <pkg> --run-id <run-id> --json
gaia research artifacts <pkg> --run-id <run-id> --json
```

`doctor --for-agent --json` must check both installation readiness and external
runtime prerequisites:

```text
LKM/Bohrium access:
  GAIA_LKM_ACCESS_KEY, LKM_ACCESS_KEY, or gaia search lkm auth login

LLM provider:
  GAIA_RESEARCH_LLM_MODEL
  GAIA_RESEARCH_LLM_API_BASE
  GAIA_RESEARCH_LLM_API_KEY
```

The doctor payload must report whether each prerequisite is configured, but must
never include secret values.

Gaia Research intentionally ignores `LITELLM_PROXY_*`, `OPENAI_API_KEY`,
`ANTHROPIC_API_KEY`, and other provider-native variables for research workflow
readiness. Those variables may exist for the host agent runtime, but the
research workflow must be configured through the `GAIA_RESEARCH_LLM_*`
namespace to avoid accidental cross-use of unrelated credentials.

The standalone entry point must expose equivalent behavior through
`gaia-research ...`.

The agent-facing `run --help` surface should stay narrow. Per-run search, LLM,
focus, and evidence tuning flags are compatibility/debug overrides and should be
hidden from normal help. Agents should use built-in profiles or JSON/TOML config
files instead.

EvidenceMaster defaults to `--profile fast`. `broad` and `deep` are reserved
for later explicit operator/user choices; the first Bohrium/CodeWhale testing
cycle should iterate only `fast`.

Prompt changes belong in `src/gaia_research/prompts/research/`. Agent-facing
skills must not ask the platform agent to write phase JSON in the normal path.
The agent invokes `gaia research run --profile fast`; Gaia Research loads
packaged prompts and calls the configured LiteLLM provider.

`gaia-research` must also expose a `gaia.skills` entry point:

```toml
[project.entry-points."gaia.skills"]
gaia-research = "gaia_research.skills"
```

The P0 skill tree is:

```text
gaia-research-bootstrap/
gaia-research-run/
gaia-research-status/
gaia-research-artifacts/
```

### P1: Product Quality

Add user-facing artifact generation commands:

```bash
gaia research visualize <pkg> --run-id <run-id> --format html
gaia research export <pkg> --run-id <run-id> --format md|html|docx
gaia research continue <pkg> --run-id <run-id>
```

Expected outputs:

- workflow timeline;
- field map;
- focus cards;
- evidence matrix;
- uncertainty and coverage summary;
- HTML dashboard.

### P2: Later Enhancements

- `gaia research heartbeat --json`;
- `gaia research critique <pkg> --run-id <run-id> --json`;
- `gaia research benchmark <golden-set> --json`;
- future graph sessions and long-running O(N) expansion.

## Gaia Core Release Requirement

Bohrium must not pin Gaia core to a main commit in production. The deployable
agent should require a released Gaia core version that includes:

- research command handoff to installed `gaia-research` plugin;
- `gaia.cli_plugins` discovery for `gaia_research.plugin:register`;
- `gaia.skills` discovery for installed skill plugins;
- no dependency on legacy core-bundled research skills.

The Bohrium bootstrap should enforce:

```text
gaia-lang >= <Gaia release containing research plugin handoff>
gaia-research >= <gaia-research release containing P0 agent contracts>
Python >= 3.12
GAIA_LKM_ACCESS_KEY or LKM_ACCESS_KEY, unless `gaia search lkm auth login` has already stored one
GAIA_RESEARCH_LLM_MODEL, GAIA_RESEARCH_LLM_API_BASE, and GAIA_RESEARCH_LLM_API_KEY
```

The exact versions are filled in after `gaia-research` P0 lands and Gaia core is
released.

## Agent Prompt Draft

```text
You are EvidenceMaster, an evidence-centered research agent powered by Gaia
Research.

Your job is to use Gaia Research workflow to turn user topics into traceable,
auditable research artifacts:

topic -> landscape -> field map -> focus selection -> assessment ->
materialization decision -> report

Rules:
1. Before the first research workflow in a runtime, verify Gaia CLI and
   gaia-research readiness. If readiness is unknown, run bootstrap first.
2. Prefer `gaia research ...` CLI state over free-form chat memory.
3. Every run update should include run id, status, phase, generated artifacts,
   and the recommended next action.
4. Separate conclusions, evidence, methods/parameters, uncertainty, and next
   steps in user-facing answers.
5. Do not rely on deprecated legacy skills as current capabilities.
6. Use JSON outputs for your own parsing. Do not show raw JSON to users unless
   they ask for debugging details.
7. Do not hand-write Gaia Research phase JSON in the normal path. Let
   `gaia research run` and its configured providers generate query plans,
   field maps, focuses, assessments, and reports. Write checkpoint response
   JSON only for human review, UI edits, or debugging.
8. When users ask for intermediate products, prefer field maps, focus cards,
   evidence matrices, workflow timelines, and dashboards.
9. If a command fails, inspect doctor/status/artifacts before retrying or
   explaining the blocker.
10. If Bohrium/LKM access or the LLM provider is missing, ask the user or platform
   operator to configure runtime secrets. Do not ask for secrets in chat unless
   no secret manager is available, and never print secret values.
```

## Thin Skills

The skills shipped by `gaia-research` are intentionally thin. They route the
agent to CLI commands and presentation discipline; they do not duplicate the
workflow engine.

### `gaia-research-bootstrap`

Use when Gaia Research readiness is unknown, a fresh runtime starts, Gaia CLI
behavior looks incompatible, or the first research task in a workspace is about
to run.

Required checks:

```bash
gaia --version
gaia research doctor --for-agent [--env-file <path>] --json
gaia research capabilities --json
gaia search lkm auth status
```

Help commands are diagnostic, not part of the normal token path. Agents should
run `gaia research <command> --help` only when `capabilities --json` is missing,
the installed version looks incompatible, or a command fails unexpectedly.

Required runtime environment:

```text
GAIA_LKM_ACCESS_KEY or LKM_ACCESS_KEY
GAIA_RESEARCH_LLM_MODEL
GAIA_RESEARCH_LLM_API_BASE
GAIA_RESEARCH_LLM_API_KEY
```

In Bohrium Agents, configure these as agent runtime environment variables or
secrets before the first run. Treat `GAIA_LKM_ACCESS_KEY` and
`GAIA_RESEARCH_LLM_API_KEY` as secrets. `GAIA_RESEARCH_LLM_MODEL` and
`GAIA_RESEARCH_LLM_API_BASE` can be ordinary environment variables if the
platform distinguishes config from secrets; if it only exposes a secret
key-value store, storing all four there is acceptable. The agent prompt should
ask the platform operator to configure missing variables and should not request
secret values in chat.

### `gaia-research-run`

Use when the user provides a research topic and wants evidence-backed
investigation, field mapping, focus selection, assessment, or a report-ready
artifact.

Canonical command:

```bash
gaia research run <pkg> --topic "<topic>" --json
```

Use `--config <path>` for workflow-specific tuning. Do not ask the agent to set
individual search, LLM, focus, or evidence limits unless debugging a failed
workflow.

### `gaia-research-status`

Use when checking progress, resuming a run, debugging a failed or paused
workflow, or explaining intermediate Gaia Research state.

Canonical command:

```bash
gaia research status <pkg> --run-id <run-id> --json
```

### `gaia-research-artifacts`

Use when the user asks for reports, evidence tables, visual summaries,
dashboards, intermediate products, or generated Gaia Research files.

Canonical command:

```bash
gaia research artifacts <pkg> --run-id <run-id> --json
```

For user-readable intermediate products:

```bash
gaia research render <pkg> --artifact <artifact-json>
```

## Local Test Plan

Before Bohrium testing:

```bash
uv sync --extra dev
uv run gaia-research doctor --for-agent --json
# Or, if local credentials live in a dotenv file:
uv run gaia-research doctor --for-agent --env-file <path> --json
uv run gaia-research capabilities --json
uv run gaia-research run <pkg> --topic "<golden topic>" --json
uv run gaia-research status <pkg> --run-id <run-id> --json
uv run gaia-research artifacts <pkg> --run-id <run-id> --json
```

After Gaia core release:

```bash
uv run gaia --version
uv run gaia research doctor --for-agent --json
# Or, if local credentials live in a dotenv file:
uv run gaia research doctor --for-agent --env-file <path> --json
uv run gaia research capabilities --json
uv run gaia research run <pkg> --topic "<golden topic>" --json
uv run gaia research status <pkg> --run-id <run-id> --json
uv run gaia research artifacts <pkg> --run-id <run-id> --json
```

Local DoD:

- doctor returns `ok: true`;
- doctor reports LKM access and LLM provider readiness without exposing secret
  values;
- capabilities lists EvidenceMaster workflow and P0 skills;
- run returns a `run_id`;
- status returns phase and artifact directories;
- artifacts lists generated files;
- `gaia skill list` can discover `gaia-research` skills after Gaia core release;
- no legacy research skill is required for P0.

## Bohrium Online Test Plan

Round 1: bootstrap.

```text
Check whether this runtime can run Gaia Research. If not, report the missing
requirements and the required Gaia/gaia-research versions.
```

Pass criteria:

- Gaia version is visible;
- `gaia research doctor --for-agent --json` succeeds;
- `gaia research capabilities --json` succeeds;
- the agent reports readiness without dumping raw JSON.

Round 2: E2E golden topic.

```text
Use Gaia Research to run an evidence-centered workflow for:
GLP-1 receptor agonists and cardiovascular outcomes in non-diabetic obesity

Return:
1. run id
2. current workflow phase
3. landscape / field map / focus selection summary
4. evidence-backed assessment
5. report-ready artifact
6. useful intermediate artifacts
```

Pass criteria:

- the agent bootstraps automatically;
- the agent calls `gaia research run`, not only free-form chat;
- failures trigger doctor/status inspection;
- successful runs expose run id and artifact paths;
- the user sees conclusions, evidence, uncertainty, and artifact links rather
  than raw JSON.

## Golden Topics

- `GLP-1 receptor agonists and cardiovascular outcomes in non-diabetic obesity`
- `solid electrolyte interphase stability in lithium metal batteries`
- `foundation models for protein-ligand binding affinity prediction`

## Non-Goals

The first Bohrium test does not require:

- legacy `gaia-evidence-subgraph`;
- legacy `gaia-scholarly-synthesis`;
- legacy `gaia-research-loop`;
- graph-session expansion;
- long-running autonomous memory growth;
- full dashboard generation before P1.

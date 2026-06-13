# Research Workflow Parity Matrix

> **Status:** Inventory and target mapping for the current report workflow
> parity milestone. This is not a completion claim.
>
> **Acceptance parent:**
> [Research Workflow Parity Acceptance](2026-06-13-research-workflow-parity-acceptance.md)
>
> **Gaia source snapshot:** `origin/main` at
> `652aa11afebb36c1d9144d7789c222c7c87c8975`.

## Purpose

This matrix prevents scope drift during the `gaia-research` split. Every Gaia
main upper research workflow surface should either be reproduced in
`gaia-research`, served through `gaia research ...` plugin handoff, retained as
a short-lived deprecated alias, or intentionally removed after parity.

`gaia search lkm` is excluded from migration because it is a Gaia core
primitive. `gaia-research` may call it, but must not replace Gaia core ownership
of LKM search.

## Inventory Sources

- `pyproject.toml`: `gaia` and `gaia-lkm-explore` console scripts.
- `gaia/cli/commands/research.py`: Gaia main `gaia research ...` workflow
  commands.
- `gaia/lkm_explorer/client/cli.py`: `gaia-lkm-explore` command registration.
- `gaia/lkm_explorer/client/verbs.py`: deterministic exploration verbs.
- `docs/foundations/cli/research-loop.md`: canonical Gaia main research-loop
  semantics before split.
- `tests/cli/test_research.py`: Gaia main research CLI behavior.
- `tests/lkm_explorer/test_cli_explore.py`: `gaia-lkm-explore` CLI behavior.

## Gaia Core Primitive Exclusions

| Surface | Classification | Target | Rationale |
|---|---|---|---|
| `gaia search lkm docs` | `primitive-excluded` | Keep in Gaia core | LKM endpoint documentation remains core substrate. |
| `gaia search lkm knowledge` | `primitive-excluded` | Keep in Gaia core; call from `gaia-research` | Broad and targeted search are primitives used by report workflow. |
| `gaia search lkm reasoning` | `primitive-excluded` | Keep in Gaia core; call from `gaia-research` when needed | Reasoning-backed search remains LKM substrate. |
| `gaia search lkm nodes` | `primitive-excluded` | Keep in Gaia core | Node lookup is a primitive, not upper workflow orchestration. |
| `gaia search lkm package` | `primitive-excluded` | Keep in Gaia core | Package/paper graph fetch remains materialization substrate. |
| `gaia add`, `gaia inquiry`, `gaia author` | `primitive-excluded` | Keep in Gaia core; orchestrate from `gaia-research` | These are accepted package/inquiry/source operations, not research workflow ownership. |

## `gaia research ...` Surfaces

| Old Gaia main surface | Classification | `gaia-research` target | Required parity behavior |
|---|---|---|---|
| `gaia research contract <kind>` | `ported` | `gaia-research contract <kind>` and `gaia research contract <kind>` | Print agent-facing JSON contracts for `field_map`, `focus`, `assess`, and `propose`. |
| `gaia research status <pkg>` | `ported` | `gaia-research status <workspace-or-pkg>` and plugin handoff | Initialize/read research manifest or run state and show focus, mode, obligations, and actionable next commands. |
| `gaia research trace record` | `ported` | `gaia-research trace record` and plugin handoff | Append timing/provider/search/external trace records for benchmark and audit output. |
| `gaia research trace summarize` | `ported` | `gaia-research trace summarize` and plugin handoff | Rebuild benchmark summary from trace records. |
| `gaia research run --topic ...` | `ported` | `gaia-research report --topic ...` and `gaia research report --topic ...` | Primary end-to-end fast report path: topic/query to landscape, field map, focus, assessment, materialization decision, and final report. |
| `gaia research explore --mode scan` | `ported` | `gaia-research explore --mode scan` and plugin handoff | Consume saved or live LKM search payloads, write landscape artifacts, shallow source/package sync decisions, hypotheses, and obligations. |
| `gaia research explore --mode expand` | `ported` | `gaia-research explore --mode expand` and plugin handoff | Target expansion around a focus or obligation using saved or live LKM search payloads. |
| `gaia research expand` | `deprecated-alias` | Alias to `gaia-research explore --mode expand` | Preserve old short command while making `explore --mode expand` the shared engine path. |
| `gaia research focus` | `ported` | `gaia-research focus` and plugin handoff | Synthesize assessment-ready focuses from landscapes, sync accepted focuses into package questions/inquiry focus/obligations where requested. |
| `gaia research assess` | `ported` | `gaia-research assess` and plugin handoff | Assess one focus against selected evidence, optionally deep-materialize selected papers/chains, write assessment artifacts, notes, obligations, hypotheses, and candidate relations. |
| `gaia research propose` | `ported` | `gaia-research propose` and plugin handoff | Turn an assessment into proposed next research questions; with accept flag, write accepted questions and inquiry state. |
| `gaia research promote` | `ported` | `gaia-research promote` and plugin handoff | Record explicit materialization decisions/links from scaffold to formal records. |
| `gaia research report --artifact ...` | `deprecated-alias` | `gaia-research render --artifact ...`; compatibility alias allowed | Render an existing research artifact to Markdown. The primary `report` command is reserved for topic-to-report workflow. |
| `gaia research stop` | `ported` | `gaia-research stop` and plugin handoff | Evaluate stop criteria from focus, assessment, and landscape artifacts. |

## `gaia-lkm-explore ...` Surfaces

The current report parity milestone does not recreate long-running graph-session
behavior. `gaia-lkm-explore` remains prior art for landscape, focus, artifact,
gate, frontier, and turn concepts, but graph-session/O(N) expansion gets a
separate future acceptance standard.

| Old `gaia-lkm-explore` surface | Classification | `gaia-research` target | Required parity behavior |
|---|---|---|---|
| `gaia-lkm-explore init` | `removed-after-parity` | No report-parity command; future graph-session spec | Initializes `.gaia/exploration/map.json`; not required for topic-to-report parity. |
| `gaia-lkm-explore scope` | `ported` | `gaia-research scope` or report workflow scope stage | Build explicit scope artifact from seeds/profile/dimensions under `.gaia/research`. |
| `gaia-lkm-explore observe` | `deprecated-alias` | `gaia-research explore --search-json ...` | Saved LKM search payload ingestion becomes report workflow landscape input. |
| `gaia-lkm-explore landscape` | `ported` | `gaia-research landscape` or report workflow landscape stage | Aggregate saved LKM search payloads into deduplicated paper-lead landscape under `.gaia/research`. |
| `gaia-lkm-explore focuses` | `ported` | `gaia-research focus` | Build focus candidates from landscape artifacts with evidence references. |
| `gaia-lkm-explore artifact` | `ported` | `gaia-research artifact` or report workflow handoff stage | Link scope, landscape, focus, package, and report workflow provenance. |
| `gaia-lkm-explore gate` | `ported` | `gaia-research gate` or assessment-readiness stage | Block/revise/pass assessment readiness based on required artifacts and evidence refs. |
| `gaia-lkm-explore frontier` | `removed-after-parity` | Future graph-session spec | Frontier ranking belongs to later continuous expansion, not current report parity. |
| `gaia-lkm-explore round` | `removed-after-parity` | Future graph-session spec | Round discovery bookkeeping belongs to later continuous expansion. |
| `gaia-lkm-explore status` | `deprecated-alias` | `gaia-research status` for report runs; future graph-session status later | Current parity needs run/artifact status, not `.gaia/exploration/map.json` status. |
| `gaia-lkm-explore render` | `removed-after-parity` | Future graph-session visualization spec | Exploration-map HTML rendering is graph-session visualization, not report parity. |
| `gaia-lkm-explore turn` | `removed-after-parity` | Future graph-session spec | Phase-aware turn loop is the future large-scale graph-session workflow. |

## Fast Report Acceptance Path

The fast product path must be verified independently of individual atomic
commands:

```bash
gaia-research report \
  --topic "<query>" \
  --workspace "<workspace>" \
  --profile fast \
  --json
```

and through Gaia plugin handoff:

```bash
gaia research report \
  --topic "<query>" \
  --workspace "<workspace>" \
  --profile fast \
  --json
```

Expected workflow stages:

```text
topic/query
  -> landscape search
  -> field map
  -> focus selection
  -> assessment or report-ready artifact
  -> materialization decision
  -> report
```

Expected verifier output:

- elapsed time, with a 3-5 minute target for the configured fast profile;
- run id;
- status and phase;
- run directory;
- state and event paths;
- landscape, field-map, focus, assessment, materialization, and report paths;
- explicit failure reason when external search or model services are
  unavailable.

## Current Implementation Gap Summary

As of this matrix, `gaia-research` has a bridge milestone with `review` and
`status` commands, `.gaia/research/runs/<run-id>/` state, and Gaia CLI plugin
handoff. It does not yet satisfy this parity matrix.

The next implementation work should therefore start with:

1. porting the deterministic state/artifact contracts into `gaia-research`;
2. adding `report` as the primary end-to-end command;
3. mapping old `run`, `report --artifact`, and `gaia-lkm-explore` aliases to
   the new commands only after equivalent behavior exists;
4. adding cross-repo installed-wheel and fast-report smoke verifiers.

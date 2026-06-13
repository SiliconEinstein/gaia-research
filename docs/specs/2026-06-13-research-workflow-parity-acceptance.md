# Research Workflow Parity Acceptance

> **Status:** Canonical acceptance standard for the current `gaia-research`
> split milestone.
>
> **Date:** 2026-06-13
>
> **Scope:** Reproduce Gaia main's existing upper research workflow behavior in
> the standalone `gaia-research` package. This document defines what "split
> complete" means for the current report workflow milestone.

## Goal Statement

Move the upper research workflow out of Gaia core and into `gaia-research`
without losing the user-facing capabilities that already worked from Gaia main.

After this milestone, a user should be able to install `gaia-research` and run
the same research workflow capabilities through:

```bash
gaia-research ...
```

and, when the package is installed beside Gaia core:

```bash
gaia research ...
```

The `gaia research` command is a cross-package plugin/handoff surface. Gaia core
must not statically import `gaia_research`.

## Acceptance Criteria

### 1. Parity Matrix Exists

Create and maintain a parity matrix that inventories every Gaia-main upper
research workflow entry point that existed before the split:

- `gaia research ...` atomic commands;
- `gaia research ...` higher-level run or end-to-end workflow commands;
- `gaia-lkm-explore ...` commands that serve the report workflow;
- relevant docs and examples that present those commands as canonical.

Each row must classify the old surface as one of:

- `ported`: reproduced in `gaia-research`;
- `plugin-handoff`: served by `gaia research ...` through the installed
  `gaia-research` plugin;
- `deprecated-alias`: retained only for migration compatibility;
- `removed-after-parity`: intentionally removed after an equivalent
  `gaia-research` path exists;
- `primitive-excluded`: not part of the upper workflow split.

`gaia search lkm` is always `primitive-excluded`. It remains a Gaia core
primitive, not a command to migrate into `gaia-research`.

The current matrix is
[Research Workflow Parity Matrix](2026-06-13-research-workflow-parity-matrix.md).

### 2. Standalone CLI Reproduces Existing Workflow Capability

Every Gaia-main upper research workflow capability in the parity matrix must
have an equivalent standalone `gaia-research` CLI path or a documented
intentional replacement.

The primary end-to-end command must support a flow equivalent to:

```bash
gaia-research report \
  --topic "aspirin primary prevention cardiovascular disease" \
  --workspace ./runs/aspirin-fast-report \
  --profile fast \
  --json
```

The workflow must start from a user-provided topic or query and produce the same
class of user-visible outputs as the Gaia-main workflow it replaces.

### 3. Gaia CLI Can Call The External Package

After installing Gaia core and `gaia-research` together, Gaia CLI must be able
to discover and run the external research workflow:

```bash
gaia research report \
  --topic "aspirin primary prevention cardiovascular disease" \
  --workspace ./runs/aspirin-fast-report \
  --profile fast \
  --json
```

Required boundary behavior:

- Gaia core exposes the plugin/handoff surface.
- `gaia-research` owns the implementation.
- Gaia core does not statically import `gaia_research`.
- `gaia-research` depends on Gaia core only through declared package dependency,
  public Python surfaces, subprocess adapters, or stable CLI primitives.

### 4. Fast Report Smoke Completes End To End

There must be a repeatable smoke test that starts from a query and completes the
full report workflow in the fast product mode:

```text
topic/query
  -> landscape search
  -> field map
  -> focus selection
  -> assessment or report-ready artifact
  -> materialization decision
  -> report
```

Acceptance target:

- completes in approximately 3-5 minutes for the configured fast profile;
- writes observable state and events;
- writes all expected intermediate artifacts;
- writes a final report;
- emits machine-readable JSON with run id, status, phase, run directory, report
  path, and event count.

If external services make timing unstable, the verifier must still record the
elapsed time and make the failure reason explicit.

### 5. Artifact And Behavior Parity Are Verified

The replacement workflow must produce equivalent user-visible behavior to the
Gaia-main workflow it replaces.

Required artifacts under the `gaia-research` namespace:

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

Required semantic behavior:

- raw search hits and paper leads remain research artifacts;
- field-map clusters, candidate nodes, and candidate relations remain research
  artifacts until accepted;
- obligations enter Gaia inquiry state only through an explicit decision;
- stable truth-bearing content enters Gaia source only through explicit
  materialization or promotion;
- final reports cite the research artifacts and Gaia package state they used.

### 6. Gaia Core Keeps Only Primitive Ownership

Gaia core remains responsible for primitives:

- `gaia search lkm`;
- `gaia add`;
- `gaia inquiry`;
- `gaia author`;
- package scaffolding, checks, inference, materialization, and rendering;
- stable public surfaces used by external workflow packages.

Gaia core must stop owning upper research workflow implementation after parity
replacement exists. Old upper workflow surfaces should either hand off to
`gaia-research`, become deprecated aliases, or be removed after parity.

### 7. Verification Suite Covers The Split

Completion requires all of the following evidence:

- parity matrix document;
- `gaia-research` engine tests for deterministic workflow stages;
- `gaia-research` standalone CLI tests;
- Gaia plugin/handoff tests for `gaia research report`;
- source-boundary tests proving Gaia core does not import `gaia_research`;
- cross-repo installed-wheel smoke for Gaia core plus `gaia-research`;
- fast report smoke from topic/query to final report;
- Gaia core deprecation/handoff tests for old upper workflow surfaces;
- docs that state `gaia-research` owns upper research workflow and Gaia core
  owns primitives.

## Non-Goals For This Milestone

This acceptance standard does not require:

- large graph-session expansion;
- O(N) long-running graph growth;
- thousands or tens of thousands of node exploration;
- pause/resume graph expansion beyond current report workflow needs;
- deep/broad continuous expansion policies;
- LKM writeback;
- public registry publication.

Those are future milestones and should get their own acceptance standard.

## Suggested `/goal` Template

```text
/goal Move Gaia main's existing upper research workflow into gaia-research with
functional parity.

Acceptance:
1. Inventory all existing Gaia-main upper research commands and workflows into a
   parity matrix, excluding gaia search lkm as a primitive.
2. Reproduce the ported surfaces in gaia-research CLI.
3. Make gaia research report discover and run gaia-research through package
   plugin/handoff installation.
4. Prove a topic/query can complete a fast end-to-end report workflow in about
   3-5 minutes.
5. Verify artifacts, state, events, report output, and deprecation behavior with
   tests and smoke scripts.
6. Keep graph-session/O(N) expansion out of this milestone.
```

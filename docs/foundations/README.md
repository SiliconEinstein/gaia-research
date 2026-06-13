# gaia-research Foundations

This directory is the durable design home for `gaia-research` workflow
semantics.

The current acceptance boundary is
[Research Workflow Parity Acceptance](../specs/2026-06-13-research-workflow-parity-acceptance.md).

Gaia core keeps primitives. `gaia-research` owns upper research workflows built
from those primitives.

Current milestone:

```text
topic
  -> landscape
  -> field map
  -> focus selection
  -> assess/report-ready artifact
  -> materialization decision
  -> report
```

Future milestone:

```text
graph session
  -> continuous expansion
  -> O(N) append/resume discipline
  -> large field map and relation memory
```

## Maintenance Rule

When code changes alter workflow semantics, artifact schemas, CLI behavior, or
engine boundaries, update the relevant foundation document in the same PR. If no
foundation document exists yet, create one here instead of extending Gaia-core
design docs.

## Migration Rule

Historical Gaia research and `gaia-lkm-explore` documents are prior art. Do not
copy them verbatim into this directory. Rewrite migrated material against the
current ownership boundary:

- Gaia core owns primitives such as `gaia search lkm`, `gaia add`,
  `gaia inquiry`, `gaia author`, materialization, checks, inference, and
  rendering.
- `gaia-research` owns landscape, field map, focus selection, assessment,
  materialization policy, report workflow, and future graph-session workflow.

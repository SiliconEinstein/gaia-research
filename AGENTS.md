# Contributor And Agent Guide

This repository owns Gaia's upper research workflows. Gaia core owns primitives
such as `gaia search lkm`, `gaia add`, `gaia inquiry`, `gaia author`,
materialization, package checks, inference, and rendering.

## Documentation Ownership

Keep workflow design documentation in this repository, not in Gaia core.

- `docs/foundations/` is the durable design home for research workflow concepts:
  landscape, field map, focus, assessment, materialization policy, report
  workflow, and future graph sessions.
- Update `docs/foundations/` in the same PR as code changes that alter workflow
  semantics, artifact schemas, CLI behavior, or engine boundaries.
- Use `docs/execution-record.md` for PR learnings and tracking notes, not as the
  canonical design source.
- Gaia core may keep migration/deprecation pointers, but current workflow specs
  should live here once migrated.
- Do not copy old Gaia research docs verbatim. When migrating prior art, rewrite
  it against current `gaia-research` ownership and mark historical assumptions.

## Current Milestone

The current milestone is report workflow parity migration:

```text
topic
  -> landscape
  -> field map
  -> focus selection
  -> assess/report-ready artifact
  -> materialization decision
  -> report
```

Large graph-session expansion, O(N) continuous growth, and long-running
deep/broad graph memory are future work.

## Development

Use `uv` for dependency management.

```bash
uv sync --extra dev
```

Run the local verifier before claiming completion:

```bash
scripts/audit_goal_a.sh
```

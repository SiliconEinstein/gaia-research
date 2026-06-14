---
name: gaia-research-status
description: Use when checking progress, resuming a run, debugging a failed or paused workflow, or explaining intermediate Gaia Research state.
---

# Gaia Research Status

Use this to inspect an existing report workflow run.

## Steps

1. Run:

```bash
gaia research status <pkg> --run-id <run-id> --json
```

2. Read `status`, `phase`, `events`, `recent_events`, `run_dir`, and
   `artifacts`.
3. If the run is paused or failed, inspect the state and event paths before
   deciding whether to continue, rerun, or ask for missing input.
4. Tell the user the current phase, the latest meaningful event, generated
   artifact areas, and next action.

## User-Facing Output

Do not show raw JSON by default. Translate status into a short progress update
with concrete artifact paths when they are useful.

---
name: gaia-research-artifacts
description: Use when the user asks for reports, evidence tables, visual summaries, dashboards, intermediate products, or generated Gaia Research files.
---

# Gaia Research Artifacts

Use this to find generated run outputs and turn them into user-facing answers.

## Steps

1. Run:

```bash
gaia research artifacts <pkg> --run-id <run-id> --json
```

2. Prefer structured artifacts over reconstructing from chat memory.
3. Present useful outputs in this order when available: final report, evidence
   matrix, field map, focus cards, assessments, landscape.
4. For JSON artifacts such as landscape, field map, focus synthesis, assessment,
   proposal, or stop artifacts, render Markdown with:

```bash
gaia research render <pkg> --artifact <artifact-json>
```

5. If a requested artifact is missing, explain the current run phase and the
   command needed to generate it.

## User-Facing Output

Summarize conclusions, evidence, methods, uncertainty, and next steps. Link or
name artifact files for inspection. Do not dump raw JSON unless the user asks
for debugging details.

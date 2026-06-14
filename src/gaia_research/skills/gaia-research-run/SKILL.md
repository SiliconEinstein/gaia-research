---
name: gaia-research-run
description: Use when the user provides a research topic and wants evidence-backed investigation, field mapping, focus selection, assessment, or a report-ready artifact.
---

# Gaia Research Run

Use this to start the Gaia Research report workflow in an existing Gaia
knowledge package.

## Steps

1. Ensure bootstrap readiness has been checked in the current runtime.
2. Ensure there is an existing Gaia knowledge package path. If not, scaffold one
   with `gaia pkg scaffold --target <pkg> --name <name>-gaia`.
3. Run:

```bash
gaia research run <pkg> --topic "<topic>" --profile <profile> --json
```

Use `--config <path>` for workflow tuning instead of passing individual search,
LLM, focus, or evidence limits on the command line:

```bash
gaia research run <pkg> --topic "<topic>" --profile <profile> --config <path> --json
```

If credentials are provided through a local dotenv file, include it as runtime
environment only:

```bash
gaia research run <pkg> --topic "<topic>" --profile <profile> --env-file <path> --json
```

4. Capture `run_id`, `status`, `phase`, `run_dir`, `state_path`, and
   `events_path`.
5. Summarize the workflow state for the user and suggest the next status or
   artifacts command.

## Discipline

Prefer CLI state over free-form memory. If the command fails, inspect
`gaia research doctor --for-agent --json` and `gaia research status` before
retrying.

Do not tune per-run search, LLM, focus, or evidence flags from chat unless the
user explicitly asks for low-level debugging. Put those settings in a profile
config file.

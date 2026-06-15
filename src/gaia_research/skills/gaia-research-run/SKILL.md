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
3. Prefer the managed workflow: let Gaia Research generate and consume phase
   JSON through its configured providers. Do not hand-write analysis JSON or
   checkpoint responses in the normal path.
4. Run:

```bash
gaia research run <pkg> --topic "<topic>" --profile fast --json-stream
```

EvidenceMaster defaults to `fast`. Do not switch to `broad` or `deep` unless
the user or platform operator explicitly asks.

Use `--config <path>` only for workflow tuning/debugging instead of passing
individual search, LLM, focus, or evidence limits on the command line:

```bash
gaia research run <pkg> --topic "<topic>" --profile fast --config <path> --json-stream
```

If credentials are provided through a local dotenv file, include it as runtime
environment only:

```bash
gaia research run <pkg> --topic "<topic>" --profile fast --env-file <path> --json-stream
```

5. Treat each stdout line as one NDJSON progress event. Capture `run_id`,
   `phase`, `run_dir`, `state_path`, `events_path`, generated artifact paths,
   and provider/search events as they arrive.
6. Summarize the workflow state for the user and suggest the next status or
   artifacts command.

## Managed Path

The simplest agent behavior is:

```bash
gaia research run <pkg> --topic "<topic>" --profile fast --env-file <path> --json-stream
gaia research status <pkg> --run-id <run-id> --json
gaia research artifacts <pkg> --run-id <run-id> --json
```

When LLM credentials are present, Gaia Research should own query planning,
field-map analysis, focus synthesis, assessment, and report JSON. The agent
should summarize state and artifacts for the user, not invent or fill those JSON
objects itself.

Use `--json` only when the caller does not need live progress and wants a final
machine-readable summary after the command completes. For interactive agents,
prefer `--json-stream`.

If the host platform does not expose streaming stdout while `run` is active,
poll `gaia research status <pkg> --run-id <run-id> --json` from a separate
tool/session when possible. The status payload includes `recent_events` from
`events.ndjson`.

## Checkpoint Flow

When `run` returns `status=waiting_for_input`, it has paused at a checkpoint.
Do not expect `status` to auto-advance after writing a response file.

First try the managed continuation: re-run the same `run` command with the same
package, topic, run id, profile, config, and env file. This lets the CLI consume
the checkpoint default action or any existing response.

Manual response writing is a fallback for human review, UI edits, or debugging.
For `query_plan` only:

1. Read `checkpoints/query_plan.request.json`.
2. Write `checkpoints/query_plan.response.json`:

```json
{
  "schema_version": 1,
  "checkpoint_id": "query_plan_001",
  "action": "continue",
  "queries": ["broad search query"]
}
```

3. Re-run `gaia research run` with the same package, topic, run id, profile,
   config, and env file:

```bash
gaia research run <pkg> --topic "<topic>" --run-id <run-id> --profile fast --json-stream
```

Only the second `run` invocation advances the state machine. `status` reports
state; it does not consume checkpoint responses.

## Discipline

Prefer CLI state over free-form memory. If the command fails, inspect
`gaia research doctor --for-agent --json` and `gaia research status` before
retrying.

Do not tune per-run search, LLM, focus, or evidence flags from chat unless the
user explicitly asks for low-level debugging. Put those settings in a profile
config file.

---
name: gaia-research-bootstrap
description: Use when Gaia Research readiness is unknown, a fresh runtime starts, Gaia CLI behavior looks incompatible, or the first research task in a workspace is about to run.
---

# Gaia Research Bootstrap

Use this before the first Gaia Research workflow in a fresh agent runtime.

## Steps

1. Run `gaia --version`.
2. Run `gaia research doctor --for-agent --json`. If local credentials live in
   a dotenv file, include `--env-file <path>`.
3. Run `gaia research capabilities --json`.
4. Run help commands only when `capabilities --json` is missing, Gaia versions
   look incompatible, or a command fails unexpectedly.
5. Confirm Bohrium/LKM access is configured through `GAIA_LKM_ACCESS_KEY`,
   `LKM_ACCESS_KEY`, or `gaia search lkm auth login`.
6. Confirm the LLM provider is configured through the explicit Gaia Research
   namespace: `GAIA_RESEARCH_LLM_MODEL`, `GAIA_RESEARCH_LLM_API_BASE`, and
   `GAIA_RESEARCH_LLM_API_KEY`.

## If Gaia Is Missing

Install released packages that satisfy the Bohrium agent requirements:

```bash
uv tool install "gaia-lang>=<minimum-release>"
uv tool install "gaia-research>=<minimum-release>"
```

Use the actual release versions from the deployment spec. Do not pin a Gaia
main commit in a production Bohrium agent unless the user explicitly asks for a
pre-release test.

## If Credentials Are Missing

For Bohrium Agents, ask the user or platform operator to configure secrets in
the agent runtime. Do not ask the user to paste secrets into chat unless no
secret manager is available.

Required LKM/Bohrium access:

```bash
export GAIA_LKM_ACCESS_KEY="<bohrium-access-key>"
```

or run:

```bash
gaia search lkm auth login
gaia search lkm auth status
```

Required LLM provider:

```bash
export GAIA_RESEARCH_LLM_MODEL="<litellm-model-name>"
export GAIA_RESEARCH_LLM_API_BASE="<llm-api-base>"
export GAIA_RESEARCH_LLM_API_KEY="<llm-api-key>"
```

Do not rely on `LITELLM_PROXY_*`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or
other provider-native variables for Gaia Research runs. Those may be present for
the host agent itself, but Gaia Research treats them as unrelated.

For local testing, put these values in a dotenv file and pass
`--env-file <path>` to both `gaia research doctor` and `gaia research run`.
Never print secret values back to the user.

## User-Facing Output

Report readiness, versions, missing requirements, and the next command. Do not
show raw JSON unless the user asks for debugging details.

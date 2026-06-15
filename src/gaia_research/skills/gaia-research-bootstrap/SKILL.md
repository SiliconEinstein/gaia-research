---
name: gaia-research-bootstrap
description: Use when Gaia Research readiness is unknown, a fresh runtime starts, Gaia CLI behavior looks incompatible, or the first research task in a workspace is about to run.
---

# Gaia Research Bootstrap

Use this before the first Gaia Research workflow in a fresh agent runtime.

## Package Facts

- Gaia CLI is the `gaia` command provided by Gaia core.
- The Gaia core Python distribution name is `gaia-lang`, not `gaia`.
- Gaia Research is the Python distribution named `gaia-research`.
- Installing `gaia-research` provides the standalone `gaia-research ...` CLI,
  the Gaia CLI plugin that exposes `gaia research ...`, and this Gaia skills
  entry point.
- Do not ask the user what Gaia CLI is, what package name to install, or where
  gaia-research comes from. Those facts are part of this skill.

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

Do not attempt a research run. If the user asked you to prepare a local
pre-release test runtime, create a project-local virtual environment and install
Gaia core plus Gaia Research from the project repositories:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install "gaia-lang @ git+https://github.com/SiliconEinstein/Gaia.git@main"
python -m pip install "gaia-research @ git+https://github.com/SiliconEinstein/gaia-research.git@codex/evidencemaster-agent-contract"
```

For production Bohrium deployments, ask the platform operator to install
released versions that satisfy the agent requirements:

```bash
uv tool install "gaia-lang>=<minimum-release>"
```

Then install Gaia Research into the same runtime where `gaia` runs:

```bash
uv tool install "gaia-research>=<minimum-release>"
```

Use the actual release versions from the deployment spec. Production Bohrium
agents should not pin a Gaia main commit unless the user explicitly asks for a
pre-release test.

## If `gaia research` Is Missing

If `gaia --version` works but `gaia research doctor --for-agent --json` fails
because the `research` command is missing, the runtime has Gaia CLI but lacks
the research plugin handoff or the `gaia-research` plugin package.

Ask the platform operator to install or upgrade both sides:

```bash
uv tool upgrade "gaia-lang>=<minimum-release>"
uv tool install --force "gaia-research>=<minimum-release>"
```

After installation, rerun:

```bash
gaia --version
gaia research doctor --for-agent --json
gaia research capabilities --json
```

Do not fall back to deprecated legacy research skills when `gaia research` is
missing.

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

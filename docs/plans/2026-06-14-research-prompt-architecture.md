# Research Prompt Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.
>
> **Parent context:**
> EvidenceMaster/Bohrium agent integration and the current `fast` profile.

**Goal:** Move Gaia Research phase prompts out of provider code, make them
auditable package assets, and create a clean iteration path for EvidenceMaster
`fast`.

**Architecture:** Keep CLI contracts and artifact validation in Python code.
Store LLM-facing system and phase prompts as package resources under
`src/gaia_research/prompts/`, loaded by a tiny typed helper. The LiteLLM
provider only assembles messages, calls the model, records traces, and never
owns research prompt content.

**Tech Stack:** Python 3.12, importlib.resources, Typer, LiteLLM, pytest,
ruff, mypy, Gaia Research artifacts.

---

## Scope

This plan is prompt architecture work, not a full prompt-quality rewrite.

Included:

- Move current hardcoded prompt strings and output-shape hints to package
  assets.
- Preserve current runtime behavior for `fast`, `broad`, and `deep`.
- Add tests proving packaged wheels can load prompts.
- Document how EvidenceMaster should iterate prompts.
- Define a second-phase prompt rewrite backlog for EvidenceMaster `fast`.

Excluded:

- Changing artifact JSON schemas.
- Adding new workflow phases.
- Rewriting every prompt in this PR.
- Reintroducing agent-authored JSON as the normal path.

## File Structure

- Create `src/gaia_research/prompts/__init__.py`: package marker for prompt
  resources.
- Create `src/gaia_research/prompts/research/__init__.py`: research prompt
  resource package marker.
- Create `src/gaia_research/prompts/research/system.md`: common JSON compiler
  system prompt.
- Create `src/gaia_research/prompts/research/query_plan.md`: query-planning
  prompt.
- Create `src/gaia_research/prompts/research/field_map_analysis.md`:
  field-map prompt.
- Create `src/gaia_research/prompts/research/focus_analysis.md`: focus prompt.
- Create `src/gaia_research/prompts/research/assess_analysis.md`: assessment
  prompt.
- Create `src/gaia_research/prompts/research/report_plan.md`: report-plan
  prompt.
- Create `src/gaia_research/prompts/research/report_section.md`: section-writing
  prompt.
- Create `src/gaia_research/prompts/research/report_stitch.md`: final-stitch
  prompt.
- Create `src/gaia_research/prompts/research/output_shapes.json`: compact
  output-shape hints keyed by phase.
- Create `src/gaia_research/prompt_assets.py`: typed prompt loading helpers.
- Modify `src/gaia_research/research_providers.py`: replace hardcoded phase
  prompts and output shapes with prompt asset loading.
- Modify `pyproject.toml`: ensure markdown/json prompt resources ship in wheels.
- Create `tests/test_prompt_assets.py`: prompt resource and wheel packaging
  tests.
- Modify `tests/test_research_providers.py`: assert LiteLLM messages use
  prompt assets.
- Create `docs/foundations/research-prompts.md`: durable prompt ownership and
  iteration guide.
- Modify `docs/specs/2026-06-14-evidencemaster-bohrium-agent.md`: reference
  the prompt ownership model and `fast` prompt iteration policy.

## Task 1: Add Prompt Asset Loader Tests

**Files:**
- Create: `tests/test_prompt_assets.py`

- [ ] **Step 1: Write failing tests for prompt asset loading**

  Add:

  ```python
  """Tests for packaged Gaia Research prompt assets."""

  from __future__ import annotations

  import json

  from gaia_research.prompt_assets import (
      RESEARCH_PROMPT_PHASES,
      load_research_output_shape,
      load_research_phase_prompt,
      load_research_system_prompt,
  )


  def test_research_system_prompt_is_packaged() -> None:
      prompt = load_research_system_prompt()

      assert "Return exactly one valid JSON object" in prompt
      assert "source refs and ids" in prompt


  def test_every_research_phase_has_prompt_and_shape() -> None:
      assert RESEARCH_PROMPT_PHASES == (
          "query_plan",
          "field_map_analysis",
          "focus_analysis",
          "assess_analysis",
          "report_plan",
          "report_section",
          "report_stitch",
      )

      for phase in RESEARCH_PROMPT_PHASES:
          prompt = load_research_phase_prompt(phase)
          shape = load_research_output_shape(phase)
          json.dumps(shape)
          assert len(prompt.strip()) > 40
          assert shape["required_top_level_keys"]


  def test_unknown_research_phase_fails_clearly() -> None:
      try:
          load_research_phase_prompt("unknown")
      except ValueError as exc:
          assert "unknown research prompt phase" in str(exc)
      else:
          raise AssertionError("expected unknown prompt phase to fail")
  ```

- [ ] **Step 2: Run test to verify it fails**

  Run:

  ```bash
  uv run pytest tests/test_prompt_assets.py -q
  ```

  Expected: failure because `gaia_research.prompt_assets` does not exist.

## Task 2: Create Prompt Assets And Loader

**Files:**
- Create: `src/gaia_research/prompts/__init__.py`
- Create: `src/gaia_research/prompts/research/__init__.py`
- Create: `src/gaia_research/prompts/research/system.md`
- Create: `src/gaia_research/prompts/research/query_plan.md`
- Create: `src/gaia_research/prompts/research/field_map_analysis.md`
- Create: `src/gaia_research/prompts/research/focus_analysis.md`
- Create: `src/gaia_research/prompts/research/assess_analysis.md`
- Create: `src/gaia_research/prompts/research/report_plan.md`
- Create: `src/gaia_research/prompts/research/report_section.md`
- Create: `src/gaia_research/prompts/research/report_stitch.md`
- Create: `src/gaia_research/prompts/research/output_shapes.json`
- Create: `src/gaia_research/prompt_assets.py`

- [ ] **Step 1: Add prompt package markers**

  Create empty marker files:

  ```python
  """Packaged prompt assets for Gaia Research."""
  ```

  and:

  ```python
  """Research workflow prompt assets."""
  ```

- [ ] **Step 2: Copy current system prompt into `system.md`**

  Use the current `research_providers.py` system content exactly:

  ```markdown
  You are Gaia's deterministic JSON compiler for research artifacts. Return
  exactly one valid JSON object. The first non-whitespace character must be `{`
  and the last must be `}`. Do not include markdown, prose, XML, citations
  outside JSON, or code fences. Use only source refs and ids present in the input
  artifact payloads.
  ```

- [ ] **Step 3: Copy current phase instructions into phase markdown files**

  Move each branch of `_litellm_phase_instruction()` into the matching `.md`
  file without semantic edits. For example `query_plan.md` must contain:

  ```markdown
  Generate 3-5 broad live-search queries for the topic. Cover distinct evidence
  families likely to support an autonomous review map: foundational theory,
  canonical models, methods/diagnostics, experiments where relevant, and recent
  controversies. Do not assess evidence yet.
  ```

  Repeat this exact move for `field_map_analysis`, `focus_analysis`,
  `assess_analysis`, `report_plan`, `report_section`, and `report_stitch`.

- [ ] **Step 4: Move output-shape hints into JSON**

  Create `output_shapes.json` with the same keys and payloads currently returned
  by `_litellm_output_shape()`:

  ```json
  {
    "query_plan": {
      "required_top_level_keys": ["queries"],
      "queries_item_shape": {
        "query": "search query text",
        "rationale": "why it helps"
      }
    }
  }
  ```

  Include all seven phases in the final file.

- [ ] **Step 5: Implement typed loader**

  Add:

  ```python
  """Packaged prompt loading helpers."""

  from __future__ import annotations

  import json
  from importlib.resources import files
  from typing import Any, cast

  _RESEARCH_PROMPTS_PACKAGE = "gaia_research.prompts.research"

  RESEARCH_PROMPT_PHASES = (
      "query_plan",
      "field_map_analysis",
      "focus_analysis",
      "assess_analysis",
      "report_plan",
      "report_section",
      "report_stitch",
  )


  def load_research_system_prompt() -> str:
      return _read_prompt_text("system.md")


  def load_research_phase_prompt(phase: str) -> str:
      if phase not in RESEARCH_PROMPT_PHASES:
          msg = f"unknown research prompt phase: {phase}"
          raise ValueError(msg)
      return _read_prompt_text(f"{phase}.md")


  def load_research_output_shape(phase: str) -> dict[str, Any]:
      if phase not in RESEARCH_PROMPT_PHASES:
          msg = f"unknown research prompt phase: {phase}"
          raise ValueError(msg)
      payload = json.loads(_read_prompt_text("output_shapes.json"))
      shape = payload.get(phase)
      if not isinstance(shape, dict):
          msg = f"missing output shape for research prompt phase: {phase}"
          raise ValueError(msg)
      return cast(dict[str, Any], shape)


  def _read_prompt_text(name: str) -> str:
      resource = files(_RESEARCH_PROMPTS_PACKAGE).joinpath(name)
      return resource.read_text(encoding="utf-8").strip()
  ```

- [ ] **Step 6: Run tests**

  Run:

  ```bash
  uv run pytest tests/test_prompt_assets.py -q
  ```

  Expected: pass.

## Task 3: Wire Provider To Prompt Assets

**Files:**
- Modify: `src/gaia_research/research_providers.py`
- Modify: `tests/test_research_providers.py`

- [ ] **Step 1: Add provider test for loaded prompt content**

  Add to `tests/test_research_providers.py`:

  ```python
  def test_litellm_messages_use_packaged_prompt_assets() -> None:
      messages = research_providers._litellm_messages(
          phase="query_plan",
          input_payload={"topic": "smoke"},
      )

      assert messages[0]["role"] == "system"
      assert "Return exactly one valid JSON object" in messages[0]["content"]
      assert messages[1]["role"] == "user"
      assert "Generate 3-5 broad live-search queries" in messages[1]["content"]
      assert "required_top_level_keys" in messages[1]["content"]
  ```

- [ ] **Step 2: Replace provider helper internals**

  Import the loader:

  ```python
  from gaia_research.prompt_assets import (
      load_research_output_shape,
      load_research_phase_prompt,
      load_research_system_prompt,
  )
  ```

  Change `_litellm_messages()` to call:

  ```python
  "content": load_research_system_prompt()
  ```

  and:

  ```python
  "instruction": load_research_phase_prompt(phase),
  "output_shape": load_research_output_shape(phase),
  ```

- [ ] **Step 3: Remove hardcoded provider prompt helpers**

  Delete `_litellm_phase_instruction()` and `_litellm_output_shape()` from
  `research_providers.py`. No caller should reference them after Step 2.

- [ ] **Step 4: Run provider tests**

  Run:

  ```bash
  uv run pytest tests/test_prompt_assets.py tests/test_research_providers.py -q
  ```

  Expected: pass.

## Task 4: Ensure Wheel Packaging Includes Prompt Assets

**Files:**
- Modify: `pyproject.toml`
- Modify: `tests/test_installed_wheel_smoke.py`

- [ ] **Step 1: Add explicit wheel artifact inclusion**

  Under `[tool.hatch.build.targets.wheel]`, keep the existing package setting
  and add:

  ```toml
  artifacts = [
    "src/gaia_research/prompts/**/*.md",
    "src/gaia_research/prompts/**/*.json",
  ]
  ```

- [ ] **Step 2: Add installed-wheel prompt smoke**

  Extend the installed wheel smoke so it runs:

  ```bash
  python -c "from gaia_research.prompt_assets import load_research_system_prompt; print(load_research_system_prompt()[:20])"
  ```

  Expected stdout prefix contains:

  ```text
  You are Gaia's
  ```

- [ ] **Step 3: Run wheel smoke**

  Run:

  ```bash
  uv run pytest tests/test_installed_wheel_smoke.py -q
  ```

  Expected: pass.

## Task 5: Document Prompt Ownership

**Files:**
- Create: `docs/foundations/research-prompts.md`
- Modify: `docs/foundations/README.md`
- Modify: `docs/specs/2026-06-14-evidencemaster-bohrium-agent.md`

- [ ] **Step 1: Add foundations doc**

  Create:

  ```markdown
  # Research Prompts

  Gaia Research owns the workflow prompts for `gaia research run`.

  Prompt assets live under `src/gaia_research/prompts/research/`. The provider
  layer loads these assets, combines them with live input payloads and output
  shape hints, and calls the configured LLM provider.

  CLI contracts remain the schema authority. Prompt text may describe desired
  behavior, but JSON validation, grounding repair, artifact writing, and render
  behavior stay in Python code.

  EvidenceMaster defaults to the `fast` profile. Prompt iteration should focus
  on `query_plan`, `field_map_analysis`, `focus_analysis`, `assess_analysis`,
  `report_plan`, `report_section`, and `report_stitch` in that order. `broad`
  and `deep` may reuse the same prompt assets until product testing justifies
  separate profile-specific prompts.
  ```

- [ ] **Step 2: Link foundations README**

  Add one bullet for `research-prompts.md`.

- [ ] **Step 3: Update EvidenceMaster spec**

  Add:

  ```markdown
  Agent-facing skills must not ask the platform agent to write phase JSON in the
  normal path. The agent invokes `gaia research run --profile fast`; Gaia
  Research loads packaged prompts and calls the configured LiteLLM provider.
  Prompt changes belong in `src/gaia_research/prompts/research/`, not in the
  Bohrium agent prompt.
  ```

## Task 6: Plan The Fast Prompt Rewrite Backlog

**Files:**
- Create: `docs/specs/2026-06-14-evidencemaster-fast-prompt-backlog.md`

- [ ] **Step 1: Create backlog doc**

  Add:

  ```markdown
  # EvidenceMaster Fast Prompt Backlog

  The first quality iteration targets `fast` only.

  ## Rewrite Order

  1. `query_plan`: produce fewer, sharper, domain-aware search queries.
  2. `field_map_analysis`: build a readable evidence map before choosing a
     focus.
  3. `focus_analysis`: choose one assessable focus with explicit readiness.
  4. `assess_analysis`: classify evidence without writing final report prose.
  5. `report_plan`: produce reader-facing section structure.
  6. `report_section`: write grounded, citation-preserving sections.
  7. `report_stitch`: polish without dropping evidence or converting to a
     summary.

  ## Quality Fixtures

  Keep at least three local prompt fixtures:

  - a biomedical topic with mixed clinical evidence;
  - a physical-science topic with theory and numeric evidence;
  - a sparse-evidence topic that should honestly report uncertainty.

  ## Acceptance Signals

  - The run completes without checkpoint responses when LLM env is configured.
  - The final report is readable to a human user.
  - Intermediate artifacts have rendered summaries.
  - No prompt asks the platform agent to hand-write JSON in the normal path.
  - Source refs are grounded in the input payloads.
  ```

- [ ] **Step 2: Run markdown and targeted tests**

  Run:

  ```bash
  uv run pytest tests/test_prompt_assets.py tests/test_research_providers.py -q
  ```

  Expected: pass.

## Task 7: Full Verification

**Files:**
- Verify only.

- [ ] **Step 1: Run prompt-related tests**

  Run:

  ```bash
  uv run pytest tests/test_prompt_assets.py tests/test_research_providers.py tests/test_installed_wheel_smoke.py -q
  ```

  Expected: pass.

- [ ] **Step 2: Run repository audit**

  Run:

  ```bash
  scripts/audit_goal_a.sh
  ```

  Expected: ruff, mypy, tests, and wheel smoke pass.

- [ ] **Step 3: Commit**

  Run:

  ```bash
  git add pyproject.toml src/gaia_research tests docs
  git commit -m "refactor: package research prompt assets"
  ```

  Expected: commit succeeds.

## Self-Review

- Spec coverage: The plan covers prompt assetization, provider wiring, wheel
  packaging, foundations docs, EvidenceMaster spec updates, and a fast-only
  prompt rewrite backlog.
- Placeholder scan: No implementation step uses TBD/TODO/fill-in language.
- Type consistency: Prompt phases are consistently named
  `query_plan`, `field_map_analysis`, `focus_analysis`, `assess_analysis`,
  `report_plan`, `report_section`, and `report_stitch`.

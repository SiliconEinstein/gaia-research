# EvidenceMaster Feedback Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.
>
> **Source feedback:**
> `docs/testing/2026-06-14-evidencemaster-gaia-feedback-report.md`

**Goal:** Address the CodeWhale E2E feedback for EvidenceMaster `fast` so stop
criteria, assessment input prioritization, report faithfulness, and run
observability match the behavior expected by a Bohrium agent user.

**Architecture:** Keep agent skills thin and fix the workflow engine first.
Use structured artifact metadata and provider input payloads to make LLM prompts
less ambiguous, then reinforce the behavior in prompt assets. Each behavioral
change must have an artifact-level unit test so future prompt edits do not hide
contract regressions.

**Tech Stack:** Python 3.12, Typer, LiteLLM, Gaia Research artifacts, packaged
Markdown prompt assets, pytest, ruff, mypy.

---

## Priority Summary

| Priority | Items | Rationale |
|---|---|---|
| P0 | BUG-1, ISSUE-5 | Directly affects stop decisions and whether new evidence is assessed. |
| P1 | ISSUE-1, ISSUE-2, ISSUE-3, ISSUE-4, BUG-3 | Improves final report faithfulness and user-visible run recovery. |
| P2 | BUG-2 | Important local runtime ergonomics, but partly Gaia core/materialization ownership. |

## File Structure

- Modify `src/gaia_research/stop.py`: compute query novelty metrics from
  assessment-grounded paper ids, including ids that appear in the assessment
  evidence packet.
- Modify `tests/test_research_stop.py`: reproduce the CodeWhale stop metric
  failure and lock the corrected ratios.
- Modify `src/gaia_research/evidence_selection.py`: annotate selected evidence
  items and paper leads with source landscape action and `is_new` where the
  record comes from an expansion landscape.
- Modify `tests/test_research_evidence_selection.py`: assert `is_new` and
  provenance fields survive selection.
- Modify `src/gaia_research/prompts/research/assess_analysis.md`: instruct the
  assessor to inspect new expansion evidence first and explain omitted relevant
  new evidence.
- Modify `src/gaia_research/prompts/research/report_plan.md`,
  `report_section.md`, and `report_stitch.md`: require scope boundaries,
  epistemic status language, obligations coverage, and assessment-controlled
  citation wording.
- Modify `src/gaia_research/research_report_writing.py`: add structured report
  context for coverage gaps, candidate obligations, epistemic statuses, and
  assessed-vs-packet-only refs to report provider inputs.
- Modify `tests/test_research_report.py`: assert report inputs and rendered
  Markdown preserve scope, obligations, and epistemic status.
- Modify `src/gaia_research/research_providers.py`: emit typed timeout/failure
  events for LiteLLM provider failures.
- Modify `src/gaia_research/research_cli.py` and `tests/test_cli_status.py`:
  make `status --json` report `stalled` when the latest provider start exceeds
  its TTL without completion/failure.
- Modify `docs/specs/2026-06-14-evidencemaster-fast-prompt-backlog.md`: record
  the prompt behavior changes as accepted fast-profile requirements.
- Modify `docs/testing/2026-06-14-evidencemaster-codewhale-v2-bug-list.md` or
  a follow-up testing note only if BUG-2 mitigation changes the local setup SOP.

## Non-Goals

- Do not add a new deep/broad workflow mode while fixing these issues.
- Do not make the agent write assessment/report JSON by hand.
- Do not hide provider failures by returning partial reports as success.
- Do not run `uv cache clean` automatically against a user's global cache.

## Task 1: Fix Stop Query Novelty Grounding Metrics (P0)

**Files:**
- Modify: `src/gaia_research/stop.py`
- Modify: `tests/test_research_stop.py`

- [ ] **Step 1: Add a failing regression test for assessment evidence-packet paper ids**

  Add a test where the current landscape has two new expand paper leads, the
  previous landscape has none of them, and the assessment evidence packet
  contains one selected item whose `source.paper_id` is one of those new papers.

  Expected assertions:

  ```python
  assert artifact["metrics"]["new_paper_leads"] == 2
  assert artifact["metrics"]["assessment_grounded_paper_leads"] == 1
  assert artifact["metrics"]["assessment_grounded_paper_lead_ratio"] == 0.5
  ```

  Run:

  ```bash
  uv run pytest -q tests/test_research_stop.py::test_stop_counts_grounded_new_paper_leads_from_assessment_packet
  ```

  Expected: fail before implementation because `assessment_grounded_paper_leads`
  is computed only through variable refs resolved against current landscapes.

- [ ] **Step 2: Add a helper that extracts paper ids from assessment evidence**

  In `src/gaia_research/stop.py`, add a helper conceptually equivalent to:

  ```python
  def _assessment_grounded_paper_ids(
      assessment: dict[str, Any] | None,
      landscapes: list[dict[str, Any]],
  ) -> set[str]:
      if assessment is None:
          return set()
      paper_ids = {
          paper_id
          for variable_id, paper_id in _paper_ids_by_variable(landscapes).items()
          if variable_id in _assessment_variable_ids(assessment)
      }
      evidence_packet = _dict(assessment.get("evidence_packet"))
      for item in _list(evidence_packet.get("items")):
          if not isinstance(item, dict):
              continue
          source = item.get("source")
          source_paper_id = source.get("paper_id") if isinstance(source, dict) else None
          paper_id = item.get("paper_id") or source_paper_id
          if isinstance(paper_id, str) and paper_id:
              paper_ids.add(paper_id)
      return paper_ids
  ```

  Use this helper inside `_query_novelty_dimension`.

- [ ] **Step 3: Count grounded novelty over new ids, not all current ids**

  Change the metric to track both total grounded papers and grounded new papers:

  ```python
  grounded_ids = _assessment_grounded_paper_ids(assessment, landscapes)
  grounded_new_ids = grounded_ids.intersection(new_ids)
  grounding_ratio = len(grounded_new_ids) / max(len(new_ids), 1)
  ```

  Keep `assessment_grounded_paper_leads` as the grounded-new count, because the
  feedback and current stop dimension use this number to evaluate whether new
  search results were actually used.

- [ ] **Step 4: Run focused and full tests**

  Run:

  ```bash
  uv run pytest -q tests/test_research_stop.py
  uv run pytest -q
  ```

## Task 2: Mark Expansion Evidence As New For Assessment (P0)

**Files:**
- Modify: `src/gaia_research/evidence_selection.py`
- Modify: `tests/test_research_evidence_selection.py`
- Modify: `src/gaia_research/prompts/research/assess_analysis.md`

- [ ] **Step 1: Add a failing test for expansion provenance**

  Build two landscapes in `tests/test_research_evidence_selection.py`: one
  `action="explore.scan"` and one `action="explore.expand"`. Assert selected
  items and matching paper leads from the expansion landscape include:

  ```python
  assert item["source_landscape_action"] == "explore.expand"
  assert item["is_new"] is True
  assert lead["source_landscape_action"] == "explore.expand"
  assert lead["is_new"] is True
  ```

- [ ] **Step 2: Add provenance when flattening landscapes**

  In `_evidence_packet_from_landscapes`, copy each item/lead and add:

  ```python
  action = landscape.get("action")
  item["landscape_index"] = landscape_index
  item["source_landscape_action"] = action
  item["is_new"] = action == "explore.expand"
  ```

  Apply the same fields to `paper_leads`.

- [ ] **Step 3: Update the assessment prompt**

  Amend `src/gaia_research/prompts/research/assess_analysis.md` to say:

  ```markdown
  Prioritize evidence items and paper leads marked `"is_new": true`; explicitly
  decide whether each materially relevant new item supports, qualifies,
  undercuts, or should be omitted as search noise.
  ```

- [ ] **Step 4: Verify packaged prompt tests**

  Run:

  ```bash
  uv run pytest -q tests/test_research_evidence_selection.py tests/test_prompt_assets.py
  ```

## Task 3: Carry Scope, Epistemic Status, And Obligations Into Reports (P1)

**Files:**
- Modify: `src/gaia_research/research_report_writing.py`
- Modify: `src/gaia_research/prompts/research/report_plan.md`
- Modify: `src/gaia_research/prompts/research/report_section.md`
- Modify: `src/gaia_research/prompts/research/report_stitch.md`
- Modify: `tests/test_research_report.py`

- [ ] **Step 1: Add tests for report provider input context**

  Add a test that constructs a focus artifact with `coverage_gaps`, an
  assessment with `relations[].epistemic_status`, and
  `candidate_obligations`. Stub the provider input capture and assert the
  `report_plan` input contains:

  ```python
  assert payload["report_context"]["coverage_gaps"]
  assert payload["report_context"]["candidate_obligations"]
  assert payload["report_context"]["epistemic_status_counts"]["candidate"] == 1
  assert payload["report_context"]["scope_note"]
  ```

- [ ] **Step 2: Build `report_context` in `research_report_writing.py`**

  Add a small helper that derives:

  - `covered_focus`: selected focus id/question/readiness
  - `coverage_gaps`: focus and field-map coverage gaps
  - `candidate_obligations`: copied from assessment
  - `epistemic_status_counts`: count of relation statuses
  - `assessed_ref_keys`: refs used by structured relations

  Pass this helper output into `report_plan`, `report_section`, and
  `report_stitch` input payloads.

- [ ] **Step 3: Update report prompts**

  Update prompt assets so:

  - `report_plan` must include an opening scope section when coverage gaps
    exist.
  - `report_section` must phrase `candidate` as preliminary and `provisional`
    as conditionally supported.
  - `report_section` must include candidate obligations in limitations/future
    work when they are in `report_context`.
  - `report_stitch` may polish wording but must not drop the scope statement,
    obligations, or epistemic caveats.

- [ ] **Step 4: Verify report and prompt tests**

  Run:

  ```bash
  uv run pytest -q tests/test_research_report.py tests/test_prompt_assets.py
  ```

## Task 4: Distinguish Structured Assessment Evidence From Packet-Only Evidence (P1)

**Files:**
- Modify: `src/gaia_research/research_report_writing.py`
- Modify: `src/gaia_research/prompts/research/report_section.md`
- Modify: `tests/test_research_report.py`

- [ ] **Step 1: Add a test for packet-only refs**

  Create one assessment relation citing `variable:A` and one evidence packet
  item for `variable:B`. Ask a report section to use both refs and assert
  `section_evidence` marks:

  ```python
  assert relation_item["assessment_status"] == "structured_relation"
  assert packet_only_item["assessment_status"] == "packet_only"
  ```

- [ ] **Step 2: Annotate section evidence**

  In `_collect_report_section_evidence`, compute relation-backed refs from
  `_relation_report_ref_keys`. When adding packet records, set
  `assessment_status` to `"structured_relation"` if any item ref is relation
  backed, otherwise `"packet_only"`.

- [ ] **Step 3: Update report wording prompt**

  Add to `report_section.md`:

  ```markdown
  Treat `assessment_status="structured_relation"` as assessed evidence. Treat
  `assessment_status="packet_only"` as background or additional evidence only;
  do not phrase it as an assessment conclusion.
  ```

## Task 5: Make Provider Hangs Observable And Recoverable (P1)

**Files:**
- Modify: `src/gaia_research/research_providers.py`
- Modify: `src/gaia_research/research_cli.py`
- Modify: `tests/test_research_providers.py`
- Modify: `tests/test_cli_status.py`

- [ ] **Step 1: Add a provider timeout/failure event test**

  In `tests/test_research_providers.py`, monkeypatch `_litellm_completion` to
  raise `TimeoutError("timed out")`. Assert `events.ndjson` contains a typed
  event:

  ```python
  assert event["type"] in {"provider.timeout", "provider.failed"}
  assert event["phase"] == "report_plan"
  assert event["payload"]["timeout_seconds"] == 1.0
  ```

- [ ] **Step 2: Emit typed provider failure events**

  In `_run_analysis_provider_litellm`, distinguish timeout exceptions from
  generic failures:

  ```python
  event_type = "provider.timeout" if isinstance(exc, TimeoutError) else "provider.failed"
  ```

  Include `timeout_seconds`, `input`, `output`, `raw_path`, `model`, and
  `error_type` in the event payload before writing `run.failed`.

- [ ] **Step 3: Add stalled status detection**

  In `status --json`, inspect recent events. If the latest provider event for a
  phase is `provider.started` and no matching `provider.completed`,
  `provider.failed`, `provider.timeout`, or `run.failed` exists after it, and
  the run age exceeds the configured LLM timeout plus a small grace window,
  return:

  ```json
  {
    "status": "stalled",
    "stalled_phase": "report_plan",
    "stalled_reason": "provider.started without terminal event"
  }
  ```

- [ ] **Step 4: Verify status tests**

  Run:

  ```bash
  uv run pytest -q tests/test_research_providers.py tests/test_cli_status.py
  ```

## Task 6: Handle macOS `uv` Cache Failures Without Touching Global Cache (P2)

**Files:**
- Modify: `docs/testing/2026-06-14-evidencemaster-codewhale-v2-bug-list.md`
- Modify: `src/gaia_research/skills/gaia-research-bootstrap/SKILL.md`
- Modify: `src/gaia_research/skills/gaia-research-run/SKILL.md`
- Optional modify: `src/gaia_research/research_cli.py`
- Optional test: `tests/test_agent_platform_contract.py`

- [ ] **Step 1: Keep the safe workaround in agent-facing docs**

  Document that local CodeWhale/macOS agent tests should set:

  ```bash
  export UV_CACHE_DIR="$PWD/.uv-cache"
  ```

  before invoking `gaia research run` if `uv` reports
  `Operation not permitted` under `~/.cache/uv`.

- [ ] **Step 2: Do not run `uv cache clean` automatically**

  The feedback suggested cleaning or probing the global cache. Do not implement
  automatic global cache mutation in Gaia Research. That would be surprising in
  an agent runtime and may cross ownership boundaries.

- [ ] **Step 3: Add a doctor hint if we keep this in Gaia Research**

  If we decide to surface this in CLI, make `doctor --for-agent --json` include
  a non-secret advisory field:

  ```json
  {
    "runtime_hints": {
      "uv_cache_dir": {
        "env_var": "UV_CACHE_DIR",
        "recommended_for_sandbox": "$PWD/.uv-cache"
      }
    }
  }
  ```

  Add a test in `tests/test_agent_platform_contract.py` that the advisory exists
  and does not require probing the user's home cache.

## Rollout Order

1. Land Task 1 and Task 2 together. This is the minimum useful correction for
   EvidenceMaster `fast` quality.
2. Run a local fast E2E with the same cuprate topic and compare
   `stop.json`, `assess_analysis.input.json`, and final report scope wording.
3. Land Task 3 and Task 4. These improve human-readable report faithfulness.
4. Land Task 5. This improves agent observability when providers hang.
5. Land Task 6 as documentation/doctor polish unless Gaia core owns the final
   materialization-side cache behavior.

## Acceptance Checks

- `stop.json` reports grounded-new paper leads consistently with assessment
  evidence packet paper ids.
- `assess_analysis.input.json` makes expansion evidence visible via `is_new`.
- Final report contains a scope statement when field/focus coverage gaps exist.
- Final report includes candidate obligations in limitations or future work.
- Final report wording reflects `candidate` vs `provisional` status.
- Packet-only evidence is not phrased as a structured assessment conclusion.
- A provider timeout emits a typed terminal event and `status --json` can report
  stalled runs.
- `scripts/audit_goal_a.sh` passes before merging.

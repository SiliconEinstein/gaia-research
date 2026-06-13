# Report Workflow Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.
>
> **Parent spec:**
> [Research Workflow Parity Acceptance](../specs/2026-06-13-research-workflow-parity-acceptance.md)

**Goal:** Make `gaia-research` own the current topic-to-report workflow with
parity for the existing Gaia research and `gaia-lkm-explore` upper workflow
surfaces.

**Architecture:** Keep Gaia core as the primitive substrate and move workflow
orchestration into `gaia-research`. The CLI and Gaia plugin are thin adapters
over one engine API that writes durable artifacts under `.gaia/research/runs/`.
This is a code ownership migration, not a wrapper over Gaia core's upper
research implementation.

**Tech Stack:** Python, Typer, argparse, pytest, ruff, mypy, Gaia core public
surfaces, saved `gaia search lkm` JSON payloads, `.gaia/research` artifacts.

---

## Scope

This plan implements report workflow parity only:

```text
topic -> landscape -> field map -> focus selection
  -> assessment/report-ready artifact -> materialization decision -> report
```

It does not implement large graph-session expansion, O(N) long-running graph
growth, deep/broad expansion policies, LKM writeback, or public registry
publication. The engine boundaries should leave room for those future features,
but they are not acceptance criteria for this milestone.

## File Structure

- Create `docs/foundations/report-workflow.md`: canonical workflow design for
  topic-to-report parity.
- Create `docs/foundations/landscape-field-map-focus.md`: migrated and rewritten
  design for landscape, field-map, and focus artifacts.
- Create `docs/foundations/materialization-policy.md`: rules for when research
  artifacts may be promoted into Gaia source through `gaia add`,
  `gaia inquiry`, or `gaia author`.
- Create `docs/plans/2026-06-13-report-workflow-parity-implementation.md`: this
  implementation plan.
- Create `src/gaia_research/workflow.py`: public engine entry points
  `run_report_workflow()` and `resume_report_workflow()`.
- Create `src/gaia_research/workflow_state.py`: dataclasses and JSON helpers
  for run state, stage status, and artifact paths.
- Create `src/gaia_research/landscape.py`: deterministic landscape builder
  adapted from Gaia core `gaia.lkm_explorer.engine.landscape`.
- Create `src/gaia_research/artifacts.py`: deterministic scope, focus,
  workflow artifact, gate, field-map, and materialization-decision builders.
- Create `src/gaia_research/lkm.py`: adapter for saved LKM search payloads and,
  later, Gaia core LKM search primitive calls.
- Create `src/gaia_research/report.py`: final report assembly over research
  artifacts.
- Modify `src/gaia_research/cli.py`: add primary `report` command.
- Modify `src/gaia_research/plugin.py`: expose `gaia research report`.
- Modify `README.md`: update examples from `review` to `report`.
- Modify `AGENTS.md`: keep the same-PR foundations update rule current.
- Create `tests/test_workflow_state.py`: state path and resume contract tests.
- Create `tests/test_landscape.py`: deterministic LKM payload aggregation tests.
- Create `tests/test_artifacts.py`: field-map, focus, gate, and materialization
  artifact tests.
- Create `tests/test_report_workflow.py`: end-to-end topic-to-report workflow
  tests with stubbed LKM inputs.
- Create `tests/test_cli_report.py`: report-command tests.
- Modify `tests/test_cli_plugin.py`: add `gaia research report` plugin tests.
- Modify `tests/test_source_boundary.py`: keep Gaia core imports behind declared
  dynamic surfaces or subprocess adapters.

## Task 1: Foundations Migration

**Files:**
- Create: `docs/foundations/report-workflow.md`
- Create: `docs/foundations/landscape-field-map-focus.md`
- Create: `docs/foundations/materialization-policy.md`
- Modify: `docs/foundations/README.md`
- Modify: `README.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: Write the foundations docs**

  `docs/foundations/report-workflow.md` must state:

  ```markdown
  # Report Workflow

  The current parity workflow starts from a topic and produces a cited report:

  topic -> landscape -> field map -> focus selection
    -> assessment/report-ready artifact -> materialization decision -> report

  Gaia core remains the primitive owner for `gaia search lkm`, `gaia add`,
  `gaia inquiry`, `gaia author`, package checks, inference, and rendering.
  `gaia-research` owns the orchestration and writes workflow artifacts under
  `.gaia/research/runs/<run-id>/`.

  The CLI must be a thin adapter over the engine API. Product calls, agent
  skills, standalone CLI calls, and `gaia research report` must all call the
  same workflow implementation.
  ```

  `docs/foundations/landscape-field-map-focus.md` must define:

  ```markdown
  # Landscape, Field Map, And Focus

  Landscape is a neutral paper-lead aggregation over saved or freshly generated
  `gaia search lkm` results.

  Field map groups paper leads and candidate concepts into provisional regions
  without writing stable Gaia source.

  Focus selection chooses assessment targets from the field map. Focus rows
  must carry evidence references before they can feed assessment.
  ```

  `docs/foundations/materialization-policy.md` must define:

  ```markdown
  # Materialization Policy

  Raw search hits, paper leads, field-map clusters, candidate nodes, and
  candidate relations are research artifacts until explicitly promoted.

  Use `gaia add` for accepted stable content. Use `gaia inquiry` for accepted
  obligations and process work. Use `gaia author` when report generation needs
  authored Gaia source. A report workflow must record the materialization
  decision even when the decision is "do not promote yet".
  ```

- [ ] **Step 2: Link foundations from README and AGENTS**

  Update `docs/foundations/README.md` so it links the three new files and says
  old Gaia-core docs are prior art unless rewritten here.

  Update `README.md` and `AGENTS.md` only if the current wording stops pointing
  contributors to `docs/foundations/`.

- [ ] **Step 3: Verify docs are discoverable**

  Run:

  ```bash
  rg "report workflow|Landscape|Materialization Policy" docs/foundations README.md AGENTS.md
  ```

  Expected: output includes all three new foundation documents and at least one
  top-level pointer from `README.md` or `AGENTS.md`.

- [ ] **Step 4: Commit**

  ```bash
  git add docs/foundations README.md AGENTS.md
  git commit -m "docs: migrate report workflow foundations"
  ```

## Task 2: Workflow State Contract

**Files:**
- Create: `src/gaia_research/workflow_state.py`
- Create: `tests/test_workflow_state.py`

- [ ] **Step 1: Write failing state tests**

  Create tests that assert a run writes paths under:

  ```text
  <workspace>/.gaia/research/runs/<run-id>/
    state.json
    events.ndjson
    landscape/
    field_map/
    focuses/
    assessments/
    materialization/
    reports/
  ```

  Required test cases:

  - `create_report_run()` creates every directory above.
  - `write_state()` and `read_state()` round-trip topic, profile, phase, status,
    and artifact paths.
  - `record_event()` appends one JSON line per event.
  - `resume_report_run()` rejects missing `state.json` with `FileNotFoundError`.

- [ ] **Step 2: Run failing tests**

  ```bash
  uv run pytest -q tests/test_workflow_state.py
  ```

  Expected: FAIL because `gaia_research.workflow_state` does not exist yet.

- [ ] **Step 3: Implement state helpers**

  Implement dataclasses:

  ```python
  @dataclass(frozen=True)
  class ReportRunHandle:
      workspace: Path
      run_id: str
      run_dir: Path
      state_path: Path
      events_path: Path
      landscape_dir: Path
      field_map_dir: Path
      focuses_dir: Path
      assessments_dir: Path
      materialization_dir: Path
      reports_dir: Path

  @dataclass(frozen=True)
  class ReportRunState:
      run_id: str
      topic: str
      profile: str
      status: str
      phase: str
      created_at: str
      updated_at: str
      artifacts: dict[str, str]
  ```

  Provide `create_report_run()`, `read_state()`, `write_state()`,
  `record_event()`, and `resume_report_run()`.

- [ ] **Step 4: Run state tests**

  ```bash
  uv run pytest -q tests/test_workflow_state.py
  ```

  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add src/gaia_research/workflow_state.py tests/test_workflow_state.py
  git commit -m "feat: add report workflow state contract"
  ```

## Task 3: Landscape Builder

**Files:**
- Create: `src/gaia_research/lkm.py`
- Create: `src/gaia_research/landscape.py`
- Create: `tests/test_landscape.py`

- [ ] **Step 1: Write failing landscape tests**

  Use fixture dictionaries shaped like saved `gaia search lkm knowledge --json`
  payloads. Tests must cover:

  - duplicate paper IDs across queries merge into one lead;
  - best rank wins;
  - query provenance is preserved in first-seen order;
  - already materialized paper IDs are excluded;
  - the output kind is `research_landscape`, not `exploration_landscape`.

- [ ] **Step 2: Run failing tests**

  ```bash
  uv run pytest -q tests/test_landscape.py
  ```

  Expected: FAIL because the new landscape module does not exist.

- [ ] **Step 3: Implement landscape without static Gaia imports**

  Port the deterministic behavior from Gaia core
  `gaia.lkm_explorer.engine.landscape`, but do not import that module
  statically. Keep the output schema owned by `gaia-research`:

  ```python
  LANDSCAPE_SCHEMA_VERSION = 1
  LANDSCAPE_KIND = "research_landscape"
  ```

  `src/gaia_research/lkm.py` should expose a small function that extracts paper
  leads from saved LKM payloads. If Gaia core has no stable public callable for
  this yet, implement the minimal parser against the payload fixture and mark
  the public-surface gap in `docs/execution-record.md`.

- [ ] **Step 4: Run landscape and source-boundary tests**

  ```bash
  uv run pytest -q tests/test_landscape.py tests/test_source_boundary.py
  ```

  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add src/gaia_research/lkm.py src/gaia_research/landscape.py tests/test_landscape.py docs/execution-record.md
  git commit -m "feat: port research landscape builder"
  ```

## Task 4: Field Map, Focus, Gate, And Materialization Artifacts

**Files:**
- Create: `src/gaia_research/artifacts.py`
- Create: `tests/test_artifacts.py`

- [ ] **Step 1: Write failing artifact tests**

  Tests must assert:

  - field map groups landscape leads into deterministic clusters;
  - focus rows carry `evidence_refs`;
  - a gate report blocks when no focus has evidence refs;
  - a materialization decision can record `defer`, `gaia_add`, `gaia_inquiry`,
    or `gaia_author`;
  - artifact paths use `.gaia/research/runs/<run-id>/`, never
    `.gaia/exploration/`.

- [ ] **Step 2: Run failing tests**

  ```bash
  uv run pytest -q tests/test_artifacts.py
  ```

  Expected: FAIL because artifact builders do not exist.

- [ ] **Step 3: Implement deterministic builders**

  Implement these functions:

  ```python
  build_field_map(landscape: dict[str, object]) -> dict[str, object]
  build_focuses(field_map: dict[str, object]) -> dict[str, object]
  build_assessment_gate(focuses: dict[str, object]) -> dict[str, object]
  build_materialization_decision(
      focuses: dict[str, object],
      *,
      decision: str = "defer",
  ) -> dict[str, object]
  ```

  Use schema strings owned by this repo, for example
  `gaia.research.artifact.v1`.

- [ ] **Step 4: Run artifact tests**

  ```bash
  uv run pytest -q tests/test_artifacts.py
  ```

  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add src/gaia_research/artifacts.py tests/test_artifacts.py
  git commit -m "feat: add report workflow artifacts"
  ```

## Task 5: Engine Workflow

**Files:**
- Create: `src/gaia_research/workflow.py`
- Create: `src/gaia_research/report.py`
- Create: `tests/test_report_workflow.py`
- Modify: `src/gaia_research/workflow_state.py`

- [ ] **Step 1: Write failing workflow tests**

  Test with stubbed saved LKM payloads and stubbed report rendering. Required
  assertions:

  - `run_report_workflow(topic, workspace, policy)` creates a run;
  - the run writes landscape, field map, focuses, gate, materialization
    decision, and final report artifacts;
  - `state.json` ends with `status="completed"` and `phase="report"`;
  - report text references the landscape and focus artifacts it used;
  - no Gaia source is written when materialization decision is `defer`.

- [ ] **Step 2: Run failing tests**

  ```bash
  uv run pytest -q tests/test_report_workflow.py
  ```

  Expected: FAIL because `workflow.py` does not exist.

- [ ] **Step 3: Implement the engine API**

  Implement:

  ```python
  def run_report_workflow(
      *,
      topic: str,
      workspace: str | Path,
      profile: str = "fast",
      run_id: str | None = None,
      lkm_payloads: Sequence[Mapping[str, object]] | None = None,
      materialization_decision: str = "defer",
  ) -> ReportWorkflowResult:
      ...

  def resume_report_workflow(
      *,
      workspace: str | Path,
      run_id: str,
  ) -> ReportWorkflowResult:
      ...
  ```

  The first implementation may require `lkm_payloads` or saved payload paths in
  tests. Fresh LKM search execution can be introduced after the state and
  artifact contract is stable.

- [ ] **Step 4: Run workflow tests**

  ```bash
  uv run pytest -q tests/test_report_workflow.py tests/test_workflow_state.py
  ```

  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add src/gaia_research/workflow.py src/gaia_research/report.py src/gaia_research/workflow_state.py tests/test_report_workflow.py
  git commit -m "feat: add report workflow engine"
  ```

## Task 6: CLI And Plugin Command Rename

**Files:**
- Modify: `src/gaia_research/cli.py`
- Modify: `src/gaia_research/plugin.py`
- Create: `tests/test_cli_report.py`
- Modify: `tests/test_cli_plugin.py`
- Modify: `README.md`

- [ ] **Step 1: Write failing CLI tests**

  Standalone CLI tests must call:

  ```bash
  gaia-research report --topic dqcp --workspace <tmp> --run-id cli-run --json
  ```

  Plugin tests must call:

  ```bash
  gaia research report --topic dqcp --workspace <tmp> --run-id plugin-run --json
  ```

  The JSON payload must include `run_id`, `status`, `phase`, `run_dir`,
  `report`, and `events`.

- [ ] **Step 2: Run failing CLI tests**

  ```bash
  uv run pytest -q tests/test_cli_report.py tests/test_cli_plugin.py
  ```

  Expected: FAIL because the report command does not exist yet.

- [ ] **Step 3: Add `report`**

  Add `report` as the primary command. Do not restore `review`; it was an
  inquiry review bridge and is not part of research workflow parity.

- [ ] **Step 4: Update README examples**

  Replace primary examples with `gaia-research report` and
  `gaia research report`.

- [ ] **Step 5: Run CLI tests**

  ```bash
  uv run pytest -q tests/test_cli_report.py tests/test_cli_plugin.py
  ```

  Expected: PASS.

- [ ] **Step 6: Commit**

  ```bash
  git add src/gaia_research/cli.py src/gaia_research/plugin.py tests/test_cli_report.py tests/test_cli_plugin.py README.md
  git commit -m "feat: expose report workflow commands"
  ```

## Task 7: Gaia-Core Deprecation PR

**Files in Gaia core repository:**
- Modify Gaia core CLI handoff tests for `gaia research`.
- Modify Gaia core script registration or help text for `gaia-lkm-explore`.
- Modify Gaia core docs that still describe `gaia-lkm-explore` as canonical.

- [ ] **Step 1: Inventory upper workflow surfaces**

  In Gaia core, run:

  ```bash
  rg "gaia-lkm-explore|gaia research|lkm_explorer|research" pyproject.toml gaia docs tests
  ```

  Classify every result as primitive, upper workflow, docs prior art, or test.
  Do not deprecate `gaia search lkm`.

- [ ] **Step 2: Write failing Gaia-core tests**

  Add tests that assert:

  - `gaia search lkm` remains available;
  - `gaia research report` is served through the installed plugin;
  - `gaia-lkm-explore --help` shows deprecation text or is removed only after
    replacement parity exists.

- [ ] **Step 3: Implement deprecation/handoff**

  Keep Gaia core as primitive owner. Make upper workflow help text point to
  `gaia-research report` and `gaia research report`.

- [ ] **Step 4: Run Gaia-core gates**

  ```bash
  uv run pytest -q tests/cli
  uv run pytest -q tests -m "pr_gate and not slow"
  ```

  Expected: PASS.

- [ ] **Step 5: Commit in Gaia core**

  ```bash
  git add gaia tests docs pyproject.toml
  git commit -m "refactor(research): hand off report workflow"
  ```

## Task 8: Cross-Repo Parity Audit

**Files:**
- Create: `scripts/audit_report_workflow_parity.sh`
- Create or modify: CI workflow once the audit is stable.
- Modify: `README.md`

- [ ] **Step 1: Write the audit script**

  The script must:

  - install Gaia core and `gaia-research`;
  - run `gaia-research report --json` against a fixture workspace;
  - run `gaia research report --json` through Gaia plugin handoff;
  - verify artifact existence for landscape, field map, focuses, assessment
    gate, materialization decision, and report;
  - fail if output uses hidden Gaia-core upper workflow implementation paths.

- [ ] **Step 2: Run local audit**

  ```bash
  scripts/audit_report_workflow_parity.sh
  ```

  Expected: PASS with run id, status, artifact paths, report path, and event
  count printed.

- [ ] **Step 3: Commit**

  ```bash
  git add scripts/audit_report_workflow_parity.sh README.md
  git commit -m "test: audit report workflow parity"
  ```

## Final Verification

Run in `gaia-research`:

```bash
uv run pytest -q
uv run ruff check src tests
uv run mypy src tests
uv build --wheel --out-dir dist
scripts/smoke_installed_wheel.sh
```

Run in Gaia core after the deprecation PR:

```bash
uv run pytest -q tests/cli
uv run pytest -q -m "pr_gate and not slow"
```

Completion evidence:

- `gaia-research report --topic ...` works from a clean install.
- `gaia research report --topic ...` works through Gaia plugin handoff.
- Gaia core no longer owns upper report workflow execution.
- `gaia-lkm-explore` is deprecated or removed as a canonical product workflow
  surface.
- `gaia search lkm` remains a Gaia core primitive.
- Foundations docs and execution record are updated in the same PRs as the code
  that changed behavior.

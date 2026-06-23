# Gaia-Native Research MVP

This document defines the smallest Gaia-native EvidenceMaster workflow worth
building. The goal is not to reproduce a full evidence-review platform. The MVP
only validates whether a research run can create reusable Gaia graph assets.

## Core Principle

The durable output of an MVP research run is a scoped set of Gaia-native
research assets:

```text
question
new Gaia `claim(...)` records with candidate/provisional metadata
candidate relations among existing claims
candidate relations between existing claims and newly authored Gaia claims
open obligations
```

The evidence matrix is a view over candidate relation metadata, not an
independent source of truth.

## MVP Flow

```text
topic or focus
  -> one Gaia question
  -> retrieve existing LKM claim/question hits
  -> materialize each hit's backing paper package
  -> resolve hit claims/questions to package-local Gaia symbols
  -> generate new Gaia claims with candidate/provisional metadata
  -> propose existing-existing candidate relations
  -> propose existing-new candidate relations
  -> derive evidence matrix rows from relation metadata
  -> create open inquiry obligations for unresolved high-value gaps
  -> record whether open obligations should be continued now or explicitly
     deferred
```

The MVP success contract does not require field maps, multi-focus scheduling,
profile-specific per-action budget tuning, rich obligation ledgers, report
generation, or inference-backed formalization. A profile may still use field
maps or other context-building steps before graph-asset authoring. The MVP
includes a lightweight shared budget envelope plus an obligation scheduler:
open obligations are either selected as the next workflow action or explicitly
deferred. When a live LLM provider is available, the scheduler can use an
advisory obligation-policy score to adjust ordering to the current research
need; deterministic validation still decides whether an action is executable.
Full multi-round execution is built on this scheduler rather than a separate MVP
mode.

## LKM Dependency Decision

The MVP uses Gaia package management as the only default dependency layer for
LKM search results.

Default materialization is package-shaped:

```text
gaia pkg add --lkm-paper <paper_id>
```

All LKM search surfaces are normalized to a backing paper package before they
enter relation authoring:

- `gaia search lkm knowledge` claim/question hits use their LKM provenance to
  identify the backing `paper_id`;
- `gaia search lkm package` results already identify the backing paper/package;
- `gaia search lkm reasoning` or chain results use the relevant claim only to
  recover the backing paper when possible.

The workflow installs by paper and tracks by claim:

```text
LKM hit claim/question C
  -> backing source ref lkm:<index>:paper:<paper_id>
  -> one Gaia dependency for that paper
  -> C resolves to a concrete claim/question symbol inside that dependency
```

The claim/question hit must remain a first-class anchor after materialization.
This is a lookup layer, not a second dependency layer. Each selected LKM hit
should keep enough data to recover:

- the original LKM hit id or node id;
- its `kind` (`claim` or `question`);
- its backing `lkm:<index>:paper:<paper_id>` source ref;
- the materialized package `import_name`;
- the package-local `symbol` and claim/question-level `ref`, once resolved.

For a given `lkm:<index>:paper:<paper_id>`, Gaia Research must create at most
one Gaia package dependency. If an early landscape scan finds claim `C` from a
paper and a later step needs the whole paper, the later step reuses or upgrades
the same paper dependency. It must not install a second shallow package for the
same paper.

Candidate relations never point at a package as a whole. They point at
claim-level endpoints:

```text
package dependency -> import_name + symbol -> claim endpoint
```

The original search hit remains the attention anchor for focus selection,
evidence selection, and relation planning. Pulling the whole paper package does
not mean dumping the whole package into prompts; context hydration should pass
only the anchored claim/question, compact paper metadata, selected neighboring
claims or chains, and the concrete claim refs needed for the current step.

Materialization budget and assessment budget are different controls. Once a
landscape step has admitted LKM papers into the candidate corpus, those backing
paper packages should enter Gaia dependency management by default. Evidence
selection budgets such as selected items, selected papers for prompt diversity,
or matrix rows may limit what is read, judged, hydrated, or authored into
relations, but they must not silently cap which candidate paper packages are
installed. Failed or deferred package materialization should become obligations
or deferred records.

Assessment worksets should be large enough to support actual judgment. Product
run entrypoints should require at least 10 selected evidence items per focus
when enough candidates exist. Lower limits are debug or unit-test controls, not
normal research-run behavior.

Selected-evidence artifacts should remain compact. They may include the
materialization plan, a materialization manifest path, and a small summary, but
must not embed the full package materialization result. The full result belongs
in a separate `evidence_materialization` artifact that can be inspected or
replayed without flooding assessment prompts.

Graph-assets output should therefore expose a corpus funnel separately from the
assessment funnel:

```text
candidate corpus papers
  -> package materialization requests
  -> selected evidence anchors for assessment
  -> resolved refs used in candidate relations
```

`gaia pkg add --lkm-claim` and chain materialization are not MVP defaults. They
may be used only as resolver or deep-evidence fallbacks when a claim hit cannot
be mapped to a unique paper through search provenance, or when a later workflow
explicitly asks for focused reasoning-chain evidence.

## Asset Semantics

### Question

The question scopes the run. It is not a relation endpoint.

```python
rq_dqc_order = question(
    "Is deconfined criticality continuous or weakly first-order?",
    title="dqc-order",
    metadata={"gaia_research": {"kind": "research_question"}},
)
```

### New Gaia Claims With Candidate Status

New research claims are newly proposed scientific assertions generated by the
research run. They may answer the scoped question, but they are not treated as
settled conclusions. They are ordinary Gaia `claim(...)` objects written into
the local development package with metadata marking their source, category, and
candidate/provisional status. There is no separate Gaia object type for
candidate claims.

Authoring performs only deterministic duplicate avoidance on new research
claims. If an already authored local claim has the same normalized text, the new
analysis id is mapped to the existing binding and relations reuse that binding.
The MVP does not attempt LLM-based semantic deduplication; near-duplicates can
be left as provisional claims or flagged later through obligations.

```python
dqc_weak_first_order = claim(
    "Deconfined criticality is better described as a weak first-order transition "
    "in the studied lattice-model regimes.",
    title="dqc-weak-first-order",
    metadata={
        "gaia_research": {
            "kind": "research_claim",
            "answers_question": "dqc-order",
            "status": "candidate",
        }
    },
)
```

### Candidate Relations

Candidate relations are the primary evidence-analysis asset. They connect claims
only. A relation may connect:

- an existing claim to another existing claim;
- an existing claim to a newly authored Gaia claim;
- one newly authored Gaia claim to another, when needed.

The MVP only requires the first two.

Assessment prompts should encourage dense grounded relation capture rather than
a thin summary. When endpoints are visible, the assessor should write both
existing-existing relations between pulled package claims and existing-new
relations between pulled package claims and newly authored research claims,
without inventing endpoints or padding weak rows to satisfy a quota.

Use Gaia's native `pattern` only for relation shapes Gaia understands:

```text
equal
contradict
exclusive
None
```

Other evidence-analysis stances are stored under `metadata.gaia_research`.

```python
candidate_relation(
    claims=[finite_size_drift_claim, dqc_weak_first_order],
    pattern=None,
    rationale=(
        "Finite-size drift may support the weak first-order interpretation, "
        "but the relation remains scaffolded."
    ),
    metadata={
        "gaia_research": {
            "kind": "candidate_relation",
            "scope_question": "dqc-order",
            "relation_type": "supports",
            "strength": "moderate",
            "scope_note": "Applies to studied lattice-model regimes.",
            "source_refs": ["gcn_example"],
        }
    },
)
```

For competing existing claims, use `pattern="contradict"` when the relation is
explicitly a contradiction:

```python
candidate_relation(
    claims=[continuous_transition_claim, weak_first_order_claim],
    pattern="contradict",
    rationale="These claims make competing assertions about the same regime.",
    metadata={
        "gaia_research": {
            "kind": "candidate_relation",
            "scope_question": "dqc-order",
            "relation_type": "conflicts",
        }
    },
)
```

## Evidence Matrix Projection

The evidence matrix is derived from `candidate_relation` records. It is a table
view for inspection and downstream consumers.

Minimum derived row:

```json
{
  "source_claim_id": "finite_size_drift_claim",
  "target_claim_id": "dqc_weak_first_order",
  "pattern": null,
  "relation_type": "supports",
  "strength": "moderate",
  "scope_question": "dqc-order",
  "scope_note": "Applies to studied lattice-model regimes.",
  "rationale": "Finite-size drift may support the weak first-order interpretation.",
  "source_refs": ["gcn_example"]
}
```

Rows without a `candidate_relation` do not enter the MVP matrix. Search hits,
unjudged context, and omitted but potentially relevant evidence stay outside
the matrix until they are attached to a claim-claim candidate relation.

### Extended Matrix Fields

The MVP matrix has a small required surface, but relation metadata may carry
richer cross-disciplinary assessment fields. These fields live under
`candidate_relation(..., metadata={"gaia_research": ...})` so the relation
remains the source of truth.

Recommended optional metadata:

```json
{
  "gaia_research": {
    "kind": "candidate_relation",
    "scope_question": "dqc-order",
    "relation_type": "supports",
    "strength": "moderate",
    "epistemic_status": "scaffolded",
    "system": "lattice deconfined criticality models",
    "condition": "studied finite-size simulation regimes",
    "method": "finite-size scaling analysis",
    "observable": "drift in scaling exponents or histogram structure",
    "certainty": "moderate",
    "scope_note": "Applies to studied lattice-model regimes.",
    "source_refs": ["gcn_example"]
  }
}
```

Projection rules:

- top-level `candidate_relation.claims` becomes matrix claim endpoints;
- top-level `candidate_relation.pattern` becomes matrix `pattern`;
- top-level `candidate_relation.rationale` becomes matrix `rationale`;
- `metadata.gaia_research.relation_type` becomes the reader-facing stance;
- `metadata.gaia_research.system`, `condition`, `method`, and `observable`
  become optional cross-disciplinary matrix columns;
- `metadata.gaia_research.strength`, `certainty`, and `epistemic_status`
  become optional confidence/status columns;
- `metadata.gaia_research.scope_note` and `source_refs` become audit columns.

Do not put unjudged search hits, omitted relevant evidence, next queries, or
free-form limitations into relation metadata unless they directly describe the
claim-claim relation. Those belong in the assessment artifact or open
obligations.

## Open Obligations

Open obligations track the next research actions that should be taken and the
important issues that cannot be resolved in the current pass. They are projected
to Gaia inquiry when they are actionable enough to revisit. An obligation target
may be a scoped question, a claim, or a candidate relation. The content must
make the next action explicit: what kind of action is needed and what concrete
work should be done.

Gaia core owns the `diagnostic_kind` vocabulary. Research workflows must only
use the allowed inquiry kinds (`prior_hole`, `structural_hole`, `support_weak`,
`focus_weakness`, `other`). Workflow-specific taxonomy lives in
`anchor.gaia_research`, not in `diagnostic_kind`:

```json
{
  "target": {"kind": "question", "id": "continuous-vs-weak-first"},
  "action_type": "assess_focus",
  "action": "Assess ready focus continuous-vs-weak-first before downstream synthesis.",
  "diagnostic_kind": "focus_weakness",
  "anchor": {
    "kind": "research_obligation",
    "gaia_research": {
      "obligation_type": "workflow",
      "action_type": "assess_focus",
      "auto_closeable": true,
      "blocking": true,
      "budget_class": "assessment",
      "source": "focus_artifact"
    }
  }
}
```

`obligation_type=workflow` covers auto-closeable actions the run can schedule
and execute inside the bounded obligation loop. The minimal dispatcher supports:

- `assess_focus`: run evidence selection, materialization, and assessment for a
  ready focus;
- `expand_focus`: run targeted search and landscape expansion around a focus;
- `search_more_evidence`: search around a claim, question, or relation whose
  support remains thin;
- `close_coverage_gap`: run coverage search, focus regeneration, or evidence
  expansion for a missing field slice.

Other obligations, such as unresolved anchor repair or method-scope checks, may
still be collected in Gaia inquiry state, but they remain deferred or manual
until an auto-closeable action implementation exists. Deferred obligations are
not all treated as future context: when the open queue has no supported
candidate and budget remains, the scheduler may promote a deferred obligation
only if it is explicitly marked `auto_closeable=true` and uses one of the
supported action types. Future-research obligations cover important but
non-blocking or not-yet-actionable follow-up work.

Each loop iteration plans the highest-value supported obligation, executes it,
records an `executions` entry in `trace/obligations.json`, removes that
obligation from the run-local open queue, and refreshes open/deferred
obligations from the new artifacts. Current execution closes obligations at the
run-trace level; if Gaia core later exposes first-class obligation close/resolve
state, the dispatcher should call that API from the same execution hook.

With `analysis_provider=litellm`, each loop iteration may request a compact
`gaia.research.obligation_policy` JSON object. The policy scores existing
obligations by report impact, uncertainty reduction, coverage gain, and cost.
It cannot create obligations or bypass validation: the scheduler only honors a
policy entry if it matches an existing supported candidate within budget. If the
policy does not match a valid candidate, the deterministic priority order is the
fallback.

## Profile And Budget Model

Profiles should scale by obligation-loop rounds, not by changing the meaning of
an individual action. `fast`, `broad`, and `deep` share the same per-action
guardrails for search fanout, selected evidence, materialization, assessment
context, new claims, and candidate relations. They differ in how many
auto-closeable obligations the scheduler may try to close.

The default guardrail intent is:

- one focus is assessed in the initial pass;
- each action uses bounded targeted search rather than unbounded expansion;
- each focus assesses at most 20 selected claim/evidence anchors in one pass;
- if the result is still incomplete, the assessment records a new obligation
  instead of silently raising the prompt size or widening the action.

This keeps `fast`, `broad`, and `deep` as the same workflow at different loop
depths, instead of three divergent implementations.

## Non-Goals

The MVP does not implement:

- field maps as required graph-asset success criteria;
- multi-focus assessment;
- profile-specific per-action max tuning;
- unbounded continuous graph growth;
- a separate rich research obligation ledger beyond Gaia inquiry state;
- standalone claim-package dependency management as a default path;
- shallow landscape source packages as the primary dependency path;
- report generation or report planning;
- `infer(...)` or belief-propagation commitments;
- relation endpoints involving `question(...)`;
- evidence matrix rows not backed by candidate relation metadata.

## Success Criteria

An MVP run succeeds when it produces:

- one scoped `question(...)`;
- selected LKM claim/question hits normalized through at most one backing paper
  package dependency per `lkm:<index>:paper:<paper_id>`;
- at least one selected anchor resolved to a package-local Gaia symbol, with
  unresolved selected anchors captured as open or deferred obligations instead
  of silently entering relation authoring;
- at least two new research `claim(...)` records with candidate/provisional status;
- at least one existing-existing or existing-new `candidate_relation(...)`;
- an evidence matrix derived from those relations;
- at least one open obligation when important gaps remain, with a target
  question, claim, or relation and content that specifies the next action type
  and action content;
- a way to continue the run from open obligations or explicitly defer them.

## Implementation TODO

This backlog is intentionally narrower than the full report workflow. It exists
to turn the MVP asset model into code without making field maps, multi-focus
scheduling, profile-specific per-action max tuning, or report generation hidden
requirements for graph-asset success.

### P0: MVP Spine

1. Add a graph-assets output contract on the shared run surface.
   - Input: a topic or accepted focus.
   - Output: graph assets, optionally without a report.
   - The CLI surface is an existing profile, such as `--profile fast`, plus
     `--no-report` when the caller wants graph assets only.
   - The persisted run-state source of truth is `output_contracts`: containing
     `research_report` means report generation is required; omitting it means
     graph-assets only. Do not introduce a separate MVP mode.
   - If open obligations remain, the run must record whether the next action is
     to continue from the highest-value obligation or explicitly defer it. The
     scheduler decision is the shared entrypoint for later multi-round
     execution.
   - Pipeline:

     ```text
     topic/focus
       -> scoped question
       -> LKM claim/question hits
       -> package-backed anchors
       -> new research claims
       -> candidate relations
       -> matrix projection
       -> open obligations
       -> obligation scheduler decision
     ```

2. Normalize selected LKM results and resolve anchors as one implementation
   slice.
   - Convert `gaia search lkm knowledge`, `package`, and `reasoning` results to
     a backing `lkm:<index>:paper:<paper_id>` whenever possible.
   - Default materialization must call Gaia core's paper dependency path,
     equivalent to `gaia pkg add --lkm-paper <paper_id>`.
   - `gaia pkg add --lkm-claim` and chain materialization remain resolver or
     deep-evidence fallbacks, not the main path.
   - Store the original LKM hit id or node id.
   - Store hit `kind` (`claim` or `question`).
   - Store backing `lkm:<index>:paper:<paper_id>`.
   - Store materialized `import_name`.
   - Store package-local `symbol` and claim/question-level `ref` after
     resolution.
   - The invariant is: install by paper, track by claim/question, author
     relations by concrete claim refs.

3. Remove shallow source packages from the default MVP path.
   - The current landscape source-package path may remain as legacy/debug mode.
   - It must not create a second dependency for a paper that later enters
     through `gaia pkg add --lkm-paper`.

4. Write a scoped `question(...)` for each MVP run.
   - The question scopes the run.
   - It is referenced by metadata such as
     `metadata.gaia_research.scope_question`.
   - It is not a `candidate_relation` endpoint.

5. Add a machine-checkable MVP success validator.
   - Verify exactly the success criteria above.
   - A generated report must not count as MVP success.
   - Open obligations must either be selected for continuation by the obligation
     decision or explicitly deferred.
   - Unresolved anchors may coexist with success only when they are represented
     by open or deferred `resolve_anchor` obligations.

### P1: Candidate Assets And Matrix

1. Author new Gaia claims and candidate relations together.
   - New research claims are normal Gaia `claim(...)` objects written into the
     local development package.
   - Do not introduce a separate Gaia object type or separate long-lived
     candidate-claim artifact class.
   - Workflow analysis may stage these under `new_claims`, but that is an
     authoring queue field, not a Gaia object type.
   - Metadata records source and category, including
     `metadata.gaia_research.kind = "research_claim"`.
   - New research claims should carry `answers_question` and
     `status="candidate"` when they are not yet settled.
   - Prefer writing Gaia DSL directly instead of routing this path through the
     `gaia author` CLI, so partial package/import issues do not block research
     assets.
   - A successful authored candidate relation must have proper refs and valid
     Gaia DSL syntax.

2. Rewrite candidate relation metadata as the matrix source of truth.
   - Store `kind`, `scope_question`, `relation_type`, `strength`,
     `epistemic_status`, `system`, `condition`, `method`, `observable`,
     `certainty`, `scope_note`, and `source_refs` under
     `metadata.gaia_research` when available.
   - Use Gaia's native `pattern` only for relation shapes Gaia understands.
   - Derive evidence matrix rows only from authored `candidate_relation(...)`
     records.

3. Separate evidence context from matrix rows and obligations.
   - Unjudged search hits and other context remain in the assessment artifact or
     prompt context.
   - Rows without candidate relations do not enter the MVP matrix.
   - Important unresolved gaps and next actions become open or deferred
     obligations.

4. Define context hydration for paper-backed anchors.
   - Pulling a whole paper package must not mean passing the whole package into
     every prompt.
   - Hydrate only the anchored claim/question, compact paper metadata, selected
     neighboring claims or chains, and concrete refs needed for the current
     relation-planning step.

### P2: Inquiry And Guardrails

1. Define the minimum Gaia inquiry projection.
   - MVP does not maintain a rich budgeted research obligation ledger.
   - Obligations track next actions to take and important unresolved issues.
   - Actionable items may be projected with `gaia inquiry obligation add`.
   - The target may be a scoped question, claim, or candidate relation.
   - The content must include the action type and concrete action content.
   - Non-actionable gaps remain deferred in the assessment artifact.
   - The lightweight scheduler selects only supported auto-closeable workflow
     actions and records unsupported, manual, and future-research obligations
     separately.
   - Optional LLM policy scoring may reorder supported candidates according to
     current research value, but may not invent or execute unsupported actions.
   - Profiles control loop iterations; per-action guardrails remain shared.

2. Keep report generation outside the MVP default path.
   - Existing report code can remain.
   - MVP success is graph-asset success.
   - A later report planner should read the matrix and obligations; it should
     not be required to validate the MVP.

3. Add non-goal guardrails in CLI, tests, and docs.
   - Field maps, profile-specific per-action max tuning, unbounded graph
     growth, report planning, inference commitments, relation endpoints
     involving `question(...)`, and matrix rows not backed by candidate
     relations must not become required for the MVP path.

## Orchestrated Implementation Plan

The work can be split across independent workers after the P0 contracts are
clear. The orchestrator should keep ownership of cross-task schema decisions and
merge order.

```yaml
tasks:
  - id: graph-asset-run-surface
    description: "Add graph-assets output contract, success validator, and obligation-loop entrypoint on the shared run surface."
    dependencies: []
    estimated_complexity: medium
    worker_type: implement
    context:
      - src/gaia_research/research_cli.py
      - src/gaia_research/orchestrator.py
      - src/gaia_research/stop.py
      - src/gaia_research/workflow_state.py
      - tests/test_research_stop.py
    success_criteria:
      - "The graph-only surface accepts a topic or accepted focus and writes one scoped question."
      - "`--profile fast --no-report` writes `output_contracts=[\"gaia_graph_assets\"]` and does not require report generation."
      - "Success validator checks scoped question, at least one resolved anchor, unresolved-anchor obligations, candidate Gaia claims, candidate relations, matrix projection, and open/deferred obligations."
      - "If open obligations remain, the run can either continue from the highest-value obligation or explicitly defer the remaining obligations."

  - id: lkm-package-anchor-resolution
    description: "Normalize LKM hits to backing paper dependencies and resolve claim/question anchors in the same slice."
    dependencies: []
    estimated_complexity: high
    worker_type: implement
    context:
      - src/gaia_research/research_materialization.py
      - src/gaia_research/source_packages.py
      - src/gaia_research/evidence_selection.py
      - src/gaia_research/landscape.py
      - tests/test_research_evidence_selection.py
      - tests/test_landscape.py
    success_criteria:
      - "Selected LKM knowledge/package/reasoning hits resolve to one backing paper source ref when possible."
      - "The MVP path uses paper dependency materialization, equivalent to gaia pkg add --lkm-paper, by default."
      - "Candidate corpus paper materialization is not capped by assessment or prompt-selection budgets."
      - "Selected-evidence and graph-assets artifacts expose candidate corpus, materialization, and selected-assessment counts separately."
      - "The same paper cannot be installed once as a shallow source package and again as an LKM paper dependency."
      - "Each selected hit keeps hit id or node id, kind, backing paper source ref, import name, symbol, and claim/question ref when resolved."
      - "Multiple hits from the same paper share one dependency but keep distinct anchors."
      - "Unresolved anchors are not passed into relation authoring and create an open or deferred obligation instead of disappearing."

  - id: gaia-dsl-asset-authoring
    description: "Author scoped candidate Gaia claims, candidate relations, and relation-backed matrix projection together."
    dependencies:
      - graph-asset-run-surface
      - lkm-package-anchor-resolution
    estimated_complexity: high
    worker_type: implement
    context:
      - src/gaia_research/assessment.py
      - src/gaia_research/contracts.py
      - src/gaia_research/sync.py
      - src/gaia_research/report.py
      - src/gaia_research/proposal.py
      - src/gaia_research/prompts/research/assess_analysis.md
      - src/gaia_research/prompts/research/output_shapes.json
      - tests/test_research_assessment.py
      - tests/test_research_contracts.py
      - tests/test_research_artifacts.py
      - tests/test_research_report.py
    success_criteria:
      - "New research claims are authored as ordinary Gaia claim(...) objects in the local development package with metadata marking source, category, and candidate/provisional status."
      - "No separate Gaia object type or long-lived candidate-claim artifact class is introduced."
      - "Gaia DSL is written directly for new research claims and candidate relations; the MVP path does not depend on gaia author CLI."
      - "Candidate relations have proper refs and valid Gaia DSL syntax after authoring."
      - "Existing-existing and existing-new candidate relations are authored when refs resolve."
      - "Relations use Gaia-native pattern only for native Gaia relation shapes."
      - "Extended cross-disciplinary metadata remains under metadata.gaia_research."
      - "Evidence matrix projection contains only relation-backed rows."

  - id: context-hydration
    description: "Limit prompt context for paper-backed anchors to selected claims, compact paper metadata, and nearby evidence."
    dependencies:
      - lkm-package-anchor-resolution
    estimated_complexity: medium
    worker_type: implement
    context:
      - src/gaia_research/evidence_selection.py
      - src/gaia_research/research_runtime.py
      - src/gaia_research/orchestrator.py
      - src/gaia_research/prompts/research/
    success_criteria:
      - "Prompts do not receive whole paper packages by default."
      - "Prompt packets preserve the original anchored claim/question and the concrete refs needed for relation planning."
      - "Prompt packets can be inspected to see which context item came from which anchor or relation target."

  - id: obligation-continuation
    description: "Track next research actions and unresolved issues as Gaia inquiry obligations, then continue or defer them."
    dependencies:
      - graph-asset-run-surface
      - lkm-package-anchor-resolution
      - gaia-dsl-asset-authoring
    estimated_complexity: medium
    worker_type: implement
    context:
      - src/gaia_research/sync.py
      - src/gaia_research/research_cli.py
      - src/gaia_research/orchestrator.py
      - tests/test_research_artifacts.py
      - Gaia inquiry state primitives
    success_criteria:
      - "Obligations can target a scoped question, claim, or candidate relation."
      - "Each obligation content specifies the next action type and concrete action content."
      - "diagnostic_kind remains one of Gaia inquiry's allowed kinds; workflow/future-research taxonomy is stored in anchor.gaia_research."
      - "Focus readiness gaps, unassessed ready focuses, coverage gaps, assessment gaps, and anchor/materialization failures are collected into the obligation plan."
      - "Obligations track both actions to take next and issues that cannot be resolved in the current pass."
      - "The workflow can continue from an open obligation by running the relevant next action or mark it deferred."
      - "Anchor/materialization/relation failures create obligations or deferred records and are not silently dropped."
      - "Duplicate obligations are not repeatedly written for the same target/action."

  - id: mvp-guardrails-docs-tests
    description: "Add CLI/test/doc guardrails so non-goals do not become MVP requirements."
    dependencies:
      - graph-asset-run-surface
      - gaia-dsl-asset-authoring
      - obligation-continuation
    estimated_complexity: low
    worker_type: test
    context:
      - docs/foundations/gaia-native-research-mvp.md
      - docs/foundations/README.md
      - tests/test_research_contracts.py
      - tests/test_agent_platform_contract.py
    success_criteria:
      - "Tests fail if the graph-assets subset requires field maps, multi-focus scheduling, reports, inference, or question relation endpoints."
      - "Docs and CLI help describe graph assets as the MVP output."
```

Recommended scheduling:

1. Start `graph-asset-run-surface` and `lkm-package-anchor-resolution` in parallel.
2. Start `context-hydration` once resolver and anchor behavior is stable.
3. Start `gaia-dsl-asset-authoring` after scoped question and anchor refs are
   available.
4. Start `obligation-continuation` after authored claims/relations and anchor
   failure semantics are clear.
5. Finish with `mvp-guardrails-docs-tests` after the main asset path exists.

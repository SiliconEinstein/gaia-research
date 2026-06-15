# EvidenceMaster Fast Prompt Backlog

The first quality iteration targets `fast` only.

## Rewrite Order

1. `query_plan`: produce fewer, sharper, domain-aware search queries.
2. `field_map_analysis`: build a readable evidence map before choosing a focus.
3. `focus_analysis`: choose one assessable focus with explicit readiness.
4. `assess_analysis`: classify evidence without writing final report prose.
5. `report_plan`: produce reader-facing section structure.
6. `report_section`: write grounded, citation-preserving sections.
7. `report_stitch`: polish without dropping evidence or converting to a summary.

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

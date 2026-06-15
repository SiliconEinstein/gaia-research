# Research Prompts

Gaia Research owns the workflow prompts for `gaia research run`.

Prompt assets live under `src/gaia_research/prompts/research/`. The provider
layer loads these assets, combines them with live input payloads and output
shape hints, and calls the configured LLM provider.

CLI contracts remain the schema authority. Prompt text may describe desired
behavior, but JSON validation, grounding repair, artifact writing, and render
behavior stay in Python code.

EvidenceMaster defaults to the `fast` profile. Prompt iteration should focus on
`query_plan`, `field_map_analysis`, `focus_analysis`, `assess_analysis`,
`report_plan`, `report_section`, and `report_stitch` in that order. `broad` and
`deep` may reuse the same prompt assets until product testing justifies separate
profile-specific prompts.

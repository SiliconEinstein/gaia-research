# LKM Explorer Prior Art

This directory archives the retired Gaia-core `gaia-lkm-explore`
implementation and tests as reference material for future `gaia-research`
graph-session work.

Status:

- not shipped as part of the Gaia core `gaia` package;
- not exposed as a console script;
- not importable as `gaia.lkm_explorer`;
- not part of `gaia-research` runtime code;
- not part of `gaia-research` CI or mypy coverage;
- not a compatibility contract.

Use this archive only as design input. The active report workflow lives in
`src/gaia_research/`; future continuous graph/session work should extract the
useful ideas from this archive into new `gaia-research` contracts instead of
reviving the old package layout.

Useful concepts to extract before implementing graph sessions:

- frontier ranking and scoring;
- round/turn state transitions;
- pause/resume cursor shape;
- `.gaia/exploration/map.json` strengths and weaknesses;
- artifact/gate handoff envelopes;
- exploration-map rendering.

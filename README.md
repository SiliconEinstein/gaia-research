# gaia-research

Standalone research package for Gaia.

This repository owns the research implementation that will be split out of
`SiliconEinstein/Gaia`. Gaia core remains the language, package, authoring,
materialization, inquiry, and plugin substrate. Dependency direction is:

```text
gaia-research -> gaia-lang
```

Gaia core must not import `gaia_research`.

## Bootstrap Status

This initial commit is intentionally small. It establishes the repository,
package metadata, and downstream contract tests before migrating the existing
review-run implementation.

The future package will own:

- review-run orchestration and SDK;
- `.gaia/research/**` artifact contracts;
- `gaia research` plugin registration;
- packaged research skills;
- contract CI against Gaia core.

Large-scale graph sessions are a follow-up capability, tracked separately from
the repo-split goal. The split should leave room for that work without claiming
it is implemented here.


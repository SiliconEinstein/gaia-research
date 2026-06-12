# gaia-research Execution Record

This record tracks the repository split work that belongs with each execution PR.
Keep future PR learnings here instead of opening separate tracking-only PRs.

## Goal A Boundary

Goal A is a repository-boundary and connection goal:

- keep `gaia-research` as a standalone repo;
- depend one-way on Gaia core public APIs;
- reconnect `gaia research` through plugin or entrypoint loading;
- migrate the current review-run path with parity;
- keep `.gaia/research/**` ownership clear.

Goal A does not claim large-scale graph sessions are implemented. Graph-session
contracts can be designed as follow-up work, but this repo split should not block
that direction.

## PR Log

### PR #1: CLI Plugin Entry Point

Branch: `feature/gaia-cli-plugin`

Learning:

- Gaia core can discover installed downstream command groups through entry
  points.
- While Gaia core still ships a built-in `gaia research`, the standalone package
  should prove only the plugin path, not command override behavior.

Verifier:

- `uv run pytest -q`
- `uv run ruff check src tests`
- `uv run mypy src tests`
- wheel metadata contains `gaia.cli_plugins`.

### PR #2: Review-Run Disk Contract

Branch: `feature/review-run-contract`

Learning:

- The first review-run migration slice should establish observable state before
  moving orchestration.
- `.gaia/research/runs/<run-id>/` is the gaia-research-owned namespace for
  state, events, checkpoints, and final report artifacts.
- `.gaia/research_loop` must not be recreated.

Verifier:

- `uv run pytest tests/test_review_run_contract.py -q`
- `uv run pytest -q`
- `uv run ruff check src tests`
- `uv run mypy src tests`
- `uv build --wheel --out-dir dist`

### PR #3: Gaia Inquiry Review Runner

Branch: `feature/review-runner`

Learning:

- `gaia-research` should not fork Gaia inquiry review logic.
- The runner should call Gaia core `run_review` / `render_markdown`, then wrap
  the result in the `.gaia/research/runs/<run-id>/` envelope.
- Failure must be observable in `state.json` and `events.ndjson` so product,
  skill, and agent callers can pause, inspect, and retry at the boundary.

Verifier:

- `uv run pytest tests/test_review_runner.py -q`
- `uv run pytest tests/test_review_run_contract.py tests/test_review_runner.py -q`
- `uv run pytest -q`
- `uv run ruff check src tests`
- `uv run mypy src tests`
- `uv run gaia-research`
- copied `examples/mendel-v0-5-gaia` to a temporary package and ran
  `run_package_review(..., no_infer=True)`, producing `completed/report` with
  `compile_status=ok`
- `uv build --wheel --out-dir dist`

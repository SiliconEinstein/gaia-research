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

### PR #4: Standalone Review CLI

Branch: `feature/review-cli`

Learning:

- The standalone `gaia-research` script should expose the same review-run path
  before the Gaia plugin stack is flattened.
- Keeping `gaia-research review` as a thin wrapper around `run_package_review`
  gives product, skill, and agent callers a runnable migration path while Gaia
  core plugin discovery is still an open PR.
- The command should preserve the existing no-argument bootstrap health check so
  CI and install smoke tests stay cheap.

Verifier:

- `uv run pytest tests/test_cli_review.py -q`
- `uv run pytest tests/test_cli_review.py tests/test_review_runner.py tests/test_review_run_contract.py -q`
- `uv run pytest -q`
- `uv run ruff check src tests`
- `uv run mypy src tests`
- `uv run gaia-research`
- copied `examples/mendel-v0-5-gaia` to a temporary package and ran
  `uv run gaia-research review --path <tmp-pkg> --topic smoke --profile quick
  --run-id smoke-review --no-infer`, producing `final_report.md`

### PR #5: Gaia CLI Plugin Review Command

Branch: `feature/review-plugin`

Learning:

- The Gaia plugin entry point should register a real `gaia research review`
  command, not only a placeholder group.
- The plugin command should reuse `run_package_review` so standalone CLI and
  Gaia plugin calls share the same review-run envelope and failure behavior.
- This PR proves the downstream package owns the command implementation through
  `gaia.cli_plugins`; Gaia core still only needs entry-point discovery.
- Direct `uv run gaia research review ...` remains blocked until Gaia core stops
  registering its built-in research command ahead of plugins. That handoff
  belongs in a Gaia core PR, not in this downstream package.

Verifier:

- `uv run pytest tests/test_cli_plugin.py -q`
- `uv run pytest -q`
- `uv run ruff check src tests`
- `uv run mypy src tests`
- `uv run python -c 'import typer; from gaia.cli.main import load_cli_plugins; ...'`
  returned `['research']` and registered the `research` group on a fresh root app
- `uv build --wheel --out-dir dist`

### PR #6: CI Wheel Build Gate

Branch: `feature/ci-build-wheel`

Learning:

- The plugin entry point is packaging metadata, so CI should build the wheel
  instead of relying only on editable-install tests.
- Keeping the wheel build in the downstream repo CI makes the one-way dependency
  contract visible at the package boundary.

Verifier:

- `uv build --wheel --out-dir dist`

### PR #7: Exact Gaia Core API Contract

Branch: `feature/core-api-contract`

Learning:

- `gaia-research` should verify the exact Gaia core callables it uses, not only
  broad module imports.
- The review-run bridge currently depends on
  `gaia.engine.inquiry.review:run_review` and
  `gaia.engine.inquiry.review:render_markdown`.
- Keeping this contract in the downstream repo makes accidental Gaia core API
  movement visible in downstream CI.

Verifier:

- `uv run pytest tests/test_core_contract.py -q`
- `uv run pytest -q`
- `uv run ruff check src tests`
- `uv run mypy src tests`
- `uv build --wheel --out-dir dist`

### PR #8: README Review-Run Acceptance Guide

Branch: `feature/readme-review-run`

Learning:

- The README should describe implemented review-run and plugin surfaces, not the
  initial bootstrap intent.
- User-facing docs need to preserve the Goal A boundary: review-run migration is
  real, while large-scale graph sessions remain follow-up work.
- The acceptance path should name both standalone `gaia-research review` and
  plugin-backed `gaia research review`.

Verifier:

- docs-only diff review

### PR #9: Review-Run Status CLI

Branch: `feature/review-run-status`

Learning:

- Writing `.gaia/research/runs/**` is not enough for agent/product acceptance;
  callers need a simple way to inspect a run envelope after execution or failure.
- `read_review_run` already provided the SDK surface, so this PR only exposes it
  through standalone and plugin CLI status paths.

Verifier:

- `uv run pytest tests/test_cli_review.py tests/test_cli_plugin.py -q`
- `uv run pytest -q`
- `uv run ruff check src tests`
- `uv run mypy src tests`
- created a temporary Mendel Gaia package, ran `gaia-research review`, then
  verified `gaia-research status --run-id status-smoke` prints completed/report
  and event count
- `uv build --wheel --out-dir dist`

### PR #10: Review-Run Status JSON Output

Branch: `feature/review-status-json`

Learning:

- Human-readable status is useful for manual acceptance, but agents need stable
  JSON for automated checks.
- The JSON shape should be a compact summary of the existing run envelope, not a
  second schema: run id, status, phase, run directory, report path, and event
  count.

Verifier:

- `uv run pytest tests/test_cli_review.py tests/test_cli_plugin.py -q`
- `uv run pytest -q`
- `uv run ruff check src tests`
- `uv run mypy src tests`
- created a temporary Mendel Gaia package, ran `gaia-research review`, then
  parsed `gaia-research status --json`
- `uv build --wheel --out-dir dist`

### PR #11: Review Command JSON Output

Branch: `feature/review-output-json`

Learning:

- Agents should be able to launch a review and immediately capture the run
  handle without a second status call or text scraping.
- `review --json` should reuse the same compact envelope summary as
  `status --json`: run id, status, phase, run directory, report path, and event
  count.
- The human-readable review output remains the default for manual acceptance.

Verifier:

- `uv run pytest tests/test_cli_review.py::test_review_command_can_emit_json
  tests/test_cli_plugin.py::test_plugin_review_command_can_emit_json -q`
- `uv run pytest tests/test_cli_review.py tests/test_cli_plugin.py -q`
- `uv run pytest -q`
- `uv run ruff check src tests`
- `uv run mypy src tests`
- `uv build --wheel --out-dir dist`
- copied `examples/mendel-v0-5-gaia` to a temporary package and ran
  `gaia-research review --json`, producing completed/report JSON with
  `events=6`

### PR #12: Installed Wheel Smoke Gate

Branch: `feature/ci-installed-wheel-smoke`

Learning:

- Building the wheel is necessary but not sufficient for the split boundary;
  CI should install the built artifact into a clean environment and run the
  packaged console script.
- The installed-wheel smoke should also verify the packaged
  `gaia.cli_plugins` entry point, because `gaia research` reconnects through
  distribution metadata.
- Keeping the smoke in `scripts/smoke_installed_wheel.sh` makes the CI gate
  locally reproducible.
- The script should avoid `mapfile` so local macOS bash and GitHub Actions bash
  both run the same verifier.

Verifier:

- `uv build --wheel --out-dir dist`
- `scripts/smoke_installed_wheel.sh`
- `bash -n scripts/smoke_installed_wheel.sh`
- `uv run pytest -q`
- `uv run ruff check src tests`
- `uv run mypy src tests`

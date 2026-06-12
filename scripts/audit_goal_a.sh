#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

wheel_dir="$(mktemp -d "${TMPDIR:-/tmp}/gaia-research-goal-a-wheel.XXXXXX")"
trap 'rm -rf "${wheel_dir}"' EXIT

uv run pytest -q
uv run ruff check src tests
uv run mypy src tests
git diff --check
uv build --wheel --out-dir "${wheel_dir}"
scripts/smoke_installed_wheel.sh "${wheel_dir}"

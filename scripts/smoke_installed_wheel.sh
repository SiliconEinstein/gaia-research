#!/usr/bin/env bash
set -euo pipefail

wheel_dir="${1:-dist}"
python_bin="${PYTHON:-python3}"

if [[ ! -d "${wheel_dir}" ]]; then
  echo "wheel directory not found: ${wheel_dir}" >&2
  exit 1
fi

wheels=()
while IFS= read -r wheel; do
  wheels+=("${wheel}")
done < <(find "${wheel_dir}" -maxdepth 1 -type f -name 'gaia_research-*.whl' | sort)
if [[ "${#wheels[@]}" -ne 1 ]]; then
  echo "expected exactly one gaia_research wheel in ${wheel_dir}, found ${#wheels[@]}" >&2
  printf '%s\n' "${wheels[@]}" >&2
  exit 1
fi

tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/gaia-research-wheel-smoke.XXXXXX")"
trap 'rm -rf "${tmp_dir}"' EXIT

uv venv "${tmp_dir}/venv" --python "${python_bin}"
uv pip install --python "${tmp_dir}/venv/bin/python" "${wheels[0]}"

"${tmp_dir}/venv/bin/gaia-research"
"${tmp_dir}/venv/bin/python" - <<'PY'
from importlib import metadata

entry_points = metadata.distribution("gaia-research").entry_points
matches = [
    entry_point
    for entry_point in entry_points
    if entry_point.group == "gaia.cli_plugins" and entry_point.name == "research"
]
if len(matches) != 1:
    raise SystemExit(f"expected one research plugin entry point, found {len(matches)}")
if matches[0].value != "gaia_research.plugin:register":
    raise SystemExit(f"unexpected research plugin target: {matches[0].value}")
PY

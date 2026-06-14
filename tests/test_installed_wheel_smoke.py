"""Tests for the installed-wheel smoke verifier script."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def test_smoke_script_can_override_gaia_core_dependency(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "gaia_research-0.1.0-py3-none-any.whl").write_text("fake wheel\n")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    command_log = tmp_path / "commands.log"
    fake_uv = fake_bin / "uv"
    fake_uv.write_text(
        f"""#!/usr/bin/env bash
set -euo pipefail
printf 'uv %s\\n' "$*" >> {command_log}

if [[ "$1" == "venv" ]]; then
  venv="$2"
  mkdir -p "${{venv}}/bin"
  cat > "${{venv}}/bin/python" <<'PY'
#!/usr/bin/env bash
script="$(cat)"
if [[ "${{script}}" == *"_remove_registered_top_level_name"* ]]; then
  exit 0
fi
if [[ "${{script}}" == *"load_research_system_prompt"* ]]; then
  echo "You are Gaia's dete"
  exit 0
fi
exit 0
PY
  chmod +x "${{venv}}/bin/python"
  cat > "${{venv}}/bin/gaia-research" <<'SH'
#!/usr/bin/env bash
echo "gaia-research bootstrap OK"
SH
  chmod +x "${{venv}}/bin/gaia-research"
  cat > "${{venv}}/bin/gaia" <<'SH'
#!/usr/bin/env bash
printf 'gaia %s\n' "$*" >> "${{GAIA_SMOKE_COMMAND_LOG}}"
if [[ "$*" == "research doctor" ]]; then
  echo "gaia-research doctor OK"
  exit 0
fi
exit 7
SH
  chmod +x "${{venv}}/bin/gaia"
fi
""",
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
    env["TMPDIR"] = str(tmp_path)
    env["GAIA_SMOKE_COMMAND_LOG"] = str(command_log)
    env["GAIA_CORE_SPEC"] = (
        "gaia-lang @ git+https://github.com/SiliconEinstein/Gaia.git@codex/research-plugin-handoff"
    )

    result = subprocess.run(
        [str(repo / "scripts" / "smoke_installed_wheel.sh"), str(dist)],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "gaia-research doctor OK" in result.stdout
    assert "You are Gaia's" in result.stdout
    assert "uv pip install --python" in command_log.read_text(encoding="utf-8")
    assert "--reinstall" in command_log.read_text(encoding="utf-8")
    assert env["GAIA_CORE_SPEC"] in command_log.read_text(encoding="utf-8")
    assert "gaia research doctor" in command_log.read_text(encoding="utf-8")
    assert "gaia research review" not in command_log.read_text(encoding="utf-8")


def test_smoke_script_can_require_gaia_research_handoff(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "gaia_research-0.1.0-py3-none-any.whl").write_text("fake wheel\n")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_uv = fake_bin / "uv"
    fake_uv.write_text(
        """#!/usr/bin/env bash
set -euo pipefail

if [[ "$1" == "venv" ]]; then
  venv="$2"
  mkdir -p "${venv}/bin"
  cat > "${venv}/bin/python" <<'PY'
#!/usr/bin/env bash
script="$(cat)"
if [[ "${script}" == *"_remove_registered_top_level_name"* ]]; then
  exit 42
fi
exit 0
PY
  chmod +x "${venv}/bin/python"
  cat > "${venv}/bin/gaia-research" <<'SH'
#!/usr/bin/env bash
echo "gaia-research bootstrap OK"
SH
  chmod +x "${venv}/bin/gaia-research"
fi
""",
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
    env["TMPDIR"] = str(tmp_path)
    env["GAIA_REQUIRE_RESEARCH_HANDOFF"] = "1"

    result = subprocess.run(
        [str(repo / "scripts" / "smoke_installed_wheel.sh"), str(dist)],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 42
    assert "installed Gaia core lacks research plugin handoff" in result.stderr

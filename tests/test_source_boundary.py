"""Source-level dependency boundary tests."""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path


def test_runtime_gaia_dependency_is_only_gaia_lang() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    project = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]
    gaia_dependencies = [
        dependency
        for dependency in project["dependencies"]
        if dependency == "gaia" or dependency.startswith(("gaia-", "gaia "))
    ]

    assert gaia_dependencies == ["gaia-lang @ git+https://github.com/SiliconEinstein/Gaia.git@main"]


def test_gaia_core_imports_stay_behind_dynamic_bridge() -> None:
    src_root = Path(__file__).resolve().parents[1] / "src" / "gaia_research"
    dynamic_bridge_files = {Path("contracts.py"), Path("runner.py")}
    offenders: list[str] = []

    for path in sorted(src_root.rglob("*.py")):
        relative_path = path.relative_to(src_root)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "gaia" or alias.name.startswith("gaia."):
                        offenders.append(f"{relative_path}:{node.lineno}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "gaia" or module.startswith("gaia."):
                    offenders.append(f"{relative_path}:{node.lineno}")
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "import_module"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
                and (node.args[0].value == "gaia" or node.args[0].value.startswith("gaia."))
                and relative_path not in dynamic_bridge_files
            ):
                offenders.append(f"{relative_path}:{node.lineno}")

    assert offenders == []

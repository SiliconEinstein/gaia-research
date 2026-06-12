"""Downstream contract tests for gaia-research -> Gaia core."""

from __future__ import annotations

import subprocess
import sys

from gaia_research import (
    CORE_PUBLIC_CALLABLES,
    CORE_PUBLIC_SIGNATURES,
    CORE_PUBLIC_SURFACES,
    verify_core_callable_contract,
    verify_core_callable_signature_contract,
    verify_core_contract,
)


def test_gaia_research_imports_declared_core_public_surfaces() -> None:
    assert verify_core_contract() == CORE_PUBLIC_SURFACES


def test_gaia_research_verifies_declared_core_public_callables() -> None:
    assert verify_core_callable_contract() == CORE_PUBLIC_CALLABLES


def test_gaia_research_verifies_declared_core_public_signatures() -> None:
    assert verify_core_callable_signature_contract() == CORE_PUBLIC_SIGNATURES


def test_importing_gaia_core_does_not_import_gaia_research() -> None:
    code = """
import sys
import gaia
import gaia.engine.inquiry
leaks = [
    name
    for name in sys.modules
    if name == "gaia_research" or name.startswith("gaia_research.")
]
raise SystemExit(1 if leaks else 0)
"""
    subprocess.run([sys.executable, "-c", code], check=True)

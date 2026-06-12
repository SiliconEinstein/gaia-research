"""Console entry point for the standalone Gaia research package."""

from __future__ import annotations

from gaia_research.contracts import verify_core_contract


def main() -> None:
    """Run a minimal bootstrap health check."""
    verify_core_contract()
    print("gaia-research bootstrap OK")


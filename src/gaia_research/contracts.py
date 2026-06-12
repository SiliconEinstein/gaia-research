"""Bootstrap contracts between gaia-research and Gaia core."""

from __future__ import annotations

from importlib import import_module

CORE_PUBLIC_SURFACES: tuple[str, ...] = (
    "gaia.lkm.client",
    "gaia.engine.authoring",
    "gaia.engine.inquiry",
    "gaia.engine.materialize",
    "gaia.engine.packaging",
)


def verify_core_contract() -> tuple[str, ...]:
    """Import the Gaia core public surfaces required by the research split."""
    for module_name in CORE_PUBLIC_SURFACES:
        import_module(module_name)
    return CORE_PUBLIC_SURFACES


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
CORE_PUBLIC_CALLABLES: tuple[str, ...] = (
    "gaia.engine.inquiry.review:render_markdown",
    "gaia.engine.inquiry.review:run_review",
)


def verify_core_contract() -> tuple[str, ...]:
    """Import the Gaia core public surfaces required by the research split."""
    for module_name in CORE_PUBLIC_SURFACES:
        import_module(module_name)
    return CORE_PUBLIC_SURFACES


def verify_core_callable_contract() -> tuple[str, ...]:
    """Verify callable Gaia core APIs used by the review-run bridge."""
    for ref in CORE_PUBLIC_CALLABLES:
        module_name, attr_name = ref.split(":", 1)
        module = import_module(module_name)
        attr = getattr(module, attr_name)
        if not callable(attr):
            raise TypeError(f"Gaia core API is not callable: {ref}")
    return CORE_PUBLIC_CALLABLES

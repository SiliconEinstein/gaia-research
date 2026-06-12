"""Bootstrap contracts between gaia-research and Gaia core."""

from __future__ import annotations

from importlib import import_module
from inspect import Parameter, signature

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
CORE_PUBLIC_SIGNATURES: dict[str, tuple[str, ...]] = {
    "gaia.engine.inquiry.review:render_markdown": ("report",),
    "gaia.engine.inquiry.review:run_review": (
        "path",
        "focus_override",
        "mode",
        "no_infer",
        "depth",
        "since",
        "strict",
    ),
}


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


def verify_core_callable_signature_contract() -> dict[str, tuple[str, ...]]:
    """Verify Gaia core callable parameters used by the review-run bridge."""
    for ref, expected_parameters in CORE_PUBLIC_SIGNATURES.items():
        module_name, attr_name = ref.split(":", 1)
        module = import_module(module_name)
        attr = getattr(module, attr_name)
        actual_parameters = tuple(
            name
            for name, parameter in signature(attr).parameters.items()
            if parameter.kind
            in {
                Parameter.POSITIONAL_ONLY,
                Parameter.POSITIONAL_OR_KEYWORD,
                Parameter.KEYWORD_ONLY,
            }
        )
        if actual_parameters != expected_parameters:
            raise TypeError(
                f"Gaia core API signature changed for {ref}: "
                f"expected {expected_parameters}, got {actual_parameters}"
            )
    return CORE_PUBLIC_SIGNATURES

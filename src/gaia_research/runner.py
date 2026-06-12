"""Runner bridge from gaia-research envelopes to Gaia core inquiry review."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, cast

from gaia_research.review import (
    ReviewRunHandle,
    ReviewRunSnapshot,
    complete_review_run,
    fail_review_run,
    record_review_run_event,
    start_review_run,
)


class ReviewRunnerError(RuntimeError):
    """Raised when the Gaia core inquiry-review runner fails."""


@dataclass(frozen=True)
class PackageReviewResult:
    """Result returned after a package inquiry review has been captured."""

    handle: ReviewRunHandle
    report: Any
    snapshot: ReviewRunSnapshot
    markdown: str


def _core_review_summary(report: Any) -> dict[str, Any]:
    return {
        "review_id": getattr(report, "review_id", None),
        "compile_status": getattr(report, "compile_status", None),
        "counts": dict(getattr(report, "counts", {}) or {}),
        "mode": getattr(report, "mode", None),
    }


def run_review(path: str | Path, **kwargs: Any) -> Any:
    """Call Gaia core inquiry review without making Gaia a typed import boundary."""
    module = import_module("gaia.engine.inquiry.review")
    return module.run_review(path, **kwargs)


def render_markdown(report: Any) -> str:
    """Render a Gaia core inquiry review report as Markdown."""
    module = import_module("gaia.engine.inquiry.review")
    return cast(str, module.render_markdown(report))


def run_package_review(
    pkg_path: str | Path,
    *,
    topic: str,
    profile: str,
    run_id: str | None = None,
    language: str = "zh",
    focus_override: str | None = None,
    mode: str = "auto",
    no_infer: bool = False,
    depth: int = 0,
    since: str | None = None,
    strict: bool = False,
) -> PackageReviewResult:
    """Run Gaia core inquiry review and capture it under ``.gaia/research``."""
    pkg = Path(pkg_path).resolve()
    handle = start_review_run(
        pkg,
        topic=topic,
        profile=profile,
        run_id=run_id,
        language=language,
    )
    record_review_run_event(
        handle,
        "core_review.started",
        phase="core_review",
        payload={"mode": mode, "focus_override": focus_override, "no_infer": no_infer},
    )

    try:
        report = run_review(
            pkg,
            focus_override=focus_override,
            mode=mode,
            no_infer=no_infer,
            depth=depth,
            since=since,
            strict=strict,
        )
        markdown = render_markdown(report)
    except Exception as exc:
        error = str(exc)
        fail_review_run(handle, error, phase="core_review")
        raise ReviewRunnerError(error) from exc

    core_review = _core_review_summary(report)
    record_review_run_event(
        handle,
        "core_review.completed",
        phase="core_review",
        payload=core_review,
    )
    snapshot = complete_review_run(
        handle,
        markdown,
        state_updates={"core_review": core_review},
    )
    return PackageReviewResult(
        handle=handle,
        report=report,
        snapshot=snapshot,
        markdown=markdown,
    )

"""Console entry point for the standalone Gaia research package."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from gaia_research.contracts import verify_core_contract
from gaia_research.runner import ReviewRunnerError, run_package_review


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gaia-research")
    subparsers = parser.add_subparsers(dest="command")

    review = subparsers.add_parser("review", help="Run Gaia inquiry review into .gaia/research")
    review.add_argument("--path", default=".", help="Gaia package path.")
    review.add_argument("--topic", required=True, help="Review-run topic.")
    review.add_argument("--profile", default="quick", help="Review profile label.")
    review.add_argument("--run-id", default=None, help="Stable run id.")
    review.add_argument("--language", default="zh", help="Run language metadata.")
    review.add_argument(
        "--focus",
        dest="focus_override",
        default=None,
        help="Inquiry focus override.",
    )
    review.add_argument("--mode", default="auto", help="Gaia inquiry review mode.")
    review.add_argument("--no-infer", action="store_true", help="Skip inference.")
    review.add_argument("--depth", type=int, default=0, help="Dependency depth for review.")
    review.add_argument("--since", default=None, help="Baseline review id for semantic diff.")
    review.add_argument("--strict", action="store_true", help="Enable strict review mode.")
    return parser


def _run_review_command(args: argparse.Namespace) -> int:
    try:
        result = run_package_review(
            args.path,
            topic=args.topic,
            profile=args.profile,
            run_id=args.run_id,
            language=args.language,
            focus_override=args.focus_override,
            mode=args.mode,
            no_infer=args.no_infer,
            depth=args.depth,
            since=args.since,
            strict=args.strict,
        )
    except ReviewRunnerError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"review run completed: {result.handle.run_id}")
    print(f"run_dir: {result.handle.run_dir}")
    print(f"report: {result.handle.report_path}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the gaia-research CLI."""
    args_list = list(argv) if argv is not None else sys.argv[1:]
    if not args_list:
        verify_core_contract()
        print("gaia-research bootstrap OK")
        return 0

    parser = _build_parser()
    args = parser.parse_args(args_list)
    if args.command == "review":
        return _run_review_command(args)

    verify_core_contract()
    print("gaia-research bootstrap OK")
    return 0

"""Console entry point for the standalone Gaia research package."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from gaia_research.contracts import verify_core_contract
from gaia_research.workflow_state import read_events, resume_report_run


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gaia-research")
    subparsers = parser.add_subparsers(dest="command")

    status = subparsers.add_parser("status", help="Inspect a report workflow run")
    status.add_argument("--path", default=".", help="Research workspace path.")
    status.add_argument("--run-id", required=True, help="Report workflow run id.")
    status.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser


def _print_report_run_status(payload: dict[str, object]) -> None:
    print(f"report run: {payload['run_id']}")
    print(f"status: {payload['status']}")
    print(f"phase: {payload['phase']}")
    print(f"run_dir: {payload['run_dir']}")
    print(f"events: {payload['events']}")


def _report_run_status_payload(path: str, run_id: str) -> dict[str, object]:
    handle, state = resume_report_run(path, run_id)
    return {
        "run_id": handle.run_id,
        "status": state.status,
        "phase": state.phase,
        "run_dir": str(handle.run_dir),
        "events": len(read_events(handle)),
        "artifacts": dict(state.artifacts),
    }


def _run_status_command(args: argparse.Namespace) -> int:
    try:
        payload = _report_run_status_payload(args.path, args.run_id)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        _print_report_run_status(payload)
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
    if args.command == "status":
        return _run_status_command(args)

    verify_core_contract()
    print("gaia-research bootstrap OK")
    return 0

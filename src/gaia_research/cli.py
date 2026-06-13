"""Console entry point for the standalone Gaia research package."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from gaia_research.contracts import verify_core_contract
from gaia_research.research_cli import research_app


def main(argv: Sequence[str] | None = None) -> int:
    """Run the gaia-research CLI."""
    args_list = list(argv) if argv is not None else sys.argv[1:]
    if not args_list:
        verify_core_contract()
        print("gaia-research bootstrap OK")
        return 0

    try:
        research_app(args=args_list, prog_name="gaia-research")
    except SystemExit as exc:
        if exc.code == 0:
            return 0
        raise
    return 0

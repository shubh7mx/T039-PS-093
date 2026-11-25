"""Command-line entry point for PS-093."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from commands import LeagueEngine
from console import render_report


USAGE = """Usage:
  python main.py <commands-file> [data-dir] [output-dir]

Example:
  python main.py T039-PS-093-sample-data/commands.txt T039-PS-093-sample-data

Options:
  -h, --help  Show this help message."""


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0 if argv else 2
    if len(argv) > 3:
        print(USAGE)
        return 2
    commands_path = Path(argv[0])
    data_dir = Path(argv[1]) if len(argv) >= 2 else commands_path.parent
    output_dir = Path(argv[2]) if len(argv) >= 3 else Path(".")
    engine = LeagueEngine(data_dir, output_dir)
    try:
        engine.run_file(commands_path)
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    colour_enabled = sys.stdout.isatty() and "NO_COLOR" not in os.environ
    print(render_report(engine, colour_enabled))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


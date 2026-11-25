"""Command-line entry point for PS-093."""

from __future__ import annotations

import sys
from pathlib import Path

from commands import LeagueEngine


def main(argv: list[str]) -> int:
    if not 1 <= len(argv) <= 3:
        print("Usage: python main.py <commands-file> [data-dir] [output-dir]")
        return 2
    commands_path = Path(argv[0])
    data_dir = Path(argv[1]) if len(argv) >= 2 else commands_path.parent
    output_dir = Path(argv[2]) if len(argv) >= 3 else Path(".")
    engine = LeagueEngine(data_dir, output_dir)
    for line in engine.run_file(commands_path):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


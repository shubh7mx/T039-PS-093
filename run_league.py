import sys
from commands import LeagueEngine


# run cli
def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python3 run_league.py <command_file>")
        return 1
    engine = LeagueEngine()
    if sys.argv[1] == "-":
        lines = sys.stdin.readlines()
    else:
        with open(sys.argv[1], "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    output = engine.run_lines(lines)
    for line in output:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

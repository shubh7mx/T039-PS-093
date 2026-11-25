"""Readable terminal report for a completed league command run."""

from __future__ import annotations

from collections import Counter

from commands import LeagueEngine
from models import Standing


WIDTH = 78
RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"


def _paint(text: str, colour: str, enabled: bool) -> str:
    return f"{colour}{text}{RESET}" if enabled else text


def _section(title: str, colour_enabled: bool) -> list[str]:
    return ["", _paint(title.upper(), BOLD + CYAN, colour_enabled), "-" * WIDTH]


def _issue_text(line: str) -> str:
    return line.removeprefix("UNSATISFIED CONSTRAINT: ").strip()


def _step_label(step: str) -> str:
    return {
        "1": "wins",
        "2": "H2H",
        "3": "NRR",
        "4": "H2H NRR",
        "5": "forfeits",
        "6": "team ID",
    }.get(step, "points")


def _table_lines(
    rows: list[Standing],
    colour_enabled: bool,
    qualify_top_four: bool = False,
) -> list[str]:
    lines = [
        "  POS   TEAM      P   W   L  NR  FF  PTS    NRR     DECIDED BY",
        "  " + "-" * (WIDTH - 2),
    ]
    for row in rows:
        qualifier = "Q" if qualify_top_four and row.position <= 4 else " "
        detail = (
            f"  {row.position:>3} {qualifier} {row.team_id:<8} "
            f"{row.played:>2} {row.won:>3} {row.lost:>3} {row.no_result:>3} "
            f"{row.forfeits:>3} {row.points:>4} {row.nrr:>+8.4f}  "
            f"{_step_label(row.decided_by_step)}"
        )
        lines.append(_paint(detail, GREEN, colour_enabled) if qualifier == "Q" else detail)
    return lines


def _fixture_lines(engine: LeagueEngine, colour_enabled: bool) -> list[str]:
    lines: list[str] = []
    for round_no in sorted(engine.round_end):
        fixtures = [
            fixture
            for fixture in engine.fixtures
            if fixture.round_no == round_no
        ]
        lines.append("")
        lines.append(_paint(f"  Round {round_no:02d}", BOLD, colour_enabled))
        lines.append("  ID       DATE        TIME   HOME     AWAY     VENUE   STATUS")
        for fixture in fixtures:
            lines.append(
                f"  {fixture.fixture_id:<8} {fixture.match_date}  "
                f"{fixture.start_time}  {fixture.home_team_id:<8} "
                f"{fixture.away_team_id:<8} {fixture.venue_id:<7} "
                f"{fixture.status.value}"
            )
    return lines


def render_report(engine: LeagueEngine, colour_enabled: bool = False) -> str:
    """Print the complete requested league output in readable sections."""
    lines = [
        "=" * WIDTH,
        _paint("  PS-093  LEAGUE COMPETITION ENGINE", BOLD + CYAN, colour_enabled),
        "  Team T039  |  Section CSDS B",
        "=" * WIDTH,
    ]

    unique_issues = list(
        dict.fromkeys(
            _issue_text(line)
            for line in engine.outputs
            if line.startswith("UNSATISFIED CONSTRAINT:")
        )
    )
    lines.extend(_section("1. Run overview", colour_enabled))
    status = (
        _paint("READY WITH WARNINGS", YELLOW, colour_enabled)
        if unique_issues
        else _paint("ALL CONSTRAINTS SATISFIED", GREEN, colour_enabled)
    )
    lines.extend(
        [
            f"  Status    : {status}",
            f"  Fixtures  : {len(engine.fixtures)}",
            f"  Rounds    : {len(engine.round_end)}",
            "  Method    : circle method + constraint-aware placement",
        ]
    )
    if unique_issues:
        lines.append("  Warnings  :")
        for issue in unique_issues:
            lines.append(f"    {_paint('!', YELLOW, colour_enabled)} {issue}")

    action_counts = Counter(row.action for row in engine.result_log)
    fixture_statuses = Counter(fixture.status.value for fixture in engine.fixtures)
    lines.extend(
        [
            "",
            f"  Result commands : {len(engine.result_log)}",
            f"  Results applied : {action_counts.get('RECORDED', 0)}",
            f"  Rescheduled     : {action_counts.get('RESCHEDULED', 0)}",
            f"  Rejected        : {action_counts.get('REJECTED', 0)}",
            f"  Rounds closed   : {max(engine.round_end, default=0)}",
            f"  Withdrawals     : {len(engine.withdrawals)}",
            f"  Over-rate calls : {len(engine.penalties)}",
        ]
    )
    status_text = "  ".join(
        f"{name}={fixture_statuses[name]}"
        for name in ("PLAYED", "ABANDONED", "FORFEIT", "WALKOVER", "CANCELLED")
        if fixture_statuses[name]
    )
    lines.append(f"  Final states    : {status_text}")

    for row in (item for item in engine.result_log if item.action == "RESCHEDULED"):
        lines.append(
            f"  {_paint('>', GREEN, colour_enabled)} {row.fixture_id} rescheduled to {row.new_match_date}"
        )
    for row in (item for item in engine.result_log if item.action == "REJECTED"):
        lines.append(
            f"  {_paint('x', RED, colour_enabled)} {row.result_id} rejected: {row.reason}"
        )
    for withdrawal in engine.withdrawals:
        action = "results expunged" if withdrawal.expunged else "remaining fixtures walkovers"
        lines.append(
            f"  {_paint('>', YELLOW, colour_enabled)} {withdrawal.team_id} "
            f"withdrew after {withdrawal.played}/{withdrawal.total}; {action}"
        )

    lines.extend(_section("2. Requested point tables", colour_enabled))
    if engine.table_snapshots:
        for round_no, table in sorted(engine.table_snapshots.items()):
            title = (
                "Final table"
                if engine.closed and round_no == max(engine.round_end)
                else f"After round {round_no}"
            )
            lines.extend(["", _paint(f"  {title}", BOLD, colour_enabled)])
            lines.extend(
                _table_lines(
                    table,
                    colour_enabled,
                    qualify_top_four=engine.closed
                    and round_no == max(engine.round_end),
                )
            )
    else:
        lines.append("  No PRINT_TABLE command requested a round table.")

    lines.extend(_section("3. Qualification and playoffs", colour_enabled))
    if engine.final_table:
        eliminated = {
            team_id
            for team_id, team in engine.data.teams.items()
            if team.withdrawn_on is not None
        }
        active = [row for row in engine.final_table if row.team_id not in eliminated][:4]
        lines.extend(
            [
                "  SEED  TEAM      TEAM NAME                 PTS       NRR",
                "  " + "-" * (WIDTH - 2),
            ]
        )
        for seed, row in enumerate(active, start=1):
            name = engine.data.teams[row.team_id].name
            lines.append(
                f"  {seed:>4}  {row.team_id:<8} {name:<24} {row.points:>4} {row.nrr:>+9.4f}"
            )
    if engine.bracket:
        lines.append("")
        lines.append(_paint("  Bracket", BOLD, colour_enabled))
        for code in ("Q1", "ELIM", "Q2", "FINAL"):
            match = engine.bracket[code]
            first = match.team1_id or "TBD"
            second = match.team2_id or "TBD"
            winner = f"  winner: {match.winner_id}" if match.winner_id else ""
            lines.append(
                f"  {match.label:<14} {first:<8} vs {second:<8}{winner}"
            )
    else:
        lines.append("  Qualification has not been calculated.")

    lines.extend(_section("4. Complete fixture list", colour_enabled))
    lines.extend(_fixture_lines(engine, colour_enabled))

    lines.extend(_section("5. Output files", colour_enabled))
    preferred = [
        engine.output_dir / "result_log.csv",
        *sorted(engine.output_dir.glob("points_table_r*.csv")),
        engine.output_dir / "qualification.csv",
        engine.output_dir / "generated_fixtures.csv",
        engine.output_dir / "fixtures.csv",
    ]
    for path in dict.fromkeys(preferred):
        if path.exists():
            lines.append(
                f"  {_paint('+', GREEN, colour_enabled)} {path.name:<24} {path.stat().st_size:>6} bytes"
            )
    lines.extend(["", "=" * WIDTH])
    return "\n".join(lines)


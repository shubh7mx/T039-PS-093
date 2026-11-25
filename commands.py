"""Command-file dispatcher for the league engine."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from loaders import LeagueData, load_data, write_fixtures, write_points_table, write_qualification, write_result_log
from models import (
    Fixture,
    MatchResult,
    MatchStatus,
    Penalty,
    PlayoffMatch,
    ResultLogRow,
    Standing,
    Withdrawal,
)
from playoffs import bracket_lines, build_bracket, qualification_rows, record_playoff_result
from scheduler import audit_fixtures, generate_fixtures, reschedule_fixture
from standings import compute_standings, overs_to_balls


class LeagueEngine:
    def __init__(self, data_dir: str | Path, output_dir: str | Path = ".") -> None:
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.data: LeagueData = load_data(self.data_dir)
        self.fixtures: list[Fixture] = []
        self.fixtures_by_id: dict[str, Fixture] = {}
        self.round_end: dict[int, date] = {}
        self.current_round = 0
        self.penalties: list[Penalty] = []
        self.withdrawals: list[Withdrawal] = []
        self.result_log: list[ResultLogRow] = []
        self.bracket: dict[str, PlayoffMatch] | None = None
        self.final_table: list[Standing] = []
        self.table_snapshots: dict[int, list[Standing]] = {}
        self.closed = False
        self.outputs: list[str] = []
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def last_round_end(self) -> date:
        if not self.round_end:
            raise ValueError("No fixture list has been loaded or generated")
        return max(self.round_end.values())

    @property
    def league_cutoff(self) -> date:
        return self.last_round_end + timedelta(days=self.data.season.reserve_days)

    def run_file(self, path: str | Path) -> list[str]:
        with Path(path).open(encoding="utf-8") as handle:
            return self.run_lines(handle.readlines())

    def run_lines(self, lines: list[str]) -> list[str]:
        self.outputs = []
        for line_number, raw_line in enumerate(lines, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                self.execute(line.split("|"))
            except Exception as error:
                raise ValueError(f"Line {line_number}: {error}") from error
        self._write_result_log()
        return self.outputs

    def execute(self, fields: list[str]) -> None:
        command = fields[0].strip().upper()
        args = [field.strip() for field in fields[1:]]
        if command == "GENERATE_FIXTURES":
            self._generate(args[0] if args and args[0] else None)
        elif command == "CHECK_FIXTURES":
            self._check_fixtures()
        elif command == "LOAD_FIXTURES":
            self._load_fixtures(args[0])
        elif command == "RECORD_RESULT":
            self._record_result(args[0])
        elif command == "OVER_RATE_OFFENCE":
            self._record_offence(args[0])
        elif command == "WITHDRAW_TEAM":
            self._withdraw(args[0], date.fromisoformat(args[1]))
        elif command == "END_ROUND":
            self.current_round = int(args[0])
            self.outputs.append(f"END_ROUND {self.current_round}")
        elif command == "PRINT_TABLE":
            self._print_table(int(args[0]))
        elif command == "CLOSE_LEAGUE_STAGE":
            self._close_league()
        elif command == "PRINT_QUALIFICATION":
            self._print_qualification()
        elif command == "PRINT_FIXTURES":
            self._print_fixtures(args[0] if args and args[0] else None)
        elif command == "PLAYOFF_RESULT":
            self._record_playoff_result(args)
        else:
            raise ValueError(f"unknown command {command}")

    def _set_fixtures(self, fixtures: list[Fixture]) -> None:
        self.fixtures = sorted(fixtures, key=lambda item: item.fixture_id)
        self.fixtures_by_id = {fixture.fixture_id: fixture for fixture in self.fixtures}
        self.round_end = {}
        for fixture in self.fixtures:
            self.round_end[fixture.round_no] = max(
                self.round_end.get(fixture.round_no, fixture.original_date), fixture.original_date
            )

    def _generate(self, start_text: str | None) -> None:
        if start_text:
            self.data.season.start_date = date.fromisoformat(start_text)
        fixtures, issues = generate_fixtures(
            self.data.teams,
            self.data.venues,
            self.data.league_blackouts,
            self.data.season,
            self.data.distances,
        )
        self._set_fixtures(fixtures)
        write_fixtures(self.output_dir / "generated_fixtures.csv", fixtures)
        self.outputs.append(
            f"Generated {len(fixtures)} fixtures across {len(self.round_end)} rounds"
        )
        self.outputs.extend(issues)

    def _load_fixtures(self, filename: str) -> None:
        path = Path(filename)
        if not path.is_absolute():
            candidate = self.data_dir / filename
            path = candidate if candidate.exists() else Path(filename)
        import csv

        loaded: list[Fixture] = []
        with path.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                loaded.append(
                    Fixture(
                        fixture_id=row["fixture_id"],
                        round_no=int(row["round"]),
                        match_date=date.fromisoformat(row["match_date"]),
                        start_time=row["start_time"],
                        home_team_id=row["home_team_id"],
                        away_team_id=row["away_team_id"],
                        venue_id=row["venue_id"],
                    )
                )
        self._set_fixtures(loaded)
        self.outputs.append(f"Loaded {len(loaded)} fixtures from {filename}")

    def _check_fixtures(self) -> None:
        issues = audit_fixtures(
            self.fixtures,
            self.data.teams,
            self.data.venues,
            self.data.league_blackouts,
            self.data.season,
            self.data.distances,
        )
        if issues:
            self.outputs.extend(issues)
        else:
            self.outputs.append("All fixture constraints satisfied")

    def _reject(self, result_id: str, fixture_id: str, reason: str) -> None:
        self.result_log.append(
            ResultLogRow(result_id=result_id, fixture_id=fixture_id, action="REJECTED", reason=reason)
        )
        self.outputs.append(f"REJECTED {result_id}: {reason}")

    def _record_result(self, result_id: str) -> None:
        row = self.data.results.get(result_id)
        if row is None:
            self._reject(result_id, "", f"unknown result ID {result_id}")
            return
        fixture = self.fixtures_by_id.get(row.fixture_id)
        if fixture is None:
            self._reject(result_id, row.fixture_id, f"unknown fixture {row.fixture_id}")
            return
        if fixture.expunged or fixture.status in (MatchStatus.CANCELLED, MatchStatus.WALKOVER):
            self._reject(result_id, row.fixture_id, "fixture is cancelled, expunged, or already a walkover")
            return
        if fixture.result is not None and fixture.status not in (MatchStatus.POSTPONED,):
            self._reject(result_id, row.fixture_id, "a result has already been recorded")
            return
        if row.match_date != fixture.match_date:
            self._reject(
                result_id,
                row.fixture_id,
                f"fixture is scheduled on {fixture.match_date}, received {row.match_date}",
            )
            return
        if row.match_date > self.league_cutoff:
            self._reject(result_id, row.fixture_id, "result is after the last reserve day")
            return

        try:
            status = MatchStatus(row.status)
        except ValueError:
            self._reject(result_id, row.fixture_id, f"invalid status {row.status}")
            return

        if status == MatchStatus.POSTPONED:
            fixture.status = MatchStatus.POSTPONED
            new_date = reschedule_fixture(
                fixture,
                self.fixtures,
                self.data.teams,
                self.data.venues,
                self.data.league_blackouts,
                self.data.season,
                self.data.distances,
                self.last_round_end,
            )
            if new_date is None:
                fixture.event_date = self.league_cutoff
                self.result_log.append(
                    ResultLogRow(
                        result_id=result_id,
                        fixture_id=row.fixture_id,
                        action="CANCELLED",
                        reason="no legal slot before the reserve-day cutoff",
                        new_match_date="",
                    )
                )
                self.outputs.append(f"CANCELLED {result_id}: no legal reschedule slot")
            else:
                self.result_log.append(
                    ResultLogRow(
                        result_id=result_id,
                        fixture_id=row.fixture_id,
                        action="RESCHEDULED",
                        reason="POSTPONED result required a new date",
                        new_match_date=new_date.isoformat(),
                    )
                )
                self.outputs.append(f"RESCHEDULED {row.fixture_id} to {new_date}")
            self._after_possible_result()
            return

        result = MatchResult(
            status=status,
            batting_first=row.batting_first,
            home_runs=row.home_runs,
            home_wickets=row.home_wickets,
            home_overs=row.home_overs,
            away_runs=row.away_runs,
            away_wickets=row.away_wickets,
            away_overs=row.away_overs,
            play_completed_pct=row.play_completed_pct,
            allotted_overs=self.data.season.overs_per_innings,
            forfeited_by=row.forfeiting_team_id or None,
        )
        if status == MatchStatus.PLAYED:
            if overs_to_balls(row.home_overs) > result.allotted_overs * 6:
                self._reject(result_id, row.fixture_id, "home overs exceed the innings limit")
                return
            if overs_to_balls(row.away_overs) > result.allotted_overs * 6:
                self._reject(result_id, row.fixture_id, "away overs exceed the innings limit")
                return
            result.is_tie = row.home_runs == row.away_runs
            result.winner_id = (
                None
                if result.is_tie
                else fixture.home_team_id
                if row.home_runs > row.away_runs
                else fixture.away_team_id
            )
        elif status == MatchStatus.ABANDONED:
            if row.play_completed_pct < 50:
                result.is_no_result = True
            else:
                if row.home_overs == "0.0" or row.away_overs == "0.0":
                    self._reject(result_id, row.fixture_id, "a completed abandoned match needs score data")
                    return
                result.is_tie = row.home_runs == row.away_runs
                result.winner_id = (
                    None
                    if result.is_tie
                    else fixture.home_team_id
                    if row.home_runs > row.away_runs
                    else fixture.away_team_id
                )
        elif status == MatchStatus.FORFEIT:
            if row.forfeiting_team_id not in (fixture.home_team_id, fixture.away_team_id):
                self._reject(result_id, row.fixture_id, "forfeiting team does not play in this fixture")
                return
            result.winner_id = (
                fixture.away_team_id
                if row.forfeiting_team_id == fixture.home_team_id
                else fixture.home_team_id
            )
        else:
            self._reject(result_id, row.fixture_id, f"unsupported result status {status.value}")
            return

        fixture.status = status
        fixture.result = result
        fixture.event_date = row.match_date
        self.result_log.append(
            ResultLogRow(
                result_id=result_id,
                fixture_id=row.fixture_id,
                action="RECORDED",
                reason=status.value,
                new_match_date="",
            )
        )
        self.outputs.append(f"RECORDED {result_id}: {status.value}")
        self._after_possible_result()

    def _after_possible_result(self) -> None:
        if self.closed and self.bracket is not None:
            self._refresh_final_outputs()
        self._write_result_log()

    def _record_offence(self, offence_id: str) -> None:
        offence = self.data.offences.get(offence_id)
        if offence is None:
            raise ValueError(f"unknown offence {offence_id}")
        fixture = self.fixtures_by_id.get(offence.fixture_id)
        if fixture is None:
            raise ValueError(f"offence {offence_id} refers to unknown fixture")
        previous = sum(1 for item in self.penalties if item.team_id == offence.team_id)
        deduction = 0 if previous == 0 else 1 if previous == 1 else 2
        self.penalties.append(
            Penalty(
                offence_id=offence_id,
                team_id=offence.team_id,
                round_no=fixture.round_no,
                match_date=offence.match_date,
                deduction=deduction,
            )
        )
        self.outputs.append(
            f"OFFENCE {offence_id}: {offence.team_id} offence {previous + 1}, deduction {deduction}"
        )
        if self.closed:
            self._refresh_final_outputs()

    def _withdraw(self, team_id: str, withdrawal_date: date) -> None:
        team = self.data.teams.get(team_id)
        if team is None:
            raise ValueError(f"unknown team {team_id}")
        if team.withdrawn_on is not None:
            raise ValueError(f"team {team_id} has already withdrawn")
        team_fixtures = [
            fixture
            for fixture in self.fixtures
            if team_id in (fixture.home_team_id, fixture.away_team_id)
        ]
        played = sum(
            1
            for fixture in team_fixtures
            if fixture.status in (MatchStatus.PLAYED, MatchStatus.ABANDONED, MatchStatus.FORFEIT)
            and (fixture.event_date or fixture.match_date) <= withdrawal_date
        )
        total = len(team_fixtures)
        expunged = played * 2 < total
        team.withdrawn_on = withdrawal_date
        team.expunged = expunged
        if expunged:
            for fixture in team_fixtures:
                fixture.expunged = True
                if fixture.status == MatchStatus.SCHEDULED:
                    fixture.status = MatchStatus.CANCELLED
                    fixture.result = MatchResult(MatchStatus.CANCELLED, is_no_result=True)
        else:
            for fixture in team_fixtures:
                if fixture.status in (MatchStatus.SCHEDULED, MatchStatus.POSTPONED):
                    opponent = (
                        fixture.away_team_id
                        if fixture.home_team_id == team_id
                        else fixture.home_team_id
                    )
                    fixture.status = MatchStatus.WALKOVER
                    fixture.result = MatchResult(MatchStatus.WALKOVER, winner_id=opponent)
                    fixture.event_date = withdrawal_date
        self.withdrawals.append(
            Withdrawal(team_id, withdrawal_date, played, total, expunged)
        )
        self.outputs.append(
            f"WITHDRAWN {team_id}: {played}/{total}, {'expunged' if expunged else 'walkovers'}"
        )
        if self.closed:
            self._refresh_final_outputs()

    def _table_for_round(self, round_no: int) -> list[Standing]:
        if round_no not in self.round_end:
            raise ValueError(f"round {round_no} is not present")
        return compute_standings(
            self.data.teams,
            self.fixtures,
            self.penalties,
            up_to_round=round_no,
            round_end=self.round_end[round_no],
        )

    def _print_table(self, round_no: int) -> None:
        table = self._table_for_round(round_no)
        self.table_snapshots[round_no] = table
        path = self.output_dir / f"points_table_r{round_no:02d}.csv"
        write_points_table(path, table)
        self.outputs.append(f"POINTS TABLE ROUND {round_no}")
        for row in table:
            self.outputs.append(
                f"{row.position:>2}. {row.team_id:<7} {row.points:>3} pts  {row.nrr:+.4f}"
            )

    def _close_league(self) -> None:
        self.closed = True
        self._refresh_final_outputs()
        self.outputs.append("LEAGUE STAGE CLOSED")

    def _refresh_final_outputs(self) -> None:
        table = compute_standings(self.data.teams, self.fixtures, self.penalties)
        self.final_table = table
        final_round = max(self.round_end)
        self.table_snapshots[final_round] = table
        write_points_table(
            self.output_dir / f"points_table_r{final_round:02d}.csv", table
        )
        eliminated = {
            team_id for team_id, team in self.data.teams.items() if team.withdrawn_on
        }
        self.bracket = build_bracket(table, eliminated)
        rows = qualification_rows(table, eliminated)
        write_qualification(self.output_dir / "qualification.csv", rows)

    def _print_qualification(self) -> None:
        eliminated = {
            team_id for team_id, team in self.data.teams.items() if team.withdrawn_on
        }
        if self.bracket is None:
            self.final_table = compute_standings(
                self.data.teams, self.fixtures, self.penalties
            )
            self.bracket = build_bracket(self.final_table, eliminated)
            write_qualification(
                self.output_dir / "qualification.csv",
                qualification_rows(self.final_table, eliminated),
            )
        active = [row for row in self.final_table if row.team_id not in eliminated][:4]
        self.outputs.append("QUALIFICATION")
        self.outputs.extend(f"{row.position}. {row.team_id}" for row in active)
        self.outputs.extend(bracket_lines(self.bracket))

    def _record_playoff_result(self, args: list[str]) -> None:
        if self.bracket is None:
            self._close_league()
        if self.bracket is None:
            raise ValueError("playoff bracket is not available")
        code = args[0]
        winner = args[1] if len(args) > 1 and args[1] else None
        tied = len(args) > 2 and args[2].lower() == "true"
        match = record_playoff_result(self.bracket, code, winner, tied)
        self.outputs.append(f"PLAYOFF {match.label}: {match.winner_id} won")

    def _print_fixtures(self, round_text: str | None) -> None:
        fixtures = self.fixtures
        if round_text:
            round_no = int(round_text)
            fixtures = [item for item in fixtures if item.round_no == round_no]
        write_fixtures(self.output_dir / "fixtures.csv", fixtures)
        self.outputs.append(f"FIXTURES ({len(fixtures)})")
        for fixture in fixtures:
            self.outputs.append(
                f"{fixture.fixture_id} R{fixture.round_no} {fixture.match_date} "
                f"{fixture.home_team_id} v {fixture.away_team_id} "
                f"{fixture.venue_id} {fixture.status.value}"
            )

    def _write_result_log(self) -> None:
        write_result_log(self.output_dir / "result_log.csv", self.result_log)

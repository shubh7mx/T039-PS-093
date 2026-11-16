import shlex
from datetime import date, timedelta
from typing import Optional
from data_types import (
    Fixture,
    MatchResult,
    MatchStatus,
    PenaltyOffence,
    PlayoffMatch,
    SeasonConfig,
    StandingsRow,
    Team,
    Venue,
)
from make_schedule import assign_start_times, generate_schedule, reschedule_postponed_fixture
from playoffs import build_playoff_bracket, record_playoff_outcome
from points_table import compute_standings
from run_rate import overs_to_balls


# parse date
def _parse_date(text: str) -> date:
    return date.fromisoformat(text.strip())


# expand dates
def _parse_dates(spec: str) -> set[date]:
    out: set[date] = set()
    for part in spec.split(","):
        item = part.strip()
        if not item:
            continue
        if ".." in item:
            start_s, end_s = item.split("..", 1)
            d1 = _parse_date(start_s)
            d2 = _parse_date(end_s)
            cur = d1
            while cur <= d2:
                out.add(cur)
                cur += timedelta(days=1)
        else:
            out.add(_parse_date(item))
    return out


# parse bool
def _parse_bool(val: str) -> bool:
    return val.strip().lower() in ("true", "1", "yes", "y")


# split args
def _split_kv(tokens: list[str]) -> tuple[list[str], dict[str, str]]:
    pos: list[str] = []
    kv: dict[str, str] = {}
    for tok in tokens:
        if "=" in tok:
            k, v = tok.split("=", 1)
            kv[k.strip().lower()] = v.strip()
        else:
            pos.append(tok)
    return pos, kv


class LeagueEngine:
    def __init__(self) -> None:
        self.venues: dict[str, Venue] = {}
        self.teams: dict[str, Team] = {}
        self.distances: dict[tuple[str, str], float] = {}
        self.season = SeasonConfig()
        self.fixtures: list[Fixture] = []
        self.penalties: list[PenaltyOffence] = []
        self.bracket: Optional[dict[str, PlayoffMatch]] = None
        self.qualifiers: list[StandingsRow] = []
        self.current_date: Optional[date] = None
        self.orig_round_end: dict[int, date] = {}
        self.orig_last_round_end: Optional[date] = None
        self.unsatisfied_constraints: list[str] = []

    # run file
    def run_file(self, path: str) -> list[str]:
        with open(path, "r", encoding="utf-8") as fh:
            return self.run_lines(fh.readlines())

    # run lines
    def run_lines(self, lines: list[str]) -> list[str]:
        outputs: list[str] = []
        for line_no, raw in enumerate(lines, start=1):
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            out = self.execute_line(stripped, line_no)
            if out:
                outputs.extend(out)
        return outputs

    # run command
    def execute_line(self, line: str, line_no: int = 0) -> list[str]:
        tokens = shlex.split(line)
        if not tokens:
            return []
        cmd = tokens[0].upper()
        rest = tokens[1:]
        pos, kv = _split_kv(rest)
        out: list[str] = []

        if cmd == "VENUE":
            vid = pos[0]
            city = pos[1]
            cap = int(pos[2])
            avail = _parse_dates(kv["available"]) if "available" in kv else None
            black = _parse_dates(kv["blackout"]) if "blackout" in kv else set()
            self.venues[vid] = Venue(venue_id=vid, city=city, capacity=cap, available_dates=avail, blackout_dates=black)

        elif cmd == "VENUE_BLACKOUT":
            vid = pos[0]
            for item in pos[1:]:
                self.venues[vid].blackout_dates.update(_parse_dates(item))

        elif cmd == "VENUE_AVAILABLE":
            vid = pos[0]
            dates_set: set[date] = set()
            for item in pos[1:]:
                dates_set.update(_parse_dates(item))
            if self.venues[vid].available_dates is None:
                self.venues[vid].available_dates = dates_set
            else:
                self.venues[vid].available_dates.update(dates_set)

        elif cmd == "TEAM":
            tid, name, home_vid, city = pos[0], pos[1], pos[2], pos[3]
            if home_vid not in self.venues:
                raise ValueError(f"Line {line_no}: Unknown venue {home_vid}")
            self.teams[tid] = Team(team_id=tid, name=name, home_venue_id=home_vid, city=city)

        elif cmd == "DISTANCE":
            c1, c2, km = pos[0], pos[1], float(pos[2])
            self.distances[(c1, c2)] = km
            self.distances[(c2, c1)] = km

        elif cmd == "SEASON":
            if "start" in kv:
                self.season.start_date = _parse_date(kv["start"])
            if "blackout" in kv:
                self.season.blackout_dates.update(_parse_dates(kv["blackout"]))
            if "windows" in kv:
                self.season.broadcast_windows = [w.strip() for w in kv["windows"].split(",") if w.strip()]
            if "overs" in kv:
                self.season.overs_per_innings = int(kv["overs"])
            if "reserve_days" in kv:
                self.season.reserve_days = int(kv["reserve_days"])

        elif cmd == "SEASON_START":
            self.season.start_date = _parse_date(pos[0])

        elif cmd == "BLACKOUT":
            for item in pos:
                self.season.blackout_dates.update(_parse_dates(item))

        elif cmd == "BROADCAST_WINDOWS":
            self.season.broadcast_windows = list(pos)

        elif cmd == "SET_DATE":
            self.current_date = _parse_date(pos[0])

        elif cmd == "GENERATE_FIXTURES":
            self.fixtures, self.unsatisfied_constraints = generate_schedule(
                self.teams, self.venues, self.distances, self.season
            )
            self.orig_round_end = {}
            for f in self.fixtures:
                prev = self.orig_round_end.get(f.round_no)
                if prev is None or f.match_date > prev:
                    self.orig_round_end[f.round_no] = f.match_date
            self.orig_last_round_end = max(self.orig_round_end.values()) if self.orig_round_end else None
            out.append(f"Generated {len(self.fixtures)} fixtures across {len(self.orig_round_end)} rounds.")
            if self.unsatisfied_constraints:
                out.extend(self.unsatisfied_constraints)
            else:
                out.append("All scheduling constraints satisfied.")

        elif cmd in ("RESULT", "RECORD_RESULT"):
            out.append(self._handle_result(pos, kv))

        elif cmd in ("SLOW_OVER_RATE", "PENALTY"):
            tid = pos[0]
            rnd = int(pos[1])
            out.append(self._handle_penalty(tid, rnd))

        elif cmd in ("WITHDRAW", "WITHDRAW_TEAM"):
            tid = pos[0]
            out.append(self._handle_withdraw(tid))

        elif cmd == "PLAYOFF_RESULT":
            out.append(self._handle_playoff_result(pos, kv))

        elif cmd == "PRINT_FIXTURES":
            rnd_filter = int(kv["round"]) if "round" in kv else None
            team_filter = kv.get("team")
            out.extend(self.format_fixtures(round_no=rnd_filter, team_id=team_filter))

        elif cmd == "PRINT_TABLE":
            rnd_filter = int(kv["round"]) if "round" in kv else (int(pos[0]) if pos else None)
            out.extend(self.format_table(up_to_round=rnd_filter))

        elif cmd == "PRINT_QUALIFICATION":
            out.extend(self.format_qualification())

        else:
            raise ValueError(f"Line {line_no}: Unknown command {cmd}")

        return out

    # record result
    def _handle_result(self, pos: list[str], kv: dict[str, str]) -> str:
        fix_id = pos[0]
        res_date = _parse_date(pos[1])
        status_str = pos[2].upper()

        fix = next((f for f in self.fixtures if f.fixture_id == fix_id), None)
        if fix is None:
            return f"REJECTED: Unknown fixture {fix_id}"
        if fix.expunged or fix.status == MatchStatus.CANCELLED:
            return f"REJECTED: Fixture {fix_id} is cancelled or expunged"
        if fix.status not in (MatchStatus.SCHEDULED, MatchStatus.POSTPONED):
            return f"REJECTED: Duplicate result for fixture {fix_id} (already {fix.status.value})"
        if res_date != fix.match_date:
            return f"REJECTED: Fixture {fix_id} is not scheduled on {res_date.isoformat()} (scheduled {fix.match_date.isoformat()})"

        entry_date = _parse_date(kv["entered_on"]) if "entered_on" in kv else self.current_date
        if entry_date is not None and entry_date < fix.match_date:
            return f"REJECTED: Result entered on {entry_date.isoformat()} before fixture date {fix.match_date.isoformat()}"

        try:
            status = MatchStatus(status_str)
        except ValueError:
            return f"REJECTED: Invalid status {status_str}"

        allotted = int(kv.get("allotted_overs", self.season.overs_per_innings))

        if status == MatchStatus.PLAYED:
            h_runs = int(kv.get("home_runs", "0"))
            a_runs = int(kv.get("away_runs", "0"))
            h_overs = kv.get("home_overs", str(allotted))
            a_overs = kv.get("away_overs", str(allotted))
            h_out = _parse_bool(kv.get("home_all_out", "false")) or int(kv.get("home_wickets", "0")) >= 10
            a_out = _parse_bool(kv.get("away_all_out", "false")) or int(kv.get("away_wickets", "0")) >= 10
            try:
                hb = overs_to_balls(h_overs)
                ab = overs_to_balls(a_overs)
                if hb > allotted * 6 or ab > allotted * 6:
                    return f"REJECTED: Overs exceed allotted {allotted} overs for {fix_id}"
            except ValueError as err:
                return f"REJECTED: {err}"

            is_tie = h_runs == a_runs
            winner_id: Optional[str] = None
            if not is_tie:
                winner_id = fix.home_team_id if h_runs > a_runs else fix.away_team_id

            fix.status = MatchStatus.PLAYED
            fix.result = MatchResult(
                status=MatchStatus.PLAYED,
                winner_id=winner_id,
                is_tie=is_tie,
                home_runs=h_runs,
                home_overs=h_overs,
                home_all_out=h_out,
                away_runs=a_runs,
                away_overs=a_overs,
                away_all_out=a_out,
                allotted_overs=allotted,
            )
            return f"RECORDED: {fix_id} PLAYED ({fix.home_team_id} {h_runs}/{h_overs} vs {fix.away_team_id} {a_runs}/{a_overs})"

        if status == MatchStatus.ABANDONED:
            h_runs = int(kv.get("home_runs", "0"))
            a_runs = int(kv.get("away_runs", "0"))
            h_overs = kv.get("home_overs", "0.0")
            a_overs = kv.get("away_overs", "0.0")
            h_out = _parse_bool(kv.get("home_all_out", "false"))
            a_out = _parse_bool(kv.get("away_all_out", "false"))
            if "play_pct" in kv:
                play_pct = float(kv["play_pct"])
            elif "home_overs" in kv or "away_overs" in kv:
                total_balls = overs_to_balls(h_overs) + overs_to_balls(a_overs)
                play_pct = (total_balls / (2.0 * allotted * 6.0)) * 100.0
            else:
                play_pct = 0.0

            if play_pct < 50.0:
                fix.status = MatchStatus.ABANDONED
                fix.result = MatchResult(
                    status=MatchStatus.ABANDONED,
                    is_no_result=True,
                    play_pct=play_pct,
                    allotted_overs=allotted,
                )
                return f"RECORDED: {fix_id} ABANDONED (<50% play: {play_pct:.1f}%) -> NO RESULT"

            winner = kv.get("winner")
            if winner is not None:
                if winner not in (fix.home_team_id, fix.away_team_id):
                    return f"REJECTED: Invalid winner {winner} for {fix_id}"
                fix.status = MatchStatus.ABANDONED
                fix.result = MatchResult(
                    status=MatchStatus.ABANDONED,
                    winner_id=winner,
                    home_runs=h_runs,
                    home_overs=h_overs,
                    home_all_out=h_out,
                    away_runs=a_runs,
                    away_overs=a_overs,
                    away_all_out=a_out,
                    allotted_overs=allotted,
                    play_pct=play_pct,
                )
                return f"RECORDED: {fix_id} ABANDONED (>=50% play) -> winner {winner}"

            if h_runs != a_runs:
                w = fix.home_team_id if h_runs > a_runs else fix.away_team_id
                fix.status = MatchStatus.ABANDONED
                fix.result = MatchResult(
                    status=MatchStatus.ABANDONED,
                    winner_id=w,
                    home_runs=h_runs,
                    home_overs=h_overs,
                    home_all_out=h_out,
                    away_runs=a_runs,
                    away_overs=a_overs,
                    away_all_out=a_out,
                    allotted_overs=allotted,
                    play_pct=play_pct,
                )
                return f"RECORDED: {fix_id} ABANDONED (>=50% play) -> winner {w}"

            fix.status = MatchStatus.ABANDONED
            fix.result = MatchResult(
                status=MatchStatus.ABANDONED,
                is_no_result=True,
                play_pct=play_pct,
                allotted_overs=allotted,
            )
            return f"RECORDED: {fix_id} ABANDONED -> NO RESULT"

        if status == MatchStatus.FORFEIT:
            winner = kv.get("winner")
            forfeited_by = kv.get("forfeited_by")
            if winner is not None:
                if winner not in (fix.home_team_id, fix.away_team_id):
                    return f"REJECTED: Invalid winner {winner} for {fix_id}"
                forfeited_by = fix.away_team_id if winner == fix.home_team_id else fix.home_team_id
            elif forfeited_by is not None:
                if forfeited_by not in (fix.home_team_id, fix.away_team_id):
                    return f"REJECTED: Invalid team {forfeited_by} for {fix_id}"
                winner = fix.away_team_id if forfeited_by == fix.home_team_id else fix.home_team_id
            else:
                return f"REJECTED: FORFEIT requires winner or forfeited_by for {fix_id}"

            fix.status = MatchStatus.FORFEIT
            fix.result = MatchResult(
                status=MatchStatus.FORFEIT,
                winner_id=winner,
                forfeited_by=forfeited_by,
            )
            return f"RECORDED: {fix_id} FORFEIT -> winner {winner} (forfeited by {forfeited_by})"

        if status == MatchStatus.POSTPONED:
            if self.orig_last_round_end is None:
                return f"REJECTED: Schedule not generated"
            ok, new_date = reschedule_postponed_fixture(
                fix,
                self.fixtures,
                self.teams,
                self.venues,
                self.distances,
                self.season,
                self.orig_last_round_end,
            )
            if ok and new_date is not None:
                return f"POSTPONED: {fix_id} rescheduled from {res_date.isoformat()} to {new_date.isoformat()} {fix.start_time}"
            return f"POSTPONED: {fix_id} cancelled as NO RESULT (no valid slot before reserve cutoff)"

        return f"REJECTED: Unsupported status {status_str}"

    # record penalty
    def _handle_penalty(self, team_id: str, round_no: int) -> str:
        if team_id not in self.teams:
            raise ValueError(f"Unknown team {team_id}")
        prior = sum(1 for p in self.penalties if p.team_id == team_id)
        num = prior + 1
        deduction = 0 if num == 1 else (1 if num == 2 else 2)
        self.penalties.append(
            PenaltyOffence(team_id=team_id, round_no=round_no, offence_num=num, deduction=deduction)
        )
        return f"PENALTY: {team_id} slow-over-rate offence #{num} in Round {round_no} -> -{deduction} pt(s)"

    # team withdrawal
    def _handle_withdraw(self, team_id: str) -> str:
        if team_id not in self.teams:
            raise ValueError(f"Unknown team {team_id}")
        team = self.teams[team_id]
        team_fixes = [f for f in self.fixtures if team_id in (f.home_team_id, f.away_team_id)]
        played_cnt = sum(
            1
            for f in team_fixes
            if f.status in (MatchStatus.PLAYED, MatchStatus.ABANDONED, MatchStatus.FORFEIT)
        )
        total_cnt = len(team_fixes)
        team.withdrawn = True

        # check 50 percent
        if played_cnt * 2 < total_cnt:
            team.expunged = True
            for f in team_fixes:
                if f.status in (MatchStatus.PLAYED, MatchStatus.ABANDONED, MatchStatus.FORFEIT):
                    f.expunged = True
                else:
                    f.status = MatchStatus.CANCELLED
                    f.expunged = True
            assign_start_times(self.fixtures, self.season)
            return f"WITHDRAW: {team_id} played {played_cnt}/{total_cnt} (<50%) -> played results expunged, remaining cancelled"

        for f in team_fixes:
            if f.status in (MatchStatus.SCHEDULED, MatchStatus.POSTPONED):
                opp_id = f.away_team_id if f.home_team_id == team_id else f.home_team_id
                f.status = MatchStatus.WALKOVER
                f.result = MatchResult(status=MatchStatus.WALKOVER, winner_id=opp_id)
        assign_start_times(self.fixtures, self.season)
        return f"WITHDRAW: {team_id} played {played_cnt}/{total_cnt} (>=50%) -> results stand, remaining awarded as 2-pt walkovers"

    # playoff result
    def _handle_playoff_result(self, pos: list[str], kv: dict[str, str]) -> str:
        if self.bracket is None:
            standings = compute_standings(self.teams, self.fixtures, self.penalties, None, self.orig_round_end)
            self.qualifiers, self.bracket = build_playoff_bracket(standings)
        code = pos[0].upper()
        status_str = pos[1].upper() if len(pos) > 1 else "PLAYED"
        status = MatchStatus(status_str)
        winner = kv.get("winner")
        is_tie = _parse_bool(kv.get("tie", "false"))
        is_nr = _parse_bool(kv.get("no_result", "false"))
        if not is_tie and "home_runs" in kv and "away_runs" in kv:
            hr = int(kv["home_runs"])
            ar = int(kv["away_runs"])
            if hr == ar:
                is_tie = True
        pm = record_playoff_outcome(
            self.bracket, code, status, winner_id=winner, is_tie=is_tie, is_no_result=is_nr
        )
        msg = f"PLAYOFF {code}: winner {pm.winner_id}"
        if pm.note:
            msg += f" ({pm.note})"
        return msg

    # format fixtures
    def format_fixtures(self, round_no: Optional[int] = None, team_id: Optional[str] = None) -> list[str]:
        rows = list(self.fixtures)
        if round_no is not None:
            rows = [f for f in rows if f.round_no == round_no]
        if team_id is not None:
            rows = [f for f in rows if team_id in (f.home_team_id, f.away_team_id)]
        lines = [
            f"=== FIXTURES ({len(rows)}) ===",
            f"{'ID':<5} {'RND':<4} {'DATE':<10} {'TIME':<6} {'HOME':<6} {'AWAY':<6} {'VENUE':<6} {'CITY':<12} {'STATUS':<10} {'NOTE'}",
        ]
        for f in sorted(rows, key=lambda x: (x.match_date, x.start_time, x.fixture_id)):
            notes: list[str] = []
            if f.swapped_from_blackout:
                notes.append("H/A swapped (blackout)")
            if f.rescheduled_from is not None:
                notes.append(f"from {f.rescheduled_from.isoformat()}")
            if f.expunged:
                notes.append("EXPUNGED")
            lines.append(
                f"{f.fixture_id:<5} R{f.round_no:<3} {f.match_date.isoformat():<10} {f.start_time:<6} "
                f"{f.home_team_id:<6} {f.away_team_id:<6} {f.venue_id:<6} {f.city:<12} {f.status.value:<10} {', '.join(notes)}"
            )
        return lines

    # format table
    def format_table(self, up_to_round: Optional[int] = None) -> list[str]:
        rows = compute_standings(
            self.teams, self.fixtures, self.penalties, up_to_round=up_to_round, orig_round_end=self.orig_round_end
        )
        title = f"=== POINTS TABLE (AFTER ROUND {up_to_round}) ===" if up_to_round is not None else "=== POINTS TABLE ==="
        lines = [
            title,
            f"{'POS':<4} {'ID':<5} {'TEAM':<20} {'P':<3} {'W':<3} {'L':<3} {'T':<3} {'NR':<3} {'FF':<3} {'PEN':<4} {'PTS':<4} {'NRR':>8}  {'NOTE'}",
        ]
        for r in rows:
            tag = "[WITHDRAWN]" if r.withdrawn else ""
            note = f"{tag} {r.tie_break_note}".strip()
            lines.append(
                f"{r.rank:<4} {r.team_id:<5} {r.team_name:<20} {r.played:<3} {r.won:<3} {r.lost:<3} "
                f"{r.tied:<3} {r.no_result:<3} {r.forfeits:<3} {r.penalty_points:<4} {r.points:<4} {r.nrr:>+8.4f}  {note}"
            )
        return lines

    # format playoffs
    def format_qualification(self) -> list[str]:
        standings = compute_standings(self.teams, self.fixtures, self.penalties, None, self.orig_round_end)
        if self.bracket is None:
            self.qualifiers, self.bracket = build_playoff_bracket(standings)
        else:
            active = [row for row in standings if not row.withdrawn]
            self.qualifiers = active[:4]

        lines = ["=== QUALIFICATION REPORT ===", "Top 4 Qualifiers:"]
        for seed, row in enumerate(self.qualifiers, start=1):
            note = f" [{row.tie_break_note}]" if row.tie_break_note else ""
            lines.append(
                f"  Seed #{seed}: {row.team_id} ({row.team_name}) | Pts: {row.points} | W: {row.won} | NRR: {row.nrr:+.4f}{note}"
            )
        lines.append("Playoff Bracket:")
        for code in ("Q1", "ELIM", "Q2", "FINAL"):
            pm = self.bracket[code]
            t1 = f"{pm.team1_id}(#{pm.team1_seed})" if pm.team1_id else "TBD"
            t2 = f"{pm.team2_id}(#{pm.team2_seed})" if pm.team2_id else "TBD"
            res = f" -> Winner: {pm.winner_id}" if pm.winner_id else " (Scheduled)"
            extra = f" [{pm.note}]" if pm.note else ""
            lines.append(f"  {pm.label:<12}: {t1} vs {t2}{res}{extra}")
        final_pm = self.bracket["FINAL"]
        if final_pm.winner_id:
            lines.append(f"Champion: {final_pm.winner_id} ({self.teams[final_pm.winner_id].name})")
        return lines

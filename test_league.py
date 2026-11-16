import unittest
from datetime import date, timedelta
from commands import LeagueEngine
from data_types import Fixture, MatchResult, MatchStatus, SeasonConfig, Team, Venue
from playoffs import build_playoff_bracket, record_playoff_outcome
from points_table import compute_standings
from run_rate import compute_nrr, extract_match_nrr, overs_to_balls


# setup teams
def _setup_ten_team_engine(start: str = "2026-04-04") -> LeagueEngine:
    eng = LeagueEngine()
    cities = [
        ("V1", "Mumbai", 33000, "T01", "Mumbai"),
        ("V2", "Delhi", 41000, "T02", "Delhi"),
        ("V3", "Chennai", 38000, "T03", "Chennai"),
        ("V4", "Kolkata", 66000, "T04", "Kolkata"),
        ("V5", "Bengaluru", 40000, "T05", "Bengaluru"),
        ("V6", "Hyderabad", 39000, "T06", "Hyderabad"),
        ("V7", "Jaipur", 30000, "T07", "Jaipur"),
        ("V8", "Ahmedabad", 100000, "T08", "Ahmedabad"),
        ("V9", "Lucknow", 50000, "T09", "Lucknow"),
        ("V10", "Mohali", 28000, "T10", "Mohali"),
    ]
    lines = [f"SEASON start={start} windows=15:30,19:30 overs=20 reserve_days=3"]
    for vid, city, cap, tid, name in cities:
        lines.append(f"VENUE {vid} {city} {cap}")
        lines.append(f"TEAM {tid} \"{name}\" {vid} {city}")
    lines.append("DISTANCE Mumbai Kolkata 2050")
    lines.append("DISTANCE Delhi Chennai 2200")
    lines.append("DISTANCE Mohali Chennai 2450")
    lines.append("DISTANCE Kolkata Bengaluru 1870")
    lines.append("DISTANCE Mumbai Delhi 1400")
    lines.append("DISTANCE Jaipur Chennai 1500")
    eng.run_lines(lines)
    return eng


class TestLeagueEngine(unittest.TestCase):
    # circle method
    def test_double_round_robin_and_ha_streaks(self) -> None:
        eng = _setup_ten_team_engine()
        out = eng.run_lines(["GENERATE_FIXTURES"])
        self.assertEqual(len(eng.fixtures), 90)
        self.assertEqual(eng.unsatisfied_constraints, [], "\n".join(out))

        pairs = [(f.home_team_id, f.away_team_id) for f in eng.fixtures]
        self.assertEqual(len(set(pairs)), 90)
        for t1 in eng.teams:
            for t2 in eng.teams:
                if t1 != t2:
                    self.assertIn((t1, t2), pairs)

        for tid in eng.teams:
            seq = []
            for f in sorted(eng.fixtures, key=lambda x: (x.round_no, x.match_date)):
                if f.home_team_id == tid:
                    seq.append("H")
                elif f.away_team_id == tid:
                    seq.append("A")
            self.assertEqual(len(seq), 18)
            cur = 0
            prev = ""
            for ch in seq:
                cur = cur + 1 if ch == prev else 1
                prev = ch
                self.assertLessEqual(cur, 2)

    # broadcast windows
    def test_broadcast_and_rest_rules(self) -> None:
        eng = _setup_ten_team_engine()
        eng.run_lines(["GENERATE_FIXTURES"])
        by_day: dict[date, list[Fixture]] = {}
        for f in eng.fixtures:
            by_day.setdefault(f.match_date, []).append(f)
        for d, day_list in by_day.items():
            self.assertLessEqual(len(day_list), 2)
            if len(day_list) == 2:
                self.assertEqual(sorted(f.start_time for f in day_list), ["15:30", "19:30"])
            else:
                self.assertEqual(day_list[0].start_time, "19:30")

    # three-way tie
    def test_three_way_tie_restarts_chain(self) -> None:
        teams = {
            "A": Team("A", "Alpha", "V1", "C1"),
            "B": Team("B", "Beta", "V2", "C2"),
            "C": Team("C", "Gamma", "V3", "C3"),
            "D": Team("D", "Delta", "V4", "C4"),
        }
        d0 = date(2026, 5, 1)
        fixtures = [
            Fixture("Y1", 1, "A", "B", "V1", "C1", d0, status=MatchStatus.PLAYED,
                    result=MatchResult(MatchStatus.PLAYED, winner_id="A", home_runs=155, home_overs="20.0", away_runs=150, away_overs="20.0")),
            Fixture("Y2", 2, "A", "C", "V1", "C1", d0 + timedelta(days=1), status=MatchStatus.PLAYED,
                    result=MatchResult(MatchStatus.PLAYED, winner_id="A", home_runs=155, home_overs="20.0", away_runs=150, away_overs="20.0")),
            Fixture("Y3", 3, "B", "C", "V2", "C2", d0 + timedelta(days=2), status=MatchStatus.PLAYED,
                    result=MatchResult(MatchStatus.PLAYED, winner_id="B", home_runs=152, home_overs="20.0", away_runs=150, away_overs="20.0")),
            Fixture("Y4", 4, "C", "A", "V3", "C3", d0 + timedelta(days=3), status=MatchStatus.PLAYED,
                    result=MatchResult(MatchStatus.PLAYED, winner_id="C", home_runs=155, home_overs="20.0", away_runs=150, away_overs="20.0")),
            Fixture("Y5", 5, "B", "D", "V2", "C2", d0 + timedelta(days=4), status=MatchStatus.PLAYED,
                    result=MatchResult(MatchStatus.PLAYED, winner_id="B", home_runs=155, home_overs="20.0", away_runs=150, away_overs="20.0")),
            Fixture("Y6", 6, "C", "D", "V3", "C3", d0 + timedelta(days=5), status=MatchStatus.PLAYED,
                    result=MatchResult(MatchStatus.PLAYED, winner_id="C", home_runs=220, home_overs="20.0", away_runs=100, away_overs="20.0")),
            Fixture("Y7", 7, "D", "A", "V4", "C4", d0 + timedelta(days=6), status=MatchStatus.PLAYED,
                    result=MatchResult(MatchStatus.PLAYED, winner_id="D", home_runs=160, home_overs="20.0", away_runs=150, away_overs="20.0")),
        ]
        rows = compute_standings(teams, fixtures, [])
        self.assertEqual([r.team_id for r in rows[:3]], ["A", "B", "C"])
        self.assertGreater(rows[2].nrr, rows[1].nrr)

    # bowled out
    def test_bowled_out_in_14_3_uses_20_overs_for_nrr(self) -> None:
        self.assertEqual(overs_to_balls("14.3"), 87)
        self.assertEqual(overs_to_balls("12.4"), 76)
        fix = Fixture(
            "F001", 1, "T01", "T02", "V1", "Mumbai", date(2026, 4, 4),
            status=MatchStatus.PLAYED,
            result=MatchResult(
                MatchStatus.PLAYED,
                winner_id="T01",
                home_runs=180,
                home_overs="20.0",
                home_all_out=False,
                away_runs=120,
                away_overs="14.3",
                away_all_out=True,
                allotted_overs=20,
            ),
        )
        nrr_data = extract_match_nrr(fix)
        self.assertEqual(nrr_data, (180, 120, 120, 120))
        self.assertEqual(compute_nrr(180, 120, 120, 120), 3.0)
        self.assertEqual(compute_nrr(120, 120, 180, 120), -3.0)

    # weekend blackout
    def test_blackout_on_only_weekend_day_prints_unsatisfied(self) -> None:
        eng = LeagueEngine()
        lines = [
            "SEASON start=2026-04-04 blackout=2026-04-11,2026-04-12 overs=20",
            "VENUE V1 C1 10000",
            "VENUE V2 C2 10000",
            "VENUE V3 C3 10000",
            "VENUE V4 C4 10000",
            "TEAM T1 A V1 C1",
            "TEAM T2 B V2 C2",
            "TEAM T3 C V3 C3",
            "TEAM T4 D V4 C4",
            "GENERATE_FIXTURES",
        ]
        out = eng.run_lines(lines)
        joined = "\n".join(out)
        self.assertIn("UNSATISFIED CONSTRAINT:", joined)
        self.assertIn("2026-04-11", joined)

    # exact 1500km
    def test_postponed_match_with_1500_km_exact_uses_2_clear_days(self) -> None:
        teams = {
            "T1": Team("T1", "Jaipur", "V1", "Jaipur"),
            "T2": Team("T2", "Chennai", "V2", "Chennai"),
            "T3": Team("T3", "Delhi", "V3", "Delhi"),
            "T4": Team("T4", "Mumbai", "V4", "Mumbai"),
        }
        venues = {
            "V1": Venue("V1", "Jaipur", 30000),
            "V2": Venue("V2", "Chennai", 38000),
            "V3": Venue("V3", "Delhi", 40000),
            "V4": Venue("V4", "Mumbai", 33000),
        }
        distances = {("Jaipur", "Chennai"): 1500.0, ("Chennai", "Jaipur"): 1500.0}
        season = SeasonConfig(start_date=date(2026, 4, 1), reserve_days=3)
        eng = LeagueEngine()
        eng.venues = venues
        eng.teams = teams
        eng.distances = distances
        eng.season = season
        eng.fixtures = [
            Fixture("F1", 1, "T1", "T2", "V1", "Jaipur", date(2026, 4, 1)),
            Fixture("F2", 1, "T3", "T4", "V3", "Delhi", date(2026, 4, 2)),
            Fixture("F3", 2, "T2", "T4", "V2", "Chennai", date(2026, 4, 6)),
            Fixture("F4", 2, "T1", "T3", "V1", "Jaipur", date(2026, 4, 6)),
        ]
        eng.orig_round_end = {1: date(2026, 4, 2), 2: date(2026, 4, 6)}
        eng.orig_last_round_end = date(2026, 4, 6)
        out = eng.run_lines(["RESULT F1 2026-04-01 POSTPONED"])
        self.assertIn("2026-04-03", out[0])
        self.assertEqual(eng.fixtures[0].match_date, date(2026, 4, 3))

    # final penalty
    def test_second_slow_over_rate_in_final_round_changes_qualification(self) -> None:
        eng = LeagueEngine()
        eng.run_lines([
            "SEASON start=2026-04-01",
            "VENUE V1 C1 10000", "TEAM T1 One V1 C1",
            "VENUE V2 C2 10000", "TEAM T2 Two V2 C2",
            "VENUE V3 C3 10000", "TEAM T3 Three V3 C3",
            "VENUE V4 C4 10000", "TEAM T4 Four V4 C4",
            "VENUE V5 C5 10000", "TEAM T5 Five V5 C5",
            "VENUE V6 C6 10000", "TEAM T6 Six V6 C6",
            "GENERATE_FIXTURES",
        ])
        d0 = date(2026, 4, 1)
        eng.fixtures = [
            Fixture("M1", 1, "T1", "T6", "V1", "C1", d0, status=MatchStatus.PLAYED, result=MatchResult(MatchStatus.PLAYED, winner_id="T1", home_runs=180, home_overs="20", away_runs=150, away_overs="20")),
            Fixture("M2", 2, "T2", "T6", "V2", "C2", d0 + timedelta(days=1), status=MatchStatus.PLAYED, result=MatchResult(MatchStatus.PLAYED, winner_id="T2", home_runs=180, home_overs="20", away_runs=150, away_overs="20")),
            Fixture("M3", 3, "T3", "T6", "V3", "C3", d0 + timedelta(days=2), status=MatchStatus.PLAYED, result=MatchResult(MatchStatus.PLAYED, winner_id="T3", home_runs=180, home_overs="20", away_runs=150, away_overs="20")),
            Fixture("M4", 4, "T4", "T6", "V4", "C4", d0 + timedelta(days=3), status=MatchStatus.PLAYED, result=MatchResult(MatchStatus.PLAYED, winner_id="T4", home_runs=200, home_overs="20", away_runs=100, away_overs="20")),
            Fixture("M5", 10, "T5", "T6", "V5", "C5", d0 + timedelta(days=4), status=MatchStatus.PLAYED, result=MatchResult(MatchStatus.PLAYED, winner_id="T5", home_runs=160, home_overs="20", away_runs=150, away_overs="20")),
        ]
        eng.run_lines([
            "SLOW_OVER_RATE T4 5",
            "SLOW_OVER_RATE T4 10",
            "SLOW_OVER_RATE T6 5",
            "SLOW_OVER_RATE T6 10",
        ])
        rows = compute_standings(eng.teams, eng.fixtures, eng.penalties)
        by_id = {r.team_id: r for r in rows}
        self.assertEqual(by_id["T4"].points, 1)
        self.assertEqual(by_id["T5"].points, 2)
        self.assertEqual(by_id["T6"].points, -1)
        quals, _ = build_playoff_bracket(rows)
        self.assertEqual([q.team_id for q in quals], ["T1", "T2", "T3", "T5"])

    # forfeit h2h
    def test_forfeit_counts_in_h2h_but_excluded_from_nrr(self) -> None:
        teams = {
            "A": Team("A", "Alpha", "V1", "C1"),
            "B": Team("B", "Beta", "V2", "C2"),
            "C": Team("C", "Gamma", "V3", "C3"),
            "D": Team("D", "Delta", "V4", "C4"),
        }
        d0 = date(2026, 4, 1)
        fixtures = [
            Fixture("K1", 1, "A", "B", "V1", "C1", d0, status=MatchStatus.FORFEIT,
                    result=MatchResult(MatchStatus.FORFEIT, winner_id="A", forfeited_by="B")),
            Fixture("K2", 2, "B", "D", "V2", "C2", d0 + timedelta(days=3), status=MatchStatus.PLAYED,
                    result=MatchResult(MatchStatus.PLAYED, winner_id="B", home_runs=220, home_overs="20", away_runs=100, away_overs="20")),
            Fixture("K3", 3, "C", "A", "V3", "C3", d0 + timedelta(days=6), status=MatchStatus.PLAYED,
                    result=MatchResult(MatchStatus.PLAYED, winner_id="C", home_runs=160, home_overs="20", away_runs=150, away_overs="20")),
            Fixture("K4", 4, "C", "D", "V3", "C3", d0 + timedelta(days=9), status=MatchStatus.PLAYED,
                    result=MatchResult(MatchStatus.PLAYED, winner_id="C", home_runs=160, home_overs="20", away_runs=150, away_overs="20")),
        ]
        rows = compute_standings(teams, fixtures, [])
        self.assertEqual([r.team_id for r in rows[:3]], ["C", "A", "B"])
        by_id = {r.team_id: r for r in rows}
        self.assertEqual(by_id["A"].nrr, -0.5)
        self.assertEqual(by_id["B"].forfeits, 1)

    # team withdraw
    def test_withdraw_at_exactly_50_pct_and_below_50_pct(self) -> None:
        eng = _setup_ten_team_engine()
        eng.run_lines(["GENERATE_FIXTURES"])
        t10_fixes = [f for f in eng.fixtures if "T10" in (f.home_team_id, f.away_team_id)]
        self.assertEqual(len(t10_fixes), 18)
        for f in t10_fixes[:9]:
            eng.run_lines([
                f"RESULT {f.fixture_id} {f.match_date.isoformat()} PLAYED home_runs=170 home_overs=20 away_runs=160 away_overs=20"
            ])
        out = eng.run_lines(["WITHDRAW T10"])
        self.assertIn(">=50%", out[0])
        self.assertEqual(sum(1 for f in t10_fixes if f.expunged), 0)
        self.assertEqual(sum(1 for f in t10_fixes if f.status == MatchStatus.WALKOVER), 9)

        eng_low = _setup_ten_team_engine()
        eng_low.run_lines(["GENERATE_FIXTURES"])
        t10_low = [f for f in eng_low.fixtures if "T10" in (f.home_team_id, f.away_team_id)]
        for f in t10_low[:8]:
            eng_low.run_lines([
                f"RESULT {f.fixture_id} {f.match_date.isoformat()} PLAYED home_runs=170 home_overs=20 away_runs=160 away_overs=20"
            ])
        out_low = eng_low.run_lines(["WITHDRAW T10"])
        self.assertIn("<50%", out_low[0])
        self.assertEqual(sum(1 for f in t10_low if f.expunged), 18)

    # same city
    def test_two_venues_same_city_unavailable_consecutive_days(self) -> None:
        eng = _setup_ten_team_engine("2026-04-04")
        eng.run_lines([
            "VENUE V2_MUM Mumbai 45000 blackout=2026-04-05",
            "VENUE_BLACKOUT V1 2026-04-04",
            "TEAM T02 \"Mumbai Two\" V2_MUM Mumbai",
            "GENERATE_FIXTURES",
        ])
        for f in eng.fixtures:
            self.assertTrue(eng.venues[f.venue_id].is_available(f.match_date))
        self.assertEqual(eng.unsatisfied_constraints, [])

    # swap blackout
    def test_venue_blackout_5_days_swaps_home_away(self) -> None:
        eng = LeagueEngine()
        lines = [
            "SEASON start=2026-04-04 overs=20",
            "VENUE V1 Mumbai 33000 blackout=2026-04-04..2026-04-15",
            "VENUE V2 Delhi 41000",
            "VENUE V3 Chennai 38000",
            "VENUE V4 Kolkata 66000",
            "TEAM T1 Mumbai V1 Mumbai",
            "TEAM T2 Delhi V2 Delhi",
            "TEAM T3 Chennai V3 Chennai",
            "TEAM T4 Kolkata V4 Kolkata",
            "GENERATE_FIXTURES",
        ]
        eng.run_lines(lines)
        for f in eng.fixtures:
            self.assertTrue(eng.venues[f.venue_id].is_available(f.match_date))
        self.assertTrue(any(f.swapped_from_blackout for f in eng.fixtures))

    # reject results
    def test_result_validation_rejections(self) -> None:
        eng = _setup_ten_team_engine("2026-04-04")
        eng.run_lines(["GENERATE_FIXTURES"])
        f1 = eng.fixtures[0]
        out1 = eng.run_lines([
            "SET_DATE 2026-04-01",
            f"RESULT {f1.fixture_id} {f1.match_date.isoformat()} PLAYED home_runs=150 home_overs=20 away_runs=140 away_overs=20",
        ])
        self.assertTrue(out1[0].startswith("REJECTED:"))
        wrong_d = (f1.match_date + timedelta(days=1)).isoformat()
        out2 = eng.run_lines([
            "SET_DATE 2026-04-20",
            f"RESULT {f1.fixture_id} {wrong_d} PLAYED home_runs=150 home_overs=20 away_runs=140 away_overs=20",
        ])
        self.assertTrue(out2[0].startswith("REJECTED:"))
        out3 = eng.run_lines([
            f"RESULT {f1.fixture_id} {f1.match_date.isoformat()} PLAYED home_runs=150 home_overs=20 away_runs=140 away_overs=20",
            f"RESULT {f1.fixture_id} {f1.match_date.isoformat()} PLAYED home_runs=150 home_overs=20 away_runs=140 away_overs=20",
        ])
        self.assertTrue(out3[0].startswith("RECORDED:"))
        self.assertTrue(out3[1].startswith("REJECTED:"))

    # playoff tie
    def test_abandoned_50pct_and_playoff_tie(self) -> None:
        eng = _setup_ten_team_engine("2026-04-04")
        eng.run_lines(["GENERATE_FIXTURES"])
        f1 = eng.fixtures[0]
        out = eng.run_lines([
            f"RESULT {f1.fixture_id} {f1.match_date.isoformat()} ABANDONED play_pct=45"
        ])
        self.assertIn("NO RESULT", out[0])
        rows = compute_standings(eng.teams, eng.fixtures, [])
        by_id = {r.team_id: r for r in rows}
        self.assertEqual(by_id[f1.home_team_id].points, 1)
        self.assertEqual(by_id[f1.away_team_id].points, 1)

        quals, bracket = build_playoff_bracket(rows)
        pm = record_playoff_outcome(bracket, "Q1", MatchStatus.PLAYED, is_tie=True)
        self.assertEqual(pm.winner_id, quals[0].team_id)


if __name__ == "__main__":
    unittest.main()

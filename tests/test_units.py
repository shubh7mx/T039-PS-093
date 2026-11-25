from __future__ import annotations

import unittest
from datetime import date

from models import Fixture, MatchResult, MatchStatus, Penalty, Season, Team, Venue
from scheduler import _required_clear_days, audit_fixtures, round_robin_pairings
from standings import compute_standings, net_run_rate, overs_to_balls


class UnitTests(unittest.TestCase):
    def test_circle_method_builds_balanced_double_round_robin(self) -> None:
        teams = [f"T{number:02d}" for number in range(1, 11)]
        rounds, balanced = round_robin_pairings(teams)
        self.assertTrue(balanced)
        self.assertEqual(len(rounds), 18)
        self.assertTrue(all(len(round_matches) == 5 for round_matches in rounds))
        ordered_pairs = {
            (home, away) for round_matches in rounds for home, away in round_matches
        }
        self.assertEqual(len(ordered_pairs), 90)
        for team in teams:
            appearances = sum(
                team in pair for round_matches in rounds for pair in round_matches
            )
            self.assertEqual(appearances, 18)

    def test_overs_and_bowled_out_nrr(self) -> None:
        self.assertEqual(overs_to_balls("14.3"), 87)
        self.assertEqual(overs_to_balls("12.4"), 76)
        # A side bowled out for 120 in 14.3 is treated as facing 20 overs.
        self.assertEqual(net_run_rate(180, 120, 120, 120), 3.0)

    def test_exact_1500_km_uses_two_clear_days(self) -> None:
        season = Season(date(2026, 1, 1))
        self.assertEqual(
            _required_clear_days(
                season,
                {("Delhi", "Mumbai"): 1500, ("Delhi", "Kolkata"): 1530},
                "Delhi",
                "Mumbai",
            ),
            2,
        )
        self.assertEqual(
            _required_clear_days(
                season,
                {("Delhi", "Kolkata"): 1530},
                "Delhi",
                "Kolkata",
            ),
            3,
        )

    def test_blackouts_on_both_weekend_days_are_reported(self) -> None:
        teams = {
            "A": Team("A", "Alpha", "V1", "One"),
            "B": Team("B", "Beta", "V2", "Two"),
        }
        venues = {
            "V1": Venue("V1", "One ground", "One", 10000),
            "V2": Venue("V2", "Two ground", "Two", 10000),
        }
        season = Season(date(2026, 9, 4))
        fixtures = [
            Fixture("FX-001", 1, date(2026, 9, 4), "19:30", "A", "B", "V1"),
            Fixture("FX-002", 1, date(2026, 9, 7), "19:30", "B", "A", "V2"),
        ]
        issues = audit_fixtures(
            fixtures,
            teams,
            venues,
            {date(2026, 9, 5), date(2026, 9, 6)},
            season,
            {("One", "Two"): 10, ("Two", "One"): 10},
        )
        self.assertTrue(any("2026-09-05" in issue for issue in issues))
        self.assertTrue(any("2026-09-06" in issue for issue in issues))

    def test_forfeit_is_not_given_nrr(self) -> None:
        fixture = Fixture(
            "FX-001",
            1,
            date(2026, 1, 1),
            "19:30",
            "A",
            "B",
            "V1",
            status=MatchStatus.FORFEIT,
            result=MatchResult(MatchStatus.FORFEIT, winner_id="A", forfeited_by="B"),
        )
        from standings import nrr_contribution

        self.assertIsNone(nrr_contribution(fixture))

    def test_no_result_and_penalties_can_produce_correct_negative_total(self) -> None:
        teams = {
            "A": Team("A", "Alpha", "V1", "One"),
            "B": Team("B", "Beta", "V2", "Two"),
        }
        fixtures = [
            Fixture(
                "FX-001",
                1,
                date(2026, 1, 1),
                "19:30",
                "A",
                "B",
                "V1",
                status=MatchStatus.ABANDONED,
                result=MatchResult(MatchStatus.ABANDONED, is_no_result=True),
            )
        ]
        penalties = [
            Penalty("OR-1", "A", 1, date(2026, 1, 1), 0),
            Penalty("OR-2", "A", 1, date(2026, 1, 1), 1),
            Penalty("OR-3", "A", 1, date(2026, 1, 1), 2),
        ]
        table = compute_standings(teams, fixtures, penalties)
        row_a = next(row for row in table if row.team_id == "A")
        self.assertEqual((row_a.points_before_penalty, row_a.penalty, row_a.points), (1, 3, -2))


if __name__ == "__main__":
    unittest.main()


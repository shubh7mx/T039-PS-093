from __future__ import annotations

import csv
import tempfile
import unittest
from datetime import date
from pathlib import Path

from commands import LeagueEngine
from console import render_report
from loaders import load_data
from models import MatchResult, MatchStatus
from playoffs import build_bracket, record_playoff_result


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "T039-PS-093-sample-data"


class SampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.engine = LeagueEngine(SAMPLE, cls.temp_dir.name)
        cls.outputs = cls.engine.run_file(SAMPLE / "commands.txt")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_dir.cleanup()

    def test_sample_inputs_load(self) -> None:
        data = load_data(SAMPLE)
        self.assertEqual(len(data.teams), 10)
        self.assertEqual(len(data.venues), 9)
        self.assertEqual(len(data.fixtures), 90)
        self.assertEqual(len(data.results), 87)
        self.assertEqual(len(data.offences), 3)

    def test_command_run_finishes_and_reports_impossible_weekend(self) -> None:
        self.assertIn("Generated 90 fixtures across 18 rounds", self.outputs)
        self.assertTrue(
            any("weekend 2026-09-19 (league blackout)" in line for line in self.outputs)
        )
        self.assertEqual(len(self.engine.result_log), 87)

    def test_postponements_use_expected_reserve_day_slots(self) -> None:
        dates = {
            fixture.fixture_id: fixture.match_date.isoformat()
            for fixture in self.engine.fixtures
        }
        self.assertEqual(dates["FX-011"], "2026-11-21")
        self.assertEqual(dates["FX-018"], "2026-11-21")
        self.assertEqual(dates["FX-028"], "2026-11-22")
        self.assertEqual(dates["FX-063"], "2026-11-22")

    def test_invalid_results_are_rejected(self) -> None:
        rejected = {
            row.result_id: row.reason
            for row in self.engine.result_log
            if row.action == "REJECTED"
        }
        self.assertIn("RS-027", rejected)
        self.assertIn("RS-051", rejected)
        self.assertNotIn("RS-084", rejected)
        self.assertNotIn("RS-086", rejected)

    def test_wrong_date_rejection_does_not_change_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as output_dir:
            engine = LeagueEngine(SAMPLE, output_dir)
            engine._load_fixtures("reference_fixtures.csv")
            engine._record_result("RS-051")
            fixture = engine.fixtures_by_id["FX-052"]
            self.assertIsNone(fixture.result)
            self.assertEqual(fixture.status, MatchStatus.SCHEDULED)

    def test_exactly_half_withdrawal_keeps_results_and_awards_walkovers(self) -> None:
        withdrawal = self.engine.withdrawals[0]
        self.assertEqual((withdrawal.played, withdrawal.total), (9, 18))
        self.assertFalse(withdrawal.expunged)
        t10_matches = [
            fixture
            for fixture in self.engine.fixtures
            if "T10-AHM" in (fixture.home_team_id, fixture.away_team_id)
        ]
        self.assertEqual(sum(fixture.status.value == "WALKOVER" for fixture in t10_matches), 9)

    def test_final_penalty_and_late_results_change_qualification(self) -> None:
        qualifiers = [row.team_id for row in self.engine.final_table[:4]]
        self.assertEqual(qualifiers, ["T05-DEL", "T07-HYD", "T08-DDY", "T09-JAI"])
        t02 = next(row for row in self.engine.final_table if row.team_id == "T02-MSW")
        self.assertEqual((t02.points, t02.penalty), (21, 1))

    def test_three_way_tie_restarts_remaining_group(self) -> None:
        rows = {row.team_id: row for row in self.engine.final_table}
        self.assertEqual(rows["T05-DEL"].decided_by_step, "2")
        self.assertEqual(rows["T07-HYD"].decided_by_step, "3")
        self.assertEqual(rows["T08-DDY"].decided_by_step, "3")

    def test_forfeit_changes_head_to_head_but_not_nrr_total(self) -> None:
        t08 = next(row for row in self.engine.final_table if row.team_id == "T08-DDY")
        self.assertEqual(t08.forfeits, 1)
        forfeit = next(
            fixture
            for fixture in self.engine.fixtures
            if fixture.fixture_id == "FX-085"
        )
        self.assertEqual(forfeit.status, MatchStatus.FORFEIT)

    def test_withdrawal_below_half_expunges_all_fixtures(self) -> None:
        with tempfile.TemporaryDirectory() as output_dir:
            engine = LeagueEngine(SAMPLE, output_dir)
            engine._load_fixtures("reference_fixtures.csv")
            t10_fixtures = [
                fixture
                for fixture in engine.fixtures
                if "T10-AHM" in (fixture.home_team_id, fixture.away_team_id)
            ]
            for fixture in t10_fixtures[:8]:
                fixture.status = MatchStatus.PLAYED
                fixture.result = MatchResult(
                    MatchStatus.PLAYED,
                    winner_id=fixture.home_team_id,
                    home_runs=160,
                    home_overs="20.0",
                    away_runs=150,
                    away_overs="20.0",
                )
                fixture.event_date = date(2026, 9, 30)
            engine._withdraw("T10-AHM", date(2026, 10, 13))
            self.assertTrue(engine.withdrawals[-1].expunged)
            self.assertTrue(all(fixture.expunged for fixture in t10_fixtures))

    def test_playoff_bracket_progresses_to_final(self) -> None:
        bracket = build_bracket(self.engine.final_table, {"T10-AHM"})
        record_playoff_result(bracket, "Q1", "T05-DEL", False)
        record_playoff_result(bracket, "ELIM", "T09-JAI", False)
        record_playoff_result(bracket, "Q2", "T07-HYD", False)
        record_playoff_result(bracket, "FINAL", "T05-DEL", False)
        self.assertEqual(bracket["FINAL"].winner_id, "T05-DEL")

    def test_playoff_tie_goes_to_higher_seed(self) -> None:
        bracket = build_bracket(self.engine.final_table, {"T10-AHM"})
        match = record_playoff_result(bracket, "Q1", None, True)
        self.assertEqual(match.winner_id, "T05-DEL")

    def test_output_headers_and_row_counts(self) -> None:
        expected_tables = {
            "points_table_r06.csv": 10,
            "points_table_r12.csv": 10,
            "points_table_r18.csv": 10,
            "qualification.csv": 4,
            "result_log.csv": 87,
        }
        for filename, count in expected_tables.items():
            with (Path(self.temp_dir.name) / filename).open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), count, filename)

    def test_console_report_is_complete_and_readable(self) -> None:
        report = render_report(self.engine, colour_enabled=False)
        self.assertIn("PS-093  LEAGUE COMPETITION ENGINE", report)
        self.assertIn("Team T039  |  Section CSDS B", report)
        self.assertIn("1. RUN OVERVIEW", report)
        self.assertIn("2. REQUESTED POINT TABLES", report)
        self.assertIn("After round 6", report)
        self.assertIn("After round 12", report)
        self.assertIn("Final table", report)
        self.assertIn("3. QUALIFICATION AND PLAYOFFS", report)
        self.assertIn("4. COMPLETE FIXTURE LIST", report)
        self.assertIn("OUTPUT FILES", report)
        self.assertIn("T05-DEL", report)
        self.assertEqual(
            sum(line.startswith("  FX-") for line in report.splitlines()), 90
        )
        self.assertNotIn("\033[", report)


if __name__ == "__main__":
    unittest.main()


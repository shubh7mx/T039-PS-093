"""CSV input and output helpers for the sample league format."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from models import (
    Fixture,
    OffenceRow,
    ResultLogRow,
    ResultRow,
    Season,
    Standing,
    Team,
    Venue,
)


@dataclass
class LeagueData:
    teams: dict[str, Team]
    venues: dict[str, Venue]
    distances: dict[tuple[str, str], int]
    season: Season
    league_blackouts: set[date]
    fixtures: dict[str, Fixture]
    results: dict[str, ResultRow]
    offences: dict[str, OffenceRow]


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _make_fixture(row: dict[str, str]) -> Fixture:
    return Fixture(
        fixture_id=row["fixture_id"],
        round_no=int(row["round"]),
        match_date=date.fromisoformat(row["match_date"]),
        start_time=row["start_time"],
        home_team_id=row["home_team_id"],
        away_team_id=row["away_team_id"],
        venue_id=row["venue_id"],
    )


def load_data(directory: str | Path) -> LeagueData:
    """Load one complete sample directory into memory."""
    root = Path(directory)

    season_values = {row["parameter"]: row["value"] for row in _rows(root / "season.csv")}
    slots = season_values["slots_double"].split(";")
    season = Season(
        start_date=date.fromisoformat(season_values["season_start"]),
        overs_per_innings=int(season_values["overs_per_innings"]),
        max_matches_per_day=int(season_values["max_matches_per_day"]),
        single_time=season_values["slot_single"],
        double_times=(slots[0], slots[1]),
        min_clear_days=int(season_values["min_clear_days"]),
        long_travel_clear_days=int(season_values["min_clear_days_long_travel"]),
        long_travel_km=int(season_values["long_travel_km_above"]),
        reserve_days=int(season_values["reserve_days_after_last_round"]),
        qualifiers=int(season_values["qualifiers"]),
    )

    teams = {
        row["team_id"]: Team(
            team_id=row["team_id"],
            name=row["team_name"],
            home_venue_id=row["home_venue_id"],
            city=row["city"],
        )
        for row in _rows(root / "teams.csv")
    }
    venues = {
        row["venue_id"]: Venue(
            venue_id=row["venue_id"],
            name=row["venue_name"],
            city=row["city"],
            capacity=int(row["capacity"]),
        )
        for row in _rows(root / "venues.csv")
    }

    distances: dict[tuple[str, str], int] = {}
    for row in _rows(root / "distances.csv"):
        distance = int(row["km"])
        distances[(row["city_a"], row["city_b"])] = distance
        distances[(row["city_b"], row["city_a"])] = distance

    league_blackouts: set[date] = set()
    for row in _rows(root / "blackouts.csv"):
        day = date.fromisoformat(row["date"])
        if row["scope"] == "LEAGUE":
            league_blackouts.add(day)
        else:
            venues[row["venue_id"]].blackout_dates.add(day)

    fixtures = {
        row["fixture_id"]: _make_fixture(row)
        for row in _rows(root / "reference_fixtures.csv")
    }

    results: dict[str, ResultRow] = {}
    for row in _rows(root / "results.csv"):
        results[row["result_id"]] = ResultRow(
            result_id=row["result_id"],
            fixture_id=row["fixture_id"],
            match_date=date.fromisoformat(row["match_date"]),
            status=row["status"],
            batting_first=row["batting_first"],
            home_runs=int(row["home_runs"] or 0),
            home_wickets=int(row["home_wickets"] or 0),
            home_overs=row["home_overs"] or "0.0",
            away_runs=int(row["away_runs"] or 0),
            away_wickets=int(row["away_wickets"] or 0),
            away_overs=row["away_overs"] or "0.0",
            play_completed_pct=float(row["play_completed_pct"] or 0),
            forfeiting_team_id=row["forfeiting_team_id"],
        )

    offences = {
        row["offence_id"]: OffenceRow(
            offence_id=row["offence_id"],
            fixture_id=row["fixture_id"],
            team_id=row["team_id"],
            match_date=date.fromisoformat(row["match_date"]),
        )
        for row in _rows(root / "over_rate_offences.csv")
    }
    return LeagueData(
        teams=teams,
        venues=venues,
        distances=distances,
        season=season,
        league_blackouts=league_blackouts,
        fixtures=fixtures,
        results=results,
        offences=offences,
    )


WRITE_HEADERS = {
    "result_log": ["result_id", "fixture_id", "action", "reason", "new_match_date"],
    "points_table": [
        "position",
        "team_id",
        "played",
        "won",
        "lost",
        "no_result",
        "forfeits",
        "points_before_penalty",
        "penalty",
        "points",
        "nrr",
        "decided_by_step",
    ],
    "qualification": ["position", "team_id", "points", "nrr", "playoff_match", "opponent"],
    "fixtures": [
        "fixture_id",
        "round",
        "match_date",
        "start_time",
        "home_team_id",
        "away_team_id",
        "venue_id",
    ],
}


def write_result_log(path: Path, rows: list[ResultLogRow]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=WRITE_HEADERS["result_log"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)


def write_points_table(path: Path, rows: list[Standing]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=WRITE_HEADERS["points_table"])
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "position": row.position,
                    "team_id": row.team_id,
                    "played": row.played,
                    "won": row.won,
                    "lost": row.lost,
                    "no_result": row.no_result,
                    "forfeits": row.forfeits,
                    "points_before_penalty": row.points_before_penalty,
                    "penalty": row.penalty,
                    "points": row.points,
                    "nrr": f"{row.nrr:.4f}",
                    "decided_by_step": row.decided_by_step,
                }
            )


def write_fixtures(path: Path, fixtures: list[Fixture]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=WRITE_HEADERS["fixtures"])
        writer.writeheader()
        for fixture in fixtures:
            writer.writerow(
                {
                    "fixture_id": fixture.fixture_id,
                    "round": fixture.round_no,
                    "match_date": fixture.match_date.isoformat(),
                    "start_time": fixture.start_time,
                    "home_team_id": fixture.home_team_id,
                    "away_team_id": fixture.away_team_id,
                    "venue_id": fixture.venue_id,
                }
            )


def write_qualification(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=WRITE_HEADERS["qualification"])
        writer.writeheader()
        writer.writerows(rows)


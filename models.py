"""Small data objects shared by the league engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class MatchStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    PLAYED = "PLAYED"
    ABANDONED = "ABANDONED"
    FORFEIT = "FORFEIT"
    POSTPONED = "POSTPONED"
    CANCELLED = "CANCELLED"
    WALKOVER = "WALKOVER"


@dataclass
class Venue:
    venue_id: str
    name: str
    city: str
    capacity: int
    available_dates: set[date] | None = None
    blackout_dates: set[date] = field(default_factory=set)

    def is_available(self, day: date, league_blackouts: set[date]) -> bool:
        if day in league_blackouts or day in self.blackout_dates:
            return False
        return self.available_dates is None or day in self.available_dates


@dataclass
class Team:
    team_id: str
    name: str
    home_venue_id: str
    city: str
    withdrawn_on: date | None = None
    expunged: bool = False


@dataclass
class Season:
    start_date: date
    overs_per_innings: int = 20
    max_matches_per_day: int = 2
    single_time: str = "19:30"
    double_times: tuple[str, str] = ("15:30", "19:30")
    min_clear_days: int = 2
    long_travel_clear_days: int = 3
    long_travel_km: int = 1500
    reserve_days: int = 3
    qualifiers: int = 4


@dataclass
class MatchResult:
    status: MatchStatus
    winner_id: str | None = None
    forfeited_by: str | None = None
    is_tie: bool = False
    is_no_result: bool = False
    batting_first: str | None = None
    home_runs: int = 0
    home_wickets: int = 0
    home_overs: str = "0.0"
    away_runs: int = 0
    away_wickets: int = 0
    away_overs: str = "0.0"
    play_completed_pct: float = 0.0
    allotted_overs: int = 20


@dataclass
class Fixture:
    fixture_id: str
    round_no: int
    match_date: date
    start_time: str
    home_team_id: str
    away_team_id: str
    venue_id: str
    status: MatchStatus = MatchStatus.SCHEDULED
    result: MatchResult | None = None
    original_date: date | None = None
    swapped_for_blackout: bool = False
    rescheduled: bool = False
    expunged: bool = False
    event_date: date | None = None

    def __post_init__(self) -> None:
        if self.original_date is None:
            self.original_date = self.match_date


@dataclass
class ResultRow:
    result_id: str
    fixture_id: str
    match_date: date
    status: str
    batting_first: str = ""
    home_runs: int = 0
    home_wickets: int = 0
    home_overs: str = "0.0"
    away_runs: int = 0
    away_wickets: int = 0
    away_overs: str = "0.0"
    play_completed_pct: float = 0.0
    forfeiting_team_id: str = ""


@dataclass
class OffenceRow:
    offence_id: str
    fixture_id: str
    team_id: str
    match_date: date


@dataclass
class Penalty:
    offence_id: str
    team_id: str
    round_no: int
    match_date: date
    deduction: int


@dataclass
class Withdrawal:
    team_id: str
    on_date: date
    played: int
    total: int
    expunged: bool


@dataclass
class ResultLogRow:
    result_id: str
    fixture_id: str
    action: str
    reason: str
    new_match_date: str = ""


@dataclass
class Standing:
    position: int
    team_id: str
    played: int = 0
    won: int = 0
    lost: int = 0
    no_result: int = 0
    forfeits: int = 0
    points_before_penalty: int = 0
    penalty: int = 0
    points: int = 0
    nrr: float = 0.0
    decided_by_step: str = ""
    runs_scored: int = 0
    balls_faced: int = 0
    runs_conceded: int = 0
    balls_bowled: int = 0


@dataclass
class PlayoffMatch:
    code: str
    label: str
    seed1: int | None = None
    team1_id: str | None = None
    seed2: int | None = None
    team2_id: str | None = None
    winner_id: str | None = None
    loser_id: str | None = None
    note: str = ""


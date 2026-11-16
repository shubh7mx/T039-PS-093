from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


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
    city: str
    capacity: int
    available_dates: Optional[set[date]] = None
    blackout_dates: set[date] = field(default_factory=set)

    # check date
    def is_available(self, d: date) -> bool:
        if d in self.blackout_dates:
            return False
        if self.available_dates is not None and d not in self.available_dates:
            return False
        return True


@dataclass
class Team:
    team_id: str
    name: str
    home_venue_id: str
    city: str
    withdrawn: bool = False
    expunged: bool = False
    withdrawn_round: Optional[int] = None


@dataclass
class SeasonConfig:
    start_date: Optional[date] = None
    blackout_dates: set[date] = field(default_factory=set)
    broadcast_windows: list[str] = field(default_factory=lambda: ["15:30", "19:30"])
    overs_per_innings: int = 20
    reserve_days: int = 3


@dataclass
class MatchResult:
    status: MatchStatus
    winner_id: Optional[str] = None
    forfeited_by: Optional[str] = None
    is_tie: bool = False
    is_no_result: bool = False
    home_runs: int = 0
    home_overs: str = "0.0"
    home_all_out: bool = False
    away_runs: int = 0
    away_overs: str = "0.0"
    away_all_out: bool = False
    allotted_overs: int = 20
    play_pct: Optional[float] = None


@dataclass
class Fixture:
    fixture_id: str
    round_no: int
    home_team_id: str
    away_team_id: str
    venue_id: str
    city: str
    match_date: date
    start_time: str = "19:30"
    status: MatchStatus = MatchStatus.SCHEDULED
    result: Optional[MatchResult] = None
    swapped_from_blackout: bool = False
    rescheduled_from: Optional[date] = None
    expunged: bool = False


@dataclass
class PenaltyOffence:
    team_id: str
    round_no: int
    offence_num: int
    deduction: int


@dataclass
class StandingsRow:
    rank: int
    team_id: str
    team_name: str
    played: int
    won: int
    lost: int
    tied: int
    no_result: int
    forfeits: int
    points: int
    penalty_points: int
    nrr: float
    runs_scored: int
    balls_faced: int
    runs_conceded: int
    balls_bowled: int
    withdrawn: bool = False
    tie_break_note: str = ""


@dataclass
class PlayoffMatch:
    code: str
    label: str
    team1_id: Optional[str] = None
    team1_seed: Optional[int] = None
    team2_id: Optional[str] = None
    team2_seed: Optional[int] = None
    winner_id: Optional[str] = None
    loser_id: Optional[str] = None
    status: MatchStatus = MatchStatus.SCHEDULED
    note: str = ""

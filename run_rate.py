from typing import Optional
from data_types import Fixture, MatchStatus


# convert overs
def overs_to_balls(overs_val: object) -> int:
    text = str(overs_val).strip()
    if not text:
        raise ValueError("Empty overs")
    if "." in text:
        parts = text.split(".")
        if len(parts) != 2:
            raise ValueError(f"Invalid overs: {text}")
        whole = int(parts[0])
        frac_str = parts[1]
        if len(frac_str) > 1 and frac_str.endswith("0"):
            frac_str = frac_str.rstrip("0") or "0"
        balls = int(frac_str) if frac_str else 0
    else:
        whole = int(text)
        balls = 0
    if whole < 0 or balls < 0 or balls >= 6:
        raise ValueError(f"Invalid overs: {text}")
    return whole * 6 + balls


# get match nrr
def extract_match_nrr(fixture: Fixture) -> Optional[tuple[int, int, int, int]]:
    if fixture.expunged or fixture.result is None:
        return None
    if fixture.status in (
        MatchStatus.FORFEIT,
        MatchStatus.WALKOVER,
        MatchStatus.CANCELLED,
        MatchStatus.POSTPONED,
        MatchStatus.SCHEDULED,
    ):
        return None
    res = fixture.result
    if res.is_no_result:
        return None
    max_balls = res.allotted_overs * 6
    # bowled out
    h_balls = max_balls if res.home_all_out else overs_to_balls(res.home_overs)
    a_balls = max_balls if res.away_all_out else overs_to_balls(res.away_overs)
    if h_balls == 0 and a_balls == 0:
        return None
    return (res.home_runs, h_balls, res.away_runs, a_balls)


# calculate nrr
def compute_nrr(runs_scored: int, balls_faced: int, runs_conceded: int, balls_bowled: int) -> float:
    scored_rate = (runs_scored / (balls_faced / 6.0)) if balls_faced > 0 else 0.0
    conceded_rate = (runs_conceded / (balls_bowled / 6.0)) if balls_bowled > 0 else 0.0
    return round(scored_rate - conceded_rate, 4)

"""Points table, six-level tie-breakers, and net run rate."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from models import Fixture, MatchStatus, Penalty, Standing, Team


def overs_to_balls(value: str) -> int:
    """Convert cricket overs notation to legal-ball count."""
    text = value.strip()
    if not text:
        return 0
    if "." in text:
        overs_text, balls_text = text.split(".", 1)
        if not overs_text or not balls_text:
            raise ValueError(f"Invalid overs value: {value}")
        overs = int(overs_text)
        balls = int(balls_text)
    else:
        overs = int(text)
        balls = 0
    if overs < 0 or balls < 0 or balls > 5:
        raise ValueError(f"Invalid overs value: {value}")
    return overs * 6 + balls


def _four_places(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def net_run_rate(
    runs_scored: int,
    balls_faced: int,
    runs_conceded: int,
    balls_bowled: int,
) -> float:
    if balls_faced <= 0 or balls_bowled <= 0:
        return 0.0
    scored = Decimal(runs_scored * 6) / Decimal(balls_faced)
    conceded = Decimal(runs_conceded * 6) / Decimal(balls_bowled)
    return _four_places(scored - conceded)


def _innings_balls(overs: str, wickets: int, allotted_overs: int) -> int:
    if wickets >= 10:
        return allotted_overs * 6
    return overs_to_balls(overs)


def nrr_contribution(fixture: Fixture) -> tuple[int, int, int, int] | None:
    """Return home runs/balls and away runs/balls for eligible NRR matches."""
    result = fixture.result
    if result is None or fixture.expunged:
        return None
    if fixture.status not in (MatchStatus.PLAYED, MatchStatus.ABANDONED):
        return None
    if result.is_no_result:
        return None

    home_balls = _innings_balls(
        result.home_overs, result.home_wickets, result.allotted_overs
    )
    away_balls = _innings_balls(
        result.away_overs, result.away_wickets, result.allotted_overs
    )
    if home_balls == 0 or away_balls == 0:
        return None
    return result.home_runs, home_balls, result.away_runs, away_balls


def _result_points(fixture: Fixture) -> tuple[int, int] | None:
    result = fixture.result
    if result is None or fixture.expunged:
        return None
    if fixture.status in (MatchStatus.PLAYED, MatchStatus.ABANDONED):
        if result.is_no_result or result.is_tie:
            return 1, 1
        if result.winner_id == fixture.home_team_id:
            return 2, 0
        if result.winner_id == fixture.away_team_id:
            return 0, 2
    if fixture.status in (MatchStatus.FORFEIT, MatchStatus.WALKOVER):
        if result.winner_id == fixture.home_team_id:
            return 2, 0
        if result.winner_id == fixture.away_team_id:
            return 0, 2
    if fixture.status == MatchStatus.CANCELLED and result.is_no_result:
        return 1, 1
    return None


def _fixture_is_in_snapshot(
    fixture: Fixture,
    cutoff: date | None,
) -> bool:
    if fixture.result is None or fixture.expunged:
        return False
    if cutoff is None:
        return True
    event_day = fixture.event_date or fixture.match_date
    return event_day <= cutoff


def _empty_stats(teams: dict[str, Team]) -> dict[str, dict[str, object]]:
    return {
        team_id: {
            "played": 0,
            "won": 0,
            "lost": 0,
            "no_result": 0,
            "forfeits": 0,
            "points": 0,
            "penalty": 0,
            "runs_scored": 0,
            "balls_faced": 0,
            "runs_conceded": 0,
            "balls_bowled": 0,
            "nrr": 0.0,
        }
        for team_id in teams
    }


def _apply_fixture(stats: dict[str, dict[str, object]], fixture: Fixture) -> None:
    if fixture.home_team_id not in stats or fixture.away_team_id not in stats:
        return
    points = _result_points(fixture)
    if points is None:
        return
    home_id = fixture.home_team_id
    away_id = fixture.away_team_id
    home = stats[home_id]
    away = stats[away_id]
    home_points, away_points = points
    home["played"] = int(home["played"]) + 1
    away["played"] = int(away["played"]) + 1
    home["points"] = int(home["points"]) + home_points
    away["points"] = int(away["points"]) + away_points

    if fixture.status == MatchStatus.CANCELLED or (
        fixture.result and fixture.result.is_no_result
    ):
        home["no_result"] = int(home["no_result"]) + 1
        away["no_result"] = int(away["no_result"]) + 1
    elif fixture.result and fixture.result.is_tie:
        home["no_result"] = int(home["no_result"]) + 1
        away["no_result"] = int(away["no_result"]) + 1
    elif home_points == 2:
        home["won"] = int(home["won"]) + 1
        away["lost"] = int(away["lost"]) + 1
    elif away_points == 2:
        away["won"] = int(away["won"]) + 1
        home["lost"] = int(home["lost"]) + 1

    if fixture.status == MatchStatus.FORFEIT and fixture.result:
        losing_id = (
            away_id if fixture.result.winner_id == home_id else home_id
        )
        stats[losing_id]["forfeits"] = int(stats[losing_id]["forfeits"]) + 1

    nrr = nrr_contribution(fixture)
    if nrr is None:
        return
    home_runs, home_balls, away_runs, away_balls = nrr
    home["runs_scored"] = int(home["runs_scored"]) + home_runs
    home["balls_faced"] = int(home["balls_faced"]) + home_balls
    home["runs_conceded"] = int(home["runs_conceded"]) + away_runs
    home["balls_bowled"] = int(home["balls_bowled"]) + away_balls
    away["runs_scored"] = int(away["runs_scored"]) + away_runs
    away["balls_faced"] = int(away["balls_faced"]) + away_balls
    away["runs_conceded"] = int(away["runs_conceded"]) + home_runs
    away["balls_bowled"] = int(away["balls_bowled"]) + home_balls


def _head_to_head_metrics(
    group_ids: list[str],
    fixtures: list[Fixture],
) -> tuple[dict[str, int], dict[str, float]]:
    group = set(group_ids)
    points = {team_id: 0 for team_id in group_ids}
    nrr_totals = {
        team_id: [0, 0, 0, 0] for team_id in group_ids
    }  # scored, faced, conceded, bowled
    for fixture in fixtures:
        if fixture.home_team_id not in group or fixture.away_team_id not in group:
            continue
        result_points = _result_points(fixture)
        if result_points is not None:
            points[fixture.home_team_id] += result_points[0]
            points[fixture.away_team_id] += result_points[1]
        contribution = nrr_contribution(fixture)
        if contribution is None:
            continue
        home_runs, home_balls, away_runs, away_balls = contribution
        home_total = nrr_totals[fixture.home_team_id]
        home_total[0] += home_runs
        home_total[1] += home_balls
        home_total[2] += away_runs
        home_total[3] += away_balls
        away_total = nrr_totals[fixture.away_team_id]
        away_total[0] += away_runs
        away_total[1] += away_balls
        away_total[2] += home_runs
        away_total[3] += home_balls
    nrr = {
        team_id: net_run_rate(*values) for team_id, values in nrr_totals.items()
    }
    return points, nrr


def _rank_group(
    group_ids: list[str],
    fixtures: list[Fixture],
    stats: dict[str, dict[str, object]],
    decided: dict[str, str],
    step: int = 1,
) -> list[str]:
    if len(group_ids) <= 1:
        return group_ids
    if step > 6:
        return sorted(group_ids)

    h2h_points: dict[str, int] = {}
    h2h_nrr: dict[str, float] = {}
    if step in (2, 4):
        h2h_points, h2h_nrr = _head_to_head_metrics(group_ids, fixtures)

    buckets: dict[object, list[str]] = {}
    for team_id in group_ids:
        if step == 1:
            key = int(stats[team_id]["won"])
        elif step == 2:
            key = h2h_points[team_id]
        elif step == 3:
            key = float(stats[team_id]["nrr"])
        elif step == 4:
            key = h2h_nrr[team_id]
        elif step == 5:
            key = -int(stats[team_id]["forfeits"])
        else:
            key = team_id
        buckets.setdefault(key, []).append(team_id)

    reverse = step != 6
    if len(buckets) == 1:
        return _rank_group(group_ids, fixtures, stats, decided, step + 1)

    ordered_keys = sorted(buckets, reverse=reverse)
    ranked: list[str] = []
    for key in ordered_keys:
        bucket = buckets[key]
        if len(bucket) == 1:
            decided[bucket[0]] = str(step)
            ranked.extend(bucket)
        else:
            ranked.extend(_rank_group(bucket, fixtures, stats, decided, 1))
    return ranked


def compute_standings(
    teams: dict[str, Team],
    fixtures: list[Fixture],
    penalties: list[Penalty],
    up_to_round: int | None = None,
    round_end: date | None = None,
) -> list[Standing]:
    cutoff = round_end if up_to_round is not None else None
    eligible = [
        fixture for fixture in fixtures if _fixture_is_in_snapshot(fixture, cutoff)
    ]
    stats = _empty_stats(teams)
    for fixture in eligible:
        _apply_fixture(stats, fixture)

    for penalty in penalties:
        if up_to_round is not None and penalty.round_no > up_to_round:
            continue
        if penalty.team_id not in stats:
            continue
        stats[penalty.team_id]["points"] = (
            int(stats[penalty.team_id]["points"]) - penalty.deduction
        )
        stats[penalty.team_id]["penalty"] = (
            int(stats[penalty.team_id]["penalty"]) + penalty.deduction
        )

    for team_id, values in stats.items():
        values["nrr"] = net_run_rate(
            int(values["runs_scored"]),
            int(values["balls_faced"]),
            int(values["runs_conceded"]),
            int(values["balls_bowled"]),
        )

    by_points: dict[int, list[str]] = {}
    for team_id, values in stats.items():
        by_points.setdefault(int(values["points"]), []).append(team_id)

    ordered: list[str] = []
    decided: dict[str, str] = {team_id: "" for team_id in teams}
    for points in sorted(by_points, reverse=True):
        group = by_points[points]
        ordered.extend(_rank_group(group, eligible, stats, decided, 1))

    table: list[Standing] = []
    for position, team_id in enumerate(ordered, start=1):
        values = stats[team_id]
        points_before = int(values["points"]) + int(values["penalty"])
        table.append(
            Standing(
                position=position,
                team_id=team_id,
                played=int(values["played"]),
                won=int(values["won"]),
                lost=int(values["lost"]),
                no_result=int(values["no_result"]),
                forfeits=int(values["forfeits"]),
                points_before_penalty=points_before,
                penalty=int(values["penalty"]),
                points=int(values["points"]),
                nrr=float(values["nrr"]),
                decided_by_step=decided[team_id],
                runs_scored=int(values["runs_scored"]),
                balls_faced=int(values["balls_faced"]),
                runs_conceded=int(values["runs_conceded"]),
                balls_bowled=int(values["balls_bowled"]),
            )
        )
    return table


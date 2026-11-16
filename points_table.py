from datetime import date
from typing import Optional
from data_types import Fixture, MatchStatus, PenaltyOffence, StandingsRow, Team
from run_rate import compute_nrr, extract_match_nrr


# team key
def _team_id_key(team_id: str) -> tuple[int, object]:
    if team_id.isdigit():
        return (0, int(team_id))
    return (1, team_id)


# head to head
def _compute_h2h_metrics(
    group_ids: list[str],
    fixtures: list[Fixture],
) -> tuple[dict[str, int], dict[str, float]]:
    group_set = set(group_ids)
    h2h_pts: dict[str, int] = {tid: 0 for tid in group_ids}
    runs_for: dict[str, int] = {tid: 0 for tid in group_ids}
    balls_for: dict[str, int] = {tid: 0 for tid in group_ids}
    runs_ag: dict[str, int] = {tid: 0 for tid in group_ids}
    balls_ag: dict[str, int] = {tid: 0 for tid in group_ids}

    for f in fixtures:
        if f.expunged or f.result is None:
            continue
        if f.home_team_id not in group_set or f.away_team_id not in group_set:
            continue
        h = f.home_team_id
        a = f.away_team_id
        res = f.result
        if f.status in (MatchStatus.PLAYED, MatchStatus.ABANDONED):
            if res.is_no_result or res.is_tie:
                h2h_pts[h] += 1
                h2h_pts[a] += 1
            elif res.winner_id == h:
                h2h_pts[h] += 2
            elif res.winner_id == a:
                h2h_pts[a] += 2
        elif f.status in (MatchStatus.FORFEIT, MatchStatus.WALKOVER):
            if res.winner_id == h:
                h2h_pts[h] += 2
            elif res.winner_id == a:
                h2h_pts[a] += 2
        elif f.status == MatchStatus.CANCELLED:
            h2h_pts[h] += 1
            h2h_pts[a] += 1

        nrr_data = extract_match_nrr(f)
        if nrr_data is not None:
            hr, hb, ar, ab = nrr_data
            runs_for[h] += hr
            balls_for[h] += hb
            runs_ag[h] += ar
            balls_ag[h] += ab
            runs_for[a] += ar
            balls_for[a] += ab
            runs_ag[a] += hr
            balls_ag[a] += hb

    h2h_nrr: dict[str, float] = {}
    for tid in group_ids:
        h2h_nrr[tid] = compute_nrr(runs_for[tid], balls_for[tid], runs_ag[tid], balls_ag[tid])
    return h2h_pts, h2h_nrr


# break ties
def _resolve_tie_group(
    group_ids: list[str],
    fixtures: list[Fixture],
    stats: dict[str, dict[str, object]],
    notes: dict[str, str],
    step: int = 1,
) -> list[str]:
    if len(group_ids) <= 1:
        return list(group_ids)
    if step > 6:
        return sorted(group_ids, key=_team_id_key)

    h2h_pts, h2h_nrr = ({}, {})
    if step in (2, 4):
        h2h_pts, h2h_nrr = _compute_h2h_metrics(group_ids, fixtures)

    step_names = {
        1: "wins",
        2: "H2H pts",
        3: "NRR",
        4: "H2H NRR",
        5: "forfeits",
        6: "team-id",
    }

    if step == 1:
        key_fn = lambda tid: (stats[tid]["won"],)
        reverse = True
    elif step == 2:
        key_fn = lambda tid: (h2h_pts[tid],)
        reverse = True
    elif step == 3:
        key_fn = lambda tid: (stats[tid]["nrr"],)
        reverse = True
    elif step == 4:
        key_fn = lambda tid: (h2h_nrr[tid],)
        reverse = True
    elif step == 5:
        key_fn = lambda tid: (-int(stats[tid]["forfeits"]),)
        reverse = True
    else:
        key_fn = lambda tid: _team_id_key(tid)
        reverse = False

    buckets: dict[object, list[str]] = {}
    for tid in group_ids:
        k = key_fn(tid)
        buckets.setdefault(k, []).append(tid)

    if len(buckets) == 1:
        return _resolve_tie_group(group_ids, fixtures, stats, notes, step + 1)

    sorted_keys = sorted(buckets.keys(), reverse=reverse)
    result: list[str] = []
    for k in sorted_keys:
        sub = buckets[k]
        for tid in sub:
            if not notes[tid]:
                notes[tid] = f"step {step} ({step_names[step]})"
        if len(sub) > 1:
            # restart chain
            result.extend(_resolve_tie_group(sub, fixtures, stats, notes, 1))
        else:
            result.extend(sub)
    return result


# build table
def compute_standings(
    teams: dict[str, Team],
    fixtures: list[Fixture],
    penalties: list[PenaltyOffence],
    up_to_round: Optional[int] = None,
    orig_round_end: Optional[dict[int, date]] = None,
) -> list[StandingsRow]:
    eligible: list[Fixture] = []
    for f in fixtures:
        if f.expunged:
            continue
        if up_to_round is not None:
            if f.round_no > up_to_round:
                continue
            if (
                orig_round_end is not None
                and f.rescheduled_from is not None
                and up_to_round in orig_round_end
                and f.match_date > orig_round_end[up_to_round]
            ):
                continue
        eligible.append(f)

    stats: dict[str, dict[str, object]] = {}
    for tid, t in teams.items():
        stats[tid] = {
            "team_id": tid,
            "team_name": t.name,
            "played": 0,
            "won": 0,
            "lost": 0,
            "tied": 0,
            "no_result": 0,
            "forfeits": 0,
            "points": 0,
            "penalty_points": 0,
            "runs_scored": 0,
            "balls_faced": 0,
            "runs_conceded": 0,
            "balls_bowled": 0,
            "nrr": 0.0,
            "withdrawn": t.withdrawn,
        }

    for f in eligible:
        if f.result is None:
            continue
        h = f.home_team_id
        a = f.away_team_id
        res = f.result
        if f.status in (MatchStatus.PLAYED, MatchStatus.ABANDONED):
            stats[h]["played"] += 1
            stats[a]["played"] += 1
            if res.is_no_result:
                stats[h]["no_result"] += 1
                stats[a]["no_result"] += 1
                stats[h]["points"] += 1
                stats[a]["points"] += 1
            elif res.is_tie:
                stats[h]["tied"] += 1
                stats[a]["tied"] += 1
                stats[h]["points"] += 1
                stats[a]["points"] += 1
            elif res.winner_id == h:
                stats[h]["won"] += 1
                stats[h]["points"] += 2
                stats[a]["lost"] += 1
            elif res.winner_id == a:
                stats[a]["won"] += 1
                stats[a]["points"] += 2
                stats[h]["lost"] += 1
        elif f.status == MatchStatus.FORFEIT:
            stats[h]["played"] += 1
            stats[a]["played"] += 1
            if res.winner_id == h:
                stats[h]["won"] += 1
                stats[h]["points"] += 2
                stats[a]["lost"] += 1
                stats[a]["forfeits"] += 1
            elif res.winner_id == a:
                stats[a]["won"] += 1
                stats[a]["points"] += 2
                stats[h]["lost"] += 1
                stats[h]["forfeits"] += 1
        elif f.status == MatchStatus.WALKOVER:
            stats[h]["played"] += 1
            stats[a]["played"] += 1
            if res.winner_id == h:
                stats[h]["won"] += 1
                stats[h]["points"] += 2
                stats[a]["lost"] += 1
            elif res.winner_id == a:
                stats[a]["won"] += 1
                stats[a]["points"] += 2
                stats[h]["lost"] += 1
        elif f.status == MatchStatus.CANCELLED:
            stats[h]["played"] += 1
            stats[a]["played"] += 1
            stats[h]["no_result"] += 1
            stats[a]["no_result"] += 1
            stats[h]["points"] += 1
            stats[a]["points"] += 1

        nrr_data = extract_match_nrr(f)
        if nrr_data is not None:
            hr, hb, ar, ab = nrr_data
            stats[h]["runs_scored"] += hr
            stats[h]["balls_faced"] += hb
            stats[h]["runs_conceded"] += ar
            stats[h]["balls_bowled"] += ab
            stats[a]["runs_scored"] += ar
            stats[a]["balls_faced"] += ab
            stats[a]["runs_conceded"] += hr
            stats[a]["balls_bowled"] += hb

    # apply penalties
    for off in penalties:
        if up_to_round is not None and off.round_no > up_to_round:
            continue
        if off.team_id in stats and not teams[off.team_id].expunged:
            stats[off.team_id]["points"] -= off.deduction
            stats[off.team_id]["penalty_points"] += off.deduction

    for tid in stats:
        s = stats[tid]
        s["nrr"] = compute_nrr(
            int(s["runs_scored"]),
            int(s["balls_faced"]),
            int(s["runs_conceded"]),
            int(s["balls_bowled"]),
        )

    pts_buckets: dict[int, list[str]] = {}
    for tid, s in stats.items():
        pts_buckets.setdefault(int(s["points"]), []).append(tid)

    ordered_ids: list[str] = []
    notes: dict[str, str] = {tid: "" for tid in stats}
    for pts in sorted(pts_buckets.keys(), reverse=True):
        grp = pts_buckets[pts]
        if len(grp) > 1:
            ordered_ids.extend(_resolve_tie_group(grp, eligible, stats, notes, 1))
        else:
            ordered_ids.extend(grp)

    rows: list[StandingsRow] = []
    for idx, tid in enumerate(ordered_ids, start=1):
        s = stats[tid]
        rows.append(
            StandingsRow(
                rank=idx,
                team_id=tid,
                team_name=str(s["team_name"]),
                played=int(s["played"]),
                won=int(s["won"]),
                lost=int(s["lost"]),
                tied=int(s["tied"]),
                no_result=int(s["no_result"]),
                forfeits=int(s["forfeits"]),
                points=int(s["points"]),
                penalty_points=int(s["penalty_points"]),
                nrr=float(s["nrr"]),
                runs_scored=int(s["runs_scored"]),
                balls_faced=int(s["balls_faced"]),
                runs_conceded=int(s["runs_conceded"]),
                balls_bowled=int(s["balls_bowled"]),
                withdrawn=bool(s["withdrawn"]),
                tie_break_note=notes[tid],
            )
        )
    return rows

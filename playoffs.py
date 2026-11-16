from typing import Optional
from data_types import MatchStatus, PlayoffMatch, StandingsRow


# seed qualifiers
def build_playoff_bracket(standings: list[StandingsRow]) -> tuple[list[StandingsRow], dict[str, PlayoffMatch]]:
    active = [row for row in standings if not row.withdrawn]
    qualifiers = active[:4]
    if len(qualifiers) < 4:
        raise ValueError("Need at least 4 active teams for playoffs")

    q1 = PlayoffMatch(
        code="Q1",
        label="Qualifier 1",
        team1_id=qualifiers[0].team_id,
        team1_seed=1,
        team2_id=qualifiers[1].team_id,
        team2_seed=2,
    )
    elim = PlayoffMatch(
        code="ELIM",
        label="Eliminator",
        team1_id=qualifiers[2].team_id,
        team1_seed=3,
        team2_id=qualifiers[3].team_id,
        team2_seed=4,
    )
    q2 = PlayoffMatch(
        code="Q2",
        label="Qualifier 2",
    )
    final = PlayoffMatch(
        code="FINAL",
        label="Final",
    )
    bracket = {"Q1": q1, "ELIM": elim, "Q2": q2, "FINAL": final}
    return qualifiers, bracket


# playoff result
def record_playoff_outcome(
    bracket: dict[str, PlayoffMatch],
    code: str,
    status: MatchStatus,
    winner_id: Optional[str] = None,
    is_tie: bool = False,
    is_no_result: bool = False,
) -> PlayoffMatch:
    if code not in bracket:
        raise ValueError(f"Unknown playoff match: {code}")
    pm = bracket[code]
    if pm.team1_id is None or pm.team2_id is None:
        raise ValueError(f"Teams not yet determined for {code}")
    if pm.status != MatchStatus.SCHEDULED:
        raise ValueError(f"Playoff match {code} already decided")
    if pm.team1_seed is None or pm.team2_seed is None:
        raise ValueError(f"Missing seed for {code}")

    if is_tie or is_no_result or (status == MatchStatus.ABANDONED and winner_id is None):
        # higher seed wins
        if pm.team1_seed < pm.team2_seed:
            w_id, l_id = pm.team1_id, pm.team2_id
            w_seed = pm.team1_seed
        else:
            w_id, l_id = pm.team2_id, pm.team1_id
            w_seed = pm.team2_seed
        pm.winner_id = w_id
        pm.loser_id = l_id
        pm.status = status
        pm.note = f"Tie/NR decided by higher league position (Seed #{w_seed})"
    else:
        if winner_id not in (pm.team1_id, pm.team2_id):
            raise ValueError(f"Invalid winner {winner_id} for {code}")
        pm.winner_id = winner_id
        pm.loser_id = pm.team2_id if winner_id == pm.team1_id else pm.team1_id
        pm.status = status

    # advance winner
    seed_map = {pm.team1_id: pm.team1_seed, pm.team2_id: pm.team2_seed}
    if code == "Q1":
        bracket["FINAL"].team1_id = pm.winner_id
        bracket["FINAL"].team1_seed = seed_map[pm.winner_id]
        bracket["Q2"].team1_id = pm.loser_id
        bracket["Q2"].team1_seed = seed_map[pm.loser_id]
    elif code == "ELIM":
        bracket["Q2"].team2_id = pm.winner_id
        bracket["Q2"].team2_seed = seed_map[pm.winner_id]
    elif code == "Q2":
        bracket["FINAL"].team2_id = pm.winner_id
        bracket["FINAL"].team2_seed = seed_map[pm.winner_id]
    return pm

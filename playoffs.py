"""Top-four qualification and playoff bracket progression."""

from __future__ import annotations

from datetime import date

from models import PlayoffMatch, Standing


def build_bracket(standings: list[Standing], eliminated: set[str]) -> dict[str, PlayoffMatch]:
    active = [row for row in standings if row.team_id not in eliminated]
    if len(active) < 4:
        raise ValueError("At least four active teams are required for playoffs")
    return {
        "Q1": PlayoffMatch(
            code="Q1",
            label="Qualifier 1",
            seed1=1,
            team1_id=active[0].team_id,
            seed2=2,
            team2_id=active[1].team_id,
        ),
        "ELIM": PlayoffMatch(
            code="ELIM",
            label="Eliminator",
            seed1=3,
            team1_id=active[2].team_id,
            seed2=4,
            team2_id=active[3].team_id,
        ),
        "Q2": PlayoffMatch(code="Q2", label="Qualifier 2"),
        "FINAL": PlayoffMatch(code="FINAL", label="Final"),
    }


def record_playoff_result(
    bracket: dict[str, PlayoffMatch],
    code: str,
    winner_id: str | None,
    tied: bool,
) -> PlayoffMatch:
    match = bracket.get(code.upper())
    if match is None:
        raise ValueError(f"Unknown playoff match {code}")
    if match.team1_id is None or match.team2_id is None:
        raise ValueError(f"Teams are not yet known for {match.label}")
    if match.winner_id is not None:
        raise ValueError(f"{match.label} already has a result")

    if tied or winner_id is None:
        winner_id = (
            match.team1_id
            if (match.seed1 or 99) < (match.seed2 or 99)
            else match.team2_id
        )
        match.note = "Higher league position wins the tie"
    if winner_id not in (match.team1_id, match.team2_id):
        raise ValueError(f"Invalid winner {winner_id} for {match.label}")

    match.winner_id = winner_id
    match.loser_id = match.team2_id if winner_id == match.team1_id else match.team1_id
    winning_seed = match.seed1 if winner_id == match.team1_id else match.seed2
    losing_seed = match.seed2 if winner_id == match.team1_id else match.seed1
    if code.upper() == "Q1":
        bracket["FINAL"].team1_id = winner_id
        bracket["FINAL"].seed1 = winning_seed
        bracket["Q2"].team1_id = match.loser_id
        bracket["Q2"].seed1 = losing_seed
    elif code.upper() == "ELIM":
        bracket["Q2"].team2_id = winner_id
        bracket["Q2"].seed2 = winning_seed
    elif code.upper() == "Q2":
        bracket["FINAL"].team2_id = winner_id
        bracket["FINAL"].seed2 = winning_seed
    return match


def qualification_rows(
    standings: list[Standing], eliminated: set[str]
) -> list[dict[str, object]]:
    active = [row for row in standings if row.team_id not in eliminated][:4]
    rows: list[dict[str, object]] = []
    for index, row in enumerate(active):
        if index < 2:
            match_name = "Qualifier 1"
            opponent = active[1] if index == 0 else active[0]
        else:
            match_name = "Eliminator"
            opponent = active[3] if index == 2 else active[2]
        rows.append(
            {
                "position": index + 1,
                "team_id": row.team_id,
                "points": row.points,
                "nrr": f"{row.nrr:.4f}",
                "playoff_match": match_name,
                "opponent": opponent.team_id,
            }
        )
    return rows


def bracket_lines(bracket: dict[str, PlayoffMatch]) -> list[str]:
    lines = ["Playoff bracket:"]
    for code in ("Q1", "ELIM", "Q2", "FINAL"):
        match = bracket[code]
        team1 = match.team1_id or "TBD"
        team2 = match.team2_id or "TBD"
        suffix = f" -> {match.winner_id}" if match.winner_id else ""
        lines.append(f"  {match.label}: {team1} vs {team2}{suffix}")
    return lines

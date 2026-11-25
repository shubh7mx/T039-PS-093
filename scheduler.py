"""Double round-robin generation, hard-constraint checks, and rescheduling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from models import Fixture, MatchResult, MatchStatus, Season, Team, Venue


@dataclass(frozen=True)
class Placement:
    day: date
    home_id: str
    away_id: str
    venue_id: str
    swapped: bool


def _circle_rounds(team_ids: list[str]) -> list[list[tuple[str, str]]]:
    """Return one complete round-robin cycle using the circle method."""
    if len(team_ids) < 2 or len(team_ids) % 2:
        raise ValueError("The league requires an even number of at least two teams")
    fixed = team_ids[0]
    rotating = team_ids[1:]
    rounds: list[list[tuple[str, str]]] = []
    for _ in range(len(team_ids) - 1):
        pairs = [(fixed, rotating[0])]
        pairs.extend(
            (rotating[index], rotating[-index])
            for index in range(1, len(team_ids) // 2)
        )
        rounds.append(pairs)
        rotating = [rotating[-1], *rotating[:-1]]
    return rounds


def round_robin_pairings(team_ids: list[str]) -> tuple[list[list[tuple[str, str]]], bool]:
    """Build 18 ordered pairings and find a home/away balance."""
    first_legs = _circle_rounds(team_ids)
    for mask in range(1 << len(first_legs)):
        rounds: list[list[tuple[str, str]]] = []
        for round_index, pairs in enumerate(first_legs):
            oriented = [
                (away, home) if mask & (1 << round_index) else (home, away)
                for home, away in pairs
            ]
            rounds.append(oriented)
        rounds.extend([[(away, home) for home, away in pairs] for pairs in rounds[:]])
        if _max_home_away_streak(rounds) <= 2:
            return rounds, True
    return first_legs + [[(away, home) for home, away in pairs] for pairs in first_legs], False


def _max_home_away_streak(rounds: list[list[tuple[str, str]]]) -> int:
    sequence: dict[str, list[str]] = {}
    for pairs in rounds:
        for home, away in pairs:
            sequence.setdefault(home, []).append("H")
            sequence.setdefault(away, []).append("A")

    maximum = 0
    for values in sequence.values():
        current = 0
        previous = ""
        for value in values:
            current = current + 1 if value == previous else 1
            previous = value
            maximum = max(maximum, current)
    return maximum


def _distance(
    distances: dict[tuple[str, str], int], city_a: str, city_b: str
) -> int:
    if city_a == city_b:
        return 0
    if (city_a, city_b) not in distances:
        raise ValueError(f"Missing distance between {city_a} and {city_b}")
    return distances[(city_a, city_b)]


def _required_clear_days(
    season: Season,
    distances: dict[tuple[str, str], int],
    city_a: str,
    city_b: str,
) -> int:
    return (
        season.long_travel_clear_days
        if _distance(distances, city_a, city_b) > season.long_travel_km
        else season.min_clear_days
    )


def _rest_ok(
    season: Season,
    distances: dict[tuple[str, str], int],
    last_match: dict[str, tuple[date, str]],
    team_id: str,
    candidate: date,
    candidate_city: str,
) -> bool:
    if team_id not in last_match:
        return True
    previous_date, previous_city = last_match[team_id]
    if (candidate - previous_date).days - 1 < _required_clear_days(
        season, distances, previous_city, candidate_city
    ):
        return False
    return True


def _home_available_within_four_days(
    home: Team,
    away: Team,
    venues: dict[str, Venue],
    league_blackouts: set[date],
    season: Season,
    distances: dict[tuple[str, str], int],
    last_match: dict[str, tuple[date, str]],
    round_floor: date,
) -> bool:
    venue = venues[home.home_venue_id]
    for offset in range(5):
        day = round_floor + timedelta(days=offset)
        if not venue.is_available(day, league_blackouts):
            continue
        if _rest_ok(season, distances, last_match, home.team_id, day, home.city):
            if _rest_ok(season, distances, last_match, away.team_id, day, home.city):
                return True
    return False


def _round_candidates(
    pairings: list[tuple[str, str]],
    teams: dict[str, Team],
    venues: dict[str, Venue],
    league_blackouts: set[date],
    season: Season,
    distances: dict[tuple[str, str], int],
    last_match: dict[str, tuple[date, str]],
    round_floor: date,
    allow_fallback_swaps: bool,
) -> list[list[Placement]]:
    options: list[list[Placement]] = []
    for home_id, away_id in pairings:
        home = teams[home_id]
        away = teams[away_id]
        home_possible = _home_available_within_four_days(
            home,
            away,
            venues,
            league_blackouts,
            season,
            distances,
            last_match,
            round_floor,
        )
        fixture_options: list[Placement] = []
        for offset in range(9):
            day = round_floor + timedelta(days=offset)
            if (home_possible or allow_fallback_swaps) and offset <= 4:
                venue = venues[home.home_venue_id]
                if venue.is_available(day, league_blackouts):
                    if _rest_ok(season, distances, last_match, home_id, day, home.city):
                        if _rest_ok(season, distances, last_match, away_id, day, home.city):
                            fixture_options.append(
                                Placement(day, home_id, away_id, venue.venue_id, False)
                            )
            if not home_possible or allow_fallback_swaps:
                venue = venues[away.home_venue_id]
                if venue.is_available(day, league_blackouts):
                    if _rest_ok(season, distances, last_match, away_id, day, away.city):
                        if _rest_ok(season, distances, last_match, home_id, day, away.city):
                            fixture_options.append(
                                Placement(day, away_id, home_id, venue.venue_id, True)
                            )
        if not fixture_options:
            return []
        options.append(fixture_options)
    return options


def _solve_round(
    pairings: list[tuple[str, str]],
    teams: dict[str, Team],
    venues: dict[str, Venue],
    league_blackouts: set[date],
    season: Season,
    distances: dict[tuple[str, str], int],
    last_match: dict[str, tuple[date, str]],
    round_floor: date,
) -> list[Placement] | None:
    for allow_fallback_swaps in (False, True):
        options = _round_candidates(
            pairings,
            teams,
            venues,
            league_blackouts,
            season,
            distances,
            last_match,
            round_floor,
            allow_fallback_swaps,
        )
        if not options:
            continue

        order = sorted(range(len(pairings)), key=lambda index: len(options[index]))
        chosen: list[Placement | None] = [None] * len(pairings)
        used_days: dict[date, int] = {}
        used_venues: set[tuple[date, str]] = set()
        best: tuple[tuple[object, ...], list[Placement]] | None = None

        def search(position: int) -> None:
            nonlocal best
            if position == len(order):
                placed = [item for item in chosen if item is not None]
                first_day = min(item.day for item in placed)
                last_day = max(item.day for item in placed)
                used = {item.day for item in placed}
                missing_weekends = 0
                cursor = first_day
                while cursor <= last_day:
                    if cursor.weekday() >= 5 and cursor not in used:
                        missing_weekends += 1
                    cursor += timedelta(days=1)
                swaps = sum(item.swapped for item in placed)
                span = (last_day - round_floor).days
                score = (
                    missing_weekends,
                    swaps,
                    span,
                    sum((item.day - round_floor).days for item in placed),
                    tuple((item.day.isoformat(), item.venue_id) for item in placed),
                )
                if best is None or score < best[0]:
                    best = (score, placed)
                return

            pairing_index = order[position]
            for candidate in sorted(options[pairing_index], key=lambda item: (item.day, item.swapped)):
                if used_days.get(candidate.day, 0) >= season.max_matches_per_day:
                    continue
                if (candidate.day, candidate.venue_id) in used_venues:
                    continue
                chosen[pairing_index] = candidate
                used_days[candidate.day] = used_days.get(candidate.day, 0) + 1
                used_venues.add((candidate.day, candidate.venue_id))
                search(position + 1)
                used_venues.remove((candidate.day, candidate.venue_id))
                used_days[candidate.day] -= 1
                chosen[pairing_index] = None

        search(0)
        if best is not None:
            return best[1]
    return None


def _fallback_round(
    pairings: list[tuple[str, str]],
    teams: dict[str, Team],
    venues: dict[str, Venue],
    league_blackouts: set[date],
    season: Season,
    occupied: dict[date, int],
    used_venues: set[tuple[date, str]],
    round_floor: date,
) -> list[Placement]:
    placements: list[Placement] = []
    for home_id, away_id in pairings:
        home = teams[home_id]
        venue = venues[home.home_venue_id]
        day = round_floor
        for _ in range(30):
            if (
                occupied.get(day, 0) < season.max_matches_per_day
                and (day, venue.venue_id) not in used_venues
                and venue.is_available(day, league_blackouts)
            ):
                break
            day += timedelta(days=1)
        occupied[day] = occupied.get(day, 0) + 1
        used_venues.add((day, venue.venue_id))
        placements.append(Placement(day, home_id, away_id, venue.venue_id, False))
    return placements


def _assign_start_times(fixtures: list[Fixture], season: Season) -> None:
    by_day: dict[date, list[Fixture]] = {}
    for fixture in fixtures:
        if fixture.status not in (MatchStatus.CANCELLED,) and not fixture.expunged:
            by_day.setdefault(fixture.match_date, []).append(fixture)
    for day_fixtures in by_day.values():
        day_fixtures.sort(key=lambda item: item.fixture_id)
        if len(day_fixtures) == 1:
            day_fixtures[0].start_time = season.single_time
        else:
            for index, fixture in enumerate(day_fixtures):
                fixture.start_time = season.double_times[index % 2]


def generate_fixtures(
    teams: dict[str, Team],
    venues: dict[str, Venue],
    league_blackouts: set[date],
    season: Season,
    distances: dict[tuple[str, str], int],
) -> tuple[list[Fixture], list[str]]:
    """Generate one deterministic valid schedule where the constraints allow it."""
    team_ids = sorted(teams)
    rounds, balanced = round_robin_pairings(team_ids)
    fixtures: list[Fixture] = []
    issues: list[str] = []
    if not balanced:
        issues.append("UNSATISFIED CONSTRAINT: no home/away pattern with a maximum streak of 2")

    last_match: dict[str, tuple[date, str]] = {}
    occupied: dict[date, int] = {}
    used_venues: set[tuple[date, str]] = set()
    round_floor = season.start_date
    number = 1

    for round_index, pairings in enumerate(rounds, start=1):
        placements = _solve_round(
            pairings,
            teams,
            venues,
            league_blackouts,
            season,
            distances,
            last_match,
            round_floor,
        )
        if placements is None:
            issues.append(
                f"UNSATISFIED CONSTRAINT: no legal placement for round {round_index}"
            )
            placements = _fallback_round(
                pairings,
                teams,
                venues,
                league_blackouts,
                season,
                occupied,
                used_venues,
                round_floor,
            )

        placements.sort(key=lambda item: (item.day, item.venue_id))
        for placement in placements:
            venue = venues[placement.venue_id]
            fixtures.append(
                Fixture(
                    fixture_id=f"FX-{number:03d}",
                    round_no=round_index,
                    match_date=placement.day,
                    start_time=season.single_time,
                    home_team_id=placement.home_id,
                    away_team_id=placement.away_id,
                    venue_id=placement.venue_id,
                    swapped_for_blackout=placement.swapped,
                )
            )
            occupied[placement.day] = occupied.get(placement.day, 0) + 1
            used_venues.add((placement.day, placement.venue_id))
            last_match[placement.home_id] = (placement.day, venue.city)
            last_match[placement.away_id] = (placement.day, venue.city)
            number += 1
        round_floor = max(item.day for item in placements) + timedelta(days=1)

    _assign_start_times(fixtures, season)
    issues.extend(audit_fixtures(fixtures, teams, venues, league_blackouts, season, distances))
    return fixtures, list(dict.fromkeys(issues))


def audit_fixtures(
    fixtures: list[Fixture],
    teams: dict[str, Team],
    venues: dict[str, Venue],
    league_blackouts: set[date],
    season: Season,
    distances: dict[tuple[str, str], int],
) -> list[str]:
    active = [fixture for fixture in fixtures if not fixture.expunged]
    issues: list[str] = []
    if len(active) != len(teams) * (len(teams) - 1):
        issues.append(
            f"UNSATISFIED CONSTRAINT: expected {len(teams) * (len(teams) - 1)} fixtures, found {len(active)}"
        )

    by_day: dict[date, list[Fixture]] = {}
    by_venue_day: dict[tuple[date, str], int] = {}
    for fixture in active:
        by_day.setdefault(fixture.match_date, []).append(fixture)
        key = (fixture.match_date, fixture.venue_id)
        by_venue_day[key] = by_venue_day.get(key, 0) + 1
        if not venues[fixture.venue_id].is_available(fixture.match_date, league_blackouts):
            issues.append(
                f"UNSATISFIED CONSTRAINT: {fixture.fixture_id} uses unavailable venue {fixture.venue_id} on {fixture.match_date}"
            )

    for day, day_fixtures in sorted(by_day.items()):
        if len(day_fixtures) > season.max_matches_per_day:
            issues.append(
                f"UNSATISFIED CONSTRAINT: {len(day_fixtures)} matches scheduled on {day}"
            )
        expected_times = (
            [season.single_time]
            if len(day_fixtures) == 1
            else list(season.double_times)
        )
        if sorted(item.start_time for item in day_fixtures) != sorted(expected_times):
            issues.append(f"UNSATISFIED CONSTRAINT: invalid broadcast slots on {day}")

    for (day, venue_id), count in by_venue_day.items():
        if count > 1:
            issues.append(
                f"UNSATISFIED CONSTRAINT: venue {venue_id} hosts {count} matches on {day}"
            )

    team_fixtures: dict[str, list[Fixture]] = {team_id: [] for team_id in teams}
    for fixture in active:
        team_fixtures[fixture.home_team_id].append(fixture)
        team_fixtures[fixture.away_team_id].append(fixture)

    for team_id, matches in team_fixtures.items():
        matches.sort(key=lambda item: (item.round_no, item.match_date, item.fixture_id))
        streak = 0
        previous_side = ""
        for fixture in matches:
            side = "H" if fixture.home_team_id == team_id else "A"
            streak = streak + 1 if side == previous_side else 1
            previous_side = side
            if streak > 2:
                issues.append(
                    f"UNSATISFIED CONSTRAINT: {team_id} has more than 2 consecutive {side} matches in round {fixture.round_no}"
                )
        chronological = sorted(
            matches, key=lambda item: (item.match_date, item.start_time, item.fixture_id)
        )
        for previous, current in zip(chronological, chronological[1:]):
            clear_days = (current.match_date - previous.match_date).days - 1
            previous_city = venues[previous.venue_id].city
            current_city = venues[current.venue_id].city
            required = _required_clear_days(season, distances, previous_city, current_city)
            if clear_days < required:
                issues.append(
                    f"UNSATISFIED CONSTRAINT: {team_id} has {clear_days} clear days before {current.fixture_id}; {required} required"
                )

    pair_counts: dict[tuple[str, str], int] = {}
    for fixture in active:
        pair = tuple(sorted((fixture.home_team_id, fixture.away_team_id)))
        pair_counts[pair] = pair_counts.get(pair, 0) + 1
    for first in teams:
        for second in teams:
            if first >= second:
                continue
            if pair_counts.get((first, second), 0) != 2:
                issues.append(
                    f"UNSATISFIED CONSTRAINT: {first} and {second} do not have exactly two fixtures"
                )

    for round_no, round_fixtures in {
        number: [fixture for fixture in active if fixture.round_no == number]
        for number in {fixture.round_no for fixture in active}
    }.items():
        appearances = [
            team_id
            for fixture in round_fixtures
            for team_id in (fixture.home_team_id, fixture.away_team_id)
        ]
        if len(appearances) != len(set(appearances)):
            issues.append(
                f"UNSATISFIED CONSTRAINT: a team appears twice in round {round_no}"
            )

    rounds: dict[int, list[Fixture]] = {}
    for fixture in active:
        rounds.setdefault(fixture.round_no, []).append(fixture)
    ordered_rounds = sorted(rounds.items())
    for index, (round_no, round_fixtures) in enumerate(ordered_rounds):
        first_day = min(item.match_date for item in round_fixtures)
        if index + 1 < len(ordered_rounds):
            next_first_day = min(
                item.match_date for item in ordered_rounds[index + 1][1]
            )
            last_day = next_first_day - timedelta(days=1)
        else:
            last_day = max(item.match_date for item in round_fixtures)
        played_days = {item.match_date for item in round_fixtures}
        cursor = first_day
        checked_weekends: set[date] = set()
        while cursor <= last_day:
            if cursor.weekday() >= 5:
                saturday = cursor - timedelta(days=cursor.weekday() - 5)
            else:
                saturday = None
            if saturday is not None and saturday not in checked_weekends:
                checked_weekends.add(saturday)
                sunday = saturday + timedelta(days=1)
                weekend_days = [
                    day
                    for day in (saturday, sunday)
                    if first_day <= day <= last_day
                ]
                if weekend_days and not any(day in played_days for day in weekend_days):
                    label = (
                        weekend_days[0].isoformat()
                        if len(weekend_days) == 1
                        else f"{weekend_days[0]}..{weekend_days[-1]}"
                    )
                    reason = (
                        "league blackout"
                        if all(day in league_blackouts for day in weekend_days)
                        else "no legal match"
                    )
                    issues.append(
                        f"UNSATISFIED CONSTRAINT: round {round_no} has no match on weekend {label} ({reason})"
                    )
            cursor += timedelta(days=1)
    return list(dict.fromkeys(issues))


def reschedule_fixture(
    fixture: Fixture,
    fixtures: list[Fixture],
    teams: dict[str, Team],
    venues: dict[str, Venue],
    league_blackouts: set[date],
    season: Season,
    distances: dict[tuple[str, str], int],
    league_cutoff: date,
) -> date | None:
    """Move a postponed fixture to its earliest legal slot, or cancel it."""
    active = [
        item
        for item in fixtures
        if item is not fixture and not item.expunged and item.status != MatchStatus.CANCELLED
    ]
    same_round = [item for item in active if item.round_no == fixture.round_no]
    round_end = max((item.match_date for item in same_round), default=fixture.original_date)
    start = max(round_end or fixture.match_date, fixture.match_date) + timedelta(days=1)
    cutoff = league_cutoff + timedelta(days=season.reserve_days)
    venue = venues[fixture.venue_id]

    cursor = start
    while cursor <= cutoff:
        day_fixtures = [item for item in active if item.match_date == cursor]
        if not venue.is_available(cursor, league_blackouts):
            cursor += timedelta(days=1)
            continue
        if len(day_fixtures) >= season.max_matches_per_day:
            cursor += timedelta(days=1)
            continue
        if any(item.venue_id == fixture.venue_id for item in day_fixtures):
            cursor += timedelta(days=1)
            continue

        legal = True
        for team_id in (fixture.home_team_id, fixture.away_team_id):
            team_fixtures = [
                item
                for item in active
                if team_id in (item.home_team_id, item.away_team_id)
            ]
            if any(item.match_date == cursor for item in team_fixtures):
                legal = False
                break
            previous = [item for item in team_fixtures if item.match_date < cursor]
            following = [item for item in team_fixtures if item.match_date > cursor]
            if previous:
                match = max(previous, key=lambda item: item.match_date)
                clear_days = (cursor - match.match_date).days - 1
                required = _required_clear_days(
                    season,
                    distances,
                    venues[match.venue_id].city,
                    venue.city,
                )
                if clear_days < required:
                    legal = False
                    break
            if following:
                match = min(following, key=lambda item: item.match_date)
                clear_days = (match.match_date - cursor).days - 1
                required = _required_clear_days(
                    season,
                    distances,
                    venue.city,
                    venues[match.venue_id].city,
                )
                if clear_days < required:
                    legal = False
                    break
        if not legal:
            cursor += timedelta(days=1)
            continue

        fixture.match_date = cursor
        fixture.status = MatchStatus.SCHEDULED
        fixture.result = None
        fixture.rescheduled = True
        _assign_start_times(fixtures, season)
        return cursor

    fixture.status = MatchStatus.CANCELLED
    fixture.result = MatchResult(MatchStatus.CANCELLED, is_no_result=True)
    _assign_start_times(fixtures, season)
    return None


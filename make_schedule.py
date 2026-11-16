from datetime import date, timedelta
from typing import Optional
from data_types import Fixture, MatchResult, MatchStatus, SeasonConfig, Team, Venue


# circle pairing
def _circle_half(n: int) -> list[list[tuple[int, int]]]:
    m = n - 1
    pivot = n - 1
    arr = list(range(m))
    rounds: list[list[tuple[int, int]]] = []
    for r in range(m):
        pairs: list[tuple[int, int]] = []
        if r % 2 == 0:
            pairs.append((pivot, arr[0]))
        else:
            pairs.append((arr[0], pivot))
        for i in range(1, n // 2):
            if i % 2 == 1:
                pairs.append((arr[i], arr[m - i]))
            else:
                pairs.append((arr[m - i], arr[i]))
        rounds.append(pairs)
        arr = [arr[-1]] + arr[:-1]
    return rounds


# streak check
def _max_ha_streak(rounds: list[list[tuple[int, int]]], n: int) -> int:
    best = 0
    for t in range(n):
        seq: list[str] = []
        for rnd in rounds:
            for h, a in rnd:
                if h == t:
                    seq.append("H")
                elif a == t:
                    seq.append("A")
        cur = 0
        prev = ""
        for ch in seq:
            cur = cur + 1 if ch == prev else 1
            prev = ch
            if cur > best:
                best = cur
    return best


# build rounds
def generate_round_robin_pairs(team_ids: list[str]) -> list[list[tuple[str, str]]]:
    n = len(team_ids)
    if n < 2 or n % 2 != 0:
        raise ValueError("Even team count required")
    r1 = _circle_half(n)
    r2_base = [[(a, h) for h, a in rnd] for rnd in r1]
    candidates = [
        r1 + (r2_base[1:] + r2_base[:1]),
        r1 + list(reversed(r2_base)),
        r1 + r2_base,
    ]
    chosen = candidates[-1]
    for cand in candidates:
        if _max_ha_streak(cand, n) <= 2:
            chosen = cand
            break
    return [[(team_ids[h], team_ids[a]) for h, a in rnd] for rnd in chosen]


# city distance
def get_distance(distances: dict[tuple[str, str], float], city_a: str, city_b: str) -> float:
    if city_a == city_b:
        return 0.0
    if (city_a, city_b) in distances:
        return distances[(city_a, city_b)]
    if (city_b, city_a) in distances:
        return distances[(city_b, city_a)]
    return 0.0


# rest needed
def required_clear_days(distances: dict[tuple[str, str], float], city_a: str, city_b: str) -> int:
    dist = get_distance(distances, city_a, city_b)
    return 3 if dist > 1500.0 else 2


# rest check
def _rest_ok(
    team_last: dict[str, tuple[date, str]],
    team_id: str,
    cand_date: date,
    cand_city: str,
    distances: dict[tuple[str, str], float],
) -> bool:
    if team_id not in team_last:
        return True
    prev_date, prev_city = team_last[team_id]
    clear_days = (cand_date - prev_date).days - 1
    req = required_clear_days(distances, prev_city, cand_city)
    return clear_days >= req


# blackout rule
def _apply_venue_blackout_rule(
    home_id: str,
    away_id: str,
    round_floor: date,
    team_last: dict[str, tuple[date, str]],
    day_counts: dict[date, int],
    venue_used: set[tuple[date, str]],
    teams: dict[str, Team],
    venues: dict[str, Venue],
    distances: dict[tuple[str, str], float],
    season: SeasonConfig,
) -> tuple[str, str, bool]:
    h_team = teams[home_id]
    h_venue = venues[h_team.home_venue_id]
    d0 = round_floor
    for offset in range(30):
        cand = round_floor + timedelta(days=offset)
        if cand in season.blackout_dates:
            continue
        if day_counts.get(cand, 0) >= 2:
            continue
        if not _rest_ok(team_last, home_id, cand, h_team.city, distances):
            continue
        if not _rest_ok(team_last, away_id, cand, h_team.city, distances):
            continue
        d0 = cand
        break

    if h_venue.is_available(d0) and (d0, h_venue.venue_id) not in venue_used:
        return home_id, away_id, False

    # check 4 days
    for delta in range(1, 5):
        cand = d0 + timedelta(days=delta)
        if cand in season.blackout_dates:
            continue
        if day_counts.get(cand, 0) >= 2:
            continue
        if not h_venue.is_available(cand):
            continue
        if (cand, h_venue.venue_id) in venue_used:
            continue
        if not _rest_ok(team_last, home_id, cand, h_team.city, distances):
            continue
        if not _rest_ok(team_last, away_id, cand, h_team.city, distances):
            continue
        return home_id, away_id, False

    # swap venues
    return away_id, home_id, True


# place round
def _solve_round_dates(
    pairings: list[tuple[str, str, bool]],
    next_pairings: list[tuple[str, str]],
    round_floor: date,
    team_last: dict[str, tuple[date, str]],
    day_counts: dict[date, int],
    venue_used: set[tuple[date, str]],
    teams: dict[str, Team],
    venues: dict[str, Venue],
    distances: dict[tuple[str, str], float],
    season: SeasonConfig,
) -> Optional[list[tuple[str, str, bool, date]]]:
    m = len(pairings)
    min_span = max(0, (m - 1) // 2)
    for max_span in range(min_span, 28):
        window_days = [round_floor + timedelta(days=i) for i in range(max_span + 1)]
        options_per_match: list[list[date]] = []
        possible = True
        for h_id, a_id, _ in pairings:
            h_team = teams[h_id]
            h_venue = venues[h_team.home_venue_id]
            opts: list[date] = []
            for d in window_days:
                if d in season.blackout_dates:
                    continue
                if day_counts.get(d, 0) >= 2:
                    continue
                if not h_venue.is_available(d):
                    continue
                if (d, h_venue.venue_id) in venue_used:
                    continue
                if not _rest_ok(team_last, h_id, d, h_team.city, distances):
                    continue
                if not _rest_ok(team_last, a_id, d, h_team.city, distances):
                    continue
                opts.append(d)
            if not opts:
                possible = False
                break
            options_per_match.append(opts)
        if not possible:
            continue

        order = sorted(range(m), key=lambda idx: (len(options_per_match[idx]), options_per_match[idx][0]))
        best_assign: Optional[list[date]] = None
        best_score: Optional[tuple[int, date, int]] = None
        cur_assign: list[Optional[date]] = [None] * m
        local_day = dict(day_counts)
        local_venue = set(venue_used)

        def _next_round_can_cover(d_check: date, assign_dates: list[date]) -> bool:
            if not next_pairings or d_check in season.blackout_dates:
                return False
            sim_last = dict(team_last)
            for idx_m, d_m in enumerate(assign_dates):
                hm, am, _ = pairings[idx_m]
                c_m = teams[hm].city
                sim_last[hm] = (d_m, c_m)
                sim_last[am] = (d_m, c_m)
            for nh, na in next_pairings:
                hc = teams[nh].city
                hv = venues[teams[nh].home_venue_id]
                if not hv.is_available(d_check):
                    continue
                if _rest_ok(sim_last, nh, d_check, hc, distances) and _rest_ok(sim_last, na, d_check, hc, distances):
                    return True
            return False

        def backtrack(pos: int) -> None:
            nonlocal best_assign, best_score
            if pos == m:
                dates_used = [d for d in cur_assign if d is not None]
                max_d = max(dates_used)
                # weekend check
                uncovered_weekend = 0
                cur_d = round_floor
                while cur_d <= max_d:
                    if cur_d.weekday() in (5, 6) and local_day.get(cur_d, 0) == 0:
                        uncovered_weekend += 1
                    cur_d += timedelta(days=1)
                # check gap weekends
                if next_pairings:
                    for extra in (1, 2, 3):
                        gap_d = max_d + timedelta(days=extra)
                        if gap_d.weekday() in (5, 6) and not _next_round_can_cover(gap_d, dates_used):
                            uncovered_weekend += 1
                span_sum = sum((d - round_floor).days for d in dates_used)
                score = (uncovered_weekend, max_d, span_sum)
                if best_score is None or score < best_score:
                    best_score = score
                    best_assign = [d for d in dates_used]
                return

            idx = order[pos]
            h_id, _, _ = pairings[idx]
            v_id = teams[h_id].home_venue_id
            # prefer weekends
            cands = sorted(
                options_per_match[idx],
                key=lambda d: (0 if d.weekday() in (5, 6) and local_day.get(d, 0) == 0 else 1, d),
            )
            for d in cands:
                if local_day.get(d, 0) >= 2:
                    continue
                if (d, v_id) in local_venue:
                    continue
                local_day[d] = local_day.get(d, 0) + 1
                local_venue.add((d, v_id))
                cur_assign[idx] = d
                backtrack(pos + 1)
                cur_assign[idx] = None
                local_venue.remove((d, v_id))
                local_day[d] -= 1
                if best_score is not None and best_score[0] == 0 and best_score[1] <= round_floor + timedelta(days=min_span):
                    return

        backtrack(0)
        if best_assign is not None and (best_score[0] == 0 or max_span >= min_span + 4):
            return [
                (pairings[i][0], pairings[i][1], pairings[i][2], best_assign[i])
                for i in range(m)
            ]
    return None


# set times
def assign_start_times(fixtures: list[Fixture], season: SeasonConfig) -> None:
    windows = season.broadcast_windows or ["15:30", "19:30"]
    single_slot = windows[-1]
    by_day: dict[date, list[Fixture]] = {}
    for f in fixtures:
        if f.status in (MatchStatus.POSTPONED, MatchStatus.CANCELLED) or f.expunged:
            continue
        by_day.setdefault(f.match_date, []).append(f)
    for d, day_list in by_day.items():
        day_list.sort(key=lambda x: x.fixture_id)
        if len(day_list) == 1:
            day_list[0].start_time = single_slot
        else:
            for idx, fix in enumerate(day_list):
                fix.start_time = windows[idx % len(windows)]


# build schedule
def generate_schedule(
    teams: dict[str, Team],
    venues: dict[str, Venue],
    distances: dict[tuple[str, str], float],
    season: SeasonConfig,
) -> tuple[list[Fixture], list[str]]:
    if season.start_date is None:
        raise ValueError("Season start date required")
    team_ids = list(teams.keys())
    rounds_raw = generate_round_robin_pairs(team_ids)

    fixtures: list[Fixture] = []
    unsatisfied: list[str] = []
    team_last: dict[str, tuple[date, str]] = {}
    day_counts: dict[date, int] = {}
    venue_used: set[tuple[date, str]] = set()
    round_floor = season.start_date
    fix_counter = 1

    for round_idx, raw_pairs in enumerate(rounds_raw, start=1):
        next_pairs = rounds_raw[round_idx] if round_idx < len(rounds_raw) else []
        adjusted_pairs: list[tuple[str, str, bool]] = []
        for h_id, a_id in raw_pairs:
            nh, na, swapped = _apply_venue_blackout_rule(
                h_id, a_id, round_floor, team_last, day_counts, venue_used, teams, venues, distances, season
            )
            adjusted_pairs.append((nh, na, swapped))

        solved = _solve_round_dates(
            adjusted_pairs, next_pairs, round_floor, team_last, day_counts, venue_used, teams, venues, distances, season
        )

        if solved is None:
            # fallback placement
            solved = []
            for h_id, a_id, swapped in adjusted_pairs:
                cand = round_floor
                h_city = teams[h_id].city
                v_id = teams[h_id].home_venue_id
                while (
                    cand in season.blackout_dates
                    or day_counts.get(cand, 0) >= 2
                    or (cand, v_id) in venue_used
                ):
                    cand += timedelta(days=1)
                if not venues[v_id].is_available(cand):
                    unsatisfied.append(
                        f"UNSATISFIED CONSTRAINT: Round {round_idx} {h_id} vs {a_id} placed on unavailable venue {v_id} ({cand.isoformat()})"
                    )
                if not _rest_ok(team_last, h_id, cand, h_city, distances) or not _rest_ok(
                    team_last, a_id, cand, h_city, distances
                ):
                    unsatisfied.append(
                        f"UNSATISFIED CONSTRAINT: Round {round_idx} {h_id} vs {a_id} violates rest days on {cand.isoformat()}"
                    )
                day_counts[cand] = day_counts.get(cand, 0) + 1
                venue_used.add((cand, v_id))
                team_last[h_id] = (cand, h_city)
                team_last[a_id] = (cand, h_city)
                solved.append((h_id, a_id, swapped, cand))

        max_round_date = round_floor
        for h_id, a_id, swapped, m_date in sorted(solved, key=lambda x: (x[3], x[0])):
            h_team = teams[h_id]
            v_id = h_team.home_venue_id
            day_counts[m_date] = day_counts.get(m_date, 0) + 1
            venue_used.add((m_date, v_id))
            team_last[h_id] = (m_date, h_team.city)
            team_last[a_id] = (m_date, h_team.city)
            if m_date > max_round_date:
                max_round_date = m_date
            fixtures.append(
                Fixture(
                    fixture_id=f"F{fix_counter:03d}",
                    round_no=round_idx,
                    home_team_id=h_id,
                    away_team_id=a_id,
                    venue_id=v_id,
                    city=h_team.city,
                    match_date=m_date,
                    swapped_from_blackout=swapped,
                )
            )
            fix_counter += 1

        round_floor = max_round_date + timedelta(days=1)

    assign_start_times(fixtures, season)
    unsatisfied.extend(audit_constraints(fixtures, teams, venues, distances, season))
    seen: set[str] = set()
    unique_unsat: list[str] = []
    for msg in unsatisfied:
        if msg not in seen:
            seen.add(msg)
            unique_unsat.append(msg)
    return fixtures, unique_unsat


# check rules
def audit_constraints(
    fixtures: list[Fixture],
    teams: dict[str, Team],
    venues: dict[str, Venue],
    distances: dict[tuple[str, str], float],
    season: SeasonConfig,
) -> list[str]:
    issues: list[str] = []
    active = [f for f in fixtures if f.status not in (MatchStatus.POSTPONED, MatchStatus.CANCELLED) and not f.expunged]
    if not active:
        return issues

    # check streaks
    by_team_round: dict[str, list[tuple[int, str]]] = {tid: [] for tid in teams}
    for f in sorted(fixtures, key=lambda x: (x.round_no, x.match_date, x.fixture_id)):
        by_team_round[f.home_team_id].append((f.round_no, "H"))
        by_team_round[f.away_team_id].append((f.round_no, "A"))
    for tid, seq in by_team_round.items():
        streak = 0
        prev = ""
        for rnd, ch in seq:
            streak = streak + 1 if ch == prev else 1
            prev = ch
            if streak > 2:
                issues.append(
                    f"UNSATISFIED CONSTRAINT: Team {tid} has >2 consecutive {ch} matches ending at round {rnd}"
                )

    by_day: dict[date, list[Fixture]] = {}
    by_day_venue: dict[tuple[date, str], int] = {}
    for f in active:
        by_day.setdefault(f.match_date, []).append(f)
        by_day_venue[(f.match_date, f.venue_id)] = by_day_venue.get((f.match_date, f.venue_id), 0) + 1
        if f.match_date in season.blackout_dates:
            issues.append(f"UNSATISFIED CONSTRAINT: Fixture {f.fixture_id} on season blackout {f.match_date.isoformat()}")
        if not venues[f.venue_id].is_available(f.match_date):
            issues.append(f"UNSATISFIED CONSTRAINT: Fixture {f.fixture_id} on unavailable venue {f.venue_id} ({f.match_date.isoformat()})")

    for d, day_list in sorted(by_day.items()):
        if len(day_list) > 2:
            issues.append(f"UNSATISFIED CONSTRAINT: More than 2 matches scheduled on {d.isoformat()}")
        if len(day_list) == 2:
            times = sorted(f.start_time for f in day_list)
            if times != ["15:30", "19:30"]:
                issues.append(f"UNSATISFIED CONSTRAINT: Double-header on {d.isoformat()} does not use 15:30 and 19:30")

    for (d, vid), cnt in sorted(by_day_venue.items()):
        if cnt > 1:
            issues.append(f"UNSATISFIED CONSTRAINT: Venue {vid} hosts {cnt} matches on {d.isoformat()}")

    # check rest
    team_matches: dict[str, list[Fixture]] = {tid: [] for tid in teams}
    for f in active:
        team_matches[f.home_team_id].append(f)
        team_matches[f.away_team_id].append(f)
    for tid, t_list in team_matches.items():
        t_list.sort(key=lambda x: (x.match_date, x.start_time))
        for i in range(1, len(t_list)):
            prev_f = t_list[i - 1]
            cur_f = t_list[i]
            clear_days = (cur_f.match_date - prev_f.match_date).days - 1
            req = required_clear_days(distances, prev_f.city, cur_f.city)
            if clear_days < req:
                issues.append(
                    f"UNSATISFIED CONSTRAINT: Team {tid} has {clear_days} clear days (< {req}) between {prev_f.fixture_id} and {cur_f.fixture_id}"
                )

    # check weekends
    min_d = min(f.match_date for f in active)
    max_d = max(f.match_date for f in active)
    cur_d = min_d
    while cur_d <= max_d:
        if cur_d.weekday() in (5, 6) and len(by_day.get(cur_d, [])) == 0:
            day_name = "Saturday" if cur_d.weekday() == 5 else "Sunday"
            reason = "blackout date" if cur_d in season.blackout_dates else "no available fixture"
            issues.append(
                f"UNSATISFIED CONSTRAINT: Weekend broadcast rule violated on {day_name} {cur_d.isoformat()} ({reason})"
            )
        cur_d += timedelta(days=1)

    return issues


# move postponed
def reschedule_postponed_fixture(
    fixture: Fixture,
    fixtures: list[Fixture],
    teams: dict[str, Team],
    venues: dict[str, Venue],
    distances: dict[tuple[str, str], float],
    season: SeasonConfig,
    last_round_end: date,
) -> tuple[bool, Optional[date]]:
    old_date = fixture.match_date
    round_fixtures = [f for f in fixtures if f.round_no == fixture.round_no and f.fixture_id != fixture.fixture_id]
    current_round_end = max([f.match_date for f in round_fixtures], default=old_date)
    search_start = max(old_date, current_round_end) + timedelta(days=1)
    search_end = last_round_end + timedelta(days=season.reserve_days)

    active = [
        f
        for f in fixtures
        if f.fixture_id != fixture.fixture_id
        and f.status not in (MatchStatus.POSTPONED, MatchStatus.CANCELLED)
        and not f.expunged
    ]

    venue = venues[fixture.venue_id]
    cur = search_start
    while cur <= search_end:
        if cur in season.blackout_dates or not venue.is_available(cur):
            cur += timedelta(days=1)
            continue
        day_matches = [f for f in active if f.match_date == cur]
        if len(day_matches) >= 2:
            cur += timedelta(days=1)
            continue
        if any(f.venue_id == fixture.venue_id for f in day_matches):
            cur += timedelta(days=1)
            continue

        # check teams
        ok = True
        for tid in (fixture.home_team_id, fixture.away_team_id):
            t_fixes = [f for f in active if tid in (f.home_team_id, f.away_team_id)]
            if any(f.match_date == cur for f in t_fixes):
                ok = False
                break
            prev_fixes = [f for f in t_fixes if f.match_date < cur]
            if prev_fixes:
                prev_f = max(prev_fixes, key=lambda x: x.match_date)
                clear_prev = (cur - prev_f.match_date).days - 1
                if clear_prev < required_clear_days(distances, prev_f.city, fixture.city):
                    ok = False
                    break
            next_fixes = [f for f in t_fixes if f.match_date > cur]
            if next_fixes:
                next_f = min(next_fixes, key=lambda x: x.match_date)
                clear_next = (next_f.match_date - cur).days - 1
                if clear_next < required_clear_days(distances, fixture.city, next_f.city):
                    ok = False
                    break

        if ok:
            fixture.rescheduled_from = old_date
            fixture.match_date = cur
            fixture.status = MatchStatus.SCHEDULED
            fixture.result = None
            assign_start_times(fixtures, season)
            return True, cur
        cur += timedelta(days=1)

    fixture.status = MatchStatus.CANCELLED
    fixture.result = MatchResult(status=MatchStatus.CANCELLED, is_no_result=True)
    assign_start_times(fixtures, season)
    return False, None

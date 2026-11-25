# PS-093 – League Fixture Scheduling and Points Table with Tie-Breakers — Sample Data Pack

Prepared by 10 SECONDS for Team T039.

## Files

| File | What it holds | Row count |
|---|---|---|
| `season.csv` | Season parameters | 10 data rows |
| `teams.csv` | 10 teams with home venue and city | 10 data rows |
| `venues.csv` | 9 venues (two Delhi teams share one; Mumbai has two venues) | 9 data rows |
| `distances.csv` | Road distance between cities (km) | 28 data rows |
| `blackouts.csv` | League-wide and venue blackout dates | 10 data rows |
| `reference_fixtures.csv` | Published reference fixture list (90 fixtures, 18 rounds) used for results | 90 data rows |
| `results.csv` | Results incl. postponements, forfeits, abandoned matches and two invalid rows | 87 data rows |
| `over_rate_offences.csv` | Slow-over-rate offences | 3 data rows |
| `commands.txt` | Fixture generation / check, results, offences, withdrawal, round ends and prints | 118 command lines (excluding comments) |

Row numbers quoted below are 1-based data-row numbers (the header is row 0). Line numbers for `commands.txt` are physical line numbers including comment lines.

## Column reference

Conventions: dates `YYYY-MM-DD`; timestamps `YYYY-MM-DD HH:MM:SS` (24h, IST, no timezone suffix); money in Rs as plain decimals with 2 places (no commas, no symbol); percentages as plain numbers (12.5 means 12.5%); booleans `true`/`false`; IDs uppercase with a fixed prefix. An empty cell means "not applicable" and only occurs in columns whose notes say so.

### `season.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| parameter | string | — | — | — |
| value | string | — | — | — |

### `teams.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| team_id | string | Tnn-XXX | — | lower team_id wins the last tie-break |
| team_name | string | — | — | — |
| home_venue_id | string | — | venues.csv | — |
| city | string | — | — | — |

### `venues.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| venue_id | string | VEN-nn | — | — |
| venue_name | string | — | — | — |
| city | string | — | — | — |
| capacity | int | — | — | — |

### `distances.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| city_a | string | — | — | symmetric; same city = 0 km |
| city_b | string | — | — | — |
| km | int | km | — | > 1500 needs 3 clear days |

### `blackouts.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| blackout_id | string | BO-nn | — | — |
| scope | enum | — | LEAGUE, VENUE | — |
| venue_id | string | — | venues.csv | VENUE scope only |
| date | date | — | — | — |
| reason | string | — | — | — |

### `reference_fixtures.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| fixture_id | string | FX-nnn | — | — |
| round | int | — | 1-18 | — |
| match_date | date | — | — | original date |
| start_time | string | HH:MM | 15:30, 19:30 | — |
| home_team_id | string | — | teams.csv | — |
| away_team_id | string | — | teams.csv | — |
| venue_id | string | — | venues.csv | — |

### `results.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| result_id | string | RS-nnn | — | — |
| fixture_id | string | — | reference_fixtures.csv | — |
| match_date | date | — | — | a rescheduled match carries its new date |
| status | enum | — | PLAYED, ABANDONED, FORFEIT, POSTPONED | — |
| batting_first | enum | — | HOME, AWAY | PLAYED only |
| home_runs | int | — | — | — |
| home_wickets | int | — | 0-10 | 10 = all out -> 20 overs for NRR |
| home_overs | string | overs.balls | — | e.g. 14.3 = 14 overs 3 balls |
| away_runs | int | — | — | — |
| away_wickets | int | — | — | — |
| away_overs | string | overs.balls | — | — |
| play_completed_pct | decimal | % | — | ABANDONED only (< 50 -> no-result) |
| forfeiting_team_id | string | — | teams.csv | FORFEIT only |

### `over_rate_offences.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| offence_id | string | OR-n | — | — |
| fixture_id | string | — | reference_fixtures.csv | — |
| team_id | string | — | teams.csv | — |
| match_date | date | — | — | — |

## Command file format

`commands.txt` holds one command per line in the form `COMMAND_NAME|arg1|arg2|...`. Commands must be processed strictly in file order. Lines starting with `#` are comments and blank lines are ignored. An empty argument (two pipes in a row) means "not supplied". Every command used in this pack:

| Command | Arguments (in order) | Meaning |
|---|---|---|
| `GENERATE_FIXTURES` | `season_start` | Run your scheduler (output graded by the constraint checker; print unsatisfiable constraints) |
| `CHECK_FIXTURES` | `` | Validate your generated list against every hard constraint |
| `LOAD_FIXTURES` | `file` | Load the reference fixture list for the rest of the run |
| `RECORD_RESULT` | `result_id` | Validate and apply a results.csv row (POSTPONED -> reschedule to the earliest valid date after the round) |
| `OVER_RATE_OFFENCE` | `offence_id` | Register an offence (2nd: -1 point, later: -2 each) |
| `WITHDRAW_TEAM` | `team_id|date` | Withdraw a team (expunge if < 50% played, else walkovers) |
| `END_ROUND` | `round` | Close a round |
| `PRINT_TABLE` | `round` | Points table after the round |
| `CLOSE_LEAGUE_STAGE` | `` | Final table, qualifiers, playoff bracket |
| `PRINT_QUALIFICATION` | `` | Qualification report |
| `PRINT_FIXTURES` | `` | Fixture list with reschedules |

## Planted scenarios

Every edge case in the brief, mapped to the exact record where it occurs, followed by extra traps.

- **EC-01 Three teams tied on points and wins where head-to-head separates one and the other two restart the chain**
  - T05-DEL, T08-DDY and T07-HYD finish level on 25 points and 12 wins. Head-to-head among the three: T05-DEL beat T08-DDY twice and T07-HYD twice (8 points) -> T05-DEL separates first; T08-DDY and T07-HYD restart the chain: wins equal, head-to-head between them 2-2 (FX-037 won by T08-DDY, FX-085 forfeited by T08-DDY), so net run rate decides — `reference_fixtures.csv FX-044 (row 44); reference_fixtures.csv FX-089 (row 89); reference_fixtures.csv FX-021 (row 21); reference_fixtures.csv FX-067 (row 67); reference_fixtures.csv FX-037 (row 37); reference_fixtures.csv FX-085 (row 85)`
- **EC-02 Team bowled out in 14.3 of 20 overs - NRR uses 20 overs faced**
  - RS-020: T10-AHM is bowled out in 14.3 overs -> for net run rate it has faced the full 20.0 overs (its opponents bowled 14.3 = 14 + 3/6 overs) — `results.csv RS-020 (row 20); reference_fixtures.csv FX-020 (row 20)`
- **EC-03 Blackout on the only weekend day of a round**
  - League blackout on 2026-09-19 (Saturday) is the only weekend day inside round 4's window (2026-09-16 .. 2026-09-19) -> the 'at least one match each weekend day' rule cannot be met; your generator must print it as an unsatisfiable constraint, not schedule on the blackout — `blackouts.csv BO-01 (row 1)`
- **EC-04 Postponed match with the opponent travelling 1,500 km exactly**
  - FX-011 is POSTPONED from 2026-09-12; T08-DDY last played on 2026-11-18 in Delhi, exactly 1,500 km from Mumbai (distances.csv) -> not more than 1,500 km -> 2 clear days suffice -> earliest valid date 2026-11-21 (3 clear days would have pushed it later); the result is recorded on 2026-11-21 — `reference_fixtures.csv FX-011 (row 11); results.csv RS-011 (row 11); results.csv RS-084 (row 84); distances.csv Mumbai (row 25)`
- **EC-05 Second slow-over-rate offence in the final round changing qualification**
  - T02-MSW: 1st slow-over-rate offence in round 4 (no deduction), 2nd in round 18 (FX-088) -> -1 point applied in round 18: T02-MSW drops from 22 to 21 points and from 4th (level with T09-JAI on 22, ahead on wins) to 5th -> T09-JAI qualifies instead — `commands.txt lines 29, 111; teams.csv T02-MSW (row 2); teams.csv T09-JAI (row 9)`
- **EC-06 Forfeit counted in head-to-head but excluded from NRR**
  - RS-079: T08-DDY forfeits to T07-HYD -> 2 points to T07-HYD, counted in the T08-DDY/T07-HYD head-to-head, excluded from both teams' net run rate; second forfeit RS-055 likewise — `results.csv RS-079 (row 79); results.csv RS-055 (row 55)`
- **EC-07 Team withdrawing after exactly 50 percent of fixtures**
  - T10-AHM withdraws on 2026-10-13 after playing exactly 9 of 18 fixtures (50%) -> not fewer than 50% -> its results stand and its remaining 9 fixtures become 2-point walkovers for the opponents (no results.csv rows for them) — `commands.txt line 64; reference_fixtures.csv FX-048 (row 48); reference_fixtures.csv FX-054 (row 54)`
- **EC-08 Two venues in the same city both unavailable on consecutive days**
  - Mumbai's two venues (VEN-01, VEN-02) are both blacked out on 2026-10-09 and 2026-10-10 (consecutive days) -> home matches of T01-MUM and T02-MSW cannot use either day; move to the next available day for both teams (swap only if none within 4 days) — `blackouts.csv BO-07 (row 7); blackouts.csv BO-08 (row 8); blackouts.csv BO-09 (row 9); blackouts.csv BO-10 (row 10)`
- **Extra traps (not in the brief, but realistic):**
  - RS-027: second result row for the same fixture -> REJECTED — `results.csv RS-027 (row 27)`
  - RS-051: result dated one day before its fixture date -> REJECTED (not scheduled on that date / entered before the fixture date) — `results.csv RS-051 (row 51)`
  - T09-JAI: a single slow-over-rate offence (FX-027) -> no deduction (only the 2nd and later offences cost points) — `commands.txt line 40`

## What is NOT in this pack

Expected outputs are not provided for this set. Validate your engine with your own test suite against the rules in your brief (BR-01 … BR-nn). A separate hidden input set with the same schema will be used at final evaluation; outputs are compared field-for-field, so follow the column formats above exactly in your own output.

## Output format expected at evaluation

Produce these CSV files (header row, same conventions as above, rows sorted as stated). Where the brief is silent on a format detail the choice below is binding for evaluation.

### `result_log.csv`

One row per RECORD_RESULT.

Columns, in order: `result_id`, `fixture_id`, `action`, `reason`, `new_match_date`

### `points_table_r06.csv`

Table after round 6 (also _r12, _r18 with the same columns).

Columns, in order: `position`, `team_id`, `played`, `won`, `lost`, `no_result`, `forfeits`, `points_before_penalty`, `penalty`, `points`, `nrr`, `decided_by_step`

### `qualification.csv`

Top 4 and the bracket.

Columns, in order: `position`, `team_id`, `points`, `nrr`, `playoff_match`, `opponent`

Binding choices where the brief is silent: the table after round r includes every result dated on or before the last date of round r (reschedules count when played; the final table also includes the 3 reserve days). Walkovers after a withdrawal count as wins (2 points) and in head-to-head, never in NRR; no-results and forfeits are excluded from NRR. NRR uses overs.balls -> overs + balls/6 and 20.0 overs for an all-out side, 4 decimals (half-up). A rescheduled match is placed on the earliest date after its round's last date where both teams keep 2 clear days (3 after/before a trip > 1,500 km) to every other fixture, the venue is free, the day has < 2 matches and no blackout applies; it takes 15:30 if the day already has a 19:30 match. `decided_by_step` = the tie-breaker step (1-6) that placed the team, empty if decided on points.

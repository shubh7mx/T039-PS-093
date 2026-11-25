# PS-093 League Competition Engine Design

This design covers the command-driven league engine defined by the PS-093 sample pack. Python 3.10+ and the standard library are sufficient.

## Business Rules

| ID | Rule |
|---|---|
| BR-01 | A season has 10 teams and 90 double round-robin fixtures. Pair teams with the circle method for 18 rounds, with each pair meeting twice and each team hosting once. |
| BR-02 | No team may have more than two consecutive home matches or more than two consecutive away matches when fixtures are ordered by round. |
| BR-03 | Both teams need at least two clear dates between matches. A trip of more than 1,500 km requires three clear dates; exactly 1,500 km uses the normal two-day rule. |
| BR-04 | A venue hosts at most one match per day and must be available on that date. League blackouts apply to every venue. |
| BR-05 | If the home venue is unavailable, use the next date that works for both teams and the venue. If no date is available within four days, swap home and away and use the away team's home venue. |
| BR-06 | The league has at most two matches per day. One match starts at 19:30; two matches start at 15:30 and 19:30. Every weekend day in an active round window hosts at least one match unless a blackout or unavailable slot makes that impossible, in which case the engine prints an unsatisfied constraint. |
| BR-07 | Win earns 2 points; tie or no-result earns 1 point each; loss earns 0. A forfeit awards the opponent 2 points and 0 margin, counts in head-to-head, and is excluded from NRR. |
| BR-08 | An abandoned match below 50 percent scheduled play is a no-result. A completed match at the result threshold is treated using the supplied result data. |
| BR-09 | Break equal-point groups in order: most wins, head-to-head points in the current subgroup, overall NRR, head-to-head NRR in the current subgroup, fewest forfeits, then lower team ID. |
| BR-10 | Whenever a tie-break step creates multiple buckets, separated buckets retain their order and every still-multiple bucket restarts from step 1. An undivided bucket advances to the next step. |
| BR-11 | Overs use `overs.balls` with legal balls 0-5. An all-out side is treated as having faced its full allotted overs. NRR values are rounded half-up to four decimal places. Forfeits, walkovers, no-results, and cancelled fixtures contribute no NRR. |
| BR-12 | A postponed fixture is rescheduled to the earliest legal date after its round's last scheduled date. A slot must satisfy venue, blackout, daily broadcast, and both teams' rest/travel rules. Fixtures take 15:30 when a day already contains a 19:30 match. |
| BR-13 | If a legal postponement slot is unavailable by the original last round plus three reserve days, cancel the fixture as a no-result. |
| BR-14 | Only fixtures seeded first to fourth qualify. Build Q1 (1 vs 2), Eliminator (3 vs 4), Q2 (Q1 loser vs Eliminator winner), and Final (Q1 winner vs Q2 winner). A tied or no-result playoff goes to the higher league seed. |
| BR-15 | A team's first slow-over-rate offence has no deduction; the second deducts 1 point; every later offence deducts 2. Apply the deduction in the offence round and allow negative totals. |
| BR-16 | Reject a result for an unknown/unscheduled fixture, a date different from the fixture's effective date, a duplicate result, a result entered before the match, or a result against an expunged/cancelled fixture. A rejected command changes no state. |
| BR-17 | If a team withdraws after fewer than 50 percent of its fixtures are completed, expunge its played results and cancel its remaining fixtures. At exactly 50 percent or more, keep its results and award every opponent a 2-point walkover for remaining fixtures. Walkovers count in wins and head-to-head but not NRR. A withdrawn team cannot qualify. |
| BR-18 | Point snapshots use results effective by the target round boundary. Final league output includes results through the three reserve days. Result rows are logged once, and all output columns, sort order, and decimal formats follow the sample contract. |

The code should include the BR identifier beside the function that owns each rule. A rule may appear in a helper and its caller, but its authoritative implementation is marked once.

## State Model

`LeagueEngine` holds:

- teams, venues, distance matrix, blackouts, and season parameters;
- fixtures in stable fixture-ID order;
- loaded result rows and recorded results;
- penalty offences;
- withdrawal events;
- the current round and league-closed flag;
- ordered result-log rows.

Each fixture stores its effective date, start time, venue, original date, result status, and whether it was swapped, cancelled, expunged, or replaced by a walkover. Tables are derived from fixtures, penalties, and withdrawal state instead of being mutated command by command.

## Tie-Break Pseudocode

```text
rank_points_group(group):
    if group has one team: return group
    for step in 1..6:
        calculate metric for teams in group
        make ordered buckets
        if only one bucket: continue
        result = []
        for bucket in ordered buckets:
            if bucket has one team: append it
            else: append rank_points_group(bucket)  # restart at BR-09 step 1
        return result
    return team IDs by BR-09 step 6
```

This recursion is the restart rule. Head-to-head points and head-to-head NRR use only fixtures where both teams are in the current recursive group.

## Command Lifecycle

```text
load CSV data
-> process commands strictly in file order
-> GENERATE_FIXTURES or LOAD_FIXTURES
-> RECORD_RESULT / offence / withdrawal
-> END_ROUND
-> PRINT_TABLE
-> CLOSE_LEAGUE_STAGE
-> PRINT_QUALIFICATION / PRINT_FIXTURES
```

Commands that can be rejected must be transactional: validate first, then update. A bad result or offence must not alter points, fixture status, or table snapshots.

## Interface Notes

- Run with `python main.py T039-PS-093-sample-data/commands.txt`.
- Keep all accepted IDs as strings.
- Emit clear, one-line errors including command line number and category.
- Separate `load CSV data` from `LeagueEngine` state, but keep each small enough for a student to explain.
- Do not add an optimiser until the hard-constraint schedule and evaluator CSV checks pass.

## Presentation Choices

The implementation uses these choices where the sample README is silent:

- normal results use action `RECORDED` and an empty `new_match_date`;
- a successful postponement uses `RESCHEDULED`, while an impossible slot uses `CANCELLED`;
- generated fixtures are written to `generated_fixtures.csv`, and `PRINT_FIXTURES` writes `fixtures.csv`;
- a withdrawn team remains visible in points tables for audit but is excluded from qualification;
- a reserve-day result is accepted after `CLOSE_LEAGUE_STAGE` when its date is on or before the final cutoff, and the final table and qualification file are refreshed.

These messages are created in `commands.py`, so they can be adjusted without changing accounting or scheduling logic.


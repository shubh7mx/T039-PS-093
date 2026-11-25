# Implementation Plan: PS-093 League Competition Engine

## Overview

Build a small command-file driven competition engine in Python 3.10+ using only the standard library. The engine will load the supplied CSV files into memory, process `commands.txt` in order, maintain fixtures and results, and emit deterministic CSV outputs. It needs no database, web server, UI, or third-party package.

The current Git history contains an earlier Python prototype, but those source files are deleted in the working tree. Use that prototype only as a reference. Rebuild the project as a simpler package whose code follows the business-rule IDs in `docs/design.md`.

## Fixed Technical Decisions

- Language: Python 3.10+.
- Dependencies: standard library only (`csv`, `dataclasses`, `datetime`, `decimal`, `unittest`).
- State: one in-memory `LeagueEngine` object.
- Dates: `datetime.date`; no timezone conversion because the sample uses IST timestamps without a zone.
- Money: not used. NRR arithmetic uses `Decimal` and half-up rounding to four decimal places.
- Ordering: every output has an explicit stable sort key so repeated runs are identical.
- Correctness first: earliest feasible scheduling only; travel optimisation is a stretch goal after all hard constraints pass.

## Proposed Layout

```text
main.py               CLI entry point
commands.py           command parser and dispatcher
models.py             small dataclasses and status enums
loaders.py            CSV readers and output writers
scheduler.py          round-robin pairings, date placement, rescheduling
standings.py          points table, tie-breakers, seasons and penalties
playoffs.py           top-four qualification and bracket progression
tests/                focused unit and sample integration tests
docs/design.md        architecture and BR-01 ... BR-18
```

The files stay small enough that each rule can be found by searching its BR number or function name. Avoid base classes, dependency injection, plugin systems, and generic constraint frameworks.

## Data Flow

1. Load teams, venues, distances, blackouts, season settings, results, offences, and fixtures into dictionaries keyed by ID.
2. Reject input that references an unknown team, venue, fixture, or impossible enum value with a clear error.
3. Process command lines strictly from top to bottom and ignore blank/comment lines.
4. Append every `RECORD_RESULT` outcome to the in-memory result log.
5. Recompute tables from current fixture/result state when requested; do not incrementally mutate a permanently ranked table.
6. Write snapshots and reports only after their configured print/close commands.
7. Run `CHECK_FIXTURES` over the freshly generated schedule and print every violation as `UNSATISFIED CONSTRAINT: ...`.

## Scheduler Design

### Pairings

Use the circle method for nine single round-robin rounds and mirror the pairings for rounds 10-18 with home and away reversed. This gives exactly 90 fixtures and one match for every ordered team pair.

### Home/Away Balance

Represent each first-leg round's orientation as a binary choice and derive the second-leg orientation by inversion. Search the small orientation space deterministically and choose the first schedule where every team has at most two consecutive home or away fixtures. A failed search is reported as an unsatisfied constraint.

### Dates and Slots

Place rounds sequentially with a bounded backtracking routine. For each fixture, candidates are ordered by date, time, home venue first, then swapped venue. A candidate is accepted only when all of these hold:

- League and venue availability checks pass.
- The home venue has no other match that day.
- The league has fewer than two matches that day.
- Both teams have enough clear dates, using three only for a trip strictly above 1,500 km.
- A double-header uses 15:30 and 19:30; a single match uses 19:30.

Run a local repair pass for weekend coverage in each round window. If a round has an active weekend day that cannot host a match because of a blackout or lack of a legal slot, print an exact unsatisfied constraint instead of hiding or fabricating it.

### Postponements

Search forward from the earliest date after the fixture's round window and before the original final round plus three reserve days. Preserve fixture orientation. Recheck venue blackout, venue occupancy, daily match limit, both teams' previous/next match gaps, and relevant travel distance. If no slot exists, mark the fixture `CANCELLED` and apply a one-point no-result to each team.

## Table and Tie-Break Design

Snapshots include fixtures whose effective match date, including later reserve-day results, falls within the target round/reserve window. A played result recorded after a round is not counted in that earlier snapshot.

Tie-break algorithm:

1. Split teams into equal-point groups.
2. Sort each group by the six rules in `docs/design.md`.
3. When a rule creates more than one bucket, keep the separated buckets and restart from rule 1 inside each bucket that still has multiple teams.
4. Record the rule that separated a team as `decided_by_step`; leave it empty for a one-team points bucket.

Build head-to-head metrics only from matches where both teams belong to the current tied subgroup. NRR similarly uses only the current subgroup's eligible matches. Keep the subgroup calculation in one helper so the restart rule cannot drift between overall league NRR and head-to-head NRR.

## Withdrawal Design

Count completed results on or before the withdrawal date, including no-results and forfeits but excluding outstanding postponements.

- Fewer than 50 percent: mark existing results/fixtures expunged; cancel the remainder; do not count their points or NRR.
- At least 50 percent: keep results; turn every remaining playable fixture into a two-point walkover for the opponent; exclude walkovers from NRR.
- Keep the withdrawn team identifiable as ineligible for qualification. Walkovers still count for opponents' head-to-head points and wins.

If samples show that a withdrawn row should disappear from a CSV, isolate that presentation choice in the table writer rather than changing accounting logic.

## Output Contract

Required generated files:

- `result_log.csv`
- `points_table_rNN.csv` for every requested `PRINT_TABLE` round
- `qualification.csv`

Use the exact column order in the sample README. Preserve fixture and result IDs as strings. Format dates as `YYYY-MM-DD`, point deductions as non-negative values, and NRR to exactly four decimals with `ROUND_HALF_UP`.

The sample does not yet list a filename for the generated fixture list. Keep the fixture CSV in memory for `CHECK_FIXTURES` and add one clearly named writer only after the evaluator format becomes explicit.

## Test Strategy

Use built-in `unittest`; no test library installation is needed.

- Unit tests: circle pairings, home/away streaks, overs conversion, NRR, each tie-break level, restart behaviour, penalties, withdrawal threshold, result rejection, and playoff advancement.
- Fixture auditing tests: supply deliberately invalid schedules and assert every violation is reported.
- Integration test: process the supplied `commands.txt` end to end and assert row counts, column order, and planted scenario outcomes.
- Regression fixtures: one tiny CSV set per edge case so a failed rule can be diagnosed without running all 118 commands.

## Delivery Order

Work through `tasks/todo.md` in order. Do not start stretch goals until all hard-rule checks, visible snapshots, and the command stream pass.

## Major Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Exact evaluator wording for result actions/reasons is unavailable | CSV text may differ despite correct state | Centralise messages, inspect Week 2 outputs, change one mapping table |
| Future reserve-day results can change the nominal round-18 table | Final qualification may appear early | Model forbidden/after-close results explicitly and write final snapshots at league close |
| Fixture scheduling fails only several rounds later | A local greedy schedule can dead-end | Fail-fast audit plus bounded backtracking; add the planted difficult dates as regression tests |
| Withdrawn-team display is unspecified | Exact table rows may mismatch | Separate accounting from presentation and lock the choice when expected outputs arrive |
| Float rounding changes tie order | Wrong qualifier | Use integer balls and `Decimal` throughout NRR |
| Two campus machines or the evaluator use different launch commands | Demo failure | Provide `python main.py <commands-file>` with no install step |

## Definition of Done

- Generated fixtures pass every hard constraint or list every unsatisfied constraint.
- All supplied commands run without an uncaught exception.
- Round 6, round 12, final tables, result log, and qualification CSV match the evaluator.
- Every business rule has a direct unit or integration test.
- A new rule can be changed in one module without rewriting the parser or output layer.
- `README.md` explains run command, architecture, BR mapping, sample scenario, and viva explanations for tie-break restart and bowled-out NRR.


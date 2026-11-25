# PS-093 Task List

## Phase 1: Foundation

- [x] **Task 1: Confirm sample contract**
  - Description: Load every sample file and record exact schemas, IDs, output names, and command timing.
  - Acceptance criteria: README tables match parsed headers; all command types are listed; ambiguous output choices are recorded in `docs/design.md`.
  - Verification: A short schema audit script or documented manual check reports zero missing required columns.
  - Dependencies: None.
  - Files: `docs/design.md`, `loaders.py`.

- [x] **Task 2: Build models and CSV loaders**
  - Description: Add plain dataclasses/enums and strict standard-library CSV readers for all sample inputs.
  - Acceptance criteria: Unknown IDs and malformed enums fail with file/row context; valid sample data loads into stable dictionaries.
  - Verification: Unit tests load the full sample directory and assert team, venue, fixture, result, and offence counts.
  - Dependencies: Task 1.
  - Files: `models.py`, `loaders.py`, `tests/test_loaders.py`.

- [x] **Task 3: Build command runner and result log**
  - Description: Dispatch all documented commands in file order and append each result decision.
  - Acceptance criteria: Comments/blank lines ignored; one log row per `RECORD_RESULT`; state changes happen only after successful validation.
  - Verification: A command-stream test confirms ordering, log row count, and clean failure messages.
  - Dependencies: Task 2.
  - Files: `main.py`, `commands.py`, `models.py`, `loaders.py`, `tests/test_commands.py`.

## Checkpoint A

- [x] Sample data loads and all command names dispatch.
- [x] `python -m unittest` passes the foundation tests.

## Phase 2: Scheduling

- [x] **Task 4: Generate double round-robin pairings**
  - Description: Implement circle-method pairings and deterministic home/away orientation.
  - Acceptance criteria: 90 unique ordered pairings, 18 rounds, five fixtures per round, and no home/away streak above two.
  - Verification: Unit test checks count, symmetry, and every team's sequence.
  - Dependencies: Task 2.
  - Files: `scheduler.py`, `tests/test_schedule.py`.

- [x] **Task 5: Place fixtures under hard constraints**
  - Description: Assign dates, venues, and slots with the rest, travel, blackout, venue capacity, and broadcast rules.
  - Acceptance criteria: Hard constraints pass where a slot exists; impossible weekend/blackout cases produce explicit unsatisfied messages.
  - Verification: Focused tests cover exact 1,500 km, two-city blackout, single weekend blackout, and a two-match day.
  - Dependencies: Task 4.
  - Files: `scheduler.py`, `tests/test_schedule.py`.

- [x] **Task 6: Audit and reschedule**
  - Description: Implement `CHECK_FIXTURES` and postponed-match forward search through three reserve days.
  - Acceptance criteria: Checker independently catches every hard-rule violation; impossible postponements become no-results.
  - Verification: Invalid fixture fixtures fail for one violation each; planted FX-011 scenario lands on the earliest legal date.
  - Dependencies: Task 5.
  - Files: `scheduler.py`, `models.py`, `tests/test_reschedule.py`.

## Checkpoint B

- [x] Generated fixture set passes `CHECK_FIXTURES`.
- [x] All scheduling edge cases are covered by focused tests.

## Phase 3: Competition State

- [x] **Task 7: Record and validate results**
  - Description: Apply PLAYED, ABANDONED, FORFEIT, and POSTPONED results with all rejection rules.
  - Acceptance criteria: Wrong dates, future entries, duplicates, cancelled/expunged fixtures, and unknown IDs are rejected without state changes.
  - Verification: The two invalid sample rows are rejected and valid rows produce the required actions.
  - Dependencies: Task 6.
  - Files: `commands.py`, `models.py`, `tests/test_results.py`.

- [x] **Task 8: Build points table and tie-breakers**
  - Description: Implement the six-level chain, subgroup restart, NRR, and slow-over deductions.
  - Acceptance criteria: Full chain is tested; bowled-out 14.3 becomes 20 overs; forfeits affect head-to-head but not NRR; penalties may make points negative.
  - Verification: Unit tests reproduce all planted tie and NRR cases; round snapshots use the correct date window.
  - Dependencies: Task 7.
  - Files: `standings.py`, `tests/test_standings.py`.

- [x] **Task 9: Implement withdrawal and league closure**
  - Description: Apply below-50-percent expunging, at-least-50-percent walkovers, reserve-day handling, and final table creation.
  - Acceptance criteria: Exactly 50 percent keeps results; withdrawn teams cannot qualify; walkovers count in win/head-to-head and not NRR.
  - Verification: Sample T10 scenario and a below-50 percent scenario both pass.
  - Dependencies: Task 8.
  - Files: `commands.py`, `standings.py`, `tests/test_withdrawal.py`.

## Checkpoint C

- [x] All result and accounting unit tests pass.
- [x] Supplied round snapshots can be generated without manual updates.

## Phase 4: Qualification and Outputs

- [x] **Task 10: Build qualification and playoff bracket**
  - Description: Qualify top four, create Q1/Eliminator/Q2/Final, and resolve ties by league seed.
  - Acceptance criteria: Bracket progression works from Q1 and Eliminator through Q2 to Final; final-round penalty changes the qualifier.
  - Verification: Dedicated bracket tests and sample integration test pass.
  - Dependencies: Tasks 8-9.
  - Files: `playoffs.py`, `tests/test_playoffs.py`.

- [x] **Task 11: Write exact CSV outputs**
  - Description: Write result log, requested round tables, qualification report, and any confirmed fixture output.
  - Acceptance criteria: Headers, row order, decimal formatting, and names match sample/evaluator contract.
  - Verification: Compare file text/rows against the first visible expected outputs; no environment-specific paths inside files.
  - Dependencies: Tasks 3, 9, 10.
  - Files: `loaders.py`, `commands.py`, `tests/test_outputs.py`.

- [x] **Task 12: Run the complete sample and document viva**
  - Description: Add README run instructions, BR-to-code map, architecture summary, and explanations required in viva.
  - Acceptance criteria: Fresh checkout runs with no install; all planted scenarios are documented; restart semantics and bowled-out NRR are explained with examples.
  - Verification: Run full sample, all tests, and a clean-directory smoke test.
  - Dependencies: Tasks 1-11.
  - Files: `README.md`, `docs/design.md`.

## Final Checkpoint

- [x] Full command stream finishes without manual intervention.
- [x] Hard constraints and required CSV outputs pass.
- [x] BR-01 through BR-18 each map to code and a test.
- [x] Optional stretch goal remains unstarted until this checkpoint passes.



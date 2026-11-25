# PS-093 League Competition Engine

A small command-file driven engine for double round-robin fixtures, results, points tables, tie-breakers, postponements, withdrawals, and playoffs. It uses Python 3.10+ and the standard library only.

## Team Information

| Team ID | Member 1 | Member 2 | Section |
|---|---|---|---|
| T039 | SHUBHAM KUMAR SINGH – 1AT24CD079 | SIDHANT RAJESH BIRADAR – 1AT24CD080 | CSDS B |

## Run

```powershell
python main.py T039-PS-093-sample-data/commands.txt T039-PS-093-sample-data
```

Optional third argument: output directory.

```powershell
python main.py T039-PS-093-sample-data/commands.txt T039-PS-093-sample-data output
```

Run the tests:

```powershell
python -m unittest discover -v
```

The terminal prints the complete requested output: scheduling warnings, processing totals, round 6/12/18 tables, qualification and bracket, and all 90 fixtures. Detailed command history remains available in `result_log.csv`.

## Files

| File | Responsibility |
|---|---|
| `main.py` | CLI entry point |
| `console.py` | Formats the complete terminal report |
| `commands.py` | Processes commands in file order and owns league state |
| `loaders.py` | Reads sample CSVs and writes output CSVs |
| `models.py` | Small dataclasses and status enums |
| `scheduler.py` | Round-robin generation, constraint checks, and postponements |
| `standings.py` | Points, NRR, penalties, and tie-breakers |
| `playoffs.py` | Top-four qualification and playoff progression |
| `docs/design.md` | Business rules BR-01 through BR-18 |
| `docs/T039_PS-093_Design_Document.pdf` | Final submission design document |
| `scripts/generate_design_pdf.py` | Reproducible PDF report generator |

## Explainer Video

A five-minute 1080p project walkthrough is produced with Explainroo. Its narration, scene descriptions, and visual scenes are stored in `videos/capstone-explainer/`.

Regenerate or preview the video with:

```powershell
npx --yes explainroo check videos/capstone-explainer
npx --yes explainroo render videos/capstone-explainer
npx --yes explainroo verify videos/capstone-explainer
```

The generated video, subtitles, chapters, contact sheet, and cover image are written to `videos/capstone-explainer/out/`. Generated media is ignored by Git.

## Outputs

Running the supplied command file creates:

- `result_log.csv`
- `points_table_r06.csv`
- `points_table_r12.csv`
- `points_table_r18.csv`
- `qualification.csv`
- `generated_fixtures.csv`
- `fixtures.csv`

The required evaluation files use the headers and order defined in the sample README. NRR is written with exactly four decimal places.

Generated output files are intentionally ignored by Git. Recreate them from the sample command file whenever needed instead of editing or committing result CSVs directly. Python cache files and local output directories are ignored as well.

## How It Works

1. CSV input is loaded into dictionaries keyed by fixture, team, venue, result, and offence IDs.
2. The command runner processes comments, commands, and result IDs from top to bottom.
3. Fixtures are generated with the circle method. A small orientation search limits home/away streaks.
4. A bounded backtracking routine chooses legal dates and venues. It checks rest days, long travel, blackouts, venue use, and broadcast slots.
5. Standings are recomputed from current fixture state whenever requested.
6. Postponements search forward only through the three reserve days.
7. `CLOSE_LEAGUE_STAGE` builds the bracket. Later reserve-day results refresh the final table and qualification file.

## Tie-Break Restart

Teams are first grouped by points. Each tied group applies:

1. Most wins
2. Head-to-head points inside the current group
3. Overall NRR
4. Head-to-head NRR inside the current group
5. Fewest forfeits
6. Lower team ID

If one rule separates a team but leaves two or more other teams tied, those remaining teams restart at rule 1. Head-to-head calculations also shrink to that smaller group. This is why head-to-head is recalculated instead of reusing the original three-team totals. `_rank_group` in `standings.py` is the direct implementation.

## Net Run Rate

Text such as `14.3` means 14 overs and 3 balls. Internally it becomes `14 * 6 + 3 = 87` legal balls. The run rate is `runs * 6 / balls`.

If a team is all out, its overs are replaced by the full innings allocation. For example, a team all out for 120 in 14.3 of 20 overs is treated as having faced 120 balls for NRR. The opponent is treated as having bowled those same 120 balls.

NRR uses `Decimal` and half-up rounding to four decimal places. Forfeits, walkovers, no-results, and cancelled matches have no NRR contribution.

## Withdrawal

The completed-fixture count includes results recorded on or before the withdrawal date. Exactly 50 percent counts as enough to keep results. Below 50 percent expunges the team's played results and cancels all its fixtures. At 50 percent or more, remaining fixtures become two-point walkovers for the opponents. A withdrawn team remains in the table for audit purposes but is excluded from qualification.

## Supplied Edge Cases

The sample integration test covers:

- the three-way tie that restarts the chain;
- the 14.3-over all-out NRR rule;
- the postponed fixture involving an exact 1,500 km trip;
- forfeit treatment in head-to-head and NRR;
- withdrawal after exactly 50 percent;
- duplicate and wrong-date result rejection;
- the final-round penalty changing the qualifier;
- all four postponements landing on their expected reserve dates.

The blackout and same-city behaviour are checked by focused unit tests in `tests/`.

## Assumptions Fixed From the Sample Contract

- A single match uses 19:30; a double-header uses 15:30 and 19:30.
- A trip strictly above 1,500 km needs three clear dates. Exactly 1,500 km needs two.
- The points-table `no_result` column includes ties and no-results because the required output has no separate tie column.
- Normal results leave `new_match_date` empty in `result_log.csv`; postponed matches show their new date.
- Withdrawn teams remain visible in the points table and are excluded from the top four used for qualification.

## Stretch Goal

Fixture travel optimisation is intentionally separate from the hard-constraint scheduler. Add it only after the sample and hidden result checks pass.


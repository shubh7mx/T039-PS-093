"""Generate the final PS-093 design document PDF."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "T039_PS-093_Design_Document.pdf"

NAVY = colors.HexColor("#17324D")
TEAL = colors.HexColor("#0E7490")
SKY = colors.HexColor("#E8F3F6")
PALE = colors.HexColor("#F4F6F8")
MID = colors.HexColor("#64748B")
GREEN = colors.HexColor("#166534")
AMBER = colors.HexColor("#92400E")


styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        name="CoverTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=23,
        leading=27,
        textColor=colors.white,
        alignment=TA_LEFT,
        spaceAfter=8,
    )
)
styles.add(
    ParagraphStyle(
        name="CoverSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=12,
        leading=17,
        textColor=colors.HexColor("#D9EEF3"),
    )
)
styles.add(
    ParagraphStyle(
        name="H1Custom",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=21,
        textColor=NAVY,
        spaceBefore=10,
        spaceAfter=8,
        keepWithNext=True,
    )
)
styles.add(
    ParagraphStyle(
        name="H2Custom",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11.5,
        leading=15,
        textColor=TEAL,
        spaceBefore=9,
        spaceAfter=5,
        keepWithNext=True,
    )
)
styles.add(
    ParagraphStyle(
        name="BodyCustom",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.1,
        leading=13,
        textColor=colors.HexColor("#1F2937"),
        spaceAfter=5,
    )
)
styles.add(
    ParagraphStyle(
        name="SmallCustom",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor("#475569"),
    )
)
styles.add(
    ParagraphStyle(
        name="BulletCustom",
        parent=styles["BodyCustom"],
        leftIndent=12,
        firstLineIndent=-7,
        bulletIndent=3,
        spaceAfter=3,
    )
)
styles.add(
    ParagraphStyle(
        name="CodeCustom",
        parent=styles["Code"],
        fontName="Courier",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#0F172A"),
        backColor=PALE,
        borderColor=colors.HexColor("#D7DEE7"),
        borderWidth=0.5,
        borderPadding=6,
        leftIndent=6,
        rightIndent=6,
        spaceBefore=4,
        spaceAfter=7,
    )
)


def paragraph(text: str, style: str = "BodyCustom") -> Paragraph:
    return Paragraph(text, styles[style])


def bullet(text: str) -> Paragraph:
    return Paragraph(text, styles["BulletCustom"], bulletText="-")


def section(number: str, title: str) -> Paragraph:
    return Paragraph(f"{number}. {title}", styles["H1Custom"])


def subsection(title: str) -> Paragraph:
    return Paragraph(title, styles["H2Custom"])


def data_table(
    rows: list[list[object]],
    widths: list[float],
    header: bool = True,
    font_size: float = 8.2,
) -> Table:
    converted: list[list[object]] = []
    for row_index, row in enumerate(rows):
        converted_row: list[object] = []
        for cell in row:
            if isinstance(cell, Paragraph):
                converted_row.append(cell)
            else:
                style = ParagraphStyle(
                    name=f"Cell{row_index}",
                    parent=styles["SmallCustom"],
                    fontName="Helvetica-Bold" if header and row_index == 0 else "Helvetica",
                    fontSize=font_size,
                    leading=font_size + 2,
                    textColor=colors.white if header and row_index == 0 else colors.HexColor("#1F2937"),
                )
                converted_row.append(Paragraph(str(cell), style))
        converted.append(converted_row)
    table = Table(converted, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D7DEE7")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]
    if header:
        commands.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ]
        )
    table.setStyle(TableStyle(commands))
    return table


def callout(title: str, text: str, colour: colors.Color = SKY) -> Table:
    inner = paragraph(text)
    table = Table(
        [[paragraph(f"<b>{title}</b>", "BodyCustom")], [inner]],
        colWidths=[164 * mm],
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colour),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#B8DCE5")),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def page_decorator(canvas, doc) -> None:
    page = canvas.getPageNumber()
    width, height = A4
    canvas.saveState()
    if page > 1:
        canvas.setStrokeColor(colors.HexColor("#D7DEE7"))
        canvas.setLineWidth(0.5)
        canvas.line(20 * mm, height - 16 * mm, width - 20 * mm, height - 16 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MID)
        canvas.drawString(20 * mm, height - 12.5 * mm, "PS-093  |  League Competition Engine")
        canvas.drawRightString(width - 20 * mm, height - 12.5 * mm, "T039")
    canvas.setStrokeColor(colors.HexColor("#D7DEE7"))
    canvas.line(20 * mm, 14 * mm, width - 20 * mm, 14 * mm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MID)
    canvas.drawString(20 * mm, 9 * mm, "Design Document  |  CSDS B")
    canvas.drawRightString(width - 20 * mm, 9 * mm, f"Page {page}")
    canvas.restoreState()


def build_story() -> list[object]:
    story: list[object] = []

    cover = Table(
        [
            [paragraph("PS-093", "CoverSubtitle")],
            [paragraph("League Fixture Scheduling<br/>and Points Table<br/>with Tie-Breakers", "CoverTitle")],
            [paragraph("Design Document", "CoverSubtitle")],
        ],
        colWidths=[164 * mm],
        rowHeights=[12 * mm, 38 * mm, 10 * mm],
        hAlign="LEFT",
    )
    cover.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("LEFTPADDING", (0, 0), (-1, -1), 13 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 13 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 7 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7 * mm),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.extend(
        [
            Spacer(1, 38 * mm),
            cover,
            Spacer(1, 18 * mm),
            paragraph("Command-file driven competition engine for a 10-team double round-robin season.", "H2Custom"),
            Spacer(1, 7 * mm),
            data_table(
                [
                    ["Team ID", "T039"],
                    ["Section", "CSDS B"],
                    ["Member 1", "SHUBHAM KUMAR SINGH - 1AT24CD079"],
                    ["Member 2", "SIDHANT RAJESH BIRADAR - 1AT24CD080"],
                    ["Language", "Python 3.10+"],
                    ["Document status", "Final"],
                    ["Date", date.today().isoformat()],
                ],
                [45 * mm, 119 * mm],
                header=False,
                font_size=9,
            ),
            Spacer(1, 25 * mm),
            callout(
                "Project statement",
                "Generate and validate a constrained fixture list, record match outcomes, compute a full points table with restarting tie-breakers, reschedule postponed matches, and determine playoff qualification and seeding.",
            ),
            PageBreak(),
        ]
    )

    story.extend(
        [
            section("1", "Executive Summary"),
            paragraph(
                "The PS-093 League Competition Engine is a command-file driven application that models a complete cricket league season. "
                "It loads teams, venues, travel distances, blackout dates, season settings, fixtures, results, and over-rate offences from CSV files. "
                "The engine then processes an ordered command stream and writes deterministic reports for matching, standings, qualification, and scheduling validation."
            ),
            paragraph(
                "The implementation uses only Python 3.10+ and the standard library. The code is divided by responsibility so that scheduling, result accounting, tie-breaking, playoff progression, CSV I/O, and command handling remain easy to inspect and modify during evaluation."
            ),
            subsection("1.1 Design Objectives"),
            bullet("Correctly implement every hard scheduling, result, table, and qualification rule."),
            bullet("Make hidden-business-rule changes possible in one clearly identified module."),
            bullet("Keep player-facing output readable while preserving exact CSV field formats."),
            bullet("Provide a test suite that can reproduce each planted sample scenario without manual inspection."),
            subsection("1.2 Document Map"),
            data_table(
                [
                    ["Section", "Purpose"],
                    ["2-3", "Scope, architecture, and command lifecycle"],
                    ["4-6", "Scheduling, NRR, tie-breakers, and state transitions"],
                    ["7", "Formal business-rule register BR-01 to BR-18"],
                    ["8-9", "Edge-case traceability and test strategy"],
                    ["10-11", "Viva explanation, assumptions, and limitations"],
                ],
                [30 * mm, 134 * mm],
            ),
            section("2", "Problem Scope and Requirements"),
            paragraph(
                "The system represents a 10-team league. Each unordered pair of teams meets twice, once at each team's home city, producing 90 fixtures across 18 rounds. "
                "Every round contains five fixtures. The scheduler must respect venue availability, at most one fixture per venue per day, league-wide blackouts, rest periods, long-travel rest, daily broadcast limits, and start-time rules."
            ),
            subsection("2.1 In Scope"),
            data_table(
                [
                    ["Area", "Included capability"],
                    ["Registration", "Teams, home venues, cities, venue capacity, availability, season start, blackout dates, distance matrix"],
                    ["Scheduling", "Circle-method double round robin, home/away streak control, constraint-aware date and slot placement"],
                    ["Results", "PLAYED, ABANDONED, FORFEIT, and POSTPONED results with validation and transactional rejection"],
                    ["Standings", "Points, wins, losses, no-results, forfeits, penalties, NRR, six-level tie-break chain"],
                    ["Season events", "Postponement rescheduling, withdrawal, expunging, walkovers, over-rate deductions"],
                    ["Playoffs", "Top-four qualification, Q1, Eliminator, Q2, Final, and higher-seed tie resolution"],
                    ["Outputs", "Fixture CSV, result log, requested round tables, qualification CSV, and full terminal report"],
                ],
                [30 * mm, 134 * mm],
            ),
            subsection("2.2 Out of Scope"),
            paragraph(
                "A graphical interface, database, network service, payment system, and external sports-data integration are outside the capstone scope. "
                "Travel minimisation and fan-attendance forecasting remain optional stretch goals and are not part of the correctness path."
            ),
            PageBreak(),
        ]
    )

    story.extend(
        [
            section("3", "Architecture and Code Map"),
            paragraph(
                "The architecture is intentionally small. The CSV loaders create in-memory dictionaries, the command dispatcher applies state changes, and pure calculation helpers derive standings and reports. "
                "No database is required because the largest sample contains only 90 fixtures and 87 result commands."
            ),
            data_table(
                [
                    ["Module", "Responsibility", "Key concern"],
                    ["main.py", "CLI entry, argument parsing, friendly errors", "No league calculations"],
                    ["commands.py", "Sequential command processor and LeagueEngine state", "Transactions and orchestration"],
                    ["loaders.py", "CSV input/output mapping", "Stable field names and formats"],
                    ["models.py", "Dataclasses and match-status enum", "Readable in-memory model"],
                    ["scheduler.py", "Pairings, placement, audit, postponement search", "Hard constraints"],
                    ["standings.py", "Points, penalties, NRR, recursive tie-breakers", "Season calculations"],
                    ["playoffs.py", "Qualification seeds and bracket advancement", "Playoff flow"],
                    ["console.py", "Complete human-readable report", "Presentation only"],
                ],
                [29 * mm, 88 * mm, 47 * mm],
            ),
            Spacer(1, 7 * mm),
            subsection("3.1 Processing Flow"),
            data_table(
                [
                    ["Input CSV files", "LeagueEngine state", "Ordered command file", "CSV and console reports"],
                    ["Teams, venues, distances, blackouts, results", "Validated in-memory fixtures and events", "Fixture generation, results, penalties, withdrawal", "Exact artifacts plus readable terminal output"],
                ],
                [38 * mm, 42 * mm, 43 * mm, 41 * mm],
                header=True,
                font_size=7.8,
            ),
            subsection("3.2 Architectural Principles"),
            bullet("Validate before mutate: a rejected command leaves fixtures, points, and snapshots unchanged."),
            bullet("Derive, do not duplicate: standings are recalculated from fixture state rather than incrementally patched."),
            bullet("Use stable ordering: fixture IDs, team IDs, round numbers, and date-time keys make runs reproducible."),
            bullet("Separate presentation from accounting: console formatting cannot alter CSV result values."),
            callout(
                "Why the design stays simple",
                "The expected league size is fixed at 10 teams. A small search space, deterministic tie-breaks, and in-memory state produce clearer code than a generic constraint solver or database-backed system.",
            ),
            section("4", "Command Lifecycle and State Model"),
            paragraph(
                "Commands are read strictly in file order. Blank lines and comments are ignored. Each operation updates a single LeagueEngine object and may write an output snapshot."
            ),
            Paragraph(
                "load CSV data -> GENERATE_FIXTURES or LOAD_FIXTURES<br/>"
                "-> RECORD_RESULT / OVER_RATE_OFFENCE / WITHDRAW_TEAM<br/>"
                "-> END_ROUND -> PRINT_TABLE -> CLOSE_LEAGUE_STAGE<br/>"
                "-> PRINT_QUALIFICATION / PRINT_FIXTURES",
                styles["CodeCustom"],
            ),
            data_table(
                [
                    ["State group", "Stored values"],
                    ["League configuration", "Teams, venues, cities, capacities, blackouts, distances, season limits"],
                    ["Fixture state", "Fixture ID, round, effective date, time, venue, teams, status, result, original date"],
                    ["Season events", "Penalties, withdrawals, expunged fixtures, walkovers, result-log actions"],
                    ["Reporting state", "Requested table snapshots, final table, bracket, closed flag"],
                ],
                [34 * mm, 130 * mm],
            ),
            PageBreak(),
        ]
    )

    story.extend(
        [
            section("5", "Fixture Scheduling Design"),
            subsection("5.1 Circle-Method Pairings"),
            paragraph(
                "Ten teams are arranged with one fixed team and nine rotating positions. Nine first-leg rounds pair every team with every other team exactly once. "
                "The second leg repeats the same pairings with home and away inverted. The result is 18 rounds and 90 ordered fixtures."
            ),
            subsection("5.2 Home/Away Pattern"),
            paragraph(
                "Each first-leg round has a binary orientation. The engine searches these small orientation combinations and mirrors the result in the second leg. "
                "It selects the first deterministic orientation in which no team has more than two consecutive home or away fixtures."
            ),
            subsection("5.3 Constraint-Aware Date Placement"),
            paragraph(
                "Each round is placed sequentially using bounded backtracking. Candidate dates and venues are rejected unless all parties remain legal."
            ),
            data_table(
                [
                    ["Check", "Implementation"],
                    ["League/venue blackout", "Venue availability plus league-wide blackout set"],
                    ["Venue use", "At most one fixture at a venue on a date"],
                    ["League daily limit", "At most two fixtures on a date"],
                    ["Rest", "At least two clear dates between team matches"],
                    ["Long travel", "At least three clear dates for a trip strictly above 1,500 km"],
                    ["Broadcast", "Single match at 19:30; double-header at 15:30 and 19:30"],
                    ["Weekend coverage", "Flag a round window only when its active weekend has no fixture"],
                ],
                [39 * mm, 125 * mm],
            ),
            subsection("5.4 Blackout Swap"),
            paragraph(
                "If the home venue cannot provide a legal slot within four days, the away team becomes home and the away venue is used. "
                "The scheduler still rechecks rest, travel, venue use, daily limits, and broadcast slots after the swap."
            ),
            section("6", "Results, Tables, NRR, and Tie-Breakers"),
            subsection("6.1 Result Validation"),
            paragraph(
                "A result is accepted only when its fixture exists, its submitted date equals the effective fixture date, and no earlier result has closed the fixture. "
                "The implementation validates the full row before changing tournament state."
            ),
            subsection("6.2 Points Table Recalculation"),
            paragraph(
                "A PRINT_TABLE command derives a new table from fixtures effective by the requested round boundary. "
                "Points are grouped first; ties are resolved with the recursive chain below. This avoids stale incremental updates when a result is rejected, rescheduled, or expunged."
            ),
            subsection("6.3 Tie-Break Chain and Restart Semantics"),
            Paragraph(
                "rank_points_group(group):<br/>"
                "&nbsp;&nbsp;if group has one team: return group<br/>"
                "&nbsp;&nbsp;for step in 1..6:<br/>"
                "&nbsp;&nbsp;&nbsp;&nbsp;calculate step metric within the current group<br/>"
                "&nbsp;&nbsp;&nbsp;&nbsp;if one bucket: continue to next step<br/>"
                "&nbsp;&nbsp;&nbsp;&nbsp;for each ordered bucket:<br/>"
                "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;single team: keep order<br/>"
                "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;multiple teams: restart at step 1",
                styles["CodeCustom"],
            ),
            callout(
                "Critical interpretation",
                "Head-to-head values are not frozen after the first separation. A subgroup created by any step recalculates head-to-head points and head-to-head NRR using only matches between teams that remain tied.",
            ),
            subsection("6.4 Net Run Rate"),
            paragraph(
                "Overs notation is converted to legal balls: 12.4 becomes 12 * 6 + 4 = 76 balls. Team NRR is the difference between runs per over scored and runs per over conceded, rounded half-up to four decimal places."
            ),
            paragraph(
                "A side dismissed for 10 wickets is treated as having used its full innings allocation. Thus 120 all out in 14.3 of 20 overs contributes 120 runs from 120 balls. "
                "Forfeits, walkovers, no-results, and cancelled matches contribute zero NRR."
            ),
            PageBreak(),
        ]
    )

    story.extend(
        [
            section("7", "Postponements, Withdrawal, Penalties, and Playoffs"),
            subsection("7.1 Postponed Matches"),
            paragraph(
                "The engine searches forward from the day after the fixture's round window. A slot is accepted only when the venue is available, the day has fewer than two league fixtures, and both teams retain their required rest before and after the new date. "
                "The search stops after the original final round plus three reserve days. Failure produces a cancelled no-result fixture."
            ),
            subsection("7.2 Mid-Season Withdrawal"),
            data_table(
                [
                    ["Completed fixtures", "State transition"],
                    ["Less than 50 percent", "Expunge played results; cancel all remaining fixtures; remove points and NRR contribution"],
                    ["Exactly 50 percent or more", "Keep played results; convert remaining fixtures to two-point opponent walkovers"],
                    ["Qualification", "Withdrawn team remains visible for audit but is excluded from the top-four seeds"],
                ],
                [47 * mm, 117 * mm],
            ),
            subsection("7.3 Slow-Over-Rate Penalties"),
            paragraph(
                "The first team offence has no deduction. The second deducts one point and every later offence deducts two. "
                "Each deduction is recorded in the offence's fixture round and can reduce the total below zero."
            ),
            subsection("7.4 Qualification and Playoff Bracket"),
            data_table(
                [
                    ["Match", "Participants", "Progression"],
                    ["Qualifier 1", "League seeds 1 and 2", "Winner to Final; loser to Qualifier 2"],
                    ["Eliminator", "League seeds 3 and 4", "Winner to Qualifier 2; loser eliminated"],
                    ["Qualifier 2", "Q1 loser and Eliminator winner", "Winner to Final"],
                    ["Final", "Q1 winner and Q2 winner", "Champion"],
                ],
                [33 * mm, 59 * mm, 72 * mm],
            ),
            paragraph(
                "A tied or no-result playoff is resolved in favour of the participant with the higher league seed. The seed remains attached while teams move through the bracket."
            ),
            section("8", "Business Rules BR-01 to BR-18"),
            data_table(
                [
                    ["ID", "Business rule"],
                    ["BR-01", "Use the circle method for 90 double round-robin fixtures in 18 rounds; each pair plays once at each home venue."],
                    ["BR-02", "A team never has more than two consecutive home or two consecutive away fixtures."],
                    ["BR-03", "Require two clear dates between matches; require three when travel is strictly above 1,500 km."],
                    ["BR-04", "A venue hosts at most one match per day and must be available; league blackouts affect all venues."],
                    ["BR-05", "For an unavailable home slot, search the next legal date; swap home and away when none exists within four days."],
                    ["BR-06", "Allow at most two matches per day with 15:30 and 19:30 slots; report a weekend window that cannot be covered."],
                    ["BR-07", "Win = 2, tie/no-result = 1 each, loss = 0; forfeit awards 2 points and counts in head-to-head only."],
                    ["BR-08", "Abandonment below 50 percent is a no-result; at or above the result threshold, supplied score data determines the outcome."],
                    ["BR-09", "Tie-break order: wins, group head-to-head points, overall NRR, group head-to-head NRR, fewest forfeits, lower team ID."],
                    ["BR-10", "On any split, keep separated buckets and restart the full chain inside every remaining multi-team bucket."],
                    ["BR-11", "Convert overs to balls; treat all-out sides as using full overs; round NRR half-up to four decimals; exclude forfeits and no-results."],
                    ["BR-12", "Reschedule a postponed fixture to the earliest legal slot after its round, checking venue, blackout, broadcast, rest, and travel."],
                    ["BR-13", "Cancel a postponed fixture as no-result when no slot exists before the final round plus three reserve days."],
                    ["BR-14", "Build Q1, Eliminator, Q2, and Final from the top four; playoff ties go to the higher league seed."],
                    ["BR-15", "First slow-over offence = 0; second = -1; later = -2; deductions apply in the offence round and may make points negative."],
                    ["BR-16", "Reject unknown, wrong-date, early, duplicate, cancelled, or expunged results without changing state."],
                    ["BR-17", "Below 50 percent, expunge and cancel; at 50 percent or more, keep results and award remaining fixtures as opponent walkovers."],
                    ["BR-18", "Use round-effective result dates for snapshots, include reserve days in the final table, and preserve exact output columns and formats."],
                ],
                [15 * mm, 149 * mm],
                font_size=7.7,
            ),
            PageBreak(),
        ]
    )

    story.extend(
        [
            section("9", "Edge-Case Traceability"),
            data_table(
                [
                    ["Edge case", "Expected behavior", "Primary verification"],
                    ["Three teams level on points and wins", "Highest head-to-head team separates; remaining two restart at step 1", "test_three_way_tie_restarts_remaining_group"],
                    ["All out in 14.3 of 20", "Use 20 overs, or 120 balls, for NRR", "test_overs_and_bowled_out_nrr"],
                    ["Blackout on only weekend day", "Print unsatisfied constraint instead of silently violating it", "test_blackouts_on_both_weekend_days_are_reported"],
                    ["Postponement trip exactly 1,500 km", "Apply normal two-clear-day rule and find the expected reserve-date slot", "Sample postponement tests"],
                    ["Second offence in final round", "Deduct one point and recompute qualification", "test_final_penalty_and_late_results_change_qualification"],
                    ["Forfeit in head-to-head", "Count two points for head-to-head; exclude match from NRR", "Forfeit unit and sample tests"],
                    ["Withdrawal at exactly 50 percent", "Keep results and award nine remaining fixtures as walkovers", "test_exactly_half_withdrawal_keeps_results_and_awards_walkovers"],
                    ["Two venues in one city blacked out", "Constraint-aware placement moves to another legal date or swaps venue", "Sample schedule audit"],
                    ["Duplicate or pre-date result", "Return REJECTED and preserve all state", "RS-027, RS-051, transactional result test"],
                ],
                [49 * mm, 70 * mm, 45 * mm],
                font_size=7.6,
            ),
            section("10", "Test Strategy and Verification"),
            paragraph(
                "The test suite uses Python's built-in unittest framework, so no package installation is required. It combines focused unit tests with one end-to-end sample run."
            ),
            data_table(
                [
                    ["Test layer", "Coverage"],
                    ["Pairings", "18 rounds, five matches per round, 90 ordered pairs, home/away streak limit"],
                    ["Scheduling", "Exact 1,500 km threshold, unavailable-weekend reporting, generated-round constraint audit"],
                    ["Results", "Wrong-date rejection without mutation, duplicate rejection, valid application"],
                    ["Standings", "No-result points, negative penalty total, forfeit/NRR exclusion, bowled-out NRR"],
                    ["Season events", "Below-50 expunging, exactly-50 walkovers, four expected postponement dates"],
                    ["Playoffs", "Three-way tie restart, final-round qualification change, bracket progression, higher-seed tie"],
                    ["Integration", "All 87 sample result commands, output row counts, complete console report"],
                ],
                [39 * mm, 125 * mm],
            ),
            callout(
                "Current verification result",
                "python -m unittest discover runs 20 tests successfully. The supplied command stream completes and emits the required fixture, result, table, and qualification artifacts.",
                colors.HexColor("#ECFDF3"),
            ),
            PageBreak(),
        ]
    )

    story.extend(
        [
            section("11", "Viva Explanations"),
            subsection("11.1 Why the Tie-Break Chain Restarts"),
            paragraph(
                "Suppose three teams have equal points and wins. Head-to-head points separate one team, leaving two teams tied. "
                "The original three-team head-to-head totals are no longer relevant because one participant has left the tie group. "
                "The remaining two teams restart at most wins and then recalculate head-to-head points using only matches between those two teams. This subgroup-local calculation is the key restart semantics."
            ),
            subsection("11.2 Why a Bowled-Out Team Uses Full Overs"),
            paragraph(
                "NRR measures scoring rate. A team that is all out has lost all ten wickets, so it cannot claim an improved rate merely because it survived fewer overs. "
                "The side is treated as if it faced the full allowance. In the sample, 120 all out in 14.3 of 20 is represented as 120 runs from 120 balls, not 87 balls."
            ),
            subsection("11.3 Why Results Are Recalculated"),
            paragraph(
                "A result row may be rejected, a postponed fixture may move, and a withdrawal may expunge previous matches. Rebuilding a requested table from current fixture state prevents stale totals and makes the snapshot rule auditable."
            ),
            section("12", "Assumptions, Limitations, and Future Work"),
            subsection("12.1 Fixed Assumptions"),
            bullet("The supplied league has ten teams and ninety fixtures."),
            bullet("All timestamps are interpreted as local Indian Standard Time without timezone conversion."),
            bullet("A single match starts at 19:30; a double-header uses 15:30 and 19:30."),
            bullet("Exactly 1,500 km uses the normal rest threshold; three clear days apply only above 1,500 km."),
            bullet("Withdrawn teams remain visible in the points table but are excluded from qualification."),
            subsection("12.2 Known Limitations"),
            bullet("Fixture generation prioritises constraint correctness and deterministic placement rather than minimum total travel."),
            bullet("Venue capacity is registered but does not restrict match feasibility because the stated hard rules do not provide a capacity threshold."),
            bullet("The command file is the user interface; there is no interactive or graphical layer."),
            subsection("12.3 Optional Extensions"),
            bullet("Optimise fixture assignment to reduce total travel distance."),
            bullet("Forecast attendance and prefer high-demand fixtures for weekend slots."),
            bullet("Add an optional interactive wrapper without changing the command-file evaluation path."),
            Spacer(1, 8 * mm),
            callout(
                "Completion statement",
                "The design covers every required functional area and keeps each rule traceable to implementation and tests. The project is ready for demonstration using the supplied command file and sample CSV pack.",
                colors.HexColor("#ECFDF3"),
            ),
        ]
    )
    return story


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=21 * mm,
        bottomMargin=20 * mm,
        title="PS-093 League Competition Engine - Design Document",
        author="T039 - CSDS B",
        subject="League Fixture Scheduling and Points Table with Tie-Breakers",
        creator="T039 report generator",
    )
    document.build(build_story(), onFirstPage=page_decorator, onLaterPages=page_decorator)
    print(OUTPUT)


if __name__ == "__main__":
    main()


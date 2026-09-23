# Product and interface design

PitchShift supports one scouting decision: does a pitcher's recent repertoire warrant a closer look? The interface moves from a ranked watchboard to a compact finding, then into the evidence behind that finding. It does not equate a large difference with an improvement or claim a probability that a mechanical change occurred.

## Reading order

```mermaid
flowchart LR
    A[Check snapshot coverage] --> B[Choose pitcher]
    B --> C[Read leading signals]
    C --> D[Compare movement and location]
    D --> E[Inspect arsenal and date-level velocity trend]
    E --> F[Inspect denominators and intervals]
    F --> G[Save or export for review]
```

The top of the page identifies the observed data cutoff and selected cohort. Four summary measures describe coverage and screening activity. The watchboard ranks pitchers by their largest qualifying `abs(delta) / practicalThreshold`, with search, latest-observed-team and saved-pitcher filters. The same threshold-relative measure orders signals within a card. Signal counts communicate how much evidence is available to inspect; they are not a ranking of pitcher quality.

The selected scouting card places identity, actual comparison dates and pitch counts beside the 100/200-pitch window control. The first three signals show the pitch type, measurement, difference, before/after values and metric-specific sample sizes. All qualifying signals remain available in the detailed comparison table and Markdown export.

The takeaway summarizes the leading change and directs further review. A pitcher without a qualifying signal receives a neutral statement. Insufficient history is a separate state. Absence of a screen does not establish that the pitcher is unchanged.

## Evidence design

Movement and location charts share pitch-type colors. Outlined points represent the preceding baseline; filled points represent recent pitches, allowing the periods to be distinguished without relying only on color. The complete baseline and recent windows are included in the plot payload, with no sampling. Missing coordinates cannot be plotted; valid points outside the fixed chart bounds are counted explicitly.

Movement axes are inches from the catcher's perspective. Location axes are feet. The location plot shows a fixed reference rectangle and explicitly labels it as illustrative: the analytical zone rate uses Savant's recognized zone codes, not this rectangle. Chart limits are fixed for consistent visual comparisons; the plot reports tracked points outside the displayed range.

The arsenal table presents usage and velocity together, including recent pitch counts. Usage differences use percentage points. Date-level mean velocity is a separate time-series view, with the recent date range shaded. Each value uses that pitch type's selected observations on that date. Boundary games may contribute only part of an outing, and two appearances on the same date would be combined. The line is contextual rather than a replacement for the window statistic or a claim to summarize full outings.

The comparison disclosure exposes all eligible measurements, approximate intervals, denominators and whether the practical and uncertainty screens both passed. The methodology dialog explains minimum samples, thresholds, rate denominators and important limitations. These details are available without requiring the user to inspect source code.

## Cohort and freshness

The initial cohort is deliberately small enough to inspect and reproduce locally:

| Latest observed team | Pitchers                                               |
| -------------------- | ------------------------------------------------------ |
| Toronto              | Dylan Cease, Max Scherzer, José Soriano, Trey Yesavage |
| Chicago Cubs         | Kevin Gausman                                          |
| Los Angeles Dodgers  | Tarik Skubal                                           |
| Philadelphia         | Cristopher Sánchez, Zack Wheeler                       |
| New York Yankees     | Max Fried                                              |
| Minnesota            | Taj Bradley                                            |
| Pittsburgh           | Paul Skenes                                            |

These labels come from the downloaded 2026 games, not career associations. A traded pitcher's baseline may include another team. The first public source set spans June 1–September 22, 2026; per-pitcher dates remain more informative than the overall cutoff. A 100-pitch window can span weeks after a gap in appearances, so “recent” always means recent pitches, not a fixed number of calendar days.

## Visual system

The interface uses a pale paper background, white analysis surfaces and a dark green scouting-card header. Olive and lime accents identify selection; restrained amber identifies review flags. The chart palette is consistent across dots, filters and the arsenal table. Signed changes are mathematical directions, not value judgments.

Manrope provides display typography and DM Sans the body text, with system sans-serif fallbacks. Monospaced alignment is reserved for numeric comparisons where supported by tabular numeral styling. Compact labels give space to the evidence; the large change values make the leading observations easy to scan.

At desktop widths, the watchboard sits beside the report. Below 780 px it becomes a horizontal pitcher list above the report. Small screens stack the charts and reflow signal cards. Wide tables scroll within their own container. Print styles remove selection controls and navigation while retaining the scouting report and plots.

## Interactions and accessibility

- Share a selected pitcher and window through the URL fragment.
- Search with the labeled input or `/` keyboard shortcut.
- Save pitcher IDs on the current device; show a session-only message if browser storage is unavailable.
- Export a plain Markdown card containing the selected window, findings, uncertainty, limitations, source and snapshot timestamp.
- Open methodology in a native modal dialog with a labeled close control and keyboard dismissal.

The implementation includes a skip link, visible focus outlines, semantic table headings, SVG titles/descriptions, selected-button state, status toasts and reduced-motion styles. Tables provide the numeric counterpart to charts. These features are implementation choices, not a claim of a completed accessibility certification; contrast, zoom and keyboard behavior still warrant real-device review.

Loading and fetch failures are explicit. A failed request offers retry, and a root rendering boundary offers reload for malformed data. An empty filtered watchboard suggests changing the search or filters. A chart with no tracked points explains the absence instead of drawing a misleading zero value.

## Analytical limits are product requirements

The analysis uses nonoverlapping windows, 100 or 200 recent eligible pitch events, up to 500 preceding baseline events and at least 300 baseline observations. Automatic calls are excluded; missing physical measurements are omitted from their own comparisons. Pitch-type physical comparisons require at least 50 baseline and 20 recent measurements. Metric-specific denominators must be displayed rather than inferred from a pitcher's total pitch count.

Practical thresholds make signals baseball-sized: velocity 0.8 mph, movement 1.5 inches, release point 1 inch, overall usage 8 percentage points, usage conditional on batter side 12 points, zone rate 10 points and whiff rate 12 points. Passing an approximate 95% interval screen as well as a practical threshold is an exploratory rule, not a validated classifier.

Pitches within outings are correlated, and screening many comparisons creates false-positive risk. Opponent mix, counts, pitch classification, tracking conditions and gaps between appearances can affect a difference. A window comparison cannot identify the exact date of a change or establish its cause. The product therefore uses “signal,” “review” and actual sample sizes rather than calibrated confidence percentages or prescriptions for a game plan.

All current comparisons stay within 2026. The [Statcast field definitions](https://baseballsavant.mlb.com/csv-docs) changed plate-location and strike-zone conventions for that season, so extending the application across seasons requires an explicit compatibility decision.

## Deliberate tradeoffs

| Choice                         | Benefit                                                 | Cost                                                            |
| ------------------------------ | ------------------------------------------------------- | --------------------------------------------------------------- |
| Frozen public JSON             | Consistent, shareable reports and a static deployment   | Updates require a refreshed snapshot and publication.           |
| Device-local watchlist         | Useful follow-up workflow with no account setup         | Saved choices do not synchronize across devices.                |
| Markdown export                | Readable, portable evidence with provenance             | It is a text report rather than a PDF image of the charts.      |
| Native SVG charts              | Small dependency surface and transparent plotting logic | Custom axis behavior and accessibility need direct maintenance. |
| Two precomputed recent windows | Fast comparison and a clear producer/consumer contract  | Arbitrary user-defined windows require pipeline changes.        |
| Selected 2026 cohort           | Bounded data, reproducibility and focused research      | Findings cannot be described as MLB-wide monitoring.            |

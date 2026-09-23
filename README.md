<div align="center">
  <img src="web/public/favicon.svg" width="64" height="64" alt="PitchShift" />
  <h1>PitchShift</h1>
  <p><strong>A closer look at what’s changed.</strong></p>
  <p>Pitcher change detection for advance scouting.<br />Real Statcast data. Transparent comparisons. A reason to review the next outing.</p>
  <p>
    <a href="https://fzxt.github.io/PitchShift/"><strong>Open the live app ↗</strong></a>
    &nbsp; · &nbsp;
    <a href="#a-signal-worth-investigating">Read a finding</a>
    &nbsp; · &nbsp;
    <a href="#run-it-locally">Run it locally</a>
    &nbsp; · &nbsp;
    <a href="deployment.md">Deploy your own</a>
  </p>
  <p>
    <a href="https://github.com/fzxt/PitchShift/actions/workflows/pages.yml"><img src="https://github.com/fzxt/PitchShift/actions/workflows/pages.yml/badge.svg" alt="Build and deployment status" /></a>
    <img src="https://img.shields.io/badge/React-TypeScript-173e31?style=flat&labelColor=20372f" alt="React and TypeScript" />
    <img src="https://img.shields.io/badge/Python-3.12+-d9f59a?style=flat&labelColor=20372f" alt="Python 3.12 or newer" />
    <img src="https://img.shields.io/badge/Hosting-GitHub_Pages-173e31?style=flat&labelColor=20372f" alt="Hosted on GitHub Pages" />
  </p>
</div>

<br />

[![PitchShift scouting workspace](https://github.com/user-attachments/assets/d037c86b-6c13-4cc6-abf2-f853bd11df82)](https://fzxt.github.io/PitchShift/)

<p align="center"><sub>The running application, using the included September 22, 2026 snapshot. No synthetic baseball data.</sub></p>

---

## The baseball question

> **Has this pitcher changed something recently that our scouting report should account for?**

Season averages can hide a pitcher’s newest look. PitchShift compares the last **100 or 200 pitches** with the **500 immediately preceding pitches**, then surfaces changes large enough to merit a second look.

The result is a scouting card: what moved, how much it moved, how many observations support it, and the movement/location context behind the numbers. Every flag can be traced to a public pitch-level source and reproduced locally.

| In the workspace               | What it helps you do                                                                             |
| :----------------------------- | :----------------------------------------------------------------------------------------------- |
| **Pitcher watchboard**         | Find pitchers with the largest changes; filter by team or your device-local watchlist.           |
| **Before / after signals**     | Compare velocity, release point, pitch movement, usage, zone rate, whiff rate and platoon usage. |
| **Movement & location plots**  | Inspect the actual pitches in both windows, in the catcher’s coordinate system.                  |
| **Arsenal & velocity trends**  | Separate changes in pitch selection from changes within a pitch type.                            |
| **Uncertainty & sample sizes** | Inspect every eligible comparison, its denominator and its approximate difference interval.      |
| **Portable scouting cards**    | Export a Markdown report with source dates, findings and limitations.                            |

## A signal worth investigating

### Dylan Cease · a slower recent fastball and slider

In the included snapshot, Cease’s last **100 pitches** span **September 13–18, 2026**. His preceding **500 pitches** span **August 16–September 13**. These are disjoint pitch sequences even though the boundary falls within the same game date.

| Pitch              | Baseline velocity | Recent velocity |        Change | Observations, baseline → recent |
| :----------------- | ----------------: | --------------: | ------------: | ------------------------------: |
| Four-seam fastball |         95.49 mph |       94.00 mph | **−1.49 mph** |                        180 → 44 |
| Slider             |         87.90 mph |       86.13 mph | **−1.77 mph** |                        164 → 29 |

Both clear the **0.8 mph practical threshold** and the approximate interval screen. The same direction across two pitch types is a useful lead for video and game-preparation review.

**What this does not establish:** an injury, a mechanical change, an exact change date, or a persistent new talent level. The recent window spans only two appearances, and opponent mix, conditions and tracking context are uncontrolled. Several alerts may describe one underlying pattern rather than independent discoveries.

A second example: Kevin Gausman’s splitter share rises from **197/500 (39.4%)** to **56/100 (56.0%)**, a **16.6 percentage-point** increase. That is a pitch-selection question, with a different denominator and interpretation from a velocity shift.

[Explore Cease’s card →](https://fzxt.github.io/PitchShift/#pitcher=656302&window=100) · [Explore Gausman’s card →](https://fzxt.github.io/PitchShift/#pitcher=592332&window=100)

## How a signal earns its place

```text
                   Prior baseline                 Recent window
              ├──────── 500 pitches ────────┤├──── 100 / 200 ────┤
              Same pitcher · same season · non-overlapping sequences
                                      ↓
                      Split by pitch type / batter side
                                      ↓
                 Enough observations + meaningful effect size
                                      ↓
                 Approximate difference interval excludes zero
                                      ↓
                         Flag for scouting review
```

| Measurement                         | Practical change required | Comparison                                      |
| :---------------------------------- | ------------------------: | :---------------------------------------------- |
| Velocity                            |                   0.8 mph | Mean by pitch type                              |
| Horizontal / vertical movement      |                1.5 inches | Mean by pitch type                              |
| Horizontal / vertical release point |                  1.0 inch | Mean by pitch type                              |
| Pitch usage                         |       8 percentage points | Pitch type / all eligible pitches               |
| Usage against LHB or RHB            |      12 percentage points | Pitch type / pitches to that batter side        |
| Zone rate                           |      10 percentage points | Savant zones 1–9 / recognized zone observations |
| Whiff rate                          |      12 percentage points | Misses / swings, including bunt attempts        |

- **Minimum evidence:** at least 300 baseline pitches and the complete recent window. Physical and zone comparisons need 50 baseline and 20 recent measurements. Whiff comparisons require that many **swings**. Usage screens use the full-window or batter-side denominator, allowing a new pitch to appear.
- **Uncertainty:** approximate Welch intervals for means; Newcombe intervals built from Wilson bounds for proportions. All are exploratory 95% intervals under an independent-pitch assumption.
- **Ordering:** the largest absolute change relative to its practical threshold appears first. This is a ranking heuristic, **not a confidence probability**.
- **Missingness:** missing measurements remain missing. Automatic balls and strikes are excluded. Unknown pitch classifications are retained as unclassified events; unknown swing descriptions never silently become swings.
- **Multiplicity:** intervals are not adjusted for the many correlated comparisons. Within-appearance correlation can make intervals too narrow. The thresholds are transparent product choices, not validated predictive cutoffs.

<details>
<summary><strong>Why 2026-only data matters</strong></summary>

Baseball Savant changed plate-location measurement from the front of home plate to the middle of the plate in 2026 for ABS. Mixing years can introduce an artificial location shift. The ingestion boundary rejects mixed seasons, and the included snapshot contains only 2026 regular-season data.

Movement and release coordinates arrive in feet and are converted to inches. Horizontal signs remain in the catcher’s perspective; they are not relabeled “arm side” without handedness adjustment. The location plot uses a reference strike-zone outline, while the actual zone-rate calculation uses Savant’s recognized zone codes.

[Official Statcast field definitions](https://baseballsavant.mlb.com/csv-docs)

</details>

## Data you can audit

| Included research snapshot | Coverage                                                      |
| :------------------------- | :------------------------------------------------------------ |
| Season                     | 2026 regular season                                           |
| Observed dates             | June 1 – September 22, 2026                                   |
| Selected pitchers          | 11, including four with Toronto as their latest observed team |
| Source rows                | 17,244                                                        |
| Eligible pitch events      | 17,240, after excluding four automatic balls                  |
| Source                     | MLB Baseball Savant public Statcast CSV                       |

This is a **selected research cohort, not full MLB coverage**. Team labels come from each pitcher’s latest observed game, not a hardcoded historical roster. Each card displays its own actual date range; 100 pitches can span a long calendar interval for an infrequent pitcher.

The repository includes a compressed source snapshot and a provenance manifest with request URLs and SHA-256 hashes. Rebuilding from that snapshot requires no network or database. Scheduled refreshes update the deployed report; the table and findings above describe the pinned research snapshot.

[Source manifest](data/snapshots/provenance.json) · [Analysis implementation](pitchshift/analytics.py) · [Regression tests](tests/test_analytics.py)

## Run it locally

**Prerequisites:** Node.js 24 recommended (22.12+ supported); Python 3.12+ for analysis.

```sh
git clone https://github.com/fzxt/PitchShift.git
cd PitchShift
npm ci
npm run dev
```

Open **http://127.0.0.1:4173**. The included report works immediately. **No API keys, database or account is required to run the app.**

Reproduce the analysis or download a new snapshot:

```sh
# Rebuild from the versioned, hashed source snapshot
python -m pitchshift.pipeline

# Download the selected cohort from public Statcast CSVs
python -m pitchshift.pipeline --refresh
```

On Windows, stop the Vite server before regenerating the snapshot if its file watcher holds the JSON file open; restart `npm run dev` afterward. A failed refresh preserves the previous valid report.

<details>
<summary><strong>Optional: persist the pipeline output in Neon</strong></summary>

Create a Neon **Free** project and put its connection URL in a local, gitignored `.env`:

```dotenv
DATABASE_URL=postgresql://ROLE:PASSWORD@HOST/DATABASE?sslmode=require
```

```sh
python -m pip install -r requirements.txt
python -m pitchshift.pipeline --sync-db
```

The pipeline owns only the `pitchshift` schema. It stores a bounded pitch history and seven report snapshots. Credentials never enter the React build. For scheduled persistence, add the URL as the repository Actions secret **`NEON_DATABASE_URL`**.

No Neon API key, paid application server, model API or external cron service is needed. The public application works independently of the database. See [deployment.md](deployment.md) for provisioning, privileges, free-tier limits and ownership transfer.

</details>

## Architecture at a glance

```mermaid
flowchart LR
    Savant[Baseball Savant CSV] --> Python[Python validation & analysis]
    Snapshot[Versioned source snapshot] --> Python
    Python --> JSON[Public report JSON]
    Python -. optional .-> Neon[(Neon Postgres)]
    JSON --> React[React + TypeScript]
    React --> Vite[Vite static build]
    Vite --> Pages[GitHub Pages]
    Actions[GitHub Actions] -. refresh & deploy .-> Python
```

**A static read path keeps the scouting tool dependable.** Visitors load a public JSON report, then explore locally in their browser. There is no database connection, secret-bearing API, login wall or cold-start dependency in the page-load path. Python owns statistical calculations; React owns interaction and presentation.

```text
web/src/                  Typed React workspace and SVG charts
web/public/data/          Public, credential-free analysis snapshot
pitchshift/analytics.py   Window construction and statistical screens
pitchshift/ingest.py      Validated public Statcast CSV ingestion
pitchshift/pipeline.py    Reproduce, refresh, optionally persist, publish
pitchshift/database.py   Private, bounded Postgres persistence
sql/schema.sql           Isolated schema and SQL recency window view
data/snapshots/          Compressed research input and provenance
tests/                    Analytical, ingestion and persistence tests
.github/workflows/       Automated checks, refresh and Pages deployment
```

## Built to be reviewed

```sh
npm run check                          # Strict TypeScript checks
python -m unittest discover -s tests -v # Analytical and data-boundary tests
python scripts/validate_snapshot.py     # Public report invariants
npm run build                          # Production static build
```

Tests cover disjoint windows, pitch ordering, real-snapshot findings, correct rate denominators, missing values, new pitch types, duplicate identities, mixed-season rejection, parameterized database writes, transaction failures, secret redaction and retention limits. The UI includes keyboard controls, responsive layouts, an accessible methodology dialog, empty/error states and portable report export.

## Operate it or make it yours

| Guide                                         | Start here when you want to…                                                 |
| :-------------------------------------------- | :--------------------------------------------------------------------------- |
| [**Launch guide**](launch.md)                 | Run the app, check a release, or hand it to a new owner.                     |
| [**Deployment & credentials**](deployment.md) | Set up GitHub Pages, Neon, scheduled refreshes and recovery.                 |
| [**Architecture**](docs/architecture.md)      | Understand system boundaries, data flow, contracts and tradeoffs.            |
| [**Design**](docs/design.md)                  | Understand the scouting workflow, visual system and accessibility decisions. |

GitHub Pages and standard GitHub Actions runners support this public-repository deployment on their free offerings. Neon is optional and is designed to fit its Free plan; provider quotas and account settings still apply. [GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages) · [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions) · [Neon Free plan](https://neon.com/blog/neon-backend-is-ga)

---

<p align="center"><sub>Independent baseball research. Not affiliated with MLB, Baseball Savant, or any club.<br />Public data supports a scouting question; it does not replace baseball context.</sub></p>

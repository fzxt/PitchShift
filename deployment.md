# Deployment and operations

The frontend is hosted on GitHub Pages. Python runs locally or in GitHub Actions, reads public Statcast CSVs, and writes `web/public/data/pitchshift.json`. Optional Neon persistence is private to that Python process; visitors read only the static report.

```text
Baseball Savant CSV → Python validation and analysis → public JSON → React → GitHub Pages
                                      ↓ optional
                              Neon: pitchshift schema
```

## GitHub Pages

Repository: [fzxt/PitchShift](https://github.com/fzxt/PitchShift). Pages address: [https://fzxt.github.io/PitchShift/](https://fzxt.github.io/PitchShift/). Verify availability against the latest successful [workflow run](https://github.com/fzxt/PitchShift/actions).

1. Keep the repository public for the intended free hosting configuration.
2. Under **Settings → Pages**, choose **GitHub Actions** as the publishing source.
3. Allow the repository workflow to run. Its build job requests `contents: write` to commit refreshed public analysis; its deployment job requests `pages: write` and `id-token: write` for Pages.
4. Push to `main`, or manually run **Build, refresh and deploy PitchShift**. Leave refresh unchecked to deploy the checked-in report without requesting new data.
5. Inspect the workflow's deployment URL and verify the site after the deploy job completes.

GitHub creates the workflow's `GITHUB_TOKEN` and Pages OIDC identity. Do not create a personal access token or store a GitHub password for this workflow. A custom domain is unnecessary. The Vite build uses relative paths and uploads only `dist`.

## Optional Neon setup

No usable database credential was available from the earlier local project files during initial setup. A successful live database sync has not been recorded by this guide. The application still works from its static report.

Create a dedicated **Free** Neon project under the intended owner's account. Keep scale-to-zero enabled and conservative compute limits. Use a separate database/role for PitchShift where possible, especially when other projects contain operational data. This app does not need Neon Functions, Auth, Object Storage, an AI Gateway, or a Neon API key.

Copy the PostgreSQL connection URL from Neon's connection dialog, selecting the intended project, branch, database, and role. A pooled URL is suitable. Preserve its connection parameters; the client explicitly uses verified TLS with system trust roots for `.neon.tech` hosts.

For minimal privileges, use a login role without superuser, role-management, or other applications' table access. It must own the `pitchshift` schema and its objects because the pipeline applies its own table/view definitions and retention. The first migration creates the schema, requiring database `CREATE` permission; this self-migrating pipeline may need that permission when rerunning its schema statements. Prefer granting it only in a dedicated PitchShift database. Never grant access to unrelated tables simply to make setup succeed. PostgreSQL documents the schema privilege requirement in [CREATE SCHEMA](https://www.postgresql.org/docs/17/sql-createschema.html).

### Local credential

Create `.env` from the example only if it does not already exist:

```powershell
if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
}
```

Edit the private `.env` locally. Replace the placeholder with the real URL without printing it in logs:

```dotenv
DATABASE_URL=postgresql://ROLE:PASSWORD@HOST/DATABASE?sslmode=require
```

The `.env` file is gitignored. Do not use `VITE_DATABASE_URL`; Vite-prefixed variables can reach the browser. Install the optional database driver and seed from the checked-in snapshot:

```powershell
python -m pip install -r requirements.txt
python -m pitchshift.pipeline --sync-db
```

For both fresh data and database persistence:

```powershell
python -m pitchshift.pipeline --refresh --sync-db
```

The pipeline reports `saved` after a successful transaction. If no URL is configured, it reports `disabled`. If a configured database fails, the command fails and preserves the existing public JSON instead of publishing a partly completed refresh. Driver failures are redacted to keep connection credentials out of output.

### GitHub credential

In **Settings → Secrets and variables → Actions**, create a repository secret named **`NEON_DATABASE_URL`**, containing the same private PostgreSQL URL. It is the only optional external service secret the application needs. The workflow exposes it only as `DATABASE_URL` during the refresh step.

Run the workflow manually with **refresh = true**. Inspect its safe `Neon persistence: saved` status, then use the Neon SQL editor to verify these queries:

```sql
SELECT count(*) AS stored_pitches, min(game_date), max(game_date)
FROM pitchshift.pitches;

SELECT created_at, report->'source'->>'dataEnd' AS through_date
FROM pitchshift.snapshots
ORDER BY created_at DESC
LIMIT 3;
```

The schema is defined in `sql/schema.sql`. Only `pitchshift.pitches`, `pitchshift.snapshots`, and `pitchshift.pitch_sequence` are created or changed. The pipeline retains at most 100,000 pitches within 120 days of the newest stored pitch and seven reports, each limited to 8 MB. These are application limits, not a guarantee of total provider storage: indexes, old row versions, and other projects' objects also use storage.

## Scheduled refresh and recovery

`.github/workflows/pages.yml` runs daily at **11:30 UTC**; this is 04:30 Pacific daylight time and 03:30 Pacific standard time. Scheduled runs can be delayed by GitHub, so use the displayed report date as the freshness indicator. No external scheduler is required.

Scheduled or explicitly requested refreshes download the configured cohort, validate and analyze it, optionally sync Neon, commit the public report, run checks, and deploy. The exact downloaded CSV and provenance are uploaded as `statcast-refresh-inputs` with **three-day retention**. Public report history remains in Git; raw refresh files are not committed. Ordinary pushes deploy the existing report without a new download.

The workflow is currently configured for **2026**, regular-season data, and an end-date cap of **October 31, 2026**. It does not automatically turn itself off after that date. Remove/comment the `schedule` block after the season if continued refreshes are unnecessary; manual deployments can remain enabled. For a new season, deliberately update the season settings, cohort, provenance, and checked-in snapshot. Do not silently mix measurement eras.

If a download, database sync, validation, or build fails, the deploy job does not run and the last successfully deployed site remains available. Review Actions logs, correct the cause, and rerun. A refresh report may have been committed before a later build fails; the public Pages deployment still remains the last successful one. To roll back a published report, restore a known-good `web/public/data/pitchshift.json` from Git history and push it to `main`.

For source reproduction beyond the initial bundled dataset, save the three-day input artifact before expiry, then run:

```powershell
python -m pitchshift.pipeline --input data/raw/latest.csv --provenance data/raw/latest.provenance.json
```

## Free-tier boundaries

The intended setup uses GitHub Free, a public repository, standard `ubuntu-latest` runners, GitHub Pages, public Statcast downloads, and optionally Neon Free. GitHub supports Pages for public repositories on Free. [GitHub Pages documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)

Standard Actions runners are free for public repositories. Artifact and cache storage still have plan allowances, so keep the three-day input retention, remove unneeded artifacts, and inspect account budgets before increasing usage. Larger runners are charged even for public repositories. [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)

Neon's September 17, 2026 announcement lists **100 CU-hours and 0.5 GB database storage per Free project**. Verify the current console limits before provisioning; plan terms can change. [Neon Free plan announcement](https://neon.com/blog/neon-backend-is-ga)

Keep the project on Free, use scale-to-zero, and watch its compute/storage dashboard. Do not enable a paid tier or extra services to resolve a limit automatically. If an existing shared Neon project is near its allowance, use a dedicated free project or disable private sync while the static application continues running. This code cannot guarantee the entire owner's provider account incurs no charges from unrelated usage.

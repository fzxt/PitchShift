# Launch and ownership guide

PitchShift is a local codebase with a static scouting application, a reproducible Python data pipeline, and optional private Neon storage. A reviewer can open the public site without an account, API key, or database connection.

- Source: [fzxt/PitchShift](https://github.com/fzxt/PitchShift)
- GitHub Pages address: [fzxt.github.io/PitchShift](https://fzxt.github.io/PitchShift/)
- Deployment status: check the latest successful run in [GitHub Actions](https://github.com/fzxt/PitchShift/actions). A URL alone does not confirm a successful deployment.
- Detailed infrastructure instructions: [deployment.md](deployment.md)

## Run it locally

Install Node.js 24 and Python 3.12 or newer. In the project directory:

```powershell
npm ci
npm run dev
```

Open [127.0.0.1:4173](http://127.0.0.1:4173/). The included public report works immediately. No environment file is required for this path.

```powershell
npm run check
python -m unittest discover -s tests -v
python scripts/validate_snapshot.py
npm run build
```

To rebuild the report from the checked-in September 22, 2026 data:

```powershell
python -m pitchshift.pipeline
```

To download current public 2026 Statcast data for the configured pitcher cohort:

```powershell
python -m pitchshift.pipeline --refresh
```

The public data source requires no API credential. This refresh uses a rolling 120-day range and downloads only the selected cohort. The report supports 100- and 200-pitch recent windows; each is compared with up to 500 preceding pitches. The sample is not full MLB coverage.

## Credentials the owner needs

| Task | Required account or credential |
| --- | --- |
| View the deployed app, run it locally, reproduce its checked-in data | None |
| Fetch public Statcast CSV data | None |
| Own the repository and publish on GitHub Pages | A GitHub account with repository administration access |
| Run the provided GitHub Actions workflow | GitHub supplies its job token and Pages OIDC identity automatically; no personal access token needs to be created |
| Persist analysis and pitches in Neon | An optional PostgreSQL connection URL for a Neon Free project |

For Neon, the same connection URL has two destinations: local `.env` as `DATABASE_URL`, and the repository Actions secret `NEON_DATABASE_URL`. The workflow maps the latter to `DATABASE_URL` for its Python process. Never add this credential to a `VITE_` variable, source control, or `web/public`.

Existing Neon credentials were not recoverable from the available local project configurations at initial setup. Database support is implemented and tested with a mock connection; do not treat that as a verified live Neon installation. The static application and refresh pipeline operate without Neon while the owner provisions or connects it.

## Launch review

1. Confirm the latest Pages deployment succeeded, then open the public URL in a fresh browser tab.
2. Check that pitcher selection, the 100/200-pitch switch, pitch filters, plots, and report export work.
3. Confirm the displayed source date and cohort before sharing a finding. A review flag is an exploratory lead, not a probability of a true change.
4. Keep a copy of the code and checked-in compressed source snapshot. For later nightly refreshes, download the `statcast-refresh-inputs` Actions artifact within its three-day retention window when you need exact source reproduction.
5. If Neon is enabled, run one private sync and verify `pitchshift.pitches` and `pitchshift.snapshots` before describing database persistence as live.

## Hand ownership to someone else

The new owner can fork the public repository into their account, or the existing owner can transfer it through GitHub repository settings. A fork is the simplest way to create independent ownership without affecting this deployment.

1. Enable Actions in the destination repository and set **Settings → Pages → Source → GitHub Actions**. Check that the workflow can write the refreshed report to `main`; branch protections may require adapting that write step.
2. Run **Build, refresh and deploy PitchShift** manually with refresh unchecked for the first deployment.
3. Update repository and demo links in documentation and any UI links to the new owner/repository. Vite uses relative asset paths, so the built app supports a different repository subpath. Review visible branding and attribution separately.
4. Prefer a new Neon Free project owned by the recipient. Add its URL as `NEON_DATABASE_URL` in their repository and, if needed, `DATABASE_URL` in their local `.env`. The checked-in dataset can seed the new database using `python -m pitchshift.pipeline --sync-db` after installing `requirements.txt`.
5. Verify the destination deployment and a fresh scheduled/manual run before retiring the original workflow. Secrets do not need to be sent through chat or copied into a handoff document.
6. Remove obsolete collaborator access and credentials after confirming the handoff. Rotate a reused Neon role only after migrating every application that shares it; changing a shared password prematurely can break the earlier application. A separate project and role avoids that dependency.

The owner controls the repository, workflow, Neon account if enabled, and public source-data refreshes. There is no separate application server, paid cron service, model API, or managed frontend subscription to transfer.

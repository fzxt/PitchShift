# PitchShift

**Has this pitcher changed something recently that our scouting report should account for?**

<img width="1574" height="1269" alt="image" src="https://github.com/user-attachments/assets/d037c86b-6c13-4cc6-abf2-f853bd11df82" />



PitchShift compares a pitcher's last 100 or 200 Statcast pitches with the immediately preceding 500. It surfaces meaningful changes in velocity, pitch movement, release point, pitch usage, zone rate and whiff rate for advance scouting.

This is an independent, exploratory baseball research project. Signals are prompts for investigation, not calibrated probabilities or causal conclusions.

## Stack

- React + TypeScript + Vite: static, accessible scouting workspace.
- Python: ingestion, validation and statistical comparisons.
- Neon Postgres: optional private persistence for the pipeline.
- GitHub Pages: frontend hosting. The browser fetches only a public analysis snapshot, never database credentials.

## Local development

```sh
npm ci
npm run dev
```

Open the local URL printed by Vite. Use Node 22.12+ and Python 3.12+.

```sh
npm run check
python -m unittest discover -s tests -v
npm run build
```

Data collection, methodology, findings and deployment instructions are being finalized alongside the first data snapshot.

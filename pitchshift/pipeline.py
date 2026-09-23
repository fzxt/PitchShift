"""Reproduce the public report or refresh it from Savant and optionally Neon."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import time
from datetime import date, timedelta
from pathlib import Path

from .analytics import build_report
from .ingest import fetch_cohort, read_csv, validate_rows

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / 'data/snapshots/statcast-2026-09-22.csv.gz'
DEFAULT_OUTPUT = ROOT / 'web/public/data/pitchshift.json'


def run(args: argparse.Namespace) -> dict:
    if args.refresh:
        end = date.fromisoformat(args.end) if args.end else min(date.today() - timedelta(days=1), date(args.season, 10, 31))
        start = date.fromisoformat(args.start) if args.start else max(date(args.season, 3, 1), end - timedelta(days=120))
        if end.year != args.season:
            raise ValueError('Requested end date must match the selected season.')
        rows, provenance = fetch_cohort(start, end, ROOT / 'data/raw/latest.csv')
    else:
        rows = read_csv(args.input)
        provenance_file = args.provenance or (ROOT / 'data/snapshots/provenance.json' if args.input.resolve() == DEFAULT_INPUT.resolve() else args.input.with_suffix('.provenance.json'))
        provenance = json.loads(provenance_file.read_text(encoding='utf-8')) if provenance_file.exists() else {}
        expected_hash = provenance.get('csv_sha256')
        if expected_hash:
            content = args.input.read_bytes()
            if args.input.suffix == '.gz':
                content = gzip.decompress(content)
            if hashlib.sha256(content).hexdigest() != expected_hash:
                raise ValueError('Input hash differs from source provenance; refusing to analyze altered input.')
    rows = validate_rows(rows, args.season)
    if len(rows) < 600:
        raise ValueError('Not enough source pitches to publish a useful snapshot.')
    report = build_report(rows)
    report['source'].update({
        'name': 'Baseball Savant / Statcast', 'url': 'https://baseballsavant.mlb.com/',
        'documentationUrl': 'https://baseballsavant.mlb.com/csv-docs',
        'dataStart': min(row['game_date'] for row in rows), 'dataEnd': max(row['game_date'] for row in rows),
        'sourceRowCount': len(rows), 'pitcherCount': len(set(row['pitcher'] for row in rows)),
        'retrievedAt': provenance.get('retrieved_at_utc'), 'season': args.season,
        'cohort': 'Selected pitchers, with a Toronto focus; not full MLB coverage.',
    })
    # A failed refresh must never overwrite the last known good public snapshot.
    if not all(any(pitcher['status'] != 'insufficient' for pitcher in report['windows'].get(window, {}).get('pitchers', [])) for window in ('100', '200')):
        raise ValueError('Analysis did not produce an eligible pitcher in both comparison windows.')
    output = json.dumps(report, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    if len(output.encode('utf-8')) > 8_000_000:
        raise ValueError('Public snapshot exceeds 8 MB safety bound.')
    if args.sync_db:
        from .database import persist_snapshot
        result = persist_snapshot(report, rows)
        print(f"Neon persistence: {result.get('status', result)}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp = args.output.with_suffix('.tmp')
    temp.write_text(output, encoding='utf-8')
    for attempt in range(5):
        try:
            temp.replace(args.output)
            break
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.1 * (attempt + 1))
    print(f"Published snapshot: {len(report['windows']['100']['pitchers'])} pitchers, {len(rows):,} source rows, through {report['source']['dataEnd']}.")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--provenance', type=Path)
    parser.add_argument('--refresh', action='store_true', help='Download the selected cohort from public Savant CSVs.')
    parser.add_argument('--season', type=int, default=2026)
    parser.add_argument('--start', help='YYYY-MM-DD, defaults to a rolling 120 days.')
    parser.add_argument('--end', help='YYYY-MM-DD, defaults to yesterday, capped at season end.')
    parser.add_argument('--sync-db', action='store_true', help='Persist to the optional private Neon database.')
    args = parser.parse_args()
    try:
        run(args)
    except Exception as exc:
        # Avoid echoing a driver exception that could contain a connection URI.
        if args.sync_db and ('postgres' in str(exc).lower() or 'password' in str(exc).lower()):
            parser.exit(1, 'Database operation failed. Verify private DATABASE_URL and network access.\n')
        parser.exit(1, f'Pipeline failed: {exc}\n')


if __name__ == '__main__':
    main()

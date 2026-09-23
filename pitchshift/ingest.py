"""Small, validated Baseball Savant CSV ingestion with no paid API dependency."""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import math
import shutil
import subprocess
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

COHORT = [592332, 656302, 702056, 453286, 667755, 669373, 694973, 554430, 608331, 650911, 671737]
COLUMNS = (
    'game_date', 'game_pk', 'at_bat_number', 'pitch_number', 'pitcher', 'player_name',
    'batter', 'pitch_type', 'pitch_name', 'game_type', 'game_year', 'release_speed',
    'release_pos_x', 'release_pos_z', 'pfx_x', 'pfx_z', 'plate_x', 'plate_z', 'sz_top',
    'sz_bot', 'zone', 'stand', 'p_throws', 'balls', 'strikes', 'description',
    'home_team', 'away_team', 'inning_topbot', 'release_spin_rate', 'release_extension', 'arm_angle',
)
REQUIRED = {'game_date', 'game_pk', 'at_bat_number', 'pitch_number', 'pitcher', 'pitch_type', 'release_speed', 'pfx_x', 'pfx_z', 'description'}
USER_AGENT = 'Mozilla/5.0'


def read_csv(path: Path) -> list[dict]:
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if not REQUIRED.issubset(reader.fieldnames or []):
            raise ValueError('CSV is missing required Statcast columns.')
        return list(reader)


def validate_rows(rows: list[dict], season: int) -> list[dict]:
    """Fail closed on wrong seasons or conflicting duplicates; skip exact repeats."""
    unique = {}
    for row in rows:
        if not row.get('game_date'):
            continue
        observed = date.fromisoformat(str(row['game_date'])[:10])
        if observed.year != season or str(row.get('game_year') or season).split('.')[0] != str(season):
            raise ValueError('Input mixes seasons. Cross-era location comparisons are not supported.')
        if row.get('game_type') not in (None, '', 'R'):
            continue
        try:
            identifiers = [float(row[field]) for field in ('game_pk', 'at_bat_number', 'pitch_number', 'pitcher')]
            if any(not math.isfinite(value) or not value.is_integer() or value <= 0 for value in identifiers):
                raise ValueError('Pitch identifiers must be positive integers.')
            key = tuple(int(value) for value in identifiers[:3])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError('Input contains an invalid pitch identity.') from exc
        projection = {column: row.get(column, '') for column in COLUMNS}
        if key in unique and unique[key] != projection:
            raise ValueError('Conflicting duplicate pitch identities; inspect source before replacing snapshot.')
        unique[key] = projection
    if not unique:
        raise ValueError('No regular-season pitches returned. Existing snapshot is preserved.')
    return sorted(unique.values(), key=lambda row: (row['game_date'], int(float(row['game_pk'])), int(float(row['at_bat_number'])), int(float(row['pitch_number']))))


def source_url(pitcher_id: int, start: date, end: date) -> str:
    return 'https://baseballsavant.mlb.com/statcast_search/csv?' + urlencode({
        'all': 'true', 'type': 'details', 'player_type': 'pitcher', 'hfGT': 'R|',
        'hfSea': f'{start.year}|', 'game_date_gt': start.isoformat(),
        'game_date_lt': end.isoformat(), 'pitchers_lookup[]': pitcher_id,
    })


def download(url: str) -> bytes:
    """Savant rejects some default HTTP clients; curl uses a browser-style UA."""
    curl = shutil.which('curl.exe') or shutil.which('curl')
    last_error = None
    for attempt in range(3):
        try:
            if curl:
                result = subprocess.run([curl, '--fail', '--silent', '--show-error', '--location', '--max-time', '100', '--user-agent', USER_AGENT, url], capture_output=True, timeout=110, check=False)
                if result.returncode:
                    raise OSError(f'Statcast request failed (curl exit {result.returncode}).')
                body = result.stdout
            else:
                with urlopen(Request(url, headers={'User-Agent': USER_AGENT}), timeout=100) as response:
                    body = response.read(25_000_001)
            if len(body) > 25_000_000:
                raise ValueError('Source response exceeded the 25 MB per-pitcher limit.')
            return body
        except (OSError, subprocess.TimeoutExpired) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 ** (attempt + 1))
    raise RuntimeError('Public Statcast download failed after three attempts.') from last_error


def fetch_cohort(start: date, end: date, destination: Path, cohort: list[int] | None = None) -> tuple[list[dict], dict]:
    if start.year != end.year or start > end:
        raise ValueError('Start and end must be in the same season and in chronological order.')
    rows, requests = [], []
    for pitcher_id in cohort or COHORT:
        url = source_url(pitcher_id, start, end)
        body = download(url)
        reader = csv.DictReader(io.StringIO(body.decode('utf-8-sig')))
        if not REQUIRED.issubset(reader.fieldnames or []):
            raise ValueError(f'Pitcher {pitcher_id}: source did not return a valid pitch CSV.')
        batch = list(reader)
        if not batch:
            raise ValueError(f'Pitcher {pitcher_id}: no rows returned; refusing an incomplete cohort refresh.')
        if any(int(float(row['pitcher'])) != pitcher_id for row in batch):
            raise ValueError('Source pitcher filter failed.')
        rows.extend(batch)
        requests.append({'pitcher_id': pitcher_id, 'row_count': len(batch), 'request_url': url, 'sha256': hashlib.sha256(body).hexdigest()})
        print(f'Fetched pitcher {pitcher_id}: {len(batch):,} source rows.')
    rows = validate_rows(rows, start.year)
    if any(not start.isoformat() <= row['game_date'][:10] <= end.isoformat() for row in rows):
        raise ValueError('Source returned pitches outside the requested range.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix('.tmp')
    with temp.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(destination)
    provenance = {'source': 'MLB Baseball Savant Statcast Search CSV', 'source_documentation_url': 'https://baseballsavant.mlb.com/csv-docs', 'retrieved_at_utc': datetime.now(timezone.utc).isoformat(), 'requested_start': start.isoformat(), 'requested_end': end.isoformat(), 'latest_observed_date': max(row['game_date'] for row in rows), 'season': start.year, 'game_type': 'R', 'row_count': len(rows), 'pitcher_count': len(set(row['pitcher'] for row in rows)), 'pitchers': requests}
    destination.with_suffix('.provenance.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')
    return rows, provenance

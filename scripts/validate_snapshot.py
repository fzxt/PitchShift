"""Fail deployment for empty/malformed snapshots or accidentally bundled secrets."""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / 'web/public/data/pitchshift.json'
text = path.read_text(encoding='utf-8')
assert not any(token in text.lower() for token in ('postgresql://', 'postgres://', 'database_url', 'neon_api_key')), 'Credential-like data in public snapshot'
report = json.loads(text)
assert report['schemaVersion'] == 1
assert report['source']['pitchCount'] >= 600
assert report['source']['season'] == 2026
for window in ('100', '200'):
    pitchers = report['windows'][window]['pitchers']
    assert len(pitchers) >= 1
    assert len({p['id'] for p in pitchers}) == len(pitchers)
    for p in pitchers:
        assert p['name'] and p['recentCount'] <= int(window) and p['baselineCount'] <= 500
        assert len(p['points']['recent']) == p['recentCount']
        assert len(p['points']['baseline']) == p['baselineCount']
        for m in p['metrics']:
            assert all(math.isfinite(m[key]) for key in ('baseline', 'recent', 'delta', 'practicalThreshold'))
            assert all(math.isfinite(v) for v in m['interval'])
            assert m['interval'][0] <= m['delta'] <= m['interval'][1]
print(f"Validated {len(report['windows']['100']['pitchers'])} pitchers and both windows; public snapshot contains no credential-like fields.")

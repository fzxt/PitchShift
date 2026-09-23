"""Optional, bounded Postgres storage used by the Python pipeline, never the browser.

Only objects inside the dedicated ``pitchshift`` schema are touched. A database
connection is opened only when ``persist_snapshot`` is explicitly called.
"""

from __future__ import annotations

from datetime import date, timedelta
from hashlib import sha256
import json
import math
import os
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
MAX_SNAPSHOTS = 7
MAX_REPORT_BYTES = 8_000_000
MAX_PITCHES = 100_000
RETENTION_DAYS = 120


class DatabaseError(RuntimeError):
    """An intentionally credential-free persistence error."""


def load_local_env(path: str | Path | None = None) -> None:
    """Load simple .env assignments without replacing existing process settings."""
    env_path = Path(path) if path is not None else ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if key.startswith("export "):
            key = key[7:].strip()
        if not key or not key.replace("_", "").isalnum():
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)


def database_status() -> dict[str, Any]:
    """Return safe metadata, never a host, user, connection string, or password."""
    load_local_env()
    value = os.environ.get("DATABASE_URL", "").strip()
    try:
        hostname = urlsplit(value).hostname or ""
    except ValueError:
        hostname = ""
    return {
        "configured": bool(value),
        "provider": "Neon" if hostname.endswith(".neon.tech") else "Postgres" if value else None,
        "schema": "pitchshift",
    }


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (ValueError, TypeError):
        return None
    return number if math.isfinite(number) else None


def _integer(value: Any) -> int:
    number = _number(value)
    if number is None or not number.is_integer():
        raise ValueError("Missing pitch identity")
    return int(number)


def _pitch_row(row: Mapping[str, Any]) -> tuple[Any, ...] | None:
    """Read the standard Baseball Savant CSV fields, skipping incomplete identities."""
    try:
        identity = (_integer(row.get("game_pk")), _integer(row.get("at_bat_number")), _integer(row.get("pitch_number")))
        game_date = date.fromisoformat(str(row.get("game_date", ""))[:10])
        pitcher = _integer(row.get("pitcher", row.get("pitcher_id")))
    except ValueError:
        return None
    pitch_type = row.get("pitch_type") or "UN"
    return (*identity, game_date, pitcher, row.get("player_name", row.get("pitcher_name")),
            pitch_type, row.get("stand"), row.get("p_throws"),
            *(_number(row.get(key)) for key in (
                "release_speed", "release_pos_x", "release_pos_z", "pfx_x", "pfx_z",
                "plate_x", "plate_z", "sz_top", "sz_bot")), row.get("description"))


def persist_snapshot(
    report: Mapping[str, Any], rows: Iterable[Mapping[str, Any]] | None = None,
    *, database_url: str | None = None,
) -> dict[str, Any]:
    """Commit report and optional raw pitches in one transaction.

    Retains seven reports and at most 100,000 pitches within 120 days of the
    newest stored pitch. Missing credentials return ``status=disabled``; a
    configured but failing database raises DatabaseError with no raw driver text.
    No database exception containing connection metadata reaches public output.
    """
    load_local_env()
    connection_url = (database_url if database_url is not None else os.environ.get("DATABASE_URL", "")).strip()
    if not connection_url:
        return {"status": "disabled", "reason": "DATABASE_URL is not configured"}
    try:
        parsed = urlsplit(connection_url)
        if parsed.scheme not in ("postgres", "postgresql") or not parsed.hostname:
            raise ValueError
    except ValueError:
        raise DatabaseError("DATABASE_URL must be a valid PostgreSQL connection URL.") from None
    encoded = json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if len(encoded.encode("utf-8")) > MAX_REPORT_BYTES:
        raise DatabaseError("Report exceeds the 8 MB storage limit.")
    snapshot_id = sha256(encoded.encode("utf-8")).hexdigest()
    pitches = []
    skipped = 0
    if rows is not None:
        for row in rows:
            converted = _pitch_row(row)
            if converted is None:
                skipped += 1
                continue
            pitches.append(converted)
        pitches.sort(key=lambda row: (row[3], row[0], row[1], row[2]), reverse=True)
        pitches = pitches[:MAX_PITCHES]
        if pitches:
            oldest = pitches[0][3] - timedelta(days=RETENTION_DAYS)
            pitches = [row for row in pitches if row[3] >= oldest]
    try:
        import psycopg
    except ImportError:
        raise DatabaseError("Install requirements.txt to enable Postgres storage.") from None
    options: dict[str, Any] = {
        "connect_timeout": 15,
        "application_name": "pitchshift-pipeline",
        "options": "-c statement_timeout=60000 -c lock_timeout=5000",
    }
    if parsed.hostname.endswith(".neon.tech"):
        options["sslmode"] = "verify-full"
        options["sslrootcert"] = "system"
    try:
        with psycopg.connect(connection_url, **options) as connection:
            with connection.cursor() as cursor:
                cursor.execute((ROOT / "sql" / "schema.sql").read_text(encoding="utf-8"))
                if pitches:
                    cursor.executemany("""
                        INSERT INTO pitchshift.pitches (
                            game_pk, at_bat_number, pitch_number, game_date, pitcher_id,
                            pitcher_name, pitch_type, batter_stand, pitcher_throws,
                            release_speed, release_pos_x, release_pos_z, pfx_x, pfx_z,
                            plate_x, plate_z, sz_top, sz_bot, description
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (game_pk, at_bat_number, pitch_number) DO UPDATE SET
                            game_date = EXCLUDED.game_date,
                            pitcher_id = EXCLUDED.pitcher_id,
                            pitcher_name = EXCLUDED.pitcher_name,
                            pitch_type = EXCLUDED.pitch_type,
                            batter_stand = EXCLUDED.batter_stand,
                            pitcher_throws = EXCLUDED.pitcher_throws,
                            release_speed = EXCLUDED.release_speed,
                            release_pos_x = EXCLUDED.release_pos_x,
                            release_pos_z = EXCLUDED.release_pos_z,
                            pfx_x = EXCLUDED.pfx_x, pfx_z = EXCLUDED.pfx_z,
                            plate_x = EXCLUDED.plate_x, plate_z = EXCLUDED.plate_z,
                            sz_top = EXCLUDED.sz_top, sz_bot = EXCLUDED.sz_bot,
                            description = EXCLUDED.description
                    """, pitches)
                cursor.execute("""
                    INSERT INTO pitchshift.snapshots (content_sha256, report)
                    VALUES (%s, %s::jsonb)
                    ON CONFLICT (content_sha256) DO UPDATE SET created_at = now()
                """, (snapshot_id, encoded))
                cursor.execute("""
                    DELETE FROM pitchshift.snapshots WHERE content_sha256 NOT IN (
                        SELECT content_sha256 FROM pitchshift.snapshots
                        ORDER BY created_at DESC, content_sha256 LIMIT %s
                    )
                """, (MAX_SNAPSHOTS,))
                cursor.execute("""
                    DELETE FROM pitchshift.pitches WHERE game_date < (
                        SELECT max(game_date) - %s FROM pitchshift.pitches
                    )
                """, (RETENTION_DAYS,))
                cursor.execute("""
                    DELETE FROM pitchshift.pitches WHERE (game_pk, at_bat_number, pitch_number) IN (
                        SELECT game_pk, at_bat_number, pitch_number FROM pitchshift.pitches
                        ORDER BY game_date DESC, game_pk DESC, at_bat_number DESC, pitch_number DESC
                        OFFSET %s
                    )
                """, (MAX_PITCHES,))
                cursor.execute("SELECT count(*) FROM pitchshift.pitches")
                stored = cursor.fetchone()[0]
    except Exception as exc:
        raise DatabaseError(f"Postgres persistence failed ({type(exc).__name__}); credentials withheld.") from None
    return {"status": "saved", "snapshotId": snapshot_id, "storedPitches": stored,
            "skippedRows": skipped, "schema": "pitchshift"}

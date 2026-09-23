"""Transparent, descriptive screening of disjoint Statcast pitch windows.

The intervals describe sampling uncertainty under an independent-pitch model.
They are exploratory, unadjusted for multiple comparisons, and do not establish
a persistent change, a change date, causality, or a probability of improvement.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from math import isfinite, sqrt
from statistics import mean, variance
from typing import Any


PITCH_TYPES = {
    "FF": ("Four-seam fastball", "#61d8ad"),
    "SI": ("Sinker", "#ffc66d"),
    "FC": ("Cutter", "#ed91ca"),
    "SL": ("Slider", "#84a9ff"),
    "ST": ("Sweeper", "#bf9aff"),
    "CU": ("Curveball", "#fb927c"),
    "KC": ("Knuckle curve", "#e49d61"),
    "CH": ("Changeup", "#72d8e4"),
    "FS": ("Splitter", "#f1d87a"),
    "FO": ("Forkball", "#f1d87a"),
    "KN": ("Knuckleball", "#b3bac7"),
    "SV": ("Slurve", "#c6b4f5"),
    "EP": ("Eephus", "#b3bac7"),
    "UN": ("Unclassified", "#b3bac7"),
}
PHYSICAL = (
    ("velocity", "Velocity", "release_speed", 1, "mph", 0.8),
    ("release_x", "Release side", "release_pos_x", 12, "in", 1.0),
    ("release_z", "Release height", "release_pos_z", 12, "in", 1.0),
    ("horizontal_break", "Horizontal movement", "pfx_x", 12, "in", 1.5),
    ("vertical_break", "Vertical movement", "pfx_z", 12, "in", 1.5),
)
WHIFFS = {"swinging_strike", "swinging_strike_blocked", "missed_bunt", "swinging_pitchout"}
SWINGS = WHIFFS | {
    "foul", "foul_tip", "foul_bunt", "bunt_foul_tip",
    "hit_into_play", "hit_into_play_no_out", "hit_into_play_score", "foul_pitchout",
}
NON_PITCHES = {"automatic_ball", "automatic_strike"}
KNOWN_ZONES = set(range(1, 10)) | {11, 12, 13, 14}
INTERVAL_NOTE = (
    "Exploratory 95% intervals treat pitches as independent; pitches within an "
    "appearance may be correlated. Intervals are not adjusted for the many "
    "pitchers, pitch types, metrics, or overlapping refreshes screened. Review "
    "flags are descriptive leads, not confirmed changes or probabilities."
)


def _number(value: Any) -> float | None:
    try:
        result = float(value)
        return result if isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    result = _number(value)
    return int(result) if result is not None and result.is_integer() else None


def _values(rows: list[dict], field: str, multiplier: float = 1) -> list[float]:
    return [value * multiplier for row in rows if (value := _number(row.get(field))) is not None]


def _rounded(value: float | None) -> float | None:
    return round(value, 4) if value is not None and isfinite(value) else None


def _wilson(successes: int, total: int) -> tuple[float, float]:
    """Wilson score bounds; remain nondegenerate at zero/all successes."""
    z = 1.959963984540054
    fraction = successes / total
    denominator = 1 + z * z / total
    center = (fraction + z * z / (2 * total)) / denominator
    half = z * sqrt(fraction * (1 - fraction) / total + z * z / (4 * total * total)) / denominator
    return max(0, center - half), min(1, center + half)


def _mean_interval(before: list[float], after: list[float]) -> tuple[float, float]:
    """Approximate Welch interval, with a t-quantile expansion for df >= 19."""
    base_term = variance(before) / len(before)
    recent_term = variance(after) / len(after)
    standard_error = sqrt(base_term + recent_term)
    difference = mean(after) - mean(before)
    if not standard_error:
        return difference, difference
    degrees = (base_term + recent_term) ** 2 / (
        base_term ** 2 / (len(before) - 1) + recent_term ** 2 / (len(after) - 1)
    )
    z = 1.959963984540054
    t = z + (z ** 3 + z) / (4 * degrees) + (5 * z ** 5 + 16 * z ** 3 + 3 * z) / (96 * degrees ** 2)
    return difference - t * standard_error, difference + t * standard_error


def _comparison(pitch_type: str, metric: str, label: str, unit: str,
                baseline: float, recent: float, baseline_n: int, recent_n: int,
                interval: tuple[float, float], threshold: float, score: float | None,
                method: str) -> dict:
    difference = recent - baseline
    candidate = abs(difference) >= threshold and (interval[0] > 0 or interval[1] < 0)
    direction = "higher" if difference > 0 else "lower" if difference < 0 else "unchanged"
    if metric in {"release_x", "horizontal_break"}:
        direction = "more positive" if difference > 0 else "more negative" if difference < 0 else "unchanged"
    interpretation = f"Recent {label.lower()} is {direction} than the preceding window."
    if metric in {"release_x", "horizontal_break"}:
        interpretation += " Horizontal values use the catcher's coordinate perspective."
    if candidate:
        interpretation += " Meets the exploratory review rule; verify across appearances and scouting context."
    else:
        interpretation += " Does not meet the exploratory review rule."
    return {
        "pitchType": pitch_type, "pitchName": PITCH_TYPES.get(pitch_type, (pitch_type, ""))[0],
        "metric": metric, "label": label, "unit": unit,
        "baseline": _rounded(baseline), "recent": _rounded(recent), "delta": _rounded(difference),
        "baselineN": baseline_n, "recentN": recent_n,
        "score": _rounded(score), "interval": [_rounded(value) for value in interval],
        "practicalThreshold": threshold, "interpretation": interpretation,
        "review": candidate, "intervalMethod": method,
    }


def _rate(pitch_type: str, metric: str, label: str, baseline_success: int,
          baseline_n: int, recent_success: int, recent_n: int, threshold: float,
          minimum_base: int = 50, minimum_recent: int = 20) -> dict | None:
    if baseline_n < minimum_base or recent_n < minimum_recent:
        return None
    before, after = baseline_success / baseline_n, recent_success / recent_n
    base_low, base_high = _wilson(baseline_success, baseline_n)
    recent_low, recent_high = _wilson(recent_success, recent_n)
    difference = after - before
    # Newcombe's independent-proportion interval combines Wilson bounds.
    interval = (
        100 * (difference - sqrt((after - recent_low) ** 2 + (base_high - before) ** 2)),
        100 * (difference + sqrt((recent_high - after) ** 2 + (before - base_low) ** 2)),
    )
    result = _comparison(pitch_type, metric, label, "pp", 100 * before, 100 * after,
                         baseline_n, recent_n, interval, threshold,
                         abs(100 * difference) / threshold, "Newcombe / Wilson 95% (unadjusted)")
    result.update(baselineSuccess=baseline_success, recentSuccess=recent_success)
    return result


def _pitch_name(value: Any) -> str:
    text = str(value or "Unknown pitcher").strip()
    return " ".join(part.strip() for part in reversed(text.split(",", 1))) if "," in text else text


def _date_range(rows: list[dict]) -> tuple[str | None, str | None]:
    dates = sorted(str(row.get("game_date", ""))[:10] for row in rows if row.get("game_date"))
    return (dates[0], dates[-1]) if dates else (None, None)


def _point(row: dict) -> dict:
    return {"type": row["pitch_type"], "x": _rounded((_number(row.get("pfx_x")) or 0) * 12) if _number(row.get("pfx_x")) is not None else None,
            "z": _rounded((_number(row.get("pfx_z")) or 0) * 12) if _number(row.get("pfx_z")) is not None else None,
            "px": _number(row.get("plate_x")), "pz": _number(row.get("plate_z"))}


def _player_metadata(metadata: dict, pitcher_id: int) -> dict:
    players = metadata.get("players", {})
    if isinstance(players, list):
        return next((player for player in players if _integer(player.get("id", player.get("mlbam_id"))) == pitcher_id), {})
    if isinstance(players, dict):
        value = players.get(str(pitcher_id), players.get(pitcher_id, {}))
        return {"name": value} if isinstance(value, str) else value if isinstance(value, dict) else {}
    return {}


def _pitcher_report(pitcher_id: int, rows: list[dict], window: int, metadata: dict) -> dict:
    recent = rows[-window:]
    baseline = rows[max(0, len(rows) - window - 500):max(0, len(rows) - window)]
    baseline_start, baseline_end = _date_range(baseline)
    recent_start, recent_end = _date_range(recent)
    context = _player_metadata(metadata, pitcher_id)
    latest = rows[-1]
    team = context.get("team", latest.get("team"))
    if not team:
        team = latest.get("home_team") if latest.get("inning_topbot") == "Top" else latest.get("away_team") if latest.get("inning_topbot") == "Bot" else None
    sufficient = len(baseline) >= 300 and len(recent) >= window
    metrics, arsenal = [], []
    for pitch_type in sorted({row["pitch_type"] for row in baseline + recent}):
        before = [row for row in baseline if row["pitch_type"] == pitch_type]
        after = [row for row in recent if row["pitch_type"] == pitch_type]
        name, color = PITCH_TYPES.get(pitch_type, (pitch_type, "#b3bac7"))
        base_velocity, recent_velocity = _values(before, "release_speed"), _values(after, "release_speed")
        arsenal.append({
            "pitchType": pitch_type, "name": name, "color": color,
            "baselineCount": len(before), "recentCount": len(after),
            "baselineUsage": _rounded(100 * len(before) / len(baseline)) if baseline else None,
            "recentUsage": _rounded(100 * len(after) / len(recent)) if recent else None,
            "baselineVelocity": _rounded(mean(base_velocity)) if base_velocity else None,
            "recentVelocity": _rounded(mean(recent_velocity)) if recent_velocity else None,
        })
        if not sufficient:
            continue
        for key, label, field, multiplier, unit, threshold in PHYSICAL:
            base_values, recent_values = _values(before, field, multiplier), _values(after, field, multiplier)
            if len(base_values) < 50 or len(recent_values) < 20:
                continue
            baseline_mean, recent_mean = mean(base_values), mean(recent_values)
            baseline_sd = sqrt(variance(base_values))
            score = abs(recent_mean - baseline_mean) / baseline_sd if baseline_sd else None
            metrics.append(_comparison(pitch_type, key, label, unit, baseline_mean, recent_mean,
                                       len(base_values), len(recent_values), _mean_interval(base_values, recent_values),
                                       threshold, score, "Approximate Welch 95% (unadjusted)"))
        rates = [_rate(pitch_type, "usage", "Pitch usage", len(before), len(baseline), len(after), len(recent), 8, 300, window)]
        for hand, suffix in (("L", "lhb"), ("R", "rhb")):
            base_hand = [row for row in baseline if row.get("stand") == hand]
            recent_hand = [row for row in recent if row.get("stand") == hand]
            rates.append(_rate(pitch_type, f"usage_{suffix}", f"Usage vs {suffix.upper()}",
                               sum(row["pitch_type"] == pitch_type for row in base_hand), len(base_hand),
                               sum(row["pitch_type"] == pitch_type for row in recent_hand), len(recent_hand), 12))
        # Untracked zones are missing, not pitches outside the strike zone.
        base_zones = [zone for row in before if (zone := _integer(row.get("zone"))) in KNOWN_ZONES]
        recent_zones = [zone for row in after if (zone := _integer(row.get("zone"))) in KNOWN_ZONES]
        rates.append(_rate(pitch_type, "zone", "Zone rate", sum(zone <= 9 for zone in base_zones), len(base_zones),
                           sum(zone <= 9 for zone in recent_zones), len(recent_zones), 10))
        base_swings = [row for row in before if row.get("description") in SWINGS]
        recent_swings = [row for row in after if row.get("description") in SWINGS]
        rates.append(_rate(pitch_type, "whiff", "Whiff rate", sum(row.get("description") in WHIFFS for row in base_swings), len(base_swings),
                           sum(row.get("description") in WHIFFS for row in recent_swings), len(recent_swings), 12))
        metrics.extend(rate for rate in rates if rate is not None)
    alerts = sorted((metric for metric in metrics if metric["review"]),
                    key=lambda metric: abs(metric["delta"]) / metric["practicalThreshold"], reverse=True)
    timeline_groups = defaultdict(list)
    for row in baseline + recent:
        timeline_groups[(str(row.get("game_date", ""))[:10], row["pitch_type"])].append(row)
    timeline = []
    for (date, pitch_type), pitches in sorted(timeline_groups.items()):
        velocities = _values(pitches, "release_speed")
        timeline.append({"date": date, "pitchType": pitch_type, "velocity": _rounded(mean(velocities)) if velocities else None,
                         "count": len(pitches), "velocityCount": len(velocities)})
    warnings = []
    recent_games = len({row.get("game_pk", row.get("game_date")) for row in recent})
    baseline_games = len({row.get("game_pk", row.get("game_date")) for row in baseline})
    if recent_games < 3:
        warnings.append("Recent window covers fewer than 3 appearances; one outing may drive the screen.")
    years = {str(row.get("game_date", ""))[:4] for row in baseline + recent}
    if any(year and year < "2026" for year in years) and any(year >= "2026" for year in years):
        warnings.append("Location convention changes across 2025/2026: front-of-plate becomes middle-of-plate. Interpret location comparisons cautiously.")
    if not sufficient:
        warnings.append(f"Requires {window} recent pitches and at least 300 preceding pitches; unavailable comparisons are omitted.")
    return {
        "id": pitcher_id, "name": _pitch_name(context.get("name", latest.get("player_name"))),
        "team": team or "MLB", "throws": context.get("throws", latest.get("p_throws")) or "?",
        "recentCount": len(recent), "baselineCount": len(baseline),
        "baselineStart": baseline_start, "baselineEnd": baseline_end, "recentStart": recent_start, "recentEnd": recent_end,
        "baselineAppearances": baseline_games, "recentAppearances": recent_games,
        "status": "review" if alerts else "stable" if sufficient and metrics else "insufficient",
        "alerts": alerts, "arsenal": sorted(arsenal, key=lambda pitch: pitch["recentCount"], reverse=True),
        "metrics": metrics, "points": {"baseline": [_point(row) for row in baseline], "recent": [_point(row) for row in recent]},
        "timeline": timeline, "warnings": warnings,
    }


def build_report(rows: list[dict], metadata: dict | None = None) -> dict:
    """Build a JSON-safe report from raw CSV dictionaries or typed Statcast rows.

    Metadata may contain ``players`` keyed by MLBAM id, plus source fields.
    Physical observation counts exclude missing measurements. Unknown event
    descriptions never silently become swings, and nulls are never zero-filled.
    """
    metadata = metadata or {}
    grouped = defaultdict(list)
    seen = set()
    cleaned = []
    excluded = duplicates = 0
    for supplied in rows:
        row = dict(supplied)
        pitcher_id = _integer(row.get("pitcher", row.get("pitcher_id")))
        if pitcher_id is None or row.get("description") in NON_PITCHES:
            excluded += 1
            continue
        identity = (pitcher_id, _integer(row.get("game_pk")), _integer(row.get("at_bat_number")), _integer(row.get("pitch_number")))
        if all(value is not None for value in identity):
            if identity in seen:
                duplicates += 1
                continue
            seen.add(identity)
        row["pitch_type"] = str(row.get("pitch_type") or "UN")
        grouped[pitcher_id].append(row)
        cleaned.append(row)
    for pitches in grouped.values():
        pitches.sort(key=lambda row: (str(row.get("game_date", ""))[:10], _integer(row.get("game_pk")) or 0,
                                     _integer(row.get("at_bat_number")) or 0, _integer(row.get("pitch_number")) or 0))
    source = dict(metadata.get("source", {}))
    source.update({key: value for key, value in metadata.items() if key not in {"source", "players"}})
    data_start, data_end = _date_range(cleaned)
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    source.setdefault("name", "Baseball Savant / Statcast")
    source.setdefault("url", "https://baseballsavant.mlb.com/")
    # Analysis time is not evidence of source retrieval time.
    source.setdefault("retrievedAt", None)
    source.update(dataStart=data_start, dataEnd=data_end, pitchCount=len(cleaned), pitcherCount=len(grouped),
                  excludedRows=excluded, duplicateRows=duplicates)
    windows = {}
    for window in (100, 200):
        pitchers = [_pitcher_report(pitcher_id, pitches, window, metadata) for pitcher_id, pitches in grouped.items()]
        pitchers.sort(key=lambda pitcher: ({"review": 0, "stable": 1, "insufficient": 2}[pitcher["status"]],
                                           -len(pitcher["alerts"]), pitcher["name"]))
        windows[str(window)] = {"pitchers": pitchers}
    return {"schemaVersion": 1, "generatedAt": now, "source": source, "windows": windows,
            "methodology": {
                "baseline": "Up to 500 immediately preceding pitches; disjoint from the recent window.",
                "minimumBaseline": 300, "recentWindows": [100, 200],
                "minimumTypeBaseline": 50, "minimumTypeRecent": 20,
                "reviewRule": "Absolute delta reaches the practical threshold and its exploratory interval excludes zero.",
                "intervals": INTERVAL_NOTE,
                "score": "Physical metrics: absolute delta / baseline SD. Rates: absolute delta / practical threshold. Neither is a probability.",
                "whiff": "Misses / swings, including bunt attempts. Missing or unrecognized events are excluded from the denominator.",
                "zone": "Savant zones 1–9 / pitches with recognized zones 1–9 or 11–14.",
                "platoon": "Pitch-type usage conditional on recorded batter side; opponent and count mix are not adjusted.",
                "coordinates": "Movement and release in inches, catcher's perspective. Plate locations in feet. Horizontal signs are preserved.",
                "interpretation": "Screening thresholds are product heuristics, not validated baseball outcome cutoffs. Stable means no review flag under this rule, not evidence of no change.",
                "limitations": ["Within-appearance correlation may make intervals too narrow.",
                                "Pitch classification changes may mimic arsenal changes.",
                                "Opponent, count, park, tracking, health, and tactical context are not controlled.",
                                "Window dates do not identify when a change began."],
                "sources": ["https://baseballsavant.mlb.com/csv-docs",
                            "https://www.mlb.com/news/pitchers-with-strong-barrel-rate-and-whiff-rate-in-2023"],
            }}

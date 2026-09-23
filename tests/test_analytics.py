import json
import unittest
from pathlib import Path

from pitchshift.analytics import build_report


def make_rows(count=700):
    return [{"pitcher": 123, "player_name": "Example, Pat", "pitch_type": "FF", "p_throws": "R",
             "game_date": f"2026-08-{1 + i // 100:02}", "game_pk": i // 100 + 1,
             "at_bat_number": i // 5, "pitch_number": i % 5 + 1, "stand": "L" if i % 2 else "R",
             "release_speed": 94 + (i % 3) / 10, "release_pos_x": -2, "release_pos_z": 6,
             "pfx_x": -1, "pfx_z": 1.5, "plate_x": 0.5, "plate_z": 2.5,
             "zone": 5, "description": "called_strike", "home_team": "TOR", "inning_topbot": "Top"}
            for i in range(count)]


class AnalyticsTests(unittest.TestCase):
    def test_empty_is_json_safe(self):
        report = build_report([])
        self.assertEqual(report["windows"]["100"]["pitchers"], [])
        self.assertEqual(report["source"]["pitchCount"], 0)
        self.assertIsNone(report["source"]["dataEnd"])
        self.assertIsNone(report["source"]["retrievedAt"])
        json.dumps(report, allow_nan=False)

    def test_windows_disjoint_sorted_and_measurements_converted(self):
        rows = make_rows()
        for i, row in enumerate(rows):
            row["release_speed"] = i
        report = build_report(list(reversed(rows)))
        short = report["windows"]["100"]["pitchers"][0]
        longer = report["windows"]["200"]["pitchers"][0]
        velocity = next(metric for metric in short["metrics"] if metric["metric"] == "velocity")
        self.assertEqual((velocity["baseline"], velocity["recent"]), (349.5, 649.5))
        velocity = next(metric for metric in longer["metrics"] if metric["metric"] == "velocity")
        self.assertEqual((velocity["baseline"], velocity["recent"]), (249.5, 599.5))
        self.assertEqual(short["points"]["recent"][0]["x"], -12)
        self.assertEqual(short["name"], "Pat Example")
        self.assertEqual(short["team"], "TOR")

    def test_whiff_denominator_swings_not_pitches(self):
        rows = make_rows(600)
        for i, row in enumerate(rows):
            row["description"] = ["swinging_strike", "foul", "hit_into_play", "called_strike", "ball"][i % 5]
        pitcher = build_report(rows)["windows"]["100"]["pitchers"][0]
        whiff = next(metric for metric in pitcher["metrics"] if metric["metric"] == "whiff")
        self.assertEqual((whiff["baselineN"], whiff["recentN"]), (300, 60))
        self.assertAlmostEqual(whiff["recent"], 100 / 3, places=3)

    def test_missing_measurements_not_zero_and_unknown_zones_not_outside(self):
        rows = make_rows(600)
        for row in rows[-90:]:
            row["release_speed"] = "NaN"
            row["zone"] = ""
        pitcher = build_report(rows)["windows"]["100"]["pitchers"][0]
        self.assertNotIn("velocity", {metric["metric"] for metric in pitcher["metrics"]})
        self.assertNotIn("zone", {metric["metric"] for metric in pitcher["metrics"]})
        json.dumps(pitcher, allow_nan=False)

    def test_small_windows_insufficient_and_no_alerts(self):
        pitcher = build_report(make_rows(399))["windows"]["100"]["pitchers"][0]
        self.assertEqual(pitcher["status"], "insufficient")
        self.assertEqual(pitcher["alerts"], [])
        self.assertEqual(pitcher["baselineCount"], 299)

    def test_duplicate_pitches_are_removed(self):
        rows = make_rows(600)
        report = build_report(rows + rows[-10:])
        self.assertEqual(report["source"]["pitchCount"], 600)
        self.assertEqual(report["source"]["duplicateRows"], 10)

    def test_new_pitch_usage_has_valid_nonzero_interval_at_zero(self):
        rows = make_rows(600)
        for row in rows[-30:]:
            row["pitch_type"] = "FS"
        pitcher = build_report(rows)["windows"]["100"]["pitchers"][0]
        usage = next(metric for metric in pitcher["alerts"] if metric["pitchType"] == "FS" and metric["metric"] == "usage")
        self.assertEqual((usage["baseline"], usage["recent"]), (0, 30))
        self.assertLess(usage["interval"][0], 30)
        self.assertGreater(usage["interval"][1], 30)
        self.assertFalse(any(metric["metric"] == "velocity" and metric["pitchType"] == "FS" for metric in pitcher["metrics"]))

    def test_unchanged_arsenal_is_stable_and_threshold_blocks_tiny_shift(self):
        rows = make_rows(600)
        for row in rows[-100:]:
            row["release_speed"] += 0.2
        pitcher = build_report(rows)["windows"]["100"]["pitchers"][0]
        self.assertEqual(pitcher["status"], "stable")

    def test_platoon_usage_conditions_on_batter_side(self):
        rows = make_rows(600)
        for row in rows:
            row["pitch_type"] = "FS" if row["stand"] == "L" else "FF"
        pitcher = build_report(rows)["windows"]["100"]["pitchers"][0]
        usage = next(metric for metric in pitcher["metrics"] if metric["metric"] == "usage_lhb" and metric["pitchType"] == "FS")
        self.assertEqual((usage["baselineN"], usage["recentN"]), (250, 50))
        self.assertEqual((usage["baseline"], usage["recent"]), (100, 100))

    def test_automatic_calls_excluded_but_physical_pitchouts_retained(self):
        rows = make_rows(600)
        rows[0]["description"] = "automatic_ball"
        rows[1]["description"] = "pitchout"
        report = build_report(rows)
        self.assertEqual(report["source"]["pitchCount"], 599)
        self.assertEqual(report["source"]["excludedRows"], 1)

    def test_pinned_2026_snapshot_reproduces_independently_counted_findings(self):
        from pitchshift.ingest import read_csv, validate_rows
        fixture = Path(__file__).resolve().parents[1] / "data/snapshots/statcast-2026-09-22.csv.gz"
        rows = validate_rows(read_csv(fixture), 2026)
        report = build_report(rows)
        self.assertEqual((len(rows), report["source"]["pitchCount"], report["source"]["excludedRows"]), (17244, 17240, 4))
        pitchers = {pitcher["id"]: pitcher for pitcher in report["windows"]["100"]["pitchers"]}
        gausman = pitchers[592332]
        splitter = next(metric for metric in gausman["metrics"] if metric["pitchType"] == "FS" and metric["metric"] == "usage")
        self.assertEqual((splitter["baselineSuccess"], splitter["recentSuccess"]), (197, 56))
        self.assertEqual((splitter["baselineN"], splitter["recentN"]), (500, 100))
        self.assertEqual((splitter["baseline"], splitter["recent"], splitter["delta"]), (39.4, 56.0, 16.6))
        self.assertEqual((gausman["recentStart"], gausman["recentEnd"]), ("2026-09-09", "2026-09-15"))
        cease_fastball = next(metric for metric in pitchers[656302]["metrics"] if metric["pitchType"] == "FF" and metric["metric"] == "velocity")
        self.assertEqual((cease_fastball["baselineN"], cease_fastball["recentN"]), (180, 44))
        self.assertAlmostEqual(cease_fastball["baseline"], 95.4906, places=4)
        self.assertAlmostEqual(cease_fastball["recent"], 94.0023, places=4)


if __name__ == "__main__":
    unittest.main()

"""Publishing safeguards exercised against temporary files, without services."""

import argparse
import contextlib
import csv
import gzip
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pitchshift import pipeline
from pitchshift.ingest import COLUMNS


def csv_fixture(count=600, split_at=None):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=COLUMNS)
    writer.writeheader()
    for index in range(count):
        writer.writerow({
            "game_date": f"2026-08-{1 + index // 100:02}",
            "game_pk": 800000 + index // 100,
            "at_bat_number": 1 + (index % 100) // 5,
            "pitch_number": 1 + index % 5,
            "pitcher": 123 if split_at is None or index < split_at else 456,
            "player_name": "Example, Pat", "pitch_type": "FF",
            "game_type": "R", "game_year": 2026, "release_speed": 94.0,
            "release_pos_x": -2, "release_pos_z": 6, "pfx_x": -1, "pfx_z": 1.5,
            "plate_x": 0.2, "plate_z": 2.5, "zone": 5,
            "description": "called_strike", "stand": "L", "p_throws": "R",
        })
    return output.getvalue().encode("utf-8")


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.pinned = self.root / "data/snapshots/statcast-2026-09-22.csv.gz"
        self.pinned.parent.mkdir(parents=True)
        self.provenance_path = self.pinned.parent / "provenance.json"
        self.provenance_path.write_text(json.dumps({"retrieved_at_utc": "2026-09-23T01:00:00Z"}), encoding="utf-8")
        self.input = self.root / "custom.csv"
        self.input.write_bytes(csv_fixture())
        self.output = self.root / "public/report.json"
        self.output.parent.mkdir()
        self.previous = b'{"lastKnownGood":true}\n'
        self.output.write_bytes(self.previous)
        self.args = argparse.Namespace(
            refresh=False, input=self.input, output=self.output, provenance=None,
            season=2026, start=None, end=None, sync_db=False,
        )
        self.addCleanup(patch.stopall)
        patch.object(pipeline, "ROOT", self.root).start()
        patch.object(pipeline, "DEFAULT_INPUT", self.pinned).start()
        self.fetch = patch.object(pipeline, "fetch_cohort", side_effect=AssertionError("Unexpected network request")).start()
        self.persist = patch("pitchshift.database.persist_snapshot", side_effect=AssertionError("Unexpected database write")).start()

    def run_pipeline(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return pipeline.run(self.args)

    def test_custom_input_without_sidecar_does_not_borrow_pinned_provenance(self):
        report = self.run_pipeline()
        self.assertIsNone(report["source"]["retrievedAt"])
        self.assertEqual(json.loads(self.output.read_text(encoding="utf-8"))["source"]["retrievedAt"], None)
        self.assertEqual(report["source"]["pitchCount"], 600)

    def test_custom_input_uses_its_own_provenance_sidecar(self):
        retrieved = "2026-08-08T12:34:56Z"
        self.input.with_suffix(".provenance.json").write_text(
            json.dumps({"retrieved_at_utc": retrieved}), encoding="utf-8")
        self.assertEqual(self.run_pipeline()["source"]["retrievedAt"], retrieved)

    def test_pinned_gzip_hash_checks_uncompressed_source(self):
        source = csv_fixture()
        self.pinned.write_bytes(gzip.compress(source))
        self.provenance_path.write_text(json.dumps({
            "csv_sha256": hashlib.sha256(source).hexdigest(),
            "retrieved_at_utc": "2026-09-23T01:00:00Z",
        }), encoding="utf-8")
        self.args.input = self.pinned
        report = self.run_pipeline()
        self.assertEqual(report["source"]["retrievedAt"], "2026-09-23T01:00:00Z")
        self.assertEqual(report["source"]["sourceRowCount"], 600)

    def test_altered_pinned_source_is_rejected_and_existing_output_preserved(self):
        source = csv_fixture()
        altered = source.replace(b"94.0", b"95.0", 1)
        self.assertNotEqual(source, altered)
        self.pinned.write_bytes(gzip.compress(altered))
        self.provenance_path.write_text(json.dumps({"csv_sha256": hashlib.sha256(source).hexdigest()}), encoding="utf-8")
        self.args.input = self.pinned
        with self.assertRaisesRegex(ValueError, "hash differs"):
            self.run_pipeline()
        self.assertEqual(self.output.read_bytes(), self.previous)
        self.persist.assert_not_called()

    def test_both_analysis_windows_need_an_eligible_pitcher(self):
        # 400 pitches qualify for recent100/prior300, but not recent200/prior300.
        # The other 200 pitches satisfy the input volume check, not eligibility.
        self.input.write_bytes(csv_fixture(split_at=400))
        with self.assertRaisesRegex(ValueError, "eligible pitcher in both"):
            self.run_pipeline()
        self.assertEqual(self.output.read_bytes(), self.previous)
        self.persist.assert_not_called()

    def test_failed_refresh_preserves_previous_public_snapshot(self):
        self.args.refresh = True
        self.args.start = "2026-06-01"
        self.args.end = "2026-09-22"
        self.fetch.side_effect = RuntimeError("Source unavailable")
        with self.assertRaisesRegex(RuntimeError, "Source unavailable"):
            self.run_pipeline()
        self.assertEqual(self.output.read_bytes(), self.previous)
        self.assertFalse(self.output.with_suffix(".tmp").exists())
        self.persist.assert_not_called()

    def test_local_publish_never_uses_optional_database_or_network(self):
        report = self.run_pipeline()
        self.fetch.assert_not_called()
        self.persist.assert_not_called()
        self.assertEqual(report["source"]["pitcherCount"], 1)
        self.assertNotEqual(self.output.read_bytes(), self.previous)
        self.assertFalse(self.output.with_suffix(".tmp").exists())


if __name__ == "__main__":
    unittest.main()

"""Exercise the optional database boundary without a live account or credentials."""

from contextlib import ExitStack
import json
import os
from pathlib import Path
import tempfile
import traceback
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from pitchshift import database


TEST_URL = "postgresql://test_user:DO_NOT_DISCLOSE@ep-example.neon.tech/testdb"


def pitch(number=1, game_date="2026-09-22", **changes):
    return {
        "game_pk": "100", "at_bat_number": "1", "pitch_number": str(number),
        "game_date": game_date, "pitcher": "592332", "player_name": "Gausman, Kevin",
        "pitch_type": "FF", "release_speed": "95.5", **changes,
    }


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        # Never inherit a developer's real DATABASE_URL or load their local .env.
        self.stack.enter_context(patch.dict(os.environ, {}, clear=True))
        self.stack.enter_context(patch.object(database, "load_local_env"))
        self.connection = MagicMock()
        self.cursor = self.connection.__enter__.return_value.cursor.return_value.__enter__.return_value
        self.cursor.fetchone.return_value = (1,)
        self.connect = MagicMock(return_value=self.connection)
        self.stack.enter_context(patch.dict("sys.modules", {"psycopg": SimpleNamespace(connect=self.connect)}))

    def test_unconfigured_database_is_optional_and_does_not_connect(self):
        result = database.persist_snapshot({"test": True}, [pitch()])
        self.assertEqual(result["status"], "disabled")
        self.connect.assert_not_called()

    def test_status_exposes_provider_without_connection_identity(self):
        os.environ["DATABASE_URL"] = TEST_URL
        status = database.database_status()
        self.assertEqual(status, {"configured": True, "provider": "Neon", "schema": "pitchshift"})
        rendered = json.dumps(status)
        for private in ("DO_NOT_DISCLOSE", "test_user", "ep-example", "testdb"):
            self.assertNotIn(private, rendered)

    def test_invalid_url_does_not_echo_credential(self):
        with self.assertRaises(database.DatabaseError) as raised:
            database.persist_snapshot({}, database_url="https://test:DO_NOT_DISCLOSE@invalid.example")
        self.assertNotIn("DO_NOT_DISCLOSE", str(raised.exception))
        self.connect.assert_not_called()

    def test_report_size_bound_prevents_database_mutation(self):
        with patch.object(database, "MAX_REPORT_BYTES", 10):
            with self.assertRaises(database.DatabaseError):
                database.persist_snapshot({"large": "x" * 100}, database_url=TEST_URL)
        self.connect.assert_not_called()

    def test_success_uses_verified_tls_and_commits_one_transaction(self):
        unsafe_name = "Player'); DROP TABLE shared; --"
        result = database.persist_snapshot({"test": True}, [pitch(player_name=unsafe_name)], database_url=TEST_URL)
        self.assertEqual(result["status"], "saved")
        self.assertEqual(result["storedPitches"], 1)
        self.assertEqual(self.connect.call_args.kwargs["sslmode"], "verify-full")
        self.assertEqual(self.connect.call_args.kwargs["sslrootcert"], "system")
        self.connection.__exit__.assert_called_once_with(None, None, None)
        sql, parameters = self.cursor.executemany.call_args.args
        self.assertNotIn(unsafe_name, sql)
        self.assertEqual(parameters[0][5], unsafe_name)
        # Report insertion and all pruning happen before the same context commits.
        statements = [(call.args[0], call.args[1] if len(call.args) > 1 else None)
                      for call in self.cursor.execute.call_args_list]
        self.assertTrue(any("INSERT INTO pitchshift.snapshots" in sql for sql, _ in statements))
        prune = [(sql, args) for sql, args in statements if "DELETE FROM" in sql]
        self.assertEqual(len(prune), 3)
        self.assertTrue(all("DELETE FROM pitchshift." in sql for sql, _ in prune))
        self.assertEqual([args for _, args in prune], [(7,), (120,), (100_000,)])

    def test_failed_write_exits_transaction_with_error_and_redacts_traceback(self):
        failure = RuntimeError("Connection failed with " + TEST_URL)
        self.cursor.executemany.side_effect = failure
        try:
            database.persist_snapshot({"test": True}, [pitch()], database_url=TEST_URL)
        except database.DatabaseError as error:
            text = "".join(traceback.format_exception(error))
        else:
            self.fail("A failed database write must propagate as DatabaseError")
        self.assertNotIn("DO_NOT_DISCLOSE", text)
        self.assertNotIn(TEST_URL, text)
        self.assertIs(self.connection.__exit__.call_args.args[0], RuntimeError)
        self.assertIs(self.connection.__exit__.call_args.args[1], failure)
        self.assertFalse(any("INSERT INTO pitchshift.snapshots" in call.args[0]
                             for call in self.cursor.execute.call_args_list))

    def test_preinsert_retention_keeps_only_recent_bounded_rows(self):
        rows = [pitch(1, "2026-01-01"), pitch(2, "2026-09-20"),
                pitch(3, "2026-09-21"), pitch(4, "2026-09-22"), {}]
        with patch.object(database, "MAX_PITCHES", 2):
            result = database.persist_snapshot({}, rows, database_url=TEST_URL)
        retained = self.cursor.executemany.call_args.args[1]
        self.assertEqual([row[2] for row in retained], [4, 3])
        self.assertEqual(result["skippedRows"], 1)

    def test_date_retention_is_applied_before_insert(self):
        rows = [pitch(1, "2026-01-01"), pitch(2, "2026-09-22")]
        database.persist_snapshot({}, rows, database_url=TEST_URL)
        self.assertEqual([row[2] for row in self.cursor.executemany.call_args.args[1]], [2])

    def test_missing_measurements_and_unknown_pitch_type_stay_distinct_from_zero(self):
        row = database._pitch_row(pitch(pitch_type="", release_speed="NaN", pfx_x="0"))
        self.assertIsNotNone(row)
        self.assertEqual(row[6], "UN")
        self.assertIsNone(row[9])
        self.assertEqual(row[12], 0.0)
        self.assertIsNone(database._pitch_row(pitch(pitch_number="1.5")))


class LocalEnvironmentTests(unittest.TestCase):
    def test_local_env_preserves_process_values_and_literal_secret_punctuation(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"DATABASE_URL": "process-value"}, clear=True):
            path = Path(directory) / ".env"
            path.write_text('# ignored\nDATABASE_URL=local-value\nexport EXAMPLE_SECRET="a#b=c"\n', encoding="utf-8")
            database.load_local_env(path)
            self.assertEqual(os.environ["DATABASE_URL"], "process-value")
            self.assertEqual(os.environ["EXAMPLE_SECRET"], "a#b=c")


if __name__ == "__main__":
    unittest.main()

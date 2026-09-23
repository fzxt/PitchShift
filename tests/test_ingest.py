import unittest
from pitchshift.ingest import validate_rows


def row(**changes):
    return {'game_date': '2026-09-22', 'game_year': '2026', 'game_type': 'R', 'game_pk': '1', 'at_bat_number': '1', 'pitch_number': '1', 'pitcher': '592332', 'pitch_type': 'FF', 'release_speed': '95', **changes}


class IngestionTests(unittest.TestCase):
    def test_exact_duplicates_are_idempotent(self):
        self.assertEqual(len(validate_rows([row(), row()], 2026)), 1)

    def test_conflicting_duplicates_fail_closed(self):
        with self.assertRaisesRegex(ValueError, 'Conflicting duplicate'):
            validate_rows([row(), row(release_speed='96')], 2026)

    def test_cross_season_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'mixes seasons'):
            validate_rows([row(game_date='2025-09-22', game_year='2025')], 2026)

    def test_non_regular_season_is_excluded(self):
        self.assertEqual(len(validate_rows([row(), row(game_pk='2', game_type='S')], 2026)), 1)

    def test_invalid_identity_rejected(self):
        with self.assertRaisesRegex(ValueError, 'identity'):
            validate_rows([row(pitch_number='not-a-number')], 2026)

    def test_fractional_or_nonfinite_identity_rejected(self):
        for invalid in ('1.5', 'NaN', 'inf', '-1', '0'):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, 'identity'):
                validate_rows([row(pitch_number=invalid)], 2026)

    def test_empty_input_fails(self):
        with self.assertRaisesRegex(ValueError, 'No regular-season'):
            validate_rows([], 2026)

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from f1_telemetry_charts.analysis import playback
from f1_telemetry_charts.analysis.workspace import _read_snapshot_dataset_cached


FIXTURE_PATH = Path("tests/fixtures/2023_bahrain_race_dataset.json")


class PlaybackCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        playback.clear_playback_caches()
        _read_snapshot_dataset_cached.cache_clear()

    def tearDown(self) -> None:
        playback.clear_playback_caches()
        _read_snapshot_dataset_cached.cache_clear()

    def test_snapshot_dataset_cache_reuses_validated_model_by_hash(self) -> None:
        path = FIXTURE_PATH.resolve()

        first = _read_snapshot_dataset_cached(path, "fixture-hash")
        second = _read_snapshot_dataset_cached(path, "fixture-hash")

        self.assertIs(first, second)
        self.assertEqual(_read_snapshot_dataset_cached.cache_info().hits, 1)

    def test_playback_preparation_and_identical_frame_are_cached(self) -> None:
        dataset = _read_snapshot_dataset_cached(FIXTURE_PATH.resolve(), "fixture-hash")
        original_prepare = playback._prepare_mini_sectors

        with patch.object(
            playback,
            "_prepare_mini_sectors",
            wraps=original_prepare,
        ) as prepare:
            lap_one = playback.build_playback_payload(
                dataset,
                cache_key="fixture-hash",
                mode="lap",
                cursor=1,
                max_frames=1,
            )
            lap_two = playback.build_playback_payload(
                dataset,
                cache_key="fixture-hash",
                mode="lap",
                cursor=2,
                max_frames=1,
            )
            lap_one_again = playback.build_playback_payload(
                dataset,
                cache_key="fixture-hash",
                mode="lap",
                cursor=1,
                max_frames=1,
            )

        self.assertEqual(prepare.call_count, 1)
        self.assertIs(lap_one, lap_one_again)
        self.assertEqual(lap_one.frames[0].lap_number, 1)
        self.assertEqual(lap_two.frames[0].lap_number, 2)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from f1_telemetry_charts.analysis.observations import Observation
from f1_telemetry_charts.analysis.report import (
    apply_observation_review,
    render_markdown_draft,
)
from f1_telemetry_charts.analysis.orchestrator import run_analysis
from f1_telemetry_charts.config.validation import validate_config


class AnalysisReportTests(unittest.TestCase):
    def test_run_analysis_writes_v1_report_package_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_analysis(_config(Path(temp_dir)))

            self.assertIsNotNone(result.observations_path)
            self.assertIsNotNone(result.review_path)
            self.assertIsNotNone(result.markdown_path)
            self.assertTrue(result.observations_path and result.observations_path.is_file())
            self.assertTrue(result.review_path and result.review_path.is_file())
            self.assertTrue(result.markdown_path and result.markdown_path.is_file())

            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            observations = json.loads(
                result.observations_path.read_text(encoding="utf-8")
            )
            draft = result.markdown_path.read_text(encoding="utf-8")

        self.assertEqual(manifest["observations_path"], "observations.json")
        self.assertEqual(manifest["review_path"], "review.json")
        self.assertEqual(manifest["markdown_path"], "draft.md")
        self.assertGreaterEqual(len(observations), 3)
        first = observations[0]
        self.assertIn("observation_id", first)
        self.assertIn("evidence", first)
        self.assertIn("metrics", first)
        self.assertIn("limitations", first)
        self.assertEqual(first["review_status"], "unreviewed")
        self.assertIn("## Observations", draft)

    def test_rejected_observations_are_excluded_from_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_analysis(_config(Path(temp_dir)))
            observations = [
                Observation.model_validate(item)
                for item in json.loads(
                    result.observations_path.read_text(encoding="utf-8")
                )
            ]

        rejected_text = observations[0].text
        reviewed = apply_observation_review(
            observations,
            observations[0].observation_id,
            "rejected",
        )
        draft = render_markdown_draft(result.manifest, reviewed)

        self.assertNotIn(rejected_text, draft)
        self.assertIn("## Observations", draft)


def _config(output_dir: Path):
    return validate_config(
        {
            "schema_version": 1,
            "project_id": "report-test",
            "output_dir": str(output_dir),
            "session": {
                "season": 2023,
                "event": "Bahrain Grand Prix",
                "session": "Race",
            },
            "driver_selection": {"drivers": ["VER", "PER", "ALO"]},
            "data_cache": {
                "fixture_path": "tests/fixtures/2023_bahrain_race_dataset.json"
            },
            "recipes": [
                {"recipe_id": "lap_time_delta"},
                {"recipe_id": "telemetry_trace"},
                {"recipe_id": "tyre_strategy"},
                {"recipe_id": "position_progression"},
            ],
        }
    )


if __name__ == "__main__":
    unittest.main()

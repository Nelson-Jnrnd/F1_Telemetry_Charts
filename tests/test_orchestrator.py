from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from f1_telemetry_charts.analysis.orchestrator import run_analysis
from f1_telemetry_charts.config.models import ProjectConfig
from f1_telemetry_charts.config.validation import validate_config


class OrchestratorTests(unittest.TestCase):
    def test_run_analysis_writes_manifest_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _config(Path(temp_dir), recipe_ids=["lap_time_delta"])

            result = run_analysis(config)

            self.assertEqual(result.status, "succeeded")
            self.assertTrue(result.manifest_path.exists())
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["status"], "succeeded")
        self.assertEqual(manifest["requested_recipes"], ["lap_time_delta"])
        self.assertEqual(len(manifest["artifacts"]), 1)
        self.assertEqual(manifest["recipes"][0]["status"], "produced")

    def test_run_analysis_preserves_successful_artifacts_on_recipe_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture_path = Path(temp_dir) / "no-telemetry.json"
            raw_fixture = json.loads(
                Path("tests/fixtures/2023_bahrain_race_dataset.json").read_text(
                    encoding="utf-8"
                )
            )
            raw_fixture["telemetry"] = []
            fixture_path.write_text(json.dumps(raw_fixture), encoding="utf-8")
            config = _config(
                Path(temp_dir),
                recipe_ids=["lap_time_delta", "telemetry_trace"],
                fixture_path=fixture_path,
            )

            result = run_analysis(config)
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(result.status, "partially_succeeded")
        self.assertEqual(len(manifest["artifacts"]), 1)
        self.assertEqual(manifest["recipes"][0]["status"], "produced")
        self.assertEqual(manifest["recipes"][1]["status"], "failed")
        self.assertIn("telemetry_trace", manifest["errors"][0])

    def test_run_analysis_uses_deterministic_output_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _config(Path(temp_dir), recipe_ids=["lap_time_delta"])

            first = run_analysis(config)
            second = run_analysis(config)

        self.assertEqual(first.output_dir, second.output_dir)
        self.assertEqual(first.manifest.configuration_hash, second.manifest.configuration_hash)

    def test_manifest_paths_are_package_relative_and_outputs_stay_local(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            local_output_dir = Path(temp_dir)
            config = _config(local_output_dir, recipe_ids=["lap_time_delta"])

            result = run_analysis(config)
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

            artifact = manifest["artifacts"][0]
            for key in ("image_path", "metadata_path"):
                path = Path(artifact[key])
                self.assertFalse(path.is_absolute())
                self.assertTrue((result.output_dir / path).is_file())

            self.assertEqual(local_output_dir, result.output_dir.parent)

    def test_duplicate_recipe_requests_get_unique_artifact_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _config(
                Path(temp_dir),
                recipe_ids=["lap_time_delta", "lap_time_delta"],
            )

            result = run_analysis(config)
            artifact_ids = [
                artifact.artifact_id for artifact in result.manifest.artifacts
            ]

        self.assertEqual(len(artifact_ids), 2)
        self.assertEqual(len(set(artifact_ids)), 2)
        self.assertTrue(all("lap_time_delta" in item for item in artifact_ids))


def _config(
    output_dir: Path,
    recipe_ids: list[str],
    fixture_path: Path = Path("tests/fixtures/2023_bahrain_race_dataset.json"),
) -> ProjectConfig:
    return validate_config(
        {
            "schema_version": 1,
            "project_id": "test-bahrain",
            "output_dir": str(output_dir),
            "session": {
                "season": 2023,
                "event": "Bahrain Grand Prix",
                "session": "Race",
            },
            "driver_selection": {"drivers": ["VER", "PER", "ALO"]},
            "data_cache": {
                "fixture_path": str(fixture_path)
            },
            "recipes": [{"recipe_id": recipe_id} for recipe_id in recipe_ids],
        }
    )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from f1_telemetry_charts.llm import describe_artifact, generate_charts


class LlmContractTests(unittest.TestCase):
    def test_generate_charts_returns_package_relative_contract_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = generate_charts(
                {
                    "contract_version": "1.0",
                    "config": _config_payload(Path(temp_dir)),
                }
            )

            self.assertEqual(payload["status"], "succeeded")
            self.assertEqual(payload["contract_version"], "1.0")
            self.assertEqual(payload["manifest_path"], "manifest.json")
            self.assertEqual(payload["observations_path"], "observations.json")
            self.assertEqual(payload["markdown_path"], "draft.md")
            self.assertGreaterEqual(len(payload["artifacts"]), 1)
            self.assertFalse(Path(payload["artifacts"][0]["image_path"]).is_absolute())

    def test_describe_artifact_returns_metadata_without_local_output_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            generation = generate_charts(
                {
                    "contract_version": "1.0",
                    "config": _config_payload(Path(temp_dir)),
                }
            )
            manifest_path = (
                Path(temp_dir)
                / "llm-test"
                / generation["run_id"]
                / generation["manifest_path"]
            )
            artifact_id = generation["artifacts"][0]["artifact_id"]

            description = describe_artifact(
                {
                    "contract_version": "1.0",
                    "manifest_path": str(manifest_path),
                    "artifact_id": artifact_id,
                }
            )

        self.assertEqual(description["status"], "succeeded")
        artifact = description["artifact"]
        self.assertEqual(artifact["artifact_id"], artifact_id)
        self.assertFalse(Path(artifact["image_path"]).is_absolute())
        self.assertFalse(Path(artifact["metadata_path"]).is_absolute())
        self.assertIn("renderer", artifact["metadata"])

    def test_unsupported_contract_version_returns_structured_error(self) -> None:
        payload = generate_charts({"contract_version": "9.9", "config": {}})

        self.assertEqual(payload["status"], "incompatible_contract")
        self.assertEqual(payload["error"]["code"], "unsupported_contract_version")


def _config_payload(output_root: Path) -> dict:
    return {
        "schema_version": 1,
        "project_id": "llm-test",
        "output_dir": str(output_root / "llm-test"),
        "session": {
            "season": 2023,
            "event": "Bahrain Grand Prix",
            "session": "Race",
        },
        "driver_selection": {"drivers": ["VER", "PER"]},
        "data_cache": {
            "fixture_path": "tests/fixtures/2023_bahrain_race_dataset.json"
        },
        "recipes": [{"recipe_id": "lap_time_delta"}],
    }


if __name__ == "__main__":
    unittest.main()

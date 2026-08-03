from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from f1_telemetry_charts.analysis.workspace import AnalysisService
from f1_telemetry_charts.config.models import DataCacheConfig, SessionConfig
from f1_telemetry_charts.llm import (
    describe_artifact,
    generate_charts,
    inspect_analysis,
    update_analysis_chart_parameters,
)


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

    def test_analysis_contract_inspects_and_updates_chart_parameters(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "analysis"
            service = AnalysisService(root)
            analysis = service.create("LLM Analysis")
            analysis = service.add_session(
                analysis,
                session=SessionConfig(
                    season=2023,
                    event="Bahrain Grand Prix",
                    session="Race",
                ),
                drivers=["VER", "PER"],
                data_cache=DataCacheConfig(
                    fixture_path=Path("tests/fixtures/2023_bahrain_race_dataset.json")
                ),
            )
            analysis = service.add_chart(
                analysis,
                recipe_id="lap_time_delta",
                target_session_ids=[analysis.sessions[0].session_id],
                parameters={"title": "Initial"},
            )
            analysis = service.add_chart(
                analysis,
                recipe_id="telemetry_trace",
                target_session_ids=[analysis.sessions[0].session_id],
                parameters={
                    "selection": {
                        "driver_selection_mode": "selected",
                        "drivers": ["VER"],
                    },
                    "analysis": {
                        "metric": "speed_kph",
                        "distance_range_m": {"start": 50, "end": 150},
                    },
                    "chart": {"title": "Telemetry"},
                },
            )
            chart_id = analysis.charts[0].chart_instance_id
            telemetry_chart_id = analysis.charts[1].chart_instance_id

            inspected = inspect_analysis(
                {"contract_version": "1.0", "analysis_path": str(root)}
            )
            self.assertEqual(inspected["status"], "succeeded")
            self.assertEqual(inspected["analysis"]["analysis_id"], analysis.analysis_id)
            self.assertTrue(inspected["templates"])
            self.assertIn("parameter_schema", inspected["templates"][0])
            self.assertTrue(inspected["recipe_schemas"])
            self.assertEqual(
                inspected["coverage_bounds"]["sessions"][analysis.sessions[0].session_id]["laps"]["maximum"],
                2,
            )
            self.assertTrue(
                inspected["coverage_bounds"]["sessions"][analysis.sessions[0].session_id]["track_map"]["available"]
            )
            self.assertEqual(inspected["chart_instances"][0]["chart_instance_id"], chart_id)
            self.assertEqual(len(inspected["track_map_summaries"]), 1)
            track_map_summary = inspected["track_map_summaries"][0]
            self.assertEqual(track_map_summary["chart_instance_id"], telemetry_chart_id)
            self.assertEqual(track_map_summary["status"], "available")
            self.assertEqual(track_map_summary["source_driver"], "VER")
            self.assertEqual(track_map_summary["segment"]["start_distance_m"], 50)
            self.assertNotIn("points", track_map_summary)
            self.assertEqual(len(inspected["playback_summaries"]), 1)
            playback_summary = inspected["playback_summaries"][0]
            self.assertEqual(playback_summary["status"], "available")
            self.assertEqual(playback_summary["default_mode"], "lap")
            self.assertTrue(playback_summary["available_modes"]["time"]["available"])
            self.assertTrue(playback_summary["available_modes"]["lap"]["available"])
            self.assertNotIn("points", playback_summary)
            self.assertNotIn("frames", playback_summary)

            updated = update_analysis_chart_parameters(
                {
                    "contract_version": "1.0",
                    "analysis_path": str(root / "analysis.json"),
                    "chart_instance_id": chart_id,
                    "parameters": {"title": "Updated"},
                }
            )
            self.assertEqual(updated["status"], "succeeded")
            chart = updated["analysis"]["charts"][0]
            self.assertEqual(chart["parameters"]["chart"]["title"], "Updated")
            self.assertTrue(chart["stale"])

            rejected = update_analysis_chart_parameters(
                {
                    "contract_version": "1.0",
                    "analysis_path": str(root / "analysis.json"),
                    "chart_instance_id": chart_id,
                    "parameters": {
                        "selection": {
                            "driver_selection_mode": "selected",
                            "drivers": ["VER"],
                            "lap_range": {"start": 1, "end": 99},
                        }
                    },
                }
            )
            self.assertEqual(rejected["status"], "failed")
            self.assertEqual(rejected["error"]["code"], "analysis_update_failed")
            self.assertIn("lap_range", rejected["error"]["message"])


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

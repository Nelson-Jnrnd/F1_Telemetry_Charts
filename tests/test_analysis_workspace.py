from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from f1_telemetry_charts.analysis.workspace import AnalysisService
from f1_telemetry_charts.config.models import DataCacheConfig, SessionConfig
from f1_telemetry_charts.ui.server import create_app


class AnalysisWorkspaceTests(unittest.TestCase):
    def test_workspace_snapshots_chart_generation_presets_and_export(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "analysis"
            service = AnalysisService(root)
            analysis = service.create("Bahrain Race")
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

            session = analysis.sessions[0]
            self.assertEqual(session.load_state, "loaded")
            self.assertTrue((root / "sessions" / session.session_id / "snapshot.json").exists())
            self.assertTrue((root / "sessions" / session.session_id / "dataset.json").exists())

            broken_fixture = DataCacheConfig(fixture_path=Path("missing-fixture.json"))
            analysis = analysis.model_copy(
                update={
                    "sessions": [
                        session.model_copy(update={"data_cache": broken_fixture}, deep=True)
                    ]
                },
                deep=True,
            )
            analysis = service.add_chart(
                analysis,
                recipe_id="lap_time_delta",
                target_session_ids=[session.session_id],
                parameters={"title": "Race pace delta"},
            )
            chart = analysis.charts[0]
            analysis = service.generate_charts(analysis, [chart.chart_instance_id])
            chart = analysis.charts[0]
            self.assertEqual(chart.generation_state, "generated")
            self.assertTrue((root / chart.image_path).exists())
            self.assertTrue(chart.observations_stale)
            self.assertTrue(analysis.review_stale)

            analysis, preset = service.save_preset(
                analysis,
                recipe_id="lap_time_delta",
                display_name="Race Delta",
                parameters={"title": "Race pace delta"},
                scope="analysis",
            )
            self.assertEqual(preset.scope, "analysis")
            self.assertEqual(analysis.presets[0].display_name, "Race Delta")

            analysis = service.export_package(analysis)
            self.assertFalse(analysis.review_stale)
            self.assertTrue((root / "package" / "manifest.json").exists())

    def test_session_removal_requires_confirmation_and_removes_dependent_charts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "analysis"
            service = AnalysisService(root)
            analysis = service.create("Removal")
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
            session_id = analysis.sessions[0].session_id
            analysis = service.add_chart(
                analysis,
                recipe_id="lap_time_delta",
                target_session_ids=[session_id],
            )

            with self.assertRaises(ValueError):
                service.remove_session(analysis, session_id)

            analysis = service.remove_session(
                analysis,
                session_id,
                confirm_delete_dependents=True,
            )
            self.assertEqual(analysis.sessions, [])
            self.assertEqual(analysis.charts, [])


class AnalysisApiTests(unittest.TestCase):
    def test_recipe_metadata_endpoint_has_schema_without_open_analysis(self) -> None:
        client = TestClient(create_app())
        response = client.get("/api/analysis/recipes")

        self.assertEqual(response.status_code, 200, response.text)
        recipes = response.json()
        self.assertTrue(recipes)
        self.assertIn("parameter_schema", recipes[0])
        self.assertFalse(Path(".analysis").exists())

    def test_analysis_api_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "analysis"
            client = TestClient(create_app())

            created = client.post(
                "/api/analysis/create",
                json={"path": str(root), "name": "API Analysis"},
            )
            self.assertEqual(created.status_code, 200, created.text)
            self.assertEqual(created.json()["analysis"]["name"], "API Analysis")

            session_response = client.post(
                "/api/analysis/sessions",
                json={
                    "session": {
                        "season": 2023,
                        "event": "Bahrain Grand Prix",
                        "session": "Race",
                    },
                    "drivers": ["VER", "PER"],
                    "data_cache": {
                        "fixture_path": "tests/fixtures/2023_bahrain_race_dataset.json"
                    },
                },
            )
            self.assertEqual(session_response.status_code, 200, session_response.text)
            session_id = session_response.json()["analysis"]["sessions"][0]["session_id"]

            chart_response = client.post(
                "/api/analysis/charts",
                json={
                    "recipe_id": "lap_time_delta",
                    "target_session_ids": [session_id],
                    "parameters": {"title": "API Delta"},
                },
            )
            self.assertEqual(chart_response.status_code, 200, chart_response.text)
            chart_id = chart_response.json()["analysis"]["charts"][0]["chart_instance_id"]

            generated = client.post(
                "/api/analysis/charts/generate",
                json={"chart_ids": [chart_id]},
            )
            self.assertEqual(generated.status_code, 200, generated.text)
            self.assertEqual(
                generated.json()["analysis"]["charts"][0]["generation_state"],
                "generated",
            )

            preset_response = client.post(
                "/api/analysis/presets",
                json={
                    "recipe_id": "lap_time_delta",
                    "display_name": "API Delta",
                    "parameters": {"title": "API Delta"},
                    "scope": "analysis",
                },
            )
            self.assertEqual(preset_response.status_code, 200, preset_response.text)
            self.assertEqual(
                preset_response.json()["analysis"]["presets"][0]["scope"],
                "analysis",
            )
            preset_id = preset_response.json()["analysis"]["presets"][0]["preset_id"]

            selected_preset = client.put(
                f"/api/analysis/charts/{chart_id}",
                json={
                    "parameters": {"title": "API Delta"},
                    "preset_id": preset_id,
                },
            )
            self.assertEqual(selected_preset.status_code, 200, selected_preset.text)
            self.assertEqual(
                selected_preset.json()["analysis"]["charts"][0]["preset_id"],
                preset_id,
            )

            cleared_preset = client.put(
                f"/api/analysis/charts/{chart_id}",
                json={
                    "parameters": {"title": "API Delta"},
                    "preset_id": None,
                },
            )
            self.assertEqual(cleared_preset.status_code, 200, cleared_preset.text)
            self.assertIsNone(cleared_preset.json()["analysis"]["charts"][0]["preset_id"])

            export_response = client.post("/api/analysis/export")
            self.assertEqual(export_response.status_code, 200, export_response.text)
            package_path = Path(export_response.json()["analysis"]["exported_package_path"])
            self.assertTrue((package_path / "manifest.json").exists())

            opened = client.post("/api/analysis/open", json={"path": str(root / "analysis.json")})
            self.assertEqual(opened.status_code, 200, opened.text)
            self.assertEqual(opened.json()["analysis"]["analysis_id"], created.json()["analysis"]["analysis_id"])

    def test_analysis_api_rejects_unknown_parameters(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            client = TestClient(create_app())
            client.post(
                "/api/analysis/create",
                json={"path": str(Path(temp_dir) / "analysis"), "name": "API Analysis"},
            )
            client.post(
                "/api/analysis/sessions",
                json={
                    "session": {
                        "season": 2023,
                        "event": "Bahrain Grand Prix",
                        "session": "Race",
                    },
                    "drivers": ["VER", "PER"],
                    "data_cache": {
                        "fixture_path": "tests/fixtures/2023_bahrain_race_dataset.json"
                    },
                },
            )
            session_id = client.get("/api/analysis").json()["analysis"]["sessions"][0]["session_id"]

            response = client.post(
                "/api/analysis/charts",
                json={
                    "recipe_id": "lap_time_delta",
                    "target_session_ids": [session_id],
                    "parameters": {"unknown": True},
                },
            )

            self.assertEqual(response.status_code, 400, response.text)
            self.assertIn("Unknown parameter", response.text)


if __name__ == "__main__":
    unittest.main()

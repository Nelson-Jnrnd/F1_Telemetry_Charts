from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from f1_telemetry_charts.analysis import workspace
from f1_telemetry_charts.analysis.workspace import AnalysisService, list_global_presets, recipe_parameter_schema
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

    def test_all_driver_session_request_resolves_to_loaded_driver_codes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "analysis"
            service = AnalysisService(root)
            analysis = service.create("Full Field")

            analysis = service.add_session(
                analysis,
                session=SessionConfig(
                    season=2023,
                    event="Bahrain Grand Prix",
                    session="Race",
                ),
                drivers=["*"],
                data_cache=DataCacheConfig(
                    fixture_path=Path("tests/fixtures/2023_bahrain_race_dataset.json")
                ),
            )

            session = analysis.sessions[0]
            self.assertEqual(session.drivers, ["VER", "PER", "ALO"])
            self.assertEqual(session.snapshot.query.drivers, ["VER", "PER", "ALO"])

    def test_full_field_fixture_request_loads_twenty_drivers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture_path = Path(temp_dir) / "full-field.json"
            fixture_path.write_text(json.dumps(_full_field_payload()), encoding="utf-8")
            root = Path(temp_dir) / "analysis"
            service = AnalysisService(root)
            analysis = service.create("Full Field")

            analysis = service.add_session(
                analysis,
                session=SessionConfig(
                    season=2023,
                    event="Bahrain Grand Prix",
                    session="Race",
                ),
                drivers=["*"],
                data_cache=DataCacheConfig(fixture_path=fixture_path),
            )

            self.assertEqual(len(analysis.sessions[0].drivers), 20)
            self.assertEqual(len(analysis.sessions[0].available_teams), 10)

    def test_schema_exposes_modes_dependencies_and_builtin_presets(self) -> None:
        schema = recipe_parameter_schema("lap_time_delta")
        fields = {field.name: field for field in schema.fields}

        self.assertEqual(fields["teams"].mode, "advanced")
        self.assertEqual(fields["reference_driver"].visible_when, {"baseline_mode": "reference_driver"})
        self.assertEqual(fields["reference_driver"].required_when, {"baseline_mode": "reference_driver"})
        preset_names = {preset.display_name for preset in list_global_presets()}
        self.assertTrue(
            {
                "Fastest-lap telemetry comparison",
                "Driver-input comparison",
                "Clean race pace",
                "Sector comparison",
                "Tyre strategy overview",
                "Position progression",
                "Race gain/loss",
                "Presentation export",
                "Dense engineering report",
            }.issubset(preset_names)
        )
        fastest_lap = next(
            preset
            for preset in list_global_presets()
            if preset.preset_id == "builtin-fastest-lap-telemetry"
        )
        self.assertEqual(
            fastest_lap.parameters["selection"],
            {"driver_selection_mode": "all_session"},
        )


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
            global_root = Path(temp_dir) / "global-presets"
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

            with patch.object(workspace, "_global_preset_root", return_value=global_root):
                templates = client.get("/api/analysis/templates")
                self.assertEqual(templates.status_code, 200, templates.text)
                template = templates.json()[0]
                self.assertIn("template_id", template)
                self.assertIn("source_type", template)
                self.assertIn("parameter_schema_version", template)

                chart_response = client.post(
                    "/api/analysis/charts",
                    json={
                        "template_id": "lap_time_delta",
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
                        "template_id": "lap_time_delta",
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

                duplicate = client.post(
                    "/api/analysis/presets",
                    json={
                        "template_id": "lap_time_delta",
                        "display_name": "API Delta",
                        "parameters": {"title": "Duplicate"},
                        "scope": "analysis",
                    },
                )
                self.assertEqual(duplicate.status_code, 409, duplicate.text)

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

                renamed = client.put(
                    f"/api/analysis/presets/{preset_id}",
                    json={"display_name": "API Delta Renamed"},
                )
                self.assertEqual(renamed.status_code, 200, renamed.text)
                self.assertEqual(
                    renamed.json()["analysis"]["presets"][0]["display_name"],
                    "API Delta Renamed",
                )

                global_preset = client.post(
                    "/api/analysis/presets",
                    json={
                        "template_id": "lap_time_delta",
                        "display_name": "Global Delta",
                        "parameters": {"title": "Global Delta"},
                        "scope": "global",
                    },
                )
                self.assertEqual(global_preset.status_code, 200, global_preset.text)
                global_names = [
                    item["display_name"] for item in global_preset.json()["global_presets"]
                ]
                self.assertIn("Global Delta", global_names)

                deleted = client.delete(f"/api/analysis/presets/{preset_id}")
                self.assertEqual(deleted.status_code, 200, deleted.text)
                self.assertEqual(deleted.json()["analysis"]["presets"], [])
                self.assertIsNone(deleted.json()["analysis"]["charts"][0]["preset_id"])

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

    def test_analysis_api_accepts_normalized_parameter_sections(self) -> None:
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
                    "drivers": ["*"],
                    "data_cache": {
                        "fixture_path": "tests/fixtures/2023_bahrain_race_dataset.json"
                    },
                },
            )
            session = client.get("/api/analysis").json()["analysis"]["sessions"][0]

            response = client.post(
                "/api/analysis/charts",
                json={
                    "template_id": "telemetry_trace",
                    "target_session_ids": [session["session_id"]],
                    "parameters": {
                        "chart": {"title": "PER Gear"},
                        "selection": {
                            "driver_selection_mode": "selected",
                            "drivers": ["PER"],
                        },
                        "analysis": {"metric": "gear"},
                        "presentation": {
                            "colors": {"overrides": {"PER": "#123456"}},
                        },
                    },
                },
            )

            self.assertEqual(response.status_code, 200, response.text)
            chart = response.json()["analysis"]["charts"][0]
            self.assertEqual(chart["parameters"]["selection"]["drivers"], ["PER"])

    def test_flat_parameters_are_saved_as_normalized_sections_and_diagnostics_resolve(self) -> None:
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
                    "drivers": ["*"],
                    "data_cache": {
                        "fixture_path": "tests/fixtures/2023_bahrain_race_dataset.json"
                    },
                },
            )
            session = client.get("/api/analysis").json()["analysis"]["sessions"][0]

            response = client.post(
                "/api/analysis/charts",
                json={
                    "template_id": "lap_time_delta",
                    "target_session_ids": [session["session_id"]],
                    "parameters": {
                        "title": "Clean delta",
                        "drivers": ["VER", "PER"],
                        "driver_selection_mode": "selected",
                        "baseline_mode": "fastest_selected_per_lap",
                    },
                },
            )
            self.assertEqual(response.status_code, 200, response.text)
            chart = response.json()["analysis"]["charts"][0]
            self.assertEqual(chart["parameters"]["chart"]["title"], "Clean delta")
            self.assertEqual(chart["parameters"]["selection"]["drivers"], ["VER", "PER"])
            self.assertEqual(chart["parameters"]["analysis"]["baseline_mode"], "fastest_selected_per_lap")

            diagnostics = client.post(
                "/api/analysis/charts/diagnostics",
                json={
                    "template_id": "lap_time_delta",
                    "target_session_ids": [session["session_id"]],
                    "parameters": chart["parameters"],
                },
            )
            self.assertEqual(diagnostics.status_code, 200, diagnostics.text)
            payload = diagnostics.json()
            self.assertEqual(payload["status"], "valid")
            self.assertIn("effective_configuration", payload)
            self.assertIn("active_filter_summary", payload)


def _full_field_payload() -> dict:
    drivers = [
        "VER",
        "PER",
        "ALO",
        "SAI",
        "HAM",
        "STR",
        "RUS",
        "BOT",
        "GAS",
        "ALB",
        "TSU",
        "SAR",
        "MAG",
        "DEV",
        "HUL",
        "ZHO",
        "NOR",
        "OCO",
        "LEC",
        "PIA",
    ]
    return {
        "metadata": {
            "season": 2023,
            "event": "Bahrain Grand Prix",
            "session": "Race",
        },
        "drivers": [
            {"abbreviation": driver, "team_name": f"Team {index // 2}"}
            for index, driver in enumerate(drivers)
        ],
        "laps": [
            {
                "driver": driver,
                "lap_number": 1,
                "lap_time_seconds": 95.0 + index,
                "compound": "SOFT",
                "position": index + 1,
            }
            for index, driver in enumerate(drivers)
        ],
        "provenance": {"provider": "fixture", "cache_status": "fixture"},
    }

if __name__ == "__main__":
    unittest.main()

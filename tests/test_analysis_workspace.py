from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from f1_telemetry_charts.analysis import workspace
from f1_telemetry_charts.analysis.findings import EditorialField, PublicationEditorial
from f1_telemetry_charts.analysis.playback import (
    PlaybackMarker,
    _equal_distance_segment_times,
    _markers_with_analyst_context,
    _markers_with_timing,
    _mini_sector_snapshot,
    _pit_state_at_time,
)
from f1_telemetry_charts.analysis.workspace import AnalysisService, list_global_presets, recipe_parameter_schema
from f1_telemetry_charts.config.models import DataCacheConfig, SessionConfig
from f1_telemetry_charts.data import (
    LapRecord,
    TelemetrySample,
    TimingAppRecord,
    TimingStreamRecord,
)
from f1_telemetry_charts.preview import read_package_view
from f1_telemetry_charts.ui.server import create_app


def _mini_sector_test_samples(
    driver: str,
    lap_number: int,
    times: list[float],
) -> list[TelemetrySample]:
    return [
        TelemetrySample(
            driver=driver,
            lap_number=lap_number,
            distance_m=distance,
            session_time_seconds=session_time,
        )
        for distance, session_time in zip([0, 200, 400, 600], times)
    ]


class AnalysisWorkspaceTests(unittest.TestCase):
    def test_playback_sparse_leader_remains_valid_relative_anchor(self) -> None:
        markers = [
            PlaybackMarker(
                driver="PER",
                status="active",
                context={"lap_number": 16},
            ),
            PlaybackMarker(
                driver="VER",
                status="active",
                context={"lap_number": 15},
            ),
        ]
        enriched = _markers_with_timing(
            markers,
            100,
            {
                "PER": [
                    TimingStreamRecord(
                        driver="PER",
                        session_time_seconds=0,
                        position=1,
                        gap_to_leader_seconds=0,
                        gap_parse_status="leader",
                    )
                ],
                "VER": [
                    TimingStreamRecord(
                        driver="VER",
                        session_time_seconds=98,
                        position=2,
                        gap_to_leader_seconds=11.516,
                        gap_parse_status="parsed",
                    )
                ],
            },
            maximum_timing_sample_age_seconds=10,
        )

        self.assertEqual(enriched[0].context.timing_status, "fresh")
        self.assertEqual(enriched[0].context.gap_to_leader_seconds, 0)
        self.assertEqual(enriched[0].context.timing_sample_age_seconds, 100)
        self.assertEqual(enriched[1].context.lap_number, 15)
        self.assertEqual(enriched[1].context.timing_status, "fresh")
        self.assertEqual(enriched[1].context.gap_to_leader_seconds, 11.516)
        self.assertIsNone(enriched[1].context.gap_to_leader_laps)

    def test_playback_mini_sectors_are_equal_distance_and_grouped_by_sector(self) -> None:
        laps_by_driver = {
            "VER": {
                1: LapRecord(
                    driver="VER",
                    lap_number=1,
                    lap_start_time_seconds=0,
                    lap_end_time_seconds=60,
                    lap_time_seconds=60,
                    sector_1_time_seconds=20,
                    sector_2_time_seconds=20,
                    sector_3_time_seconds=20,
                ),
                2: LapRecord(
                    driver="VER",
                    lap_number=2,
                    lap_start_time_seconds=60,
                    lap_end_time_seconds=114,
                    lap_time_seconds=54,
                    sector_1_time_seconds=18,
                    sector_2_time_seconds=18,
                    sector_3_time_seconds=18,
                ),
            },
            "PER": {
                1: LapRecord(
                    driver="PER",
                    lap_number=1,
                    lap_start_time_seconds=0,
                    lap_end_time_seconds=63,
                    lap_time_seconds=63,
                    sector_1_time_seconds=21,
                    sector_2_time_seconds=21,
                    sector_3_time_seconds=21,
                )
            },
        }
        telemetry = {
            "VER": {
                1: _mini_sector_test_samples("VER", 1, [0, 20, 40, 60]),
                2: _mini_sector_test_samples("VER", 2, [60, 78, 96, 114]),
            },
            "PER": {
                1: _mini_sector_test_samples("PER", 1, [0, 21, 42, 63]),
            },
        }

        states, groups = _mini_sector_snapshot(
            120,
            ["VER", "PER"],
            laps_by_driver,
            telemetry,
            track_length_metres=600,
        )

        self.assertEqual(len(groups), 15)
        self.assertEqual(set(groups), {1, 2, 3})
        self.assertEqual(states["VER"], ["fastest"] * 15)
        self.assertEqual(states["PER"], ["faster"] * 15)

    def test_playback_mini_sectors_anchor_sparse_lap_endpoints(self) -> None:
        samples = [
            TelemetrySample(
                driver="VER",
                lap_number=1,
                distance_m=10,
                session_time_seconds=1,
            ),
            TelemetrySample(
                driver="VER",
                lap_number=1,
                distance_m=590,
                session_time_seconds=59,
            ),
        ]

        durations = _equal_distance_segment_times(
            samples,
            [0, 200, 400, 600],
            lap_start_time=0,
            lap_end_time=60,
        )

        self.assertEqual(durations, [20, 20, 20])

    def test_playback_pit_state_uses_live_pit_event_timestamps(self) -> None:
        laps = [
            LapRecord(
                driver="VER",
                lap_number=10,
                pit_in_time_seconds=600,
                is_pit_in_lap=True,
            ),
            LapRecord(
                driver="VER",
                lap_number=11,
                pit_out_time_seconds=625,
                is_pit_out_lap=True,
            ),
        ]

        self.assertEqual(_pit_state_at_time(laps, 599), "none")
        self.assertEqual(_pit_state_at_time(laps, 610), "pit_in")
        self.assertEqual(_pit_state_at_time(laps, 625), "none")

    def test_playback_tyre_age_uses_live_total_then_infers_current_stint(self) -> None:
        laps = {
            "VER": {
                4: LapRecord(
                    driver="VER",
                    lap_number=4,
                    lap_start_time_seconds=300,
                    lap_end_time_seconds=400,
                    lap_time_seconds=100,
                    compound="MEDIUM",
                    stint=2,
                ),
                5: LapRecord(
                    driver="VER",
                    lap_number=5,
                    lap_start_time_seconds=400,
                    lap_end_time_seconds=500,
                    lap_time_seconds=100,
                    compound="MEDIUM",
                    stint=2,
                ),
                6: LapRecord(
                    driver="VER",
                    lap_number=6,
                    lap_start_time_seconds=500,
                    compound="MEDIUM",
                    stint=2,
                ),
            }
        }
        marker = PlaybackMarker(driver="VER", status="active")

        live = _markers_with_analyst_context(
            [marker],
            550,
            laps,
            {
                "VER": [
                    TimingAppRecord(
                        driver="VER",
                        session_time_seconds=500,
                        stint=2,
                        total_laps=7,
                        compound="MEDIUM",
                    )
                ]
            },
            {},
            [],
        )
        inferred = _markers_with_analyst_context(
            [marker],
            550,
            laps,
            {
                "VER": [
                    TimingAppRecord(
                        driver="VER",
                        session_time_seconds=500,
                        stint=2,
                        start_laps=2,
                        compound="MEDIUM",
                    )
                ]
            },
            {},
            [],
        )

        self.assertEqual(live[0].context.tyre_age_laps, 7)
        self.assertEqual(inferred[0].context.tyre_age_laps, 4)

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

            analysis = _ready_publication(service, analysis)
            analysis = service.export_package(analysis)
            self.assertFalse(analysis.review_stale)
            export_root = Path(analysis.exported_package_path)
            self.assertEqual(
                {item.name for item in export_root.iterdir()},
                {"article.md", "article.json", "evidence.json", "manifest.json", "publication-plan.json", "assets"},
            )
            export_view = read_package_view(export_root)
            self.assertEqual(export_view.health.status, "healthy")
            self.assertEqual(export_view.manifest.markdown_path, "article.md")
            self.assertIsNotNone(export_view.article)
            self.assertIsNotNone(export_view.evidence)
            article = json.loads((export_root / "article.json").read_text(encoding="utf-8"))
            evidence = json.loads((export_root / "evidence.json").read_text(encoding="utf-8"))
            self.assertEqual(article["schema_version"], 2)
            self.assertEqual(article["publication_export_contract_version"], 3)
            self.assertEqual(article["publication_policy"], evidence["publication_policy"])
            self.assertEqual(article["editorial_sources"], evidence["editorial_sources"])
            self.assertEqual(
                evidence["evidence_scope"]["target_session_id"],
                analysis.report_target_session_id,
            )
            self.assertEqual(
                evidence["evidence_scope"]["included_chart_instance_ids"],
                [analysis.charts[0].chart_instance_id],
            )
            self.assertEqual(article["editorial_sources"], ["https://example.com/editorial-source"])
            self.assertEqual(export_view.manifest.publication_plan_path, "publication-plan.json")
            published_claim_ids = {
                paragraph["claim_id"]
                for section in article["sections"]
                for paragraph in section["paragraphs"]
            }
            placement_claim_ids = {
                placement["claim_id"] for placement in evidence["publication_placements"]
            }
            evidence_claim_ids = {finding["finding_id"] for finding in evidence["findings"]}
            self.assertEqual(published_claim_ids, placement_claim_ids)
            self.assertTrue(published_claim_ids <= evidence_claim_ids)
            self.assertTrue(
                all(item["claim_id"] in published_claim_ids for item in article["at_a_glance"])
            )
            self.assertEqual(evidence["publication_export_contract_version"], 3)
            evidence_references = [
                reference
                for result in evidence["results"]
                for reference in result.get("chart_evidence", [])
            ] + [
                reference
                for finding in evidence["findings"]
                for reference in finding.get("evidence", [])
            ]
            package_references = [
                reference
                for reference in evidence_references
                if reference["reference_scope"] == "package"
            ]
            for reference in package_references:
                self.assertTrue(reference["image_path"].startswith("assets/"))
                self.assertTrue((export_root / reference["image_path"]).is_file())
                self.assertTrue((export_root / reference["metadata_path"]).is_file())
            for reference in evidence_references:
                if reference["reference_scope"] == "source_analysis":
                    self.assertNotIn("image_path", reference)
                    self.assertNotIn("metadata_path", reference)
                    self.assertIn("source_image_path", reference)
            package_root = root / "package"
            self.assertTrue((package_root / "manifest.json").exists())
            manifest = json.loads((package_root / "manifest.json").read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(manifest["artifacts"]), 1)
            for artifact in manifest["artifacts"]:
                self.assertTrue((package_root / artifact["image_path"]).exists())
                self.assertTrue((package_root / artifact["metadata_path"]).exists())
            self.assertEqual(read_package_view(package_root).health.status, "healthy")

    def test_workspace_save_preserves_artifact_and_generate_uses_edited_lap_range(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "analysis"
            service = AnalysisService(root)
            analysis = service.create("Telemetry Save")
            analysis = service.add_session(
                analysis,
                session=SessionConfig(
                    season=2023,
                    event="Bahrain Grand Prix",
                    session="Race",
                ),
                drivers=["VER"],
                data_cache=DataCacheConfig(
                    fixture_path=Path("tests/fixtures/2023_bahrain_race_dataset.json")
                ),
            )
            session = analysis.sessions[0]
            analysis = service.add_chart(
                analysis,
                recipe_id="telemetry_trace",
                target_session_ids=[session.session_id],
                parameters={
                    "title": "Telemetry",
                    "lap_range": {"start": 2, "end": 2},
                    "selection": {
                        "driver_selection_mode": "selected",
                        "drivers": ["VER"],
                    },
                    "analysis": {
                        "metric": "speed_kph",
                        "distance_range_m": {"start": 0, "end": 250},
                    },
                },
            )
            chart = analysis.charts[0]
            analysis = service.generate_charts(analysis, [chart.chart_instance_id])
            chart = analysis.charts[0]
            self.assertEqual(chart.generation_state, "generated")
            original_artifact_id = chart.artifact_id
            original_image_path = chart.image_path
            original_metadata_path = chart.metadata_path

            edited_parameters = {
                **chart.parameters,
                "selection": {
                    **chart.parameters["selection"],
                    "laps": {"range": {"start": 1, "end": 1}},
                },
                "lap_range": {"start": 2, "end": 2},
            }
            analysis = service.update_chart(
                analysis,
                chart.chart_instance_id,
                parameters=edited_parameters,
            )
            chart = analysis.charts[0]
            self.assertEqual(chart.generation_state, "stale")
            self.assertTrue(chart.stale)
            self.assertEqual(chart.artifact_id, original_artifact_id)
            self.assertEqual(chart.image_path, original_image_path)
            self.assertEqual(chart.metadata_path, original_metadata_path)
            self.assertEqual(
                chart.parameters["selection"]["laps"]["range"],
                {"start": 2, "end": 2},
            )

            analysis = service.generate_charts(analysis, [chart.chart_instance_id])
            chart = analysis.charts[0]
            self.assertEqual(chart.generation_state, "generated")
            metadata = json.loads((root / chart.metadata_path).read_text(encoding="utf-8"))
            self.assertEqual(metadata["lap_range"], {"start": 2, "end": 2})

    def test_workspace_remove_chart_does_not_render_or_export(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "analysis"
            service = AnalysisService(root)
            analysis = service.create("Remove")
            analysis = service.add_session(
                analysis,
                session=SessionConfig(
                    season=2023,
                    event="Bahrain Grand Prix",
                    session="Race",
                ),
                drivers=["VER"],
                data_cache=DataCacheConfig(
                    fixture_path=Path("tests/fixtures/2023_bahrain_race_dataset.json")
                ),
            )
            session = analysis.sessions[0]
            analysis = service.add_chart(
                analysis,
                recipe_id="lap_time_delta",
                target_session_ids=[session.session_id],
                parameters={"title": "Remove me"},
            )
            chart_id = analysis.charts[0].chart_instance_id

            with patch.object(workspace.MatplotlibRenderer, "render") as render:
                analysis = service.remove_chart(analysis, chart_id)

            render.assert_not_called()
            self.assertEqual(analysis.charts, [])
            self.assertTrue(analysis.review_stale)
            self.assertFalse((root / "package").exists())

    def test_telemetry_basic_lap_number_normalizes_to_single_lap_range(self) -> None:
        schema = recipe_parameter_schema("telemetry_trace")
        fields = {field.name: field for field in schema.fields}

        self.assertIn("lap_number", fields)
        self.assertEqual(fields["lap_number"].mode, "basic")
        self.assertEqual(fields["lap_number"].field_type, "number")
        self.assertEqual(fields["lap_range"].mode, "advanced")

        normalized = workspace.normalize_chart_parameters(
            "telemetry_trace",
            {
                "title": "Telemetry",
                "lap_number": 2,
                "selection": {
                    "driver_selection_mode": "selected",
                    "drivers": ["VER"],
                },
                "analysis": {
                    "metric": "speed_kph",
                    "distance_range_m": {"start": 0, "end": 250},
                },
            },
        )

        self.assertEqual(
            normalized["selection"]["laps"]["range"],
            {"start": 2, "end": 2},
        )
        self.assertNotIn("lap_number", normalized)

    def test_workspace_rejects_empty_selected_driver_list(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "analysis"
            service = AnalysisService(root)
            analysis = service.create("Driver Clear")
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

            diagnostics = service.resolve_chart_diagnostics(
                analysis,
                recipe_id="telemetry_trace",
                target_session_ids=[session.session_id],
                parameters={
                    "selection": {
                        "driver_selection_mode": "selected",
                        "drivers": [],
                    },
                    "analysis": {
                        "metric": "speed_kph",
                        "distance_range_m": {"start": 0, "end": 250},
                    },
                    "lap_number": 2,
                },
            )

        self.assertEqual(diagnostics.status, "invalid")
        self.assertEqual(diagnostics.errors[0]["field"], "drivers")

    def test_workspace_generates_telemetry_from_basic_lap_number(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "analysis"
            service = AnalysisService(root)
            analysis = service.create("Basic Telemetry")
            analysis = service.add_session(
                analysis,
                session=SessionConfig(
                    season=2023,
                    event="Bahrain Grand Prix",
                    session="Race",
                ),
                drivers=["VER"],
                data_cache=DataCacheConfig(
                    fixture_path=Path("tests/fixtures/2023_bahrain_race_dataset.json")
                ),
            )
            session = analysis.sessions[0]
            analysis = service.add_chart(
                analysis,
                recipe_id="telemetry_trace",
                target_session_ids=[session.session_id],
                parameters={
                    "title": "Basic telemetry",
                    "lap_number": 2,
                    "selection": {
                        "driver_selection_mode": "selected",
                        "drivers": ["VER"],
                    },
                    "analysis": {
                        "metric": "speed_kph",
                        "distance_range_m": {"start": 0, "end": 250},
                    },
                },
            )
            chart = analysis.charts[0]
            self.assertEqual(
                chart.parameters["selection"]["laps"]["range"],
                {"start": 2, "end": 2},
            )

            analysis = service.generate_charts(analysis, [chart.chart_instance_id])
            chart = analysis.charts[0]
            self.assertEqual(chart.generation_state, "generated")
            metadata = json.loads((root / chart.metadata_path).read_text(encoding="utf-8"))
            self.assertEqual(metadata["lap_range"], {"start": 2, "end": 2})

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
            self.assertEqual(
                [driver.abbreviation for driver in session.driver_details],
                ["VER", "PER", "ALO"],
            )
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

    def test_workspace_generation_marks_invalid_data_ranges_failed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "analysis"
            service = AnalysisService(root)
            analysis = service.create("Bounds")
            analysis = service.add_session(
                analysis,
                session=SessionConfig(
                    season=2023,
                    event="Bahrain Grand Prix",
                    session="Race",
                ),
                drivers=["VER"],
                data_cache=DataCacheConfig(
                    fixture_path=Path("tests/fixtures/2023_bahrain_race_dataset.json")
                ),
            )
            analysis = service.add_chart(
                analysis,
                recipe_id="telemetry_trace",
                target_session_ids=[analysis.sessions[0].session_id],
            )
            chart = analysis.charts[0].model_copy(
                update={
                    "parameters": {
                        "analysis": {
                            "distance_range_m": {"start": 0, "end": 9999}
                        }
                    }
                },
                deep=True,
            )
            analysis = analysis.model_copy(update={"charts": [chart]}, deep=True)

            analysis = service.generate_charts(analysis, [chart.chart_instance_id])

            self.assertEqual(analysis.charts[0].generation_state, "failed")
            self.assertIn("distance_range_m", analysis.charts[0].errors[0])
            self.assertIn("at most 250 m", analysis.charts[0].errors[0])

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
        self.assertIn("supported_session_types", recipes[0])
        self.assertIn("preview_asset", recipes[0])
        self.assertIn("icon", recipes[0])
        qualifying = next(
            item for item in recipes if item["template_id"] == "qualifying_progression"
        )
        self.assertEqual(qualifying["supported_session_types"], ["qualifying"])
        self.assertFalse(Path(".analysis").exists())

    def test_analysis_directory_picker_endpoint_reports_selected_cancelled_and_unavailable(self) -> None:
        client = TestClient(create_app())
        with tempfile.TemporaryDirectory() as temp_dir:
            selected_path = Path(temp_dir).resolve()

            with patch(
                "f1_telemetry_charts.ui.server._pick_analysis_directory",
                return_value=selected_path,
            ):
                selected = client.post(
                    "/api/analysis/pick-directory",
                    json={"initial_path": str(selected_path)},
                )
            self.assertEqual(selected.status_code, 200, selected.text)
            self.assertEqual(
                selected.json(),
                {
                    "status": "selected",
                    "path": str(selected_path),
                    "message": None,
                },
            )

            with patch(
                "f1_telemetry_charts.ui.server._pick_analysis_directory",
                return_value=None,
            ):
                cancelled = client.post("/api/analysis/pick-directory", json={})
            self.assertEqual(cancelled.status_code, 200, cancelled.text)
            self.assertEqual(
                cancelled.json(),
                {
                    "status": "cancelled",
                    "path": None,
                    "message": None,
                },
            )

            with patch(
                "f1_telemetry_charts.ui.server._pick_analysis_directory",
                side_effect=RuntimeError("Native folder picker is unavailable."),
            ):
                unavailable = client.post("/api/analysis/pick-directory", json={})
            self.assertEqual(unavailable.status_code, 200, unavailable.text)
            self.assertEqual(unavailable.json()["status"], "unavailable")
            self.assertIsNone(unavailable.json()["path"])
            self.assertIn("unavailable", unavailable.json()["message"])

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
                    "drivers": ["PER"],
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

                regenerated = client.post(
                    "/api/analysis/charts/generate",
                    json={"chart_ids": [chart_id]},
                )
                self.assertEqual(regenerated.status_code, 200, regenerated.text)
                self.assertEqual(
                    regenerated.json()["analysis"]["charts"][0]["generation_state"],
                    "generated",
                )

            _ready_publication(AnalysisService(root), AnalysisService(root).open())
            export_response = client.post("/api/analysis/export")
            self.assertEqual(export_response.status_code, 200, export_response.text)
            package_path = Path(export_response.json()["analysis"]["exported_package_path"])
            self.assertTrue((package_path / "manifest.json").exists())
            package_view = read_package_view(package_path)
            self.assertEqual(package_view.health.status, "healthy")
            self.assertIsNotNone(package_view.manifest)
            self.assertEqual(package_view.manifest.markdown_path, "article.md")
            asset = client.get("/api/package/assets/article.md")
            self.assertEqual(asset.status_code, 200, asset.text)

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

    def test_analysis_api_rejects_out_of_bounds_lap_range_with_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            client = TestClient(create_app())
            client.post(
                "/api/analysis/create",
                json={"path": str(Path(temp_dir) / "analysis"), "name": "API Bounds"},
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
            session = client.get("/api/analysis").json()["analysis"]["sessions"][0]
            parameters = {
                "selection": {
                    "driver_selection_mode": "selected",
                    "drivers": ["VER"],
                    "lap_range": {"start": 1, "end": 99},
                }
            }

            diagnostics = client.post(
                "/api/analysis/charts/diagnostics",
                json={
                    "template_id": "lap_time_delta",
                    "target_session_ids": [session["session_id"]],
                    "parameters": parameters,
                },
            )
            self.assertEqual(diagnostics.status_code, 200, diagnostics.text)
            payload = diagnostics.json()
            self.assertEqual(payload["status"], "invalid")
            self.assertEqual(payload["errors"][0]["field"], "lap_range")
            self.assertEqual(payload["coverage_bounds"]["laps"]["maximum"], 2)
            self.assertFalse(payload["coverage_bounds"]["session_time"]["available"])
            self.assertTrue(payload["coverage_bounds"]["track_map"]["available"])

            response = client.post(
                "/api/analysis/charts",
                json={
                    "template_id": "lap_time_delta",
                    "target_session_ids": [session["session_id"]],
                    "parameters": parameters,
                },
            )

            self.assertEqual(response.status_code, 400, response.text)
            self.assertIn("lap_range", response.text)

    def test_analysis_api_rejects_out_of_bounds_distance_range_with_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            client = TestClient(create_app())
            client.post(
                "/api/analysis/create",
                json={"path": str(Path(temp_dir) / "analysis"), "name": "API Distance"},
            )
            client.post(
                "/api/analysis/sessions",
                json={
                    "session": {
                        "season": 2023,
                        "event": "Bahrain Grand Prix",
                        "session": "Race",
                    },
                    "drivers": ["VER"],
                    "data_cache": {
                        "fixture_path": "tests/fixtures/2023_bahrain_race_dataset.json"
                    },
                },
            )
            session = client.get("/api/analysis").json()["analysis"]["sessions"][0]
            chart_response = client.post(
                "/api/analysis/charts",
                json={
                    "template_id": "telemetry_trace",
                    "target_session_ids": [session["session_id"]],
                    "parameters": {
                        "selection": {
                            "driver_selection_mode": "selected",
                            "drivers": ["VER"],
                        }
                    },
                },
            )
            self.assertEqual(chart_response.status_code, 200, chart_response.text)
            chart_id = chart_response.json()["analysis"]["charts"][0]["chart_instance_id"]
            parameters = {
                "selection": {
                    "driver_selection_mode": "selected",
                    "drivers": ["VER"],
                },
                "analysis": {"distance_range_m": {"start": 0, "end": 9999}},
            }

            diagnostics = client.post(
                "/api/analysis/charts/diagnostics",
                json={
                    "template_id": "telemetry_trace",
                    "target_session_ids": [session["session_id"]],
                    "parameters": parameters,
                },
            )
            self.assertEqual(diagnostics.status_code, 200, diagnostics.text)
            payload = diagnostics.json()
            self.assertEqual(payload["status"], "invalid")
            self.assertEqual(payload["errors"][0]["field"], "distance_range_m")
            self.assertEqual(
                payload["coverage_bounds"]["telemetry_distance_m"]["maximum"],
                250,
            )

            response = client.put(
                f"/api/analysis/charts/{chart_id}",
                json={"parameters": parameters},
            )

            self.assertEqual(response.status_code, 400, response.text)
            self.assertIn("distance_range_m", response.text)

    def test_analysis_api_track_map_selector_payload_and_saved_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "analysis"
            client = TestClient(create_app())
            client.post(
                "/api/analysis/create",
                json={"path": str(root), "name": "API Track Map"},
            )
            client.post(
                "/api/analysis/sessions",
                json={
                    "session": {
                        "season": 2023,
                        "event": "Bahrain Grand Prix",
                        "session": "Race",
                    },
                    "drivers": ["VER"],
                    "data_cache": {
                        "fixture_path": "tests/fixtures/2023_bahrain_race_dataset.json"
                    },
                },
            )
            session = client.get("/api/analysis").json()["analysis"]["sessions"][0]
            parameters = {
                "selection": {
                    "driver_selection_mode": "selected",
                    "drivers": ["VER"],
                },
                "analysis": {"metric": "speed_kph"},
            }
            chart_response = client.post(
                "/api/analysis/charts",
                json={
                    "template_id": "telemetry_trace",
                    "target_session_ids": [session["session_id"]],
                    "parameters": parameters,
                },
            )
            self.assertEqual(chart_response.status_code, 200, chart_response.text)
            chart_id = chart_response.json()["analysis"]["charts"][0]["chart_instance_id"]

            payload_response = client.post(
                "/api/analysis/track-map",
                json={
                    "template_id": "telemetry_trace",
                    "target_session_ids": [session["session_id"]],
                    "parameters": parameters,
                    "max_points": 2,
                },
            )
            self.assertEqual(payload_response.status_code, 200, payload_response.text)
            payload = payload_response.json()
            self.assertEqual(payload["status"], "available")
            self.assertIsNone(payload["source_driver"])
            self.assertIsNone(payload["source_lap"])
            self.assertEqual(payload["geometry_metadata"]["algorithm_version"], 2)
            self.assertEqual(
                payload["geometry_metadata"]["aggregation_method"],
                "per_driver_then_session_coordinate_median",
            )
            self.assertEqual(payload["geometry_metadata"]["contributing_driver_count"], 3)
            self.assertEqual(payload["geometry_metadata"]["contributing_lap_count"], 4)
            self.assertEqual(payload["point_count"], 2)
            self.assertEqual(payload["original_sample_count"], 12)
            self.assertTrue(payload["downsampled"])
            self.assertEqual(payload["segment"]["source"], "full_lap")
            self.assertEqual(payload["segment"]["start_distance_m"], 0)
            self.assertEqual(payload["segment"]["end_distance_m"], 249)
            self.assertNotIn("points", payload["diagnostics"])

            selected_parameters = {
                **parameters,
                "analysis": {
                    "metric": "speed_kph",
                    "distance_range_m": {"start": 50, "end": 150},
                },
                "selection": {
                    "driver_selection_mode": "selected",
                    "drivers": ["VER"],
                    "track_segment": {
                        "source": "manual_track_selector",
                        "start_distance_m": 50,
                        "end_distance_m": 150,
                        "source_driver": "VER",
                        "source_lap": 2,
                    },
                },
            }
            selected_payload_response = client.post(
                "/api/analysis/track-map",
                json={
                    "template_id": "telemetry_trace",
                    "target_session_ids": [session["session_id"]],
                    "parameters": selected_parameters,
                },
            )
            self.assertEqual(selected_payload_response.status_code, 200, selected_payload_response.text)
            selected_payload = selected_payload_response.json()
            self.assertEqual(selected_payload["segment"]["source"], "manual_track_selector")
            self.assertEqual(selected_payload["segment"]["start_distance_m"], 50)
            self.assertEqual(selected_payload["segment"]["end_distance_m"], 150)

            update_response = client.put(
                f"/api/analysis/charts/{chart_id}",
                json={"parameters": selected_parameters},
            )
            self.assertEqual(update_response.status_code, 200, update_response.text)
            generated = client.post(
                "/api/analysis/charts/generate",
                json={"chart_ids": [chart_id]},
            )
            self.assertEqual(generated.status_code, 200, generated.text)
            chart = generated.json()["analysis"]["charts"][0]
            self.assertEqual(chart["generation_state"], "generated")
            metadata = json.loads((root / chart["metadata_path"]).read_text(encoding="utf-8"))
            self.assertEqual(metadata["distance_range_m"], {"start": 50, "end": 150})
            self.assertEqual(
                metadata["track_segment"]["source"],
                "manual_track_selector",
            )
            self.assertEqual(
                metadata["track_segment"]["source_driver"],
                "VER",
            )

    def test_analysis_track_map_uses_session_geometry_when_selected_driver_lacks_trace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "analysis"
            client = TestClient(create_app())
            client.post(
                "/api/analysis/create",
                json={
                    "path": str(root),
                    "name": "Session Geometry",
                },
            )
            client.post(
                "/api/analysis/sessions",
                json={
                    "session": {
                        "season": 2023,
                        "event": "Bahrain Grand Prix",
                        "session": "Race",
                    },
                    "drivers": ["PER"],
                    "data_cache": {
                        "fixture_path": "tests/fixtures/2023_bahrain_race_dataset.json"
                    },
                },
            )
            session = client.get("/api/analysis").json()["analysis"]["sessions"][0]
            parameters = {
                "selection": {
                    "driver_selection_mode": "selected",
                    "drivers": ["PER"],
                },
                "analysis": {"metric": "speed_kph"},
            }

            payload_response = client.post(
                "/api/analysis/track-map",
                json={
                    "template_id": "telemetry_trace",
                    "target_session_ids": [session["session_id"]],
                    "parameters": parameters,
                },
            )

            self.assertEqual(payload_response.status_code, 200, payload_response.text)
            payload = payload_response.json()
            self.assertEqual(payload["status"], "available")
            self.assertEqual(payload["selected_drivers"], ["PER"])
            self.assertIsNone(payload["source_driver"])
            self.assertIsNone(payload["source_lap"])
            self.assertEqual(payload["geometry_metadata"]["contributing_driver_count"], 3)
            self.assertGreaterEqual(payload["point_count"], 2)

            diagnostics = client.post(
                "/api/analysis/charts/diagnostics",
                json={
                    "template_id": "telemetry_trace",
                    "target_session_ids": [session["session_id"]],
                    "parameters": parameters,
                },
            )
            self.assertEqual(diagnostics.status_code, 200, diagnostics.text)
            track_map = diagnostics.json()["coverage_bounds"]["track_map"]
            self.assertTrue(track_map["available"])
            self.assertEqual(track_map["source"], "session_track_geometry")
            self.assertIsNone(track_map["source_driver"])
            self.assertEqual(track_map["geometry"]["algorithm_version"], 2)

    def test_analysis_track_map_returns_projected_corner_markers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture_path = Path(temp_dir) / "with-corners.json"
            payload = json.loads(
                Path("tests/fixtures/2023_bahrain_race_dataset.json").read_text(
                    encoding="utf-8"
                )
            )
            payload["circuit_info"] = {
                "source": "fastf1_circuit_info",
                "reason": "fixture_corner_metadata",
                "rotation_degrees": 42.0,
                "corners": [
                    {
                        "number": 1,
                        "letter": None,
                        "label": "1",
                        "x": 0,
                        "y": 0,
                        "angle_degrees": 12,
                        "distance_m": 0,
                    },
                    {
                        "number": 2,
                        "letter": "A",
                        "label": "2A",
                        "x": 80,
                        "y": 45,
                        "angle_degrees": 18,
                        "distance_m": 125,
                    },
                ],
            }
            fixture_path.write_text(json.dumps(payload), encoding="utf-8")

            client = TestClient(create_app())
            client.post(
                "/api/analysis/create",
                json={"path": str(Path(temp_dir) / "analysis"), "name": "Corners"},
            )
            client.post(
                "/api/analysis/sessions",
                json={
                    "session": {
                        "season": 2023,
                        "event": "Bahrain Grand Prix",
                        "session": "Race",
                    },
                    "drivers": ["VER"],
                    "data_cache": {"fixture_path": str(fixture_path)},
                },
            )
            session = client.get("/api/analysis").json()["analysis"]["sessions"][0]

            payload_response = client.post(
                "/api/analysis/track-map",
                json={
                    "template_id": "telemetry_trace",
                    "target_session_ids": [session["session_id"]],
                    "parameters": {
                        "selection": {
                            "driver_selection_mode": "selected",
                            "drivers": ["VER"],
                        },
                        "analysis": {"metric": "speed_kph"},
                    },
                },
            )

            self.assertEqual(payload_response.status_code, 200, payload_response.text)
            track_map = payload_response.json()
            self.assertEqual(track_map["status"], "available")
            self.assertEqual(
                [corner["label"] for corner in track_map["corners"]],
                ["1", "2A"],
            )
            self.assertEqual(
                track_map["corners"][1]["projection_status"],
                "fastf1_distance",
            )
            self.assertEqual(track_map["corners"][1]["distance_m"], 125)
            self.assertTrue(track_map["bounds"]["corners"]["available"])

            corner_parameters = {
                "selection": {
                    "driver_selection_mode": "selected",
                    "drivers": ["VER"],
                    "track_segment": {
                        "source": "corner_selector",
                        "start_distance_m": 75,
                        "end_distance_m": 175,
                        "corner": {
                            "label": "2A",
                            "distance_m": 125,
                            "pre_padding_m": 50,
                            "post_padding_m": 50,
                            "projection_status": "fastf1_distance",
                        },
                    },
                },
                "analysis": {
                    "metric": "speed_kph",
                    "distance_range_m": {"start": 75, "end": 175},
                },
            }
            chart_response = client.post(
                "/api/analysis/charts",
                json={
                    "template_id": "telemetry_trace",
                    "target_session_ids": [session["session_id"]],
                    "parameters": corner_parameters,
                },
            )
            self.assertEqual(chart_response.status_code, 200, chart_response.text)
            chart = chart_response.json()["analysis"]["charts"][0]
            generated = client.post(
                "/api/analysis/charts/generate",
                json={"chart_ids": [chart["chart_instance_id"]]},
            )
            self.assertEqual(generated.status_code, 200, generated.text)
            chart = generated.json()["analysis"]["charts"][0]
            metadata = json.loads(
                (Path(temp_dir) / "analysis" / chart["metadata_path"]).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(metadata["track_segment"]["source"], "corner_selector")
            self.assertEqual(metadata["track_segment"]["corner"]["label"], "2A")
            self.assertEqual(metadata["distance_range_m"], {"start": 75, "end": 175})

    def test_analysis_track_map_degrades_without_position_geometry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture_path = Path(temp_dir) / "no-position.json"
            payload = json.loads(
                Path("tests/fixtures/2023_bahrain_race_dataset.json").read_text(
                    encoding="utf-8"
                )
            )
            for sample in payload["telemetry"]:
                sample.pop("x", None)
                sample.pop("y", None)
                sample.pop("z", None)
                sample.pop("position_status", None)
            fixture_path.write_text(json.dumps(payload), encoding="utf-8")

            client = TestClient(create_app())
            client.post(
                "/api/analysis/create",
                json={"path": str(Path(temp_dir) / "analysis"), "name": "No Geometry"},
            )
            client.post(
                "/api/analysis/sessions",
                json={
                    "session": {
                        "season": 2023,
                        "event": "Bahrain Grand Prix",
                        "session": "Race",
                    },
                    "drivers": ["VER"],
                    "data_cache": {"fixture_path": str(fixture_path)},
                },
            )
            session = client.get("/api/analysis").json()["analysis"]["sessions"][0]
            parameters = {
                "selection": {
                    "driver_selection_mode": "selected",
                    "drivers": ["VER"],
                },
                "analysis": {
                    "metric": "speed_kph",
                    "distance_range_m": {"start": 0, "end": 125},
                },
            }

            track_map = client.post(
                "/api/analysis/track-map",
                json={
                    "template_id": "telemetry_trace",
                    "target_session_ids": [session["session_id"]],
                    "parameters": parameters,
                },
            )
            self.assertEqual(track_map.status_code, 200, track_map.text)
            payload = track_map.json()
            self.assertEqual(payload["status"], "unavailable")
            self.assertEqual(payload["diagnostics"][0]["field"], "track_map")

            diagnostics = client.post(
                "/api/analysis/charts/diagnostics",
                json={
                    "template_id": "telemetry_trace",
                    "target_session_ids": [session["session_id"]],
                    "parameters": parameters,
                },
            )
            self.assertEqual(diagnostics.status_code, 200, diagnostics.text)
            self.assertEqual(diagnostics.json()["status"], "valid")
            self.assertFalse(diagnostics.json()["coverage_bounds"]["track_map"]["available"])

            chart_response = client.post(
                "/api/analysis/charts",
                json={
                    "template_id": "telemetry_trace",
                    "target_session_ids": [session["session_id"]],
                    "parameters": parameters,
                },
            )
            self.assertEqual(chart_response.status_code, 200, chart_response.text)

    def test_analysis_playback_returns_lap_frame_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            client = TestClient(create_app())
            client.post(
                "/api/analysis/create",
                json={"path": str(Path(temp_dir) / "analysis"), "name": "Playback"},
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
                "/api/analysis/playback",
                json={
                    "session_id": session["session_id"],
                    "mode": "lap",
                    "cursor": 2,
                    "max_points": 2,
                },
            )

            self.assertEqual(response.status_code, 200, response.text)
            payload = response.json()
            self.assertEqual(payload["status"], "available")
            self.assertEqual(payload["mode"], "lap")
            self.assertEqual(payload["default_mode"], "lap")
            self.assertTrue(payload["available_modes"]["lap"]["available"])
            self.assertTrue(payload["available_modes"]["time"]["available"])
            self.assertEqual(payload["bounds"]["laps"]["minimum"], 1)
            self.assertEqual(payload["bounds"]["laps"]["maximum"], 2)
            self.assertEqual(len(payload["points"]), 2)
            self.assertEqual(payload["leader_lap_markers"][1]["lap_number"], 2)
            self.assertEqual(payload["leader_lap_markers"][1]["leader_driver"], "VER")
            self.assertAlmostEqual(payload["leader_lap_markers"][1]["session_time_seconds"], 97.254)
            self.assertEqual(len(payload["frames"]), 1)
            frame = payload["frames"][0]
            self.assertEqual(frame["lap_number"], 2)
            self.assertEqual(frame["cursor"]["mode"], "lap")
            self.assertEqual(frame["cursor"]["leader_lap_number"], 2)
            self.assertAlmostEqual(frame["session_time_seconds"], 97.254)
            markers = {marker["driver"]: marker for marker in frame["markers"]}
            self.assertEqual(markers["VER"]["status"], "active")
            self.assertEqual(markers["VER"]["color"], "#3671C6")
            self.assertEqual(markers["VER"]["distance_m"], 0)
            self.assertEqual(markers["VER"]["context"]["position"], 1)
            self.assertEqual(markers["VER"]["context"]["gap_to_leader_seconds"], 0)
            self.assertEqual(markers["VER"]["context"]["timing_status"], "fresh")
            self.assertEqual(markers["VER"]["context"]["tyre_age_laps"], 2)
            self.assertEqual(markers["VER"]["context"]["last_lap_time_seconds"], 97.254)
            self.assertEqual(markers["VER"]["context"]["best_lap_time_seconds"], 97.254)
            self.assertEqual(
                markers["VER"]["context"]["last_sector_times_seconds"],
                [31.102, 41.942, 24.21],
            )
            self.assertEqual(markers["VER"]["context"]["mini_sector_states"], [])
            self.assertEqual(
                markers["VER"]["context"]["timing_app_source"],
                "fastf1_timing_app_data",
            )
            self.assertEqual(markers["PER"]["status"], "active")
            self.assertEqual(markers["PER"]["color"], "#3671C6")
            self.assertEqual(markers["PER"]["source_lap"], 1)
            self.assertEqual(markers["PER"]["distance_m"], 246)
            self.assertEqual(markers["PER"]["context"]["position"], 2)
            self.assertEqual(markers["PER"]["context"]["gap_to_leader_seconds"], 1.234)
            self.assertEqual(markers["PER"]["context"]["interval_to_ahead_seconds"], 1.234)
            self.assertEqual(markers["PER"]["context"]["gap_source"], "fastf1_timing_data")
            self.assertFalse(markers["PER"]["context"]["gap_inferred"])
            self.assertEqual(markers["PER"]["context"]["timing_position"], 2)
            self.assertEqual(markers["ALO"]["color"], "#358C75")
            self.assertEqual(markers["ALO"]["source_lap"], 1)
            self.assertEqual(markers["ALO"]["distance_m"], 240)
            self.assertEqual(markers["ALO"]["context"]["position"], 5)
            self.assertEqual(markers["ALO"]["context"]["gap_to_leader_seconds"], 4.321)
            self.assertNotIn("raw_telemetry", payload)
            self.assertEqual(payload["metadata"]["timing"]["record_count"], 6)
            self.assertEqual(payload["metadata"]["timing_app"]["record_count"], 3)

            coverage = client.get("/api/analysis/coverage").json()
            playback = coverage["sessions"][session["session_id"]]["playback"]
            self.assertTrue(playback["available"])
            self.assertEqual(playback["default_mode"], "lap")

    def test_analysis_playback_degrades_without_time_indexed_positions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture_path = Path(temp_dir) / "no-session-time.json"
            payload = json.loads(
                Path("tests/fixtures/2023_bahrain_race_dataset.json").read_text(
                    encoding="utf-8"
                )
            )
            for lap in payload["laps"]:
                lap.pop("lap_start_time_seconds", None)
                lap.pop("lap_end_time_seconds", None)
            for sample in payload["telemetry"]:
                sample.pop("session_time_seconds", None)
            fixture_path.write_text(json.dumps(payload), encoding="utf-8")

            client = TestClient(create_app())
            client.post(
                "/api/analysis/create",
                json={"path": str(Path(temp_dir) / "analysis"), "name": "No Time"},
            )
            client.post(
                "/api/analysis/sessions",
                json={
                    "session": {
                        "season": 2023,
                        "event": "Bahrain Grand Prix",
                        "session": "Race",
                    },
                    "drivers": ["VER"],
                    "data_cache": {"fixture_path": str(fixture_path)},
                },
            )
            session = client.get("/api/analysis").json()["analysis"]["sessions"][0]

            response = client.post(
                "/api/analysis/playback",
                json={"session_id": session["session_id"], "mode": "time"},
            )

            self.assertEqual(response.status_code, 200, response.text)
            payload = response.json()
            self.assertEqual(payload["status"], "unavailable")
            self.assertEqual(payload["diagnostics"][0]["field"], "mode")
            self.assertIn("time-indexed position", payload["diagnostics"][0]["message"])
            self.assertFalse(payload["available_modes"]["time"]["available"])
            self.assertFalse(payload["available_modes"]["lap"]["available"])

    def test_analysis_playback_time_mode_interpolates_at_shared_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            client = TestClient(create_app())
            client.post(
                "/api/analysis/create",
                json={"path": str(Path(temp_dir) / "analysis"), "name": "Time Playback"},
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
            session = client.get("/api/analysis").json()["analysis"]["sessions"][0]

            response = client.post(
                "/api/analysis/playback",
                json={
                    "session_id": session["session_id"],
                    "mode": "time",
                    "cursor": 145.31,
                    "maximum_sample_gap_seconds": 60,
                },
            )

            self.assertEqual(response.status_code, 200, response.text)
            frame = response.json()["frames"][0]
            self.assertEqual(frame["mode"], "time")
            self.assertAlmostEqual(frame["session_time_seconds"], 145.31)
            self.assertEqual(frame["cursor"]["leader_lap_number"], 2)
            markers = {marker["driver"]: marker for marker in frame["markers"]}
            self.assertEqual(markers["VER"]["interpolation_method"], "exact")
            self.assertEqual(markers["VER"]["distance_m"], 125)
            self.assertEqual(markers["PER"]["interpolation_status"], "interpolated")
            self.assertEqual(markers["PER"]["source_lap"], 2)
            self.assertLess(markers["PER"]["distance_m"], 125)
            self.assertEqual(markers["PER"]["context"]["gap_to_leader_seconds"], 1.702)
            self.assertEqual(markers["PER"]["context"]["interval_to_ahead_seconds"], 1.702)
            self.assertEqual(markers["PER"]["context"]["timing_status"], "fresh")

    def test_analysis_playback_range_handoff_preserves_other_chart_parameters(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "analysis"
            client = TestClient(create_app())
            client.post(
                "/api/analysis/create",
                json={"path": str(root), "name": "Playback Handoff"},
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
            session = client.get("/api/analysis").json()["analysis"]["sessions"][0]
            chart_response = client.post(
                "/api/analysis/charts",
                json={
                    "template_id": "lap_time_delta",
                    "target_session_ids": [session["session_id"]],
                    "parameters": {
                        "chart": {"title": "Delta"},
                        "selection": {
                            "driver_selection_mode": "selected",
                            "drivers": ["VER", "PER"],
                        },
                        "analysis": {"delta_mode": "single_lap_delta"},
                    },
                },
            )
            self.assertEqual(chart_response.status_code, 200, chart_response.text)
            chart = chart_response.json()["analysis"]["charts"][0]
            selected_parameters = {
                **chart["parameters"],
                "selection": {
                    **chart["parameters"]["selection"],
                    "laps": {"range": {"start": 2, "end": 2}},
                    "playback_interval": {
                        "source": "race_playback",
                        "mode": "lap",
                        "start_lap": 2,
                        "end_lap": 2,
                        "session_id": session["session_id"],
                    },
                },
            }

            update_response = client.put(
                f"/api/analysis/charts/{chart['chart_instance_id']}",
                json={"parameters": selected_parameters},
            )

            self.assertEqual(update_response.status_code, 200, update_response.text)
            updated = update_response.json()["analysis"]["charts"][0]
            self.assertEqual(updated["generation_state"], "stale")
            self.assertEqual(updated["parameters"]["analysis"]["delta_mode"], "single_lap_delta")
            self.assertEqual(updated["parameters"]["selection"]["laps"]["range"], {"start": 2, "end": 2})
            self.assertEqual(
                updated["parameters"]["selection"]["playback_interval"]["source"],
                "race_playback",
            )

            generated = client.post(
                "/api/analysis/charts/generate",
                json={"chart_ids": [chart["chart_instance_id"]]},
            )
            self.assertEqual(generated.status_code, 200, generated.text)
            chart = generated.json()["analysis"]["charts"][0]
            metadata = json.loads((root / chart["metadata_path"]).read_text(encoding="utf-8"))
            self.assertEqual(metadata["lap_range"], {"start": 2, "end": 2})
            self.assertEqual(
                metadata["effective_configuration"]["selection"]["playback_interval"]["source"],
                "race_playback",
            )


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

def _ready_publication(service: AnalysisService, analysis):
    analysis = service.refresh_observations(analysis)
    content = analysis.report_content
    assert content is not None and content.publication_plan is not None
    editorial = PublicationEditorial(
        headline=EditorialField(value="Verstappen leads Bahrain as the field order changes"),
        standfirst=EditorialField(value="Verstappen led the Bahrain finish while the reviewed chronology and pace evidence defined the main race story."),
        section_ledes={
            "how_the_race_developed": EditorialField(value="The classified order, field recovery and neutralised phase establish the race chronology."),
            "pace_and_strategy": EditorialField(value="The representative-lap comparisons then show how the leading pair differed on pace."),
        },
        conclusion=EditorialField(value="The reviewed chronology and representative pace evidence support this final account."),
        source_urls=["https://example.com/editorial-source"],
    )
    plan = content.publication_plan.model_copy(
        update={
            "charts": [
                chart.model_copy(
                    update={
                        "caption": EditorialField(value="The selected comparison highlights the main pace difference across the reviewed interval."),
                        "alt_text": EditorialField(value="Line chart with two driver traces plotted across the reviewed race interval and labelled at their endpoints."),
                    },
                    deep=True,
                )
                for chart in content.publication_plan.charts
            ]
        },
        deep=True,
    )
    analysis = service.update_publication(
        analysis,
        plan=plan,
        editorial=editorial,
        evidence_fingerprint=content.evidence_fingerprint,
    )
    claims = {
        item.finding_id: item
        for item in [*analysis.report_content.findings, *analysis.report_content.conclusions]
    }
    for placement in analysis.report_content.publication_plan.claims:
        if not placement.included:
            continue
        claim = claims[placement.finding_id]
        analysis = service.review_report_item(
            analysis,
            item_id=claim.finding_id,
            review_status="accepted",
            evidence_fingerprint=claim.evidence_fingerprint,
        )
    return service.regenerate_report_draft(analysis)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from f1_telemetry_charts.analysis.orchestrator import run_analysis
from f1_telemetry_charts.config.models import ProjectConfig
from f1_telemetry_charts.config.models import ChartRecipeConfig
from f1_telemetry_charts.config.validation import validate_config
from f1_telemetry_charts.data import (
    DriverMetadata,
    LapRecord,
    SessionDataset,
    SessionStyleMetadata,
    SessionMetadata,
    SessionQuery,
    SourceProvenance,
    StyleColor,
    TelemetrySample,
)
from f1_telemetry_charts.data.gateways import FixtureSessionGateway
from f1_telemetry_charts.analysis.workspace import recipe_parameter_schema
from f1_telemetry_charts.recipes.lap_time_delta import LapTimeDeltaRecipe
from f1_telemetry_charts.recipes.position_progression import PositionProgressionRecipe
from f1_telemetry_charts.recipes.registry import default_recipe_registry
from f1_telemetry_charts.recipes.telemetry_trace import TelemetryTraceRecipe
from f1_telemetry_charts.recipes.tyre_strategy import TyreStrategyRecipe


class CoreRecipeTests(unittest.TestCase):
    def test_all_mvp_recipe_factories_are_registered(self) -> None:
        registry = default_recipe_registry()

        for recipe_id in [
            "telemetry_trace",
            "lap_time_delta",
            "tyre_strategy",
            "position_progression",
        ]:
            recipe = registry.create(recipe_id)
            self.assertEqual(recipe.recipe_id, recipe_id)

    def test_all_mvp_recipes_render_in_batch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_analysis(_config(Path(temp_dir)))
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(result.status, "succeeded")
        self.assertEqual(len(manifest["artifacts"]), 4)
        self.assertEqual(
            [recipe["status"] for recipe in manifest["recipes"]],
            ["produced", "produced", "produced", "produced"],
        )

    def test_batch_generation_reports_bounded_range_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _config(Path(temp_dir))
            config = config.model_copy(
                update={
                    "recipes": [
                        ChartRecipeConfig(
                            recipe_id="telemetry_trace",
                            parameters={
                                "selection": {
                                    "driver_selection_mode": "selected",
                                    "drivers": ["VER"],
                                },
                                "analysis": {
                                    "distance_range_m": {"start": 0, "end": 9999}
                                },
                            },
                        )
                    ]
                },
                deep=True,
            )

            result = run_analysis(config)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.manifest.recipes[0].status, "failed")
        self.assertIn("distance_range_m end must be at most 250 m", result.manifest.errors[0])

    def test_builtin_template_schemas_expose_behavior_parameters(self) -> None:
        expected = {
            "telemetry_trace": {"drivers", "driver_selection_mode", "driver_order", "box_lap_policy", "metric", "distance_range_m"},
            "lap_time_delta": {"drivers", "driver_selection_mode", "driver_order", "box_lap_policy", "baseline_mode", "reference_driver", "include_pit_laps"},
            "tyre_strategy": {"drivers", "driver_selection_mode", "driver_order", "box_lap_policy", "compounds", "show_pit_markers"},
            "position_progression": {"drivers", "driver_selection_mode", "driver_order", "box_lap_policy", "invert_position_axis", "include_pit_laps"},
        }
        raw_sections = {"chart", "selection", "filters", "analysis", "presentation", "diagnostics", "effective"}

        for recipe_id, field_names in expected.items():
            schema = recipe_parameter_schema(recipe_id)
            schema_field_names = {field.name for field in schema.fields}
            self.assertGreater(len(schema.fields), 1)
            self.assertTrue(field_names.issubset(schema_field_names))
            self.assertFalse(raw_sections & schema_field_names)

    def test_builtin_template_parameters_change_chart_specs(self) -> None:
        dataset = FixtureSessionGateway(Path("tests/fixtures/2023_bahrain_race_dataset.json")).load_session(
            SessionQuery(
                season=2023,
                event="Bahrain Grand Prix",
                session="Race",
                drivers=["VER", "PER", "ALO"],
            )
        )

        telemetry = TelemetryTraceRecipe().build_spec(
            dataset,
            ChartRecipeConfig(
                recipe_id="telemetry_trace",
                parameters={
                    "selection": {
                        "driver_selection_mode": "selected",
                        "drivers": ["PER"],
                    },
                    "analysis": {"metric": "gear"},
                    "presentation": {
                        "colors": {"overrides": {"PER": "#123456"}},
                    },
                },
            ),
        )
        self.assertEqual(telemetry.y_label, "Gear")
        self.assertEqual(telemetry.selected_drivers, ["PER"])
        self.assertEqual(telemetry.series[0].color, "#123456")
        self.assertEqual(
            telemetry.metadata["style_sources"]["drivers"]["PER"]["source"],
            "user_override",
        )
        self.assertEqual(
            telemetry.metadata["effective_configuration"]["selection"]["drivers"],
            ["PER"],
        )

        delta = LapTimeDeltaRecipe().build_spec(
            dataset,
            ChartRecipeConfig(
                recipe_id="lap_time_delta",
                parameters={"baseline_mode": "reference_driver", "reference_driver": "VER"},
            ),
        )
        self.assertEqual(delta.metadata["baseline_mode"], "reference_driver")
        self.assertEqual(delta.metadata["reference_driver"], "VER")

        tyre = TyreStrategyRecipe().build_spec(
            dataset.model_copy(
                update={
                    "laps": [
                        dataset.laps[0].model_copy(update={"is_pit_in_lap": True}),
                        *dataset.laps[1:],
                    ]
                },
                deep=True,
            ),
            ChartRecipeConfig(
                recipe_id="tyre_strategy",
                parameters={"compounds": ["SOFT"], "show_pit_markers": True, "drivers": ["VER"]},
            ),
        )
        self.assertEqual(tyre.metadata["compounds"], ["SOFT"])
        self.assertTrue(tyre.metadata["show_pit_markers"])
        self.assertEqual(len(tyre.vertical_markers), 1)
        self.assertTrue(tyre.horizontal_bars)
        self.assertEqual(tyre.metadata["layout"], "stint_bars")

        position = PositionProgressionRecipe().build_spec(
            dataset,
            ChartRecipeConfig(
                recipe_id="position_progression",
                parameters={"invert_position_axis": False},
            ),
        )
        self.assertFalse(position.metadata["invert_position_axis"])
        self.assertFalse(position.y_axis_inverted)
        self.assertEqual(position.series[0].render_mode, "step")

    def test_builtin_recipes_use_session_and_deterministic_style_colors(self) -> None:
        dataset = FixtureSessionGateway(Path("tests/fixtures/2023_bahrain_race_dataset.json")).load_session(
            SessionQuery(
                season=2023,
                event="Bahrain Grand Prix",
                session="Race",
                drivers=["VER", "PER", "ALO"],
            )
        )
        styled_dataset = dataset.model_copy(
            update={
                "style": SessionStyleMetadata(
                    driver_colors={
                        "VER": StyleColor(
                            color="#112233",
                            source="fastf1_driver_color",
                            label="Red Bull Racing",
                        )
                    },
                    compound_colors={
                        "SOFT": StyleColor(
                            color="#DA291C",
                            source="fastf1_compound_mapping",
                            label="SOFT",
                        )
                    },
                )
            },
            deep=True,
        )

        delta = LapTimeDeltaRecipe().build_spec(
            styled_dataset,
            ChartRecipeConfig(
                recipe_id="lap_time_delta",
                parameters={"selection": {"drivers": ["VER"]}},
            ),
        )
        self.assertEqual(delta.series[0].color, "#112233")
        self.assertEqual(
            delta.metadata["style_sources"]["drivers"]["VER"]["source"],
            "fastf1_driver_color",
        )

        position = PositionProgressionRecipe().build_spec(
            dataset,
            ChartRecipeConfig(
                recipe_id="position_progression",
                parameters={"selection": {"drivers": ["ALO"]}},
            ),
        )
        self.assertEqual(position.series[0].color, "#358C75")
        self.assertEqual(
            position.metadata["style_sources"]["drivers"]["ALO"]["source"],
            "session_team_color",
        )

        no_style_dataset = dataset.model_copy(
            update={
                "drivers": [
                    driver.model_copy(update={"team_color": None})
                    for driver in dataset.drivers
                ],
                "style": SessionStyleMetadata(),
            },
            deep=True,
        )
        fallback = PositionProgressionRecipe().build_spec(
            no_style_dataset,
            ChartRecipeConfig(
                recipe_id="position_progression",
                parameters={"selection": {"drivers": ["VER"]}},
            ),
        )
        self.assertEqual(
            fallback.metadata["style_sources"]["drivers"]["VER"]["source"],
            "deterministic_fallback",
        )
        self.assertTrue(fallback.metadata["style_sources"]["drivers"]["VER"]["fallback"])
        self.assertTrue(
            any("deterministic fallback color" in warning for warning in fallback.warnings)
        )

        tyre = TyreStrategyRecipe().build_spec(
            styled_dataset,
            ChartRecipeConfig(
                recipe_id="tyre_strategy",
                parameters={"selection": {"drivers": ["VER"]}},
            ),
        )
        self.assertEqual(tyre.horizontal_bars[0].color, "#DA291C")
        self.assertEqual(
            tyre.metadata["style_sources"]["compounds"]["SOFT"]["source"],
            "fastf1_compound_mapping",
        )

    def test_lap_validity_track_status_and_active_filter_diagnostics(self) -> None:
        dataset = _diagnostic_dataset()

        delta = LapTimeDeltaRecipe().build_spec(
            dataset,
            ChartRecipeConfig(
                recipe_id="lap_time_delta",
                parameters={
                    "filters": {
                        "track_status_filter": {"mode": "green_only"},
                        "lap_validity": {"deleted_laps": "exclude"},
                    }
                },
            ),
        )

        diagnostics = delta.metadata["diagnostics"]
        self.assertEqual(diagnostics["exclusion_counts"]["track_status"], 2)
        self.assertIn("Track status: green_only", diagnostics["active_filter_summary"])
        self.assertEqual(delta.metadata["effective_configuration"]["filters"]["track_status_filter"]["included_codes"], ["1"])

    def test_telemetry_gap_policy_rejects_categorical_interpolation(self) -> None:
        dataset = _diagnostic_dataset()

        with self.assertRaises(ValueError) as raised:
            TelemetryTraceRecipe().build_spec(
                dataset,
                ChartRecipeConfig(
                    recipe_id="telemetry_trace",
                    parameters={
                        "analysis": {
                            "metric": "gear",
                            "telemetry_gap_policy": "interpolate_continuous",
                        }
                    },
                ),
            )

        self.assertIn("not supported for gear", str(raised.exception))


def _config(output_dir: Path) -> ProjectConfig:
    return validate_config(
        {
            "schema_version": 1,
            "project_id": "all-recipes",
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
                {"recipe_id": "telemetry_trace"},
                {"recipe_id": "lap_time_delta"},
                {"recipe_id": "tyre_strategy"},
                {"recipe_id": "position_progression"},
            ],
        }
    )


def _diagnostic_dataset() -> SessionDataset:
    drivers = [
        DriverMetadata(abbreviation="VER", team_name="Red Bull Racing"),
        DriverMetadata(abbreviation="PER", team_name="Red Bull Racing"),
    ]
    laps = [
        LapRecord(driver="VER", lap_number=1, lap_time_seconds=96.0, compound="SOFT", position=1, track_status="1"),
        LapRecord(driver="PER", lap_number=1, lap_time_seconds=97.0, compound="SOFT", position=2, track_status="1"),
        LapRecord(driver="VER", lap_number=2, lap_time_seconds=98.0, compound="SOFT", position=1, track_status="4"),
        LapRecord(driver="PER", lap_number=2, lap_time_seconds=99.0, compound="SOFT", position=2, track_status="4"),
    ]
    telemetry = [
        TelemetrySample(driver=lap.driver, lap_number=lap.lap_number, distance_m=0, speed_kph=200, throttle_percent=80, gear=5)
        for lap in laps
    ]
    return SessionDataset(
        metadata=SessionMetadata(season=2023, event="Bahrain Grand Prix", session="Race"),
        drivers=drivers,
        laps=laps,
        telemetry=telemetry,
        provenance=SourceProvenance(provider="fixture", cache_status="fixture"),
    )


if __name__ == "__main__":
    unittest.main()

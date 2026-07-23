from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from f1_telemetry_charts.charts.renderers import MatplotlibRenderer
from f1_telemetry_charts.config.models import ChartRecipeConfig, ThemeConfig
from f1_telemetry_charts.data import SessionQuery
from f1_telemetry_charts.data.gateways import FixtureSessionGateway
from f1_telemetry_charts.recipes.lap_time_delta import LapTimeDeltaRecipe


FIXTURE_PATH = Path("tests/fixtures/2023_bahrain_race_dataset.json")


class LapTimeDeltaRecipeTests(unittest.TestCase):
    def test_recipe_builds_chart_spec_from_fixture_dataset(self) -> None:
        dataset = _fixture_dataset()
        spec = LapTimeDeltaRecipe().build_spec(
            dataset, ChartRecipeConfig(recipe_id="lap_time_delta")
        )

        self.assertEqual(spec.recipe_id, "lap_time_delta")
        self.assertEqual(spec.selected_drivers, ["VER", "PER", "ALO"])
        self.assertEqual(len(spec.series), 3)
        self.assertEqual(spec.source_session["event"], "Bahrain Grand Prix")

    def test_matplotlib_renderer_writes_png_and_metadata(self) -> None:
        dataset = _fixture_dataset()
        spec = LapTimeDeltaRecipe().build_spec(
            dataset, ChartRecipeConfig(recipe_id="lap_time_delta")
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = MatplotlibRenderer().render(
                spec,
                theme=ThemeConfig(),
                output_dir=Path(temp_dir),
                artifact_id="lap_time_delta",
            )

            self.assertTrue(artifact.image_path.exists())
            self.assertTrue(artifact.metadata_path.exists())
            metadata = json.loads(artifact.metadata_path.read_text(encoding="utf-8"))

        self.assertEqual(metadata["artifact_id"], "lap_time_delta")
        self.assertEqual(metadata["recipe_id"], "lap_time_delta")
        self.assertEqual(metadata["selected_drivers"], ["VER", "PER", "ALO"])
        self.assertFalse(metadata["x_axis_inverted"])
        self.assertFalse(metadata["y_axis_inverted"])
        self.assertEqual(metadata["vertical_markers"], [])
        self.assertIn("effective_configuration", metadata)


def _fixture_dataset():
    return FixtureSessionGateway(FIXTURE_PATH).load_session(
        SessionQuery(
            season=2023,
            event="Bahrain Grand Prix",
            session="Race",
            drivers=["VER", "PER", "ALO"],
        )
    )


if __name__ == "__main__":
    unittest.main()

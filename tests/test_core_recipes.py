from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from f1_telemetry_charts.analysis.orchestrator import run_analysis
from f1_telemetry_charts.config.models import ProjectConfig
from f1_telemetry_charts.config.validation import validate_config
from f1_telemetry_charts.recipes.registry import default_recipe_registry


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


if __name__ == "__main__":
    unittest.main()

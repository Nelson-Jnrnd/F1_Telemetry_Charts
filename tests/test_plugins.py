from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from f1_telemetry_charts.analysis.orchestrator import run_analysis
from f1_telemetry_charts.config.validation import validate_config
from f1_telemetry_charts.plugins import PluginDiscoveryConfig, PluginManager
from f1_telemetry_charts.ui.server import create_app


class PluginTests(unittest.TestCase):
    def test_local_path_plugin_discovers_and_runs_recipe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_dir = _write_plugin(Path(temp_dir) / "plugin")
            config = validate_config(
                {
                    "schema_version": 1,
                    "project_id": "plugin-run",
                    "output_dir": temp_dir,
                    "session": {
                        "season": 2023,
                        "event": "Bahrain Grand Prix",
                        "session": "Race",
                    },
                    "driver_selection": {"drivers": ["VER", "PER"]},
                    "data_cache": {
                        "fixture_path": "tests/fixtures/2023_bahrain_race_dataset.json"
                    },
                    "plugins": {
                        "enabled": True,
                        "local_paths": [str(plugin_dir)],
                    },
                    "recipes": [{"recipe_id": "plugin_constant_line"}],
                }
            )

            result = run_analysis(config)

        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.manifest.artifacts[0].recipe_id, "plugin_constant_line")

    def test_duplicate_plugin_recipe_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_dir = _write_plugin(
                Path(temp_dir) / "plugin",
                recipe_id="lap_time_delta",
            )
            statuses = PluginManager(
                PluginDiscoveryConfig(enabled=True, local_paths=[plugin_dir])
            ).discover()

        self.assertEqual(statuses[0].status, "invalid")
        self.assertIn("Duplicate recipe ID", statuses[0].errors[0])

    def test_entry_point_plugin_discovery(self) -> None:
        fake = _FakeEntryPoint(
            {
                "plugin_id": "entry-plugin",
                "display_name": "Entry plugin",
                "version": "1.0.0",
                "provider": "tests",
                "recipes": [],
            }
        )

        with patch("f1_telemetry_charts.plugins.manager.entry_points", return_value=[fake]):
            statuses = PluginManager(
                PluginDiscoveryConfig(enabled=True, entry_points_enabled=True)
            ).discover()

        self.assertEqual(statuses[0].status, "valid")
        self.assertEqual(statuses[0].plugin_id, "entry-plugin")

    def test_plugin_validation_api_returns_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_dir = _write_plugin(Path(temp_dir) / "plugin")
            client = TestClient(create_app())

            response = client.post(
                "/api/plugins/validate",
                json={"enabled": True, "local_paths": [str(plugin_dir)]},
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()[0]["status"], "valid")


class _FakeEntryPoint:
    name = "entry-plugin"
    value = "tests:plugin"

    def __init__(self, definition: dict):
        self._definition = definition

    def load(self):
        return self._definition


def _write_plugin(path: Path, recipe_id: str = "plugin_constant_line") -> Path:
    path.mkdir(parents=True)
    (path / "plugin_recipe.py").write_text(
        f'''
from f1_telemetry_charts.charts.models import ChartSpec, SeriesSpec


class PluginConstantRecipe:
    recipe_id = "{recipe_id}"

    def build_spec(self, dataset, config):
        return ChartSpec(
            recipe_id=self.recipe_id,
            title=config.title or "Plugin constant line",
            x_label="Lap",
            y_label="Value",
            selected_drivers=[driver.abbreviation for driver in dataset.drivers],
            source_session=dataset.metadata.model_dump(mode="json"),
            series=[SeriesSpec(label="constant", x=[1.0, 2.0, 3.0], y=[1.0, 1.0, 1.0])],
        )
'''.strip(),
        encoding="utf-8",
    )
    (path / "f1tc-plugin.json").write_text(
        json.dumps(
            {
                "plugin_id": "test-plugin",
                "display_name": "Test plugin",
                "version": "1.0.0",
                "provider": "tests",
                "recipes": [
                    {
                        "recipe_id": recipe_id,
                        "display_name": "Plugin constant line",
                        "required_dataset_fields": ["laps"],
                        "factory": "plugin_recipe:PluginConstantRecipe",
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    unittest.main()

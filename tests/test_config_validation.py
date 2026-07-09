from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from f1_telemetry_charts import ConfigValidationError, load_config, validate_config


class ConfigValidationTests(unittest.TestCase):
    def test_example_config_loads(self) -> None:
        config = load_config(Path("configs/bahrain-race.toml"))

        self.assertEqual(config.schema_version, 1)
        self.assertEqual(config.project_id, "2023-bahrain-race")
        self.assertEqual(config.session.season, 2023)
        self.assertEqual(config.recipes[0].recipe_id, "lap_time_delta")

    def test_unknown_top_level_key_reports_path(self) -> None:
        raw = _minimal_config()
        raw["unexpected"] = True

        with self.assertRaises(ConfigValidationError) as raised:
            validate_config(raw)

        self.assertEqual(raised.exception.issues[0].path, "$.unexpected")

    def test_unknown_recipe_id_reports_path(self) -> None:
        raw = _minimal_config()
        raw["recipes"] = [{"recipe_id": "unknown_recipe"}]

        with self.assertRaises(ConfigValidationError) as raised:
            validate_config(raw)

        self.assertEqual(raised.exception.issues[0].path, "$.recipes[0].recipe_id")
        self.assertIn("unknown_recipe", raised.exception.issues[0].message)

    def test_unsupported_file_format_reports_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.yml"
            path.write_text("schema_version: 1\n", encoding="utf-8")

            with self.assertRaises(ConfigValidationError) as raised:
                load_config(path)

        self.assertEqual(raised.exception.issues[0].path, "$")
        self.assertIn("Unsupported configuration format", raised.exception.issues[0].message)


def _minimal_config() -> dict[str, object]:
    return {
        "schema_version": 1,
        "project_id": "test-project",
        "session": {
            "season": 2023,
            "event": "Bahrain Grand Prix",
            "session": "Race",
        },
        "driver_selection": {"drivers": ["VER", "PER"]},
        "recipes": [{"recipe_id": "lap_time_delta"}],
    }


if __name__ == "__main__":
    unittest.main()

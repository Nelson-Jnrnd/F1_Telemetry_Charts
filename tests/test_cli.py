from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CliTests(unittest.TestCase):
    def test_module_help_succeeds(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "f1_telemetry_charts", "--help"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0)
        self.assertIn("Generate consistent F1 analysis chart packages", completed.stdout)

    def test_config_validate_json_succeeds(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "f1_telemetry_charts",
                "config",
                "validate",
                "configs/bahrain-race.toml",
                "--json",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "valid")
        self.assertEqual(payload["schema_version"], 1)
        self.assertIn("lap_time_delta", payload["recipes"])

    def test_generate_json_succeeds_with_fixture_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            config_path.write_text(
                f"""
schema_version = 1
project_id = "cli-test"
output_dir = "{Path(temp_dir).as_posix()}"

[session]
season = 2023
event = "Bahrain Grand Prix"
session = "Race"

[driver_selection]
drivers = ["VER", "PER"]

[data_cache]
fixture_path = "tests/fixtures/2023_bahrain_race_dataset.json"

[[recipes]]
recipe_id = "lap_time_delta"
""".strip(),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "f1_telemetry_charts",
                    "generate",
                    str(config_path),
                    "--json",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "succeeded")
            self.assertTrue(Path(payload["manifest_path"]).exists())

    def test_preview_check_only_reports_url(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            config_path.write_text(
                f"""
schema_version = 1
project_id = "preview-cli-test"
output_dir = "{Path(temp_dir).as_posix()}"

[session]
season = 2023
event = "Bahrain Grand Prix"
session = "Race"

[driver_selection]
drivers = ["VER", "PER"]

[data_cache]
fixture_path = "tests/fixtures/2023_bahrain_race_dataset.json"

[[recipes]]
recipe_id = "lap_time_delta"
""".strip(),
                encoding="utf-8",
            )
            generated = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "f1_telemetry_charts",
                    "generate",
                    str(config_path),
                    "--json",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(generated.returncode, 0, generated.stderr)
            package_path = json.loads(generated.stdout)["output_dir"]

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "f1_telemetry_charts",
                    "preview",
                    package_path,
                    "--check-only",
                    "--json",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["url"], "http://127.0.0.1:8000")


if __name__ == "__main__":
    unittest.main()

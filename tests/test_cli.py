from __future__ import annotations

import json
import subprocess
import sys
import unittest


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


if __name__ == "__main__":
    unittest.main()

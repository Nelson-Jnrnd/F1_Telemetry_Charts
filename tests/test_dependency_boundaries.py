from __future__ import annotations

import json
import subprocess
import sys
import unittest


class DependencyBoundaryTests(unittest.TestCase):
    def test_core_import_does_not_import_fastapi(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import json, sys; import f1_telemetry_charts; "
                    "print(json.dumps({'fastapi': 'fastapi' in sys.modules, "
                    "'ui': 'f1_telemetry_charts.ui.server' in sys.modules}))"
                ),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertFalse(payload["fastapi"])
        self.assertFalse(payload["ui"])


if __name__ == "__main__":
    unittest.main()

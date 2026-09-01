from __future__ import annotations

import json
import ast
from pathlib import Path
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

    def test_weekend_composer_does_not_import_source_data_or_analytics(self) -> None:
        source = Path("src/f1_telemetry_charts/analysis/weekend.py").read_text(encoding="utf-8")
        imports = {
            node.module
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.ImportFrom) and node.module
        }
        forbidden = {
            value
            for value in imports
            if value.startswith("f1_telemetry_charts.data")
            or value.startswith("f1_telemetry_charts.recipes")
            or value in {
                "f1_telemetry_charts.analysis.practice",
                "f1_telemetry_charts.analysis.qualifying",
                "f1_telemetry_charts.analysis.publication",
            }
        }
        self.assertEqual(set(), forbidden)


if __name__ == "__main__":
    unittest.main()

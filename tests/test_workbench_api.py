from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from f1_telemetry_charts.ui.server import create_app


class WorkbenchApiTests(unittest.TestCase):
    def test_config_validate_save_run_and_history_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _raw_config(Path(temp_dir))
            client = TestClient(create_app())

            validated = client.post("/api/config/validate", json={"config": config})
            self.assertEqual(validated.status_code, 200, validated.text)
            self.assertEqual(validated.json()["status"], "valid")

            save_path = Path(temp_dir) / "saved-config.json"
            saved = client.post(
                "/api/config/save",
                json={"path": str(save_path), "config": config},
            )
            self.assertEqual(saved.status_code, 200, saved.text)
            self.assertTrue(save_path.exists())

            loaded = client.post("/api/config/load", json={"path": str(save_path)})
            self.assertEqual(loaded.status_code, 200, loaded.text)
            self.assertEqual(loaded.json()["status"], "valid")

            run = client.post("/api/config/run", json={"config": config})
            self.assertEqual(run.status_code, 200, run.text)
            self.assertEqual(run.json()["status"], "succeeded")

            history = client.get("/api/history")
            self.assertEqual(history.status_code, 200, history.text)
            self.assertEqual(history.json()[0]["action"], "generated")

            cleared = client.delete("/api/history")
            self.assertEqual(cleared.status_code, 200, cleared.text)
            self.assertEqual(client.get("/api/history").json(), [])

    def test_config_validate_returns_path_specific_errors(self) -> None:
        client = TestClient(create_app())

        response = client.post(
            "/api/config/validate",
            json={"config": {"schema_version": 1}},
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["status"], "invalid")
        self.assertTrue(any(issue["path"].startswith("$") for issue in payload["issues"]))


def _raw_config(output_dir: Path) -> dict:
    return {
        "schema_version": 1,
        "project_id": "workbench-api-test",
        "output_dir": str(output_dir),
        "session": {
            "season": 2023,
            "event": "Bahrain Grand Prix",
            "session": "Race",
        },
        "driver_selection": {"drivers": ["VER", "PER"]},
        "data_cache": {
            "fixture_path": "tests/fixtures/2023_bahrain_race_dataset.json"
        },
        "recipes": [{"recipe_id": "lap_time_delta"}],
    }


if __name__ == "__main__":
    unittest.main()

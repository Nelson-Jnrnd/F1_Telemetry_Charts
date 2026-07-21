from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from f1_telemetry_charts.analysis.orchestrator import run_analysis
from f1_telemetry_charts.config.models import (
    ChartRecipeConfig,
    DriverSelectionConfig,
    ProjectConfig,
    SessionConfig,
)
from f1_telemetry_charts.preview import (
    PackagePreviewError,
    read_package_view,
    resolve_package_asset,
)
from f1_telemetry_charts.ui.server import create_app


class PackagePreviewTests(unittest.TestCase):
    def test_read_package_view_reports_healthy_generated_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_analysis(_config(Path(temp_dir)))

            view = read_package_view(result.output_dir)

        self.assertEqual(view.health.status, "healthy")
        self.assertIsNotNone(view.manifest)
        self.assertGreaterEqual(len(view.observations), 1)
        self.assertIsNotNone(view.draft_markdown)

    def test_read_package_view_reports_missing_chart_asset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_analysis(_config(Path(temp_dir)))
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            missing = result.output_dir / manifest["artifacts"][0]["image_path"]
            missing.unlink()

            view = read_package_view(result.output_dir)

        self.assertEqual(view.health.status, "unhealthy")
        self.assertIn("image_path_missing", {finding.code for finding in view.health.findings})

    def test_resolve_package_asset_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(PackagePreviewError):
                resolve_package_asset(temp_dir, "../outside.txt")

    def test_api_opens_package_and_serves_asset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_analysis(_config(Path(temp_dir)))
            client = TestClient(create_app())

            opened = client.post(
                "/api/package/open",
                json={"path": str(result.output_dir)},
            )
            self.assertEqual(opened.status_code, 200, opened.text)
            payload = opened.json()
            asset_path = payload["manifest"]["artifacts"][0]["image_path"]

            asset = client.get(f"/api/package/assets/{asset_path}")

        self.assertEqual(asset.status_code, 200, asset.text)

    def test_ui_index_static_asset_links_resolve(self) -> None:
        client = TestClient(create_app())

        response = client.get("/")
        self.assertEqual(response.status_code, 200, response.text)
        asset_paths = re.findall(r'["\'](/assets/[^"\']+)["\']', response.text)

        self.assertGreaterEqual(len(asset_paths), 1)
        for asset_path in asset_paths:
            asset = client.get(asset_path)
            self.assertEqual(asset.status_code, 200, asset_path)

    def test_api_review_update_and_draft_regeneration(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_analysis(_config(Path(temp_dir)))
            view = read_package_view(result.output_dir)
            observation_id = view.observations[0]["observation_id"]
            original_text = view.observations[0]["text"]
            client = TestClient(create_app(result.output_dir))

            updated = client.put(
                f"/api/package/observations/{observation_id}/review",
                json={"review_status": "rejected"},
            )
            self.assertEqual(updated.status_code, 200, updated.text)
            regenerated = client.post("/api/package/draft/regenerate")
            self.assertEqual(regenerated.status_code, 200, regenerated.text)

            draft = result.markdown_path.read_text(encoding="utf-8")

        self.assertNotIn(original_text, draft)


def _config(output_dir: Path) -> ProjectConfig:
    return ProjectConfig(
        schema_version=1,
        project_id="preview-test",
        output_dir=output_dir,
        session=SessionConfig(
            season=2023,
            event="Bahrain Grand Prix",
            session="Race",
        ),
        driver_selection=DriverSelectionConfig(drivers=["VER", "PER"]),
        data_cache={"fixture_path": Path("tests/fixtures/2023_bahrain_race_dataset.json")},
        recipes=[ChartRecipeConfig(recipe_id="lap_time_delta")],
    )


if __name__ == "__main__":
    unittest.main()

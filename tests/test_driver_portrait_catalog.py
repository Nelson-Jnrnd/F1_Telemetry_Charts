from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
MANIFEST_PATH = ROOT / "frontend" / "src" / "data" / "driverPortraits.json"
ASSET_ROOT = ROOT / "frontend" / "public"


class DriverPortraitCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_catalog_has_historical_telemetry_era_coverage(self) -> None:
        self.assertEqual(self.manifest["schema_version"], 1)
        for season in range(2018, 2027):
            with self.subTest(season=season):
                self.assertGreaterEqual(len(self.manifest["entries"][str(season)]), 20)

    def test_catalog_paths_and_hashes_match_local_png_assets(self) -> None:
        for season, entries in self.manifest["entries"].items():
            for code, entry in entries.items():
                with self.subTest(season=season, code=code):
                    self.assertEqual(entry["code"], code)
                    self.assertEqual(entry["path"], f"/portraits/{season}/{code}.png")
                    asset = ASSET_ROOT / entry["path"].removeprefix("/")
                    image = asset.read_bytes()
                    self.assertTrue(image.startswith(b"\x89PNG\r\n\x1a\n"))
                    self.assertEqual(hashlib.sha256(image).hexdigest(), entry["sha256"])

    def test_same_driver_uses_distinct_assets_across_seasons(self) -> None:
        hashes = {
            self.manifest["entries"][str(season)]["HAM"]["sha256"]
            for season in (2018, 2020, 2022, 2024, 2026)
        }
        self.assertEqual(len(hashes), 5)


if __name__ == "__main__":
    unittest.main()

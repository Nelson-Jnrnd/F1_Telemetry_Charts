"""Build the versioned local driver-portrait catalog used by the frontend.

The script uses Jolpica's season driver index to constrain portrait candidates
to real season participants, then downloads the matching season asset from the
MultiViewer mirror used as the fallback by JustJoostNL/f1-headshots.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_FIRST_SEASON = 2017
DEFAULT_LAST_SEASON = 2026
JOLPICA_URL = "https://api.jolpi.ca/ergast/f1/{season}/drivers.json?limit=100"
PORTRAIT_URL = "https://assets.multiviewer.dev/driver-headshots/{season}/{code}.png"
OFFICIAL_PORTRAIT_URL = (
    "https://media.formula1.com/content/dam/fom-website/"
    "2018-redesign-assets/drivers/{season}/{reference}.png"
)
SOURCE_PROJECT = "https://github.com/JustJoostNL/f1-headshots"
DATASET_PROJECT = "https://github.com/toUpperCase78/formula1-datasets"
DATASET_DIRECTORY_URL = (
    "https://api.github.com/repos/toUpperCase78/formula1-datasets/contents/"
    "F1%20{season}%20Season%20Drivers"
)
USER_AGENT = "F1-Telemetry-Charts portrait catalog maintainer"


def _request(url: str, *, attempts: int = 3) -> bytes:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=30) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.5 * (attempt + 1))
    assert last_error is not None
    raise last_error


def _season_drivers(season: int) -> list[dict[str, str]]:
    payload = json.loads(_request(JOLPICA_URL.format(season=season)))
    drivers = payload["MRData"]["DriverTable"]["Drivers"]
    normalized: list[dict[str, str]] = []
    for driver in drivers:
        code = str(driver.get("code") or "").strip().upper()
        if not code:
            continue
        normalized.append(
            {
                "code": code,
                "driver_id": str(driver.get("driverId") or ""),
                "full_name": " ".join(
                    part
                    for part in (
                        str(driver.get("givenName") or "").strip(),
                        str(driver.get("familyName") or "").strip(),
                    )
                    if part
                ),
            }
        )
    return sorted(normalized, key=lambda item: item["code"])


def _driver_reference(full_name: str) -> str:
    parts = full_name.split()
    if len(parts) < 2:
        return ""
    normalized = unicodedata.normalize("NFKD", full_name).encode("ascii", "ignore").decode()
    normalized_parts = normalized.split()
    return f"{normalized_parts[0][:3]}{normalized_parts[-1][:3]}01".upper()


def _normalized_asset_name(value: str) -> str:
    return "_".join(
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode()
        .replace("'", "")
        .lower()
        .split()
    )


def _dataset_portrait_urls(season: int) -> dict[str, str]:
    try:
        payload = json.loads(_request(DATASET_DIRECTORY_URL.format(season=season)))
    except (HTTPError, URLError, TimeoutError):
        return {}
    return {
        str(item.get("name") or "").lower(): str(item.get("download_url") or "")
        for item in payload
        if str(item.get("name") or "").lower().endswith(".png")
        and item.get("download_url")
    }


def build_catalog(
    *,
    first_season: int,
    last_season: int,
    asset_root: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    if first_season > last_season:
        raise ValueError("first season must not be after last season")

    entries: dict[str, dict[str, dict[str, str]]] = {}
    missing: list[dict[str, str | int]] = []
    asset_root.mkdir(parents=True, exist_ok=True)

    for season in range(first_season, last_season + 1):
        season_entries: dict[str, dict[str, str]] = {}
        dataset_urls = _dataset_portrait_urls(season)
        season_dir = asset_root / str(season)
        season_dir.mkdir(parents=True, exist_ok=True)
        for driver in _season_drivers(season):
            code = driver["code"]
            reference = _driver_reference(driver["full_name"])
            source_urls = [
                OFFICIAL_PORTRAIT_URL.format(season=season, reference=reference),
                PORTRAIT_URL.format(season=season, code=code),
            ]
            asset_prefix = f"{_normalized_asset_name(driver['full_name'])}_"
            source_urls.extend(
                url
                for name, url in sorted(dataset_urls.items())
                if name.startswith(asset_prefix)
            )
            image: bytes | None = None
            source_url = ""
            errors: list[str] = []
            for candidate_url in source_urls:
                try:
                    image = _request(candidate_url)
                    source_url = candidate_url
                    break
                except (HTTPError, URLError, TimeoutError) as exc:
                    errors.append(str(exc))
            if image is None:
                missing.append(
                    {"season": season, "code": code, "reason": "; ".join(errors)}
                )
                continue
            if not image.startswith(b"\x89PNG\r\n\x1a\n"):
                missing.append(
                    {"season": season, "code": code, "reason": "not a PNG"}
                )
                continue
            relative_path = f"portraits/{season}/{code}.png"
            target = season_dir / f"{code}.png"
            target.write_bytes(image)
            season_entries[code] = {
                **driver,
                "path": f"/{relative_path}",
                "source_url": source_url,
                "sha256": hashlib.sha256(image).hexdigest(),
            }
        entries[str(season)] = season_entries
        print(f"{season}: {len(season_entries)} portraits")

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "first_season": first_season,
        "last_season": last_season,
        "roster_source": JOLPICA_URL,
        "portrait_source_projects": [SOURCE_PROJECT, DATASET_PROJECT],
        "portrait_source_templates": [OFFICIAL_PORTRAIT_URL, PORTRAIT_URL],
        "entries": entries,
        "missing": missing,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first-season", type=int, default=DEFAULT_FIRST_SEASON)
    parser.add_argument("--last-season", type=int, default=DEFAULT_LAST_SEASON)
    parser.add_argument(
        "--asset-root",
        type=Path,
        default=Path("frontend/public/portraits"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("frontend/src/data/driverPortraits.json"),
    )
    args = parser.parse_args()
    manifest = build_catalog(
        first_season=args.first_season,
        last_season=args.last_season,
        asset_root=args.asset_root,
        manifest_path=args.manifest,
    )
    count = sum(len(entries) for entries in manifest["entries"].values())
    print(f"Wrote {count} portraits; {len(manifest['missing'])} unavailable")


if __name__ == "__main__":
    main()

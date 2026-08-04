#!/usr/bin/env python3
"""Build and benchmark the SPEC-002 representative package preview fixture."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import time
from pathlib import Path

from f1_telemetry_charts.preview import read_package_view


MAX_PREVIEW_SECONDS = 3.0
CHART_COUNT = 20
OBSERVATION_COUNT = 50


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-analysis",
        type=Path,
        default=Path("analyses/race-analysis"),
    )
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    if args.output_dir is None:
        with tempfile.TemporaryDirectory() as temp_dir:
            return _run(args.source_analysis, Path(temp_dir) / "spec002-scale-analysis")
    if args.output_dir.exists():
        parser.error(f"output directory already exists: {args.output_dir}")
    return _run(args.source_analysis, args.output_dir)


def _run(source_analysis: Path, output_dir: Path) -> int:
    fixture_dir = _create_scale_analysis(source_analysis.resolve(), output_dir.resolve())
    package_dir = fixture_dir / "package"
    started = time.perf_counter()
    view = read_package_view(package_dir)
    elapsed = time.perf_counter() - started
    chart_count = len(view.manifest.artifacts) if view.manifest else 0
    payload = {
        "analysis_path": str(fixture_dir),
        "package_path": str(package_dir),
        "preview_seconds": round(elapsed, 4),
        "max_preview_seconds": MAX_PREVIEW_SECONDS,
        "chart_count": chart_count,
        "observation_count": len(view.observations),
        "health": view.health.status,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    failures: list[str] = []
    if elapsed > MAX_PREVIEW_SECONDS:
        failures.append("preview load exceeded threshold")
    if chart_count != CHART_COUNT:
        failures.append(f"expected {CHART_COUNT} charts, found {chart_count}")
    if len(view.observations) != OBSERVATION_COUNT:
        failures.append(
            f"expected {OBSERVATION_COUNT} observations, found {len(view.observations)}"
        )
    if view.health.status != "healthy":
        failures.append(f"fixture health was {view.health.status}")
    if failures:
        print("Benchmark failed: " + "; ".join(failures))
        return 1
    return 0


def _create_scale_analysis(source: Path, destination: Path) -> Path:
    if not (source / "analysis.json").is_file() or not (source / "package").is_dir():
        raise ValueError(f"Source Analysis is incomplete: {source}")
    shutil.copytree(source, destination)

    analysis_path = destination / "analysis.json"
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    source_chart = analysis["charts"][0]
    source_image = destination / source_chart["image_path"]
    source_metadata = destination / source_chart["metadata_path"]

    package_dir = destination / "package"
    manifest_path = package_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_artifact = manifest["artifacts"][0]

    analysis_charts: list[dict] = []
    package_artifacts: list[dict] = []
    package_recipes: list[dict] = []
    for index in range(1, CHART_COUNT + 1):
        chart_id = f"chart-scale-{index:02d}"
        artifact_id = f"scale-artifact-{index:02d}"
        analysis_image_path = Path("charts") / chart_id / f"{artifact_id}.png"
        analysis_metadata_path = Path("charts") / chart_id / f"{artifact_id}.json"
        destination_image = destination / analysis_image_path
        destination_metadata = destination / analysis_metadata_path
        destination_image.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_image, destination_image)
        shutil.copy2(source_metadata, destination_metadata)

        chart = dict(source_chart)
        chart.update(
            {
                "chart_instance_id": chart_id,
                "artifact_id": artifact_id,
                "name": f"Scale chart {index:02d}",
                "order": index,
                "image_path": analysis_image_path.as_posix(),
                "metadata_path": analysis_metadata_path.as_posix(),
            }
        )
        analysis_charts.append(chart)

        relative_image = Path("charts") / chart_id / f"{artifact_id}.png"
        relative_metadata = Path("charts") / chart_id / f"{artifact_id}.json"
        preview_image = package_dir / relative_image
        preview_metadata = package_dir / relative_metadata
        preview_image.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_image, preview_image)
        shutil.copy2(source_metadata, preview_metadata)
        artifact = dict(source_artifact)
        artifact.update(
            {
                "artifact_id": artifact_id,
                "image_path": relative_image.as_posix(),
                "metadata_path": relative_metadata.as_posix(),
            }
        )
        package_artifacts.append(artifact)
        package_recipes.append(
            {
                "recipe_id": artifact["recipe_id"],
                "status": "produced",
                "artifact_id": artifact_id,
                "warnings": [],
                "error": None,
            }
        )

    source_observations = json.loads(
        (package_dir / manifest["observations_path"]).read_text(encoding="utf-8")
    )
    observations: list[dict] = []
    source_evidence = source_observations[0]["evidence"][0]
    for index in range(1, OBSERVATION_COUNT + 1):
        observation = dict(source_observations[(index - 1) % len(source_observations)])
        artifact = package_artifacts[(index - 1) % CHART_COUNT]
        evidence = dict(source_evidence)
        evidence.update(
            {
                "artifact_id": artifact["artifact_id"],
                "recipe_id": artifact["recipe_id"],
                "image_path": artifact["image_path"],
                "metadata_path": artifact["metadata_path"],
            }
        )
        observation.update(
            {
                "observation_id": f"scale-observation-{index:02d}",
                "evidence": [evidence],
            }
        )
        observations.append(observation)

    review = [
        {
            "observation_id": observation["observation_id"],
            "review_status": observation.get("review_status", "unreviewed"),
            "edited_text": observation.get("edited_text"),
        }
        for observation in observations
    ]
    (package_dir / manifest["observations_path"]).write_text(
        json.dumps(observations, indent=2, sort_keys=True), encoding="utf-8"
    )
    (package_dir / manifest["review_path"]).write_text(
        json.dumps(review, indent=2, sort_keys=True), encoding="utf-8"
    )
    manifest.update(
        {
            "artifacts": package_artifacts,
            "recipes": package_recipes,
            "requested_recipes": [artifact["recipe_id"] for artifact in package_artifacts],
            "analysis_path": str(destination),
        }
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    analysis.update(
        {
            "charts": analysis_charts,
            "exported_package_path": str(package_dir),
        }
    )
    analysis_path.write_text(json.dumps(analysis, indent=2, sort_keys=True), encoding="utf-8")
    return destination


if __name__ == "__main__":
    raise SystemExit(main())

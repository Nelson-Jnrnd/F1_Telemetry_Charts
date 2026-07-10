"""Analysis run orchestration."""

from __future__ import annotations

import hashlib
import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from f1_telemetry_charts.analysis.manifest import (
    ArtifactManifest,
    ChartArtifactEntry,
    RecipeRunEntry,
)
from f1_telemetry_charts.charts.renderers import MatplotlibRenderer
from f1_telemetry_charts.config.models import ProjectConfig
from f1_telemetry_charts.data import SessionQuery
from f1_telemetry_charts.data.gateways import FastF1SessionGateway, FixtureSessionGateway
from f1_telemetry_charts.recipes.registry import default_recipe_registry


class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    output_dir: Path
    manifest_path: Path
    manifest: ArtifactManifest


def run_analysis(config: ProjectConfig) -> AnalysisResult:
    config_hash = _configuration_hash(config)
    run_id = _run_id(config, config_hash)
    output_dir = config.output_dir / run_id
    charts_dir = output_dir / "charts"
    manifest_path = output_dir / "manifest.json"

    dataset = _load_dataset(config)
    registry = default_recipe_registry()
    renderer = MatplotlibRenderer()

    artifacts: list[ChartArtifactEntry] = []
    recipe_entries: list[RecipeRunEntry] = []
    errors: list[str] = []
    warnings: list[str] = []

    for recipe_config in config.recipes:
        recipe_id = recipe_config.recipe_id
        try:
            recipe = registry.create(recipe_id)
            spec = recipe.build_spec(dataset, recipe_config)
            artifact_id = f"{recipe_id}-{config_hash[:8]}"
            artifact = renderer.render(
                spec,
                theme=config.theme,
                output_dir=charts_dir,
                artifact_id=artifact_id,
            )
            artifacts.append(
                ChartArtifactEntry(
                    artifact_id=artifact.artifact_id,
                    recipe_id=recipe_id,
                    image_path=_relative_path(artifact.image_path, output_dir),
                    metadata_path=_relative_path(artifact.metadata_path, output_dir),
                )
            )
            recipe_entries.append(
                RecipeRunEntry(
                    recipe_id=recipe_id,
                    status="produced",
                    artifact_id=artifact.artifact_id,
                    warnings=spec.warnings,
                )
            )
        except Exception as exc:
            error = f"{recipe_id}: {exc}"
            errors.append(error)
            recipe_entries.append(
                RecipeRunEntry(recipe_id=recipe_id, status="failed", error=str(exc))
            )

    if artifacts and errors:
        status = "partially_succeeded"
    elif artifacts:
        status = "succeeded"
    else:
        status = "failed"

    manifest = ArtifactManifest(
        run_id=run_id,
        status=status,
        framework_version=_framework_version(),
        configuration_hash=config_hash,
        session={
            "season": config.session.season,
            "event": config.session.event,
            "session": config.session.session,
        },
        requested_recipes=[recipe.recipe_id for recipe in config.recipes],
        artifacts=artifacts,
        recipes=recipe_entries,
        warnings=warnings,
        errors=errors,
    )
    manifest.write(manifest_path)
    return AnalysisResult(
        status=status,
        output_dir=output_dir,
        manifest_path=manifest_path,
        manifest=manifest,
    )


def _load_dataset(config: ProjectConfig):
    query = SessionQuery(
        season=config.session.season,
        event=config.session.event,
        session=config.session.session,
        drivers=config.driver_selection.drivers,
    )
    if config.data_cache.fixture_path is not None:
        return FixtureSessionGateway(config.data_cache.fixture_path).load_session(query)
    return FastF1SessionGateway(
        config.data_cache.directory,
        cache_only=config.data_cache.mode == "cache-only",
    ).load_session(query)


def _configuration_hash(config: ProjectConfig) -> str:
    raw = json.dumps(
        config.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _run_id(config: ProjectConfig, config_hash: str) -> str:
    return f"{config.project_id}-{config_hash[:8]}"


def _relative_path(path: Path, base: Path) -> str:
    return path.relative_to(base).as_posix()


def _framework_version() -> str:
    try:
        return version("f1-telemetry-charts")
    except PackageNotFoundError:
        return "0.0.0+local"

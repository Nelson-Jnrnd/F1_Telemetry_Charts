"""Saved Analysis workspace models and staged generation helpers."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from f1_telemetry_charts.analysis.engine import extract_observations
from f1_telemetry_charts.analysis.manifest import (
    ArtifactManifest,
    ChartArtifactEntry,
    RecipeRunEntry,
)
from f1_telemetry_charts.analysis.observations import Observation
from f1_telemetry_charts.analysis.report import write_report_package
from f1_telemetry_charts.charts.renderers import MatplotlibRenderer
from f1_telemetry_charts.config.models import (
    ChartRecipeConfig,
    DataCacheConfig,
    PluginConfig,
    SessionConfig,
    ThemeConfig,
)
from f1_telemetry_charts.data import SessionDataset, SessionQuery
from f1_telemetry_charts.data.gateways import FastF1SessionGateway, FixtureSessionGateway
from f1_telemetry_charts.plugins import build_recipe_registry
from f1_telemetry_charts.recipes.registry import RecipeMetadata, RecipeRegistry


SessionLoadState = Literal["not_loaded", "loading", "loaded", "failed", "stale"]
ChartGenerationState = Literal["not_generated", "generated", "failed", "stale"]
PresetScope = Literal["analysis", "global"]
_KEEP_PRESET = object()
ParameterFieldType = Literal[
    "text",
    "number",
    "checkbox",
    "select",
    "multi_select",
    "driver_selector",
    "lap_range",
    "color",
]


class ParameterField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    label: str = Field(min_length=1)
    field_type: ParameterFieldType
    required: bool = False
    default: Any = None
    options: list[str] = Field(default_factory=list)
    minimum: float | None = None
    maximum: float | None = None
    group: str | None = None
    order: int = 0


class RecipeParameterSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipe_id: str
    schema_version: int = 1
    fields: list[ParameterField] = Field(default_factory=list)


class DatasetSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    session_id: str
    query: SessionQuery
    source_type: Literal["fixture", "fastf1"]
    cache_mode: Literal["cache-or-fetch", "cache-only"]
    snapshot_path: str
    dataset_path: str
    created_at: datetime
    framework_version: str
    dataset_hash: str
    provenance: dict[str, Any] = Field(default_factory=dict)


class AnalysisSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    name: str
    session: SessionConfig
    drivers: list[str] = Field(min_length=1)
    data_cache: DataCacheConfig = Field(default_factory=DataCacheConfig)
    load_state: SessionLoadState = "not_loaded"
    snapshot: DatasetSnapshot | None = None
    stale: bool = False
    errors: list[str] = Field(default_factory=list)


class ChartInstance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chart_instance_id: str
    recipe_id: str
    name: str
    target_session_ids: list[str] = Field(min_length=1)
    enabled: bool = True
    parameters: dict[str, Any] = Field(default_factory=dict)
    parameter_hash: str
    schema_version: int = 1
    preset_id: str | None = None
    order: int = 0
    generation_state: ChartGenerationState = "not_generated"
    artifact_id: str | None = None
    image_path: str | None = None
    metadata_path: str | None = None
    stale: bool = False
    observations_stale: bool = False
    errors: list[str] = Field(default_factory=list)


class ParameterPreset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preset_id: str
    recipe_id: str
    schema_version: int = 1
    display_name: str
    scope: PresetScope
    parameters: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    notes: str | None = None


class AnalysisWorkspace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_id: str
    name: str
    root_path: Path
    schema_version: int = 1
    created_at: datetime
    updated_at: datetime
    theme: ThemeConfig = Field(default_factory=ThemeConfig)
    plugins: PluginConfig = Field(default_factory=PluginConfig)
    sessions: list[AnalysisSession] = Field(default_factory=list)
    charts: list[ChartInstance] = Field(default_factory=list)
    presets: list[ParameterPreset] = Field(default_factory=list)
    review_stale: bool = False
    exported_package_path: str | None = None
    errors: list[str] = Field(default_factory=list)


class AnalysisView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis: AnalysisWorkspace
    recipe_schemas: list[RecipeParameterSchema]
    recipes: list[dict[str, Any]]
    global_presets: list[ParameterPreset] = Field(default_factory=list)


class AnalysisService:
    def __init__(self, root: Path | str):
        self.root = _resolve_analysis_root(root)

    def create(self, name: str = "Untitled Analysis") -> AnalysisWorkspace:
        now = _now()
        analysis = AnalysisWorkspace(
            analysis_id=_slug_id(name or "analysis"),
            name=name or "Untitled Analysis",
            root_path=self.root,
            created_at=now,
            updated_at=now,
        )
        self.save(analysis)
        return analysis

    def open(self) -> AnalysisWorkspace:
        path = _analysis_file(self.root)
        raw = json.loads(path.read_text(encoding="utf-8"))
        analysis = AnalysisWorkspace.model_validate(raw)
        return analysis.model_copy(update={"root_path": self.root}, deep=True)

    def save(self, analysis: AnalysisWorkspace) -> AnalysisWorkspace:
        updated = analysis.model_copy(
            update={"root_path": self.root, "updated_at": _now()},
            deep=True,
        )
        self.root.mkdir(parents=True, exist_ok=True)
        _write_json(_analysis_file(self.root), updated.model_dump(mode="json"))
        return updated

    def view(self, analysis: AnalysisWorkspace | None = None) -> AnalysisView:
        current = analysis or self.open()
        registry = build_recipe_registry(current.plugins)
        return AnalysisView(
            analysis=current,
            recipe_schemas=list_recipe_parameter_schemas(registry),
            recipes=[_metadata_payload(item) for item in registry.list_metadata()],
            global_presets=list_global_presets(),
        )

    def add_session(
        self,
        analysis: AnalysisWorkspace,
        *,
        session: SessionConfig,
        drivers: list[str],
        data_cache: DataCacheConfig | None = None,
        name: str | None = None,
        load: bool = True,
    ) -> AnalysisWorkspace:
        session_id = _session_id(session, drivers)
        item = AnalysisSession(
            session_id=session_id,
            name=name or f"{session.season} {session.event} {session.session}",
            session=session,
            drivers=drivers,
            data_cache=data_cache or DataCacheConfig(),
        )
        updated = analysis.model_copy(
            update={
                "sessions": [
                    existing
                    for existing in analysis.sessions
                    if existing.session_id != session_id
                ]
                + [item]
            },
            deep=True,
        )
        if load:
            updated = self.load_session(updated, session_id)
        return self.save(updated)

    def load_session(
        self,
        analysis: AnalysisWorkspace,
        session_id: str,
    ) -> AnalysisWorkspace:
        sessions: list[AnalysisSession] = []
        for session in analysis.sessions:
            if session.session_id != session_id:
                sessions.append(session)
                continue
            try:
                dataset = _load_session_dataset(session)
                snapshot = _write_snapshot(self.root, session, dataset)
                sessions.append(
                    session.model_copy(
                        update={
                            "load_state": "loaded",
                            "snapshot": snapshot,
                            "stale": False,
                            "errors": [],
                        },
                        deep=True,
                    )
                )
            except Exception as exc:
                sessions.append(
                    session.model_copy(
                        update={"load_state": "failed", "errors": [str(exc)]},
                        deep=True,
                    )
                )
        return self.save(analysis.model_copy(update={"sessions": sessions}, deep=True))

    def remove_session(
        self,
        analysis: AnalysisWorkspace,
        session_id: str,
        *,
        confirm_delete_dependents: bool = False,
    ) -> AnalysisWorkspace:
        dependent_charts = [
            chart
            for chart in analysis.charts
            if session_id in chart.target_session_ids
        ]
        if dependent_charts and not confirm_delete_dependents:
            names = ", ".join(chart.name for chart in dependent_charts)
            raise ValueError(f"Session has dependent charts: {names}")
        updated = analysis.model_copy(
            update={
                "sessions": [
                    item for item in analysis.sessions if item.session_id != session_id
                ],
                "charts": [
                    chart
                    for chart in analysis.charts
                    if session_id not in chart.target_session_ids
                ],
                "review_stale": bool(dependent_charts) or analysis.review_stale,
            },
            deep=True,
        )
        return self.save(updated)

    def add_chart(
        self,
        analysis: AnalysisWorkspace,
        *,
        recipe_id: str,
        target_session_ids: list[str],
        name: str | None = None,
        parameters: dict[str, Any] | None = None,
        preset_id: str | None = None,
    ) -> AnalysisWorkspace:
        registry = build_recipe_registry(analysis.plugins)
        if not registry.has_recipe(recipe_id):
            raise ValueError(f"Unknown recipe ID: {recipe_id}")
        missing = [
            session_id
            for session_id in target_session_ids
            if session_id not in {session.session_id for session in analysis.sessions}
        ]
        if missing:
            raise ValueError(f"Unknown target session ID(s): {', '.join(missing)}")
        params = parameters or {}
        schema = recipe_parameter_schema(recipe_id)
        _validate_parameters(schema, params)
        chart_id = _chart_id(recipe_id, target_session_ids, params, len(analysis.charts))
        display_name = name or registry.get(recipe_id).display_name
        chart = ChartInstance(
            chart_instance_id=chart_id,
            recipe_id=recipe_id,
            name=display_name,
            target_session_ids=target_session_ids,
            parameters=params,
            parameter_hash=_hash_payload(params),
            schema_version=schema.schema_version,
            preset_id=preset_id,
            order=len(analysis.charts),
        )
        updated = analysis.model_copy(
            update={"charts": analysis.charts + [chart]},
            deep=True,
        )
        return self.save(updated)

    def update_chart(
        self,
        analysis: AnalysisWorkspace,
        chart_id: str,
        *,
        name: str | None = None,
        target_session_ids: list[str] | None = None,
        parameters: dict[str, Any] | None = None,
        preset_id: str | None | object = _KEEP_PRESET,
    ) -> AnalysisWorkspace:
        charts: list[ChartInstance] = []
        found = False
        for chart in analysis.charts:
            if chart.chart_instance_id != chart_id:
                charts.append(chart)
                continue
            found = True
            next_parameters = parameters if parameters is not None else chart.parameters
            _validate_parameters(recipe_parameter_schema(chart.recipe_id), next_parameters)
            charts.append(
                chart.model_copy(
                    update={
                        "name": name if name is not None else chart.name,
                        "target_session_ids": target_session_ids
                        if target_session_ids is not None
                        else chart.target_session_ids,
                        "parameters": next_parameters,
                        "parameter_hash": _hash_payload(next_parameters),
                        "preset_id": chart.preset_id if preset_id is _KEEP_PRESET else preset_id,
                        "generation_state": "stale",
                        "stale": True,
                        "observations_stale": True,
                    },
                    deep=True,
                )
            )
        if not found:
            raise ValueError(f"Unknown chart instance ID: {chart_id}")
        return self.save(
            analysis.model_copy(update={"charts": charts, "review_stale": True}, deep=True)
        )

    def remove_chart(self, analysis: AnalysisWorkspace, chart_id: str) -> AnalysisWorkspace:
        updated = analysis.model_copy(
            update={
                "charts": [
                    chart for chart in analysis.charts if chart.chart_instance_id != chart_id
                ],
                "review_stale": True,
            },
            deep=True,
        )
        return self.save(updated)

    def generate_charts(
        self,
        analysis: AnalysisWorkspace,
        chart_ids: list[str] | None = None,
    ) -> AnalysisWorkspace:
        selected_ids = set(chart_ids or [chart.chart_instance_id for chart in analysis.charts])
        sessions = {session.session_id: session for session in analysis.sessions}
        registry = build_recipe_registry(analysis.plugins)
        renderer = MatplotlibRenderer()
        updated_charts: list[ChartInstance] = []
        for chart in analysis.charts:
            if chart.chart_instance_id not in selected_ids or not chart.enabled:
                updated_charts.append(chart)
                continue
            try:
                if not chart.target_session_ids:
                    raise ValueError("Chart has no target session.")
                session = sessions[chart.target_session_ids[0]]
                if session.snapshot is None or session.load_state != "loaded":
                    raise ValueError("Target session is not loaded.")
                dataset = _read_snapshot_dataset(self.root, session.snapshot)
                recipe = registry.create(chart.recipe_id)
                config = ChartRecipeConfig(
                    recipe_id=chart.recipe_id,
                    title=chart.parameters.get("title") or chart.name,
                    parameters=chart.parameters,
                    preset_id=chart.preset_id,
                )
                artifact_id = _artifact_id(chart, session)
                artifact = renderer.render(
                    recipe.build_spec(dataset, config),
                    theme=analysis.theme,
                    output_dir=self.root / "charts" / chart.chart_instance_id,
                    artifact_id=artifact_id,
                )
                updated_charts.append(
                    chart.model_copy(
                        update={
                            "generation_state": "generated",
                            "artifact_id": artifact.artifact_id,
                            "image_path": _relative_path(artifact.image_path, self.root),
                            "metadata_path": _relative_path(artifact.metadata_path, self.root),
                            "stale": False,
                            "observations_stale": True,
                            "errors": [],
                        },
                        deep=True,
                    )
                )
            except Exception as exc:
                updated_charts.append(
                    chart.model_copy(
                        update={
                            "generation_state": "failed",
                            "errors": [str(exc)],
                        },
                        deep=True,
                    )
                )
        return self.save(
            analysis.model_copy(
                update={"charts": updated_charts, "review_stale": True},
                deep=True,
            )
        )

    def refresh_observations(self, analysis: AnalysisWorkspace) -> AnalysisWorkspace:
        observations = _extract_analysis_observations(self.root, analysis)
        package_dir = self.root / "package"
        package_dir.mkdir(parents=True, exist_ok=True)
        manifest = _analysis_manifest(self.root, analysis, status="succeeded")
        report_paths = write_report_package(package_dir, manifest, observations)
        manifest = manifest.model_copy(
            update={
                "observations_path": _relative_path(report_paths.observations_path, package_dir),
                "review_path": _relative_path(report_paths.review_path, package_dir),
                "markdown_path": _relative_path(report_paths.markdown_path, package_dir),
            },
            deep=True,
        )
        manifest.write(package_dir / "manifest.json")
        charts = [
            chart.model_copy(update={"observations_stale": False}, deep=True)
            for chart in analysis.charts
        ]
        return self.save(
            analysis.model_copy(
                update={
                    "charts": charts,
                    "review_stale": False,
                    "exported_package_path": str(package_dir),
                },
                deep=True,
            )
        )

    def export_package(self, analysis: AnalysisWorkspace) -> AnalysisWorkspace:
        return self.refresh_observations(analysis)

    def save_preset(
        self,
        analysis: AnalysisWorkspace,
        *,
        recipe_id: str,
        display_name: str,
        parameters: dict[str, Any],
        scope: PresetScope,
        notes: str | None = None,
    ) -> tuple[AnalysisWorkspace, ParameterPreset]:
        schema = recipe_parameter_schema(recipe_id)
        _validate_parameters(schema, parameters)
        now = _now()
        preset = ParameterPreset(
            preset_id=_slug_id(display_name or recipe_id),
            recipe_id=recipe_id,
            schema_version=schema.schema_version,
            display_name=display_name,
            scope=scope,
            parameters=parameters,
            created_at=now,
            updated_at=now,
            notes=notes,
        )
        if scope == "global":
            _write_global_preset(preset)
            return analysis, preset
        presets = [item for item in analysis.presets if item.preset_id != preset.preset_id]
        updated = self.save(
            analysis.model_copy(update={"presets": presets + [preset]}, deep=True)
        )
        return updated, preset


def list_recipe_parameter_schemas(
    registry: RecipeRegistry | None = None,
) -> list[RecipeParameterSchema]:
    registry = registry or build_recipe_registry()
    return [recipe_parameter_schema(recipe.recipe_id) for recipe in registry.list_metadata()]


def list_recipe_metadata_payloads(
    registry: RecipeRegistry | None = None,
) -> list[dict[str, Any]]:
    registry = registry or build_recipe_registry()
    return [_metadata_payload(item) for item in registry.list_metadata()]


def recipe_parameter_schema(recipe_id: str) -> RecipeParameterSchema:
    return RecipeParameterSchema(
        recipe_id=recipe_id,
        schema_version=1,
        fields=[
            ParameterField(
                name="title",
                label="Title",
                field_type="text",
                required=False,
                default=None,
                group="General",
                order=10,
            )
        ],
    )


def list_global_presets() -> list[ParameterPreset]:
    root = _global_preset_root()
    if not root.exists():
        return []
    presets: list[ParameterPreset] = []
    for path in sorted(root.glob("*/*.json")):
        try:
            presets.append(ParameterPreset.model_validate(json.loads(path.read_text(encoding="utf-8"))))
        except Exception:
            continue
    return presets


def _resolve_analysis_root(root: Path | str) -> Path:
    path = Path(root).expanduser().resolve()
    if path.name == "analysis.json":
        return path.parent
    return path


def _analysis_file(root: Path) -> Path:
    return root / "analysis.json"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load_session_dataset(session: AnalysisSession) -> SessionDataset:
    query = SessionQuery(
        season=session.session.season,
        event=session.session.event,
        session=session.session.session,
        drivers=session.drivers,
    )
    if session.data_cache.fixture_path is not None:
        return FixtureSessionGateway(session.data_cache.fixture_path).load_session(query)
    return FastF1SessionGateway(
        session.data_cache.directory,
        cache_only=session.data_cache.mode == "cache-only",
    ).load_session(query)


def _write_snapshot(
    analysis_root: Path,
    session: AnalysisSession,
    dataset: SessionDataset,
) -> DatasetSnapshot:
    session_dir = analysis_root / "sessions" / session.session_id
    dataset_path = session_dir / "dataset.json"
    dataset_payload = dataset.model_dump(mode="json")
    dataset_hash = _hash_payload(dataset_payload)
    _write_json(dataset_path, dataset_payload)
    source_type = "fixture" if session.data_cache.fixture_path is not None else "fastf1"
    snapshot = DatasetSnapshot(
        snapshot_id=f"{session.session_id}-{dataset_hash[:8]}",
        session_id=session.session_id,
        query=SessionQuery(
            season=session.session.season,
            event=session.session.event,
            session=session.session.session,
            drivers=session.drivers,
        ),
        source_type=source_type,
        cache_mode=session.data_cache.mode,
        snapshot_path=f"sessions/{session.session_id}/snapshot.json",
        dataset_path=f"sessions/{session.session_id}/dataset.json",
        created_at=_now(),
        framework_version=_framework_version(),
        dataset_hash=dataset_hash,
        provenance=dataset.provenance.model_dump(mode="json"),
    )
    _write_json(session_dir / "snapshot.json", snapshot.model_dump(mode="json"))
    return snapshot


def _read_snapshot_dataset(analysis_root: Path, snapshot: DatasetSnapshot) -> SessionDataset:
    path = analysis_root / snapshot.dataset_path
    return SessionDataset.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _hash_payload(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _session_id(session: SessionConfig, drivers: list[str]) -> str:
    payload = {
        "season": session.season,
        "event": session.event,
        "session": session.session,
        "drivers": sorted(drivers),
    }
    return f"session-{_hash_payload(payload)[:10]}"


def _chart_id(
    recipe_id: str,
    target_session_ids: list[str],
    parameters: dict[str, Any],
    index: int,
) -> str:
    payload = {
        "recipe_id": recipe_id,
        "target_session_ids": target_session_ids,
        "parameters": parameters,
        "index": index,
    }
    return f"chart-{_hash_payload(payload)[:10]}"


def _slug_id(value: str) -> str:
    slug = "".join(
        character.lower() if character.isalnum() else "-"
        for character in value.strip()
    ).strip("-")
    return f"{slug or 'item'}-{uuid4().hex[:8]}"


def _artifact_id(chart: ChartInstance, session: AnalysisSession) -> str:
    payload = {
        "chart": chart.chart_instance_id,
        "parameter_hash": chart.parameter_hash,
        "session_snapshot": session.snapshot.snapshot_id if session.snapshot else None,
    }
    return f"{chart.recipe_id}-{_hash_payload(payload)[:8]}"


def _relative_path(path: Path, base: Path) -> str:
    return path.relative_to(base).as_posix()


def _metadata_payload(metadata: RecipeMetadata) -> dict[str, Any]:
    return {
        "recipe_id": metadata.recipe_id,
        "display_name": metadata.display_name,
        "required_dataset_fields": list(metadata.required_dataset_fields),
        "output_artifact_types": list(metadata.output_artifact_types),
        "source": metadata.source,
        "parameter_schema": recipe_parameter_schema(metadata.recipe_id).model_dump(mode="json"),
    }


def _validate_parameters(schema: RecipeParameterSchema, parameters: dict[str, Any]) -> None:
    known = {field.name for field in schema.fields}
    unknown = set(parameters) - known
    if unknown:
        raise ValueError(f"Unknown parameter(s): {', '.join(sorted(unknown))}")
    for field in schema.fields:
        value = parameters.get(field.name, field.default)
        if field.required and value in (None, ""):
            raise ValueError(f"Parameter is required: {field.name}")
        if value is None:
            continue
        if field.field_type == "number" and not isinstance(value, (int, float)):
            raise ValueError(f"Parameter must be numeric: {field.name}")
        if field.field_type in {"text", "color"} and not isinstance(value, str):
            raise ValueError(f"Parameter must be text: {field.name}")
        if field.field_type == "checkbox" and not isinstance(value, bool):
            raise ValueError(f"Parameter must be boolean: {field.name}")
        if field.options and value not in field.options:
            raise ValueError(f"Parameter has unsupported option: {field.name}")


def _extract_analysis_observations(
    analysis_root: Path,
    analysis: AnalysisWorkspace,
) -> list[Observation]:
    session = next(
        (item for item in analysis.sessions if item.snapshot is not None),
        None,
    )
    if session is None or session.snapshot is None:
        return []
    dataset = _read_snapshot_dataset(analysis_root, session.snapshot)
    artifacts = [
        ChartArtifactEntry(
            artifact_id=chart.artifact_id or chart.chart_instance_id,
            recipe_id=chart.recipe_id,
            image_path=chart.image_path or "",
            metadata_path=chart.metadata_path or "",
        )
        for chart in analysis.charts
        if chart.generation_state == "generated"
        and chart.artifact_id
        and chart.image_path
        and chart.metadata_path
    ]
    return extract_observations(dataset, artifacts)


def _analysis_manifest(
    analysis_root: Path,
    analysis: AnalysisWorkspace,
    *,
    status: Literal["succeeded", "partially_succeeded", "failed"],
) -> ArtifactManifest:
    artifacts = [
        ChartArtifactEntry(
            artifact_id=chart.artifact_id or chart.chart_instance_id,
            recipe_id=chart.recipe_id,
            image_path=chart.image_path or "",
            metadata_path=chart.metadata_path or "",
        )
        for chart in analysis.charts
        if chart.generation_state == "generated"
        and chart.artifact_id
        and chart.image_path
        and chart.metadata_path
    ]
    first_session = analysis.sessions[0] if analysis.sessions else None
    return ArtifactManifest(
        run_id=f"{analysis.analysis_id}-export",
        status=status,
        framework_version=_framework_version(),
        configuration_hash=_hash_payload(analysis.model_dump(mode="json")),
        session={
            "season": first_session.session.season if first_session else 0,
            "event": first_session.session.event if first_session else "unknown",
            "session": first_session.session.session if first_session else "unknown",
        },
        requested_recipes=[chart.recipe_id for chart in analysis.charts],
        artifacts=artifacts,
        recipes=[
            RecipeRunEntry(
                recipe_id=chart.recipe_id,
                status="produced" if chart.generation_state == "generated" else "failed",
                artifact_id=chart.artifact_id,
                error="; ".join(chart.errors) if chart.errors else None,
            )
            for chart in analysis.charts
        ],
        analysis_id=analysis.analysis_id,
        analysis_path=str(analysis_root),
        sessions=[session.model_dump(mode="json") for session in analysis.sessions],
        chart_instances=[chart.model_dump(mode="json") for chart in analysis.charts],
    )


def _global_preset_root() -> Path:
    return Path.home() / ".f1_telemetry_charts" / "presets"


def _write_global_preset(preset: ParameterPreset) -> None:
    path = _global_preset_root() / preset.recipe_id / f"{preset.preset_id}.json"
    _write_json(path, preset.model_dump(mode="json"))


def _framework_version() -> str:
    try:
        return version("f1-telemetry-charts")
    except PackageNotFoundError:
        return "0.0.0+local"

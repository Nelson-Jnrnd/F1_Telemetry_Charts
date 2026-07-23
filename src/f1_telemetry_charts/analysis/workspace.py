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
ParameterMode = Literal["basic", "advanced"]
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
    "color_map",
    "numeric_range",
    "object",
]

_NORMALIZED_PARAMETER_SECTIONS = {
    "chart",
    "selection",
    "filters",
    "analysis",
    "presentation",
    "diagnostics",
    "effective",
}


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
    mode: ParameterMode = "basic"
    visible_when: dict[str, Any] = Field(default_factory=dict)
    enabled_when: dict[str, Any] = Field(default_factory=dict)
    required_when: dict[str, Any] = Field(default_factory=dict)
    reset_group: str | None = None


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
    available_teams: list[str] = Field(default_factory=list)
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


class ParameterDiagnosticsView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["valid", "invalid"]
    recipe_id: str
    schema_version: int = 1
    parameters: dict[str, Any] = Field(default_factory=dict)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    active_filter_summary: list[str] = Field(default_factory=list)
    exclusion_counts: dict[str, int] = Field(default_factory=dict)
    effective_configuration: dict[str, Any] = Field(default_factory=dict)


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
                effective_drivers = [
                    driver.abbreviation for driver in dataset.drivers
                ]
                available_teams = sorted(
                    {
                        driver.team_name
                        for driver in dataset.drivers
                        if driver.team_name
                    }
                )
                effective_session = session.model_copy(
                    update={"drivers": effective_drivers, "available_teams": available_teams},
                    deep=True,
                )
                snapshot = _write_snapshot(self.root, effective_session, dataset)
                sessions.append(
                    effective_session.model_copy(
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
            raise ValueError(f"Unknown chart template: {recipe_id}")
        missing = [
            session_id
            for session_id in target_session_ids
            if session_id not in {session.session_id for session in analysis.sessions}
        ]
        if missing:
            raise ValueError(f"Unknown target session ID(s): {', '.join(missing)}")
        _validate_target_sessions(analysis, target_session_ids, registry.get(recipe_id))
        schema = recipe_parameter_schema(recipe_id)
        _validate_parameters(schema, parameters or {})
        params = normalize_chart_parameters(recipe_id, parameters or {})
        _validate_parameters(schema, params)
        _validate_preset_reference(analysis, recipe_id, preset_id)
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
            next_parameters = (
                normalize_chart_parameters(chart.recipe_id, parameters)
                if parameters is not None
                else chart.parameters
            )
            if parameters is not None:
                _validate_parameters(recipe_parameter_schema(chart.recipe_id), parameters)
            _validate_parameters(recipe_parameter_schema(chart.recipe_id), next_parameters)
            next_preset_id = chart.preset_id if preset_id is _KEEP_PRESET else preset_id
            _validate_preset_reference(analysis, chart.recipe_id, next_preset_id)
            charts.append(
                chart.model_copy(
                    update={
                        "name": name if name is not None else chart.name,
                        "target_session_ids": target_session_ids
                        if target_session_ids is not None
                        else chart.target_session_ids,
                        "parameters": next_parameters,
                        "parameter_hash": _hash_payload(next_parameters),
                        "preset_id": next_preset_id,
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

    def resolve_chart_diagnostics(
        self,
        analysis: AnalysisWorkspace,
        *,
        recipe_id: str,
        target_session_ids: list[str],
        parameters: dict[str, Any] | None = None,
    ) -> ParameterDiagnosticsView:
        registry = build_recipe_registry(analysis.plugins)
        if not registry.has_recipe(recipe_id):
            return _diagnostics_error(recipe_id, "template_id", "Unknown chart template")
        schema = recipe_parameter_schema(recipe_id)
        requested = parameters or {}
        normalized = normalize_chart_parameters(recipe_id, requested)
        errors: list[dict[str, Any]] = []
        try:
            _validate_parameters(schema, requested)
            _validate_target_sessions(analysis, target_session_ids, registry.get(recipe_id))
            _validate_parameters(schema, normalized)
        except ValueError as exc:
            errors.append(_parameter_diagnostic_error(schema, str(exc)))
        if errors:
            return ParameterDiagnosticsView(
                status="invalid",
                recipe_id=recipe_id,
                schema_version=schema.schema_version,
                parameters=normalized,
                errors=errors,
            )

        sessions = {session.session_id: session for session in analysis.sessions}
        if not target_session_ids:
            return _diagnostics_error(recipe_id, "target_session_ids", "Target session is required")
        session = sessions.get(target_session_ids[0])
        if session is None:
            return _diagnostics_error(recipe_id, "target_session_ids", "Unknown target session")
        if session.snapshot is None or session.load_state != "loaded":
            return ParameterDiagnosticsView(
                status="valid",
                recipe_id=recipe_id,
                schema_version=schema.schema_version,
                parameters=normalized,
                warnings=[
                    {
                        "field": "target_session_ids",
                        "message": "Target session is not loaded; effective diagnostics are limited",
                    }
                ],
            )

        try:
            dataset = _read_snapshot_dataset(self.root, session.snapshot)
            spec = registry.create(recipe_id).build_spec(
                dataset,
                ChartRecipeConfig(
                    recipe_id=recipe_id,
                    title=_parameter_value(normalized, "title", registry.get(recipe_id).display_name),
                    parameters=normalized,
                ),
            )
        except Exception as exc:
            return ParameterDiagnosticsView(
                status="invalid",
                recipe_id=recipe_id,
                schema_version=schema.schema_version,
                parameters=normalized,
                errors=[_parameter_diagnostic_error(schema, str(exc))],
            )

        diagnostics = spec.metadata.get("diagnostics", {})
        return ParameterDiagnosticsView(
            status="valid",
            recipe_id=recipe_id,
            schema_version=schema.schema_version,
            parameters=normalized,
            warnings=list(diagnostics.get("warnings", [])),
            active_filter_summary=list(diagnostics.get("active_filter_summary", [])),
            exclusion_counts=dict(diagnostics.get("exclusion_counts", {})),
            effective_configuration=dict(spec.metadata.get("effective_configuration", {})),
        )

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
        replace_existing: bool = False,
    ) -> tuple[AnalysisWorkspace, ParameterPreset]:
        schema = recipe_parameter_schema(recipe_id)
        _validate_parameters(schema, parameters)
        parameters = normalize_chart_parameters(recipe_id, parameters)
        _validate_parameters(schema, parameters)
        display_name = display_name.strip()
        if not display_name:
            raise ValueError("Preset display name is required.")
        now = _now()
        existing = _find_duplicate_preset(analysis, recipe_id, scope, display_name)
        if existing is not None and not replace_existing:
            raise ValueError("Preset name already exists for this template and scope.")
        preset_id = existing.preset_id if existing is not None else _slug_id(display_name or recipe_id)
        created_at = existing.created_at if existing is not None else now
        preset = ParameterPreset(
            preset_id=preset_id,
            recipe_id=recipe_id,
            schema_version=schema.schema_version,
            display_name=display_name,
            scope=scope,
            parameters=parameters,
            created_at=created_at,
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

    def update_preset(
        self,
        analysis: AnalysisWorkspace,
        preset_id: str,
        *,
        display_name: str | None = None,
        parameters: dict[str, Any] | None = None,
        replace_existing: bool = False,
    ) -> tuple[AnalysisWorkspace, ParameterPreset]:
        preset = _find_preset(analysis, preset_id)
        if preset is None:
            raise ValueError(f"Unknown preset ID: {preset_id}")
        next_name = display_name.strip() if display_name is not None else preset.display_name
        if not next_name:
            raise ValueError("Preset display name is required.")
        next_parameters = (
            normalize_chart_parameters(preset.recipe_id, parameters)
            if parameters is not None
            else preset.parameters
        )
        if parameters is not None:
            _validate_parameters(recipe_parameter_schema(preset.recipe_id), parameters)
        _validate_parameters(recipe_parameter_schema(preset.recipe_id), next_parameters)
        duplicate = _find_duplicate_preset(
            analysis,
            preset.recipe_id,
            preset.scope,
            next_name,
            exclude_preset_id=preset.preset_id,
        )
        if duplicate is not None and not replace_existing:
            raise ValueError("Preset name already exists for this template and scope.")
        updated_preset = preset.model_copy(
            update={
                "display_name": next_name,
                "parameters": next_parameters,
                "updated_at": _now(),
            },
            deep=True,
        )
        working_analysis = analysis
        if duplicate is not None:
            working_analysis = self.delete_preset(analysis, duplicate.preset_id)
        if updated_preset.scope == "global":
            _write_global_preset(updated_preset)
            return working_analysis, updated_preset
        presets = [
            item
            for item in working_analysis.presets
            if item.preset_id != updated_preset.preset_id
        ] + [updated_preset]
        updated = self.save(working_analysis.model_copy(update={"presets": presets}, deep=True))
        return updated, updated_preset

    def delete_preset(
        self,
        analysis: AnalysisWorkspace,
        preset_id: str,
    ) -> AnalysisWorkspace:
        preset = _find_preset(analysis, preset_id)
        if preset is None:
            raise ValueError(f"Unknown preset ID: {preset_id}")
        if preset.scope == "global":
            _delete_global_preset(preset)
            presets = analysis.presets
        else:
            presets = [item for item in analysis.presets if item.preset_id != preset_id]
        charts = [
            chart.model_copy(update={"preset_id": None}, deep=True)
            if chart.preset_id == preset_id
            else chart
            for chart in analysis.charts
        ]
        return self.save(
            analysis.model_copy(update={"presets": presets, "charts": charts}, deep=True)
        )


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


def normalize_chart_parameters(
    recipe_id: str,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    normalized: dict[str, Any] = {
        key: value
        for key, value in parameters.items()
        if key in _NORMALIZED_PARAMETER_SECTIONS
    }
    chart = dict(normalized.get("chart") or {})
    selection = dict(normalized.get("selection") or {})
    filters = dict(normalized.get("filters") or {})
    analysis = dict(normalized.get("analysis") or {})
    presentation = dict(normalized.get("presentation") or {})

    _move(parameters, chart, "title")
    for key in [
        "driver_selection_mode",
        "drivers",
        "teams",
        "top_n",
        "driver_limit",
        "driver_order",
        "custom_driver_order",
    ]:
        _move(parameters, selection, key)
    if "lap_range" in parameters and "laps" not in selection:
        selection["laps"] = {"range": parameters["lap_range"]}
    for key in ["box_lap_policy", "lap_validity", "track_status_filter", "missing_series_policy"]:
        _move(parameters, filters, key)
    if "series_colors" in parameters:
        colors = dict(presentation.get("colors") or {})
        colors["overrides"] = parameters["series_colors"]
        presentation["colors"] = colors

    if recipe_id == "telemetry_trace":
        for key in [
            "metric",
            "distance_range_m",
            "telemetry_gap_policy",
            "maximum_interpolation_gap_ms",
        ]:
            _move(parameters, analysis, key)
    elif recipe_id == "lap_time_delta":
        for key in ["baseline_mode", "reference_driver", "delta_mode"]:
            _move(parameters, analysis, key)
        _map_include_pit_laps(parameters, filters, default="exclude_in_and_out_laps")
    elif recipe_id == "tyre_strategy":
        for key in ["compounds", "layout", "unknown_compound_policy"]:
            _move(parameters, analysis, key)
        _move(parameters, presentation, "show_pit_markers")
    elif recipe_id == "position_progression":
        for key in ["invert_position_axis", "line_mode"]:
            _move(parameters, presentation, key)
        _map_include_pit_laps(parameters, filters, default="exclude_in_and_out_laps")

    if chart:
        normalized["chart"] = chart
    if selection:
        normalized["selection"] = selection
    if filters:
        normalized["filters"] = filters
    if analysis:
        normalized["analysis"] = analysis
    if presentation:
        normalized["presentation"] = presentation
    for key in ["diagnostics", "effective"]:
        if key in parameters and key not in normalized:
            normalized[key] = parameters[key]
    return normalized


def recipe_parameter_schema(recipe_id: str) -> RecipeParameterSchema:
    common_fields = [
        ParameterField(
            name="title",
            label="Title",
            field_type="text",
            required=False,
            default=None,
            group="General",
            order=10,
        ),
        ParameterField(
            name="drivers",
            label="Drivers",
            field_type="driver_selector",
            required=False,
            default=[],
            group="General",
            order=20,
            visible_when={"driver_selection_mode": "selected"},
            reset_group="selection",
        ),
        ParameterField(
            name="driver_selection_mode",
            label="Driver selection",
            field_type="select",
            required=False,
            default="all_session",
            options=["all_session", "selected", "top_n", "teams"],
            group="General",
            order=21,
            reset_group="selection",
        ),
        ParameterField(
            name="top_n",
            label="Top N",
            field_type="number",
            required=False,
            default=None,
            minimum=1,
            group="General",
            order=22,
            visible_when={"driver_selection_mode": "top_n"},
            required_when={"driver_selection_mode": "top_n"},
            reset_group="selection",
        ),
        ParameterField(
            name="teams",
            label="Teams",
            field_type="driver_selector",
            required=False,
            default=[],
            group="General",
            order=23,
            mode="advanced",
            visible_when={"driver_selection_mode": "teams"},
            required_when={"driver_selection_mode": "teams"},
            reset_group="selection",
        ),
        ParameterField(
            name="driver_limit",
            label="Driver limit",
            field_type="number",
            required=False,
            default=None,
            minimum=1,
            group="General",
            order=24,
            mode="advanced",
            reset_group="selection",
        ),
        ParameterField(
            name="driver_order",
            label="Driver order",
            field_type="select",
            required=False,
            default="classification",
            options=[
                "classification",
                "fastest_lap",
                "team",
                "grid",
                "selection_order",
                "custom",
            ],
            group="General",
            order=25,
            mode="advanced",
            reset_group="selection",
        ),
        ParameterField(
            name="custom_driver_order",
            label="Custom driver order",
            field_type="driver_selector",
            required=False,
            default=[],
            group="General",
            order=26,
            mode="advanced",
            visible_when={"driver_order": "custom"},
            required_when={"driver_order": "custom"},
            reset_group="selection",
        ),
        ParameterField(
            name="lap_range",
            label="Lap range",
            field_type="lap_range",
            required=False,
            default=None,
            group="General",
            order=30,
            reset_group="filters",
        ),
        ParameterField(
            name="box_lap_policy",
            label="Box-lap policy",
            field_type="select",
            required=False,
            default=None,
            options=[
                "include_all",
                "exclude_in_laps",
                "exclude_out_laps",
                "exclude_in_and_out_laps",
                "only_in_laps",
                "only_out_laps",
            ],
            group="General",
            order=31,
            mode="advanced",
            reset_group="filters",
        ),
        ParameterField(
            name="lap_validity",
            label="Lap validity",
            field_type="object",
            required=False,
            default={
                "require_lap_time": False,
                "deleted_laps": "exclude",
                "generated_laps": "exclude",
                "accuracy_filter": "all",
                "require_complete_sectors": False,
            },
            group="Filters",
            order=32,
            mode="advanced",
            reset_group="filters",
        ),
        ParameterField(
            name="track_status_filter",
            label="Track status",
            field_type="object",
            required=False,
            default={"mode": "all", "match": "any_overlap", "custom_codes": []},
            group="Filters",
            order=33,
            mode="advanced",
            reset_group="filters",
        ),
        ParameterField(
            name="missing_series_policy",
            label="Missing series",
            field_type="select",
            required=False,
            default="warn_skip",
            options=["error", "warn_skip", "silent_skip"],
            group="Filters",
            order=34,
            mode="advanced",
            reset_group="filters",
        ),
        ParameterField(
            name="series_colors",
            label="Series colors",
            field_type="color_map",
            required=False,
            default={},
            group="Style",
            order=40,
            mode="advanced",
            reset_group="presentation",
        ),
    ]
    specific_fields: dict[str, list[ParameterField]] = {
        "telemetry_trace": [
            ParameterField(
                name="metric",
                label="Metric",
                field_type="select",
                default="speed_kph",
                options=["speed_kph", "throttle_percent", "brake", "gear"],
                group="Telemetry",
                order=100,
                reset_group="analysis",
            ),
            ParameterField(
                name="distance_range_m",
                label="Distance range",
                field_type="numeric_range",
                default=None,
                minimum=0,
                group="Telemetry",
                order=110,
                reset_group="analysis",
            ),
            ParameterField(
                name="telemetry_gap_policy",
                label="Telemetry gaps",
                field_type="select",
                default="preserve",
                options=["preserve", "interpolate_continuous", "resample"],
                group="Telemetry",
                order=120,
                mode="advanced",
                reset_group="analysis",
            ),
            ParameterField(
                name="maximum_interpolation_gap_ms",
                label="Max interpolation gap",
                field_type="number",
                default=None,
                minimum=0,
                group="Telemetry",
                order=130,
                mode="advanced",
                visible_when={"telemetry_gap_policy": "interpolate_continuous"},
                reset_group="analysis",
            ),
        ],
        "lap_time_delta": [
            ParameterField(
                name="baseline_mode",
                label="Baseline",
                field_type="select",
                default="fastest_selected_per_lap",
                options=["fastest_selected_per_lap", "reference_driver"],
                group="Delta",
                order=100,
                reset_group="analysis",
            ),
            ParameterField(
                name="reference_driver",
                label="Reference driver",
                field_type="driver_selector",
                default=None,
                group="Delta",
                order=110,
                visible_when={"baseline_mode": "reference_driver"},
                required_when={"baseline_mode": "reference_driver"},
                reset_group="analysis",
            ),
            ParameterField(
                name="include_pit_laps",
                label="Include pit laps",
                field_type="checkbox",
                default=False,
                group="Delta",
                order=120,
                mode="advanced",
                reset_group="filters",
            ),
            ParameterField(
                name="delta_mode",
                label="Delta mode",
                field_type="select",
                default="single_lap_delta",
                options=["single_lap_delta", "cumulative_filtered_pace_delta"],
                group="Delta",
                order=130,
                mode="advanced",
                reset_group="analysis",
            ),
        ],
        "tyre_strategy": [
            ParameterField(
                name="compounds",
                label="Compounds",
                field_type="multi_select",
                default=[],
                options=["HARD", "MEDIUM", "SOFT", "INTERMEDIATE", "WET"],
                group="Strategy",
                order=100,
                reset_group="analysis",
            ),
            ParameterField(
                name="show_pit_markers",
                label="Show pit markers",
                field_type="checkbox",
                default=True,
                group="Strategy",
                order=110,
                reset_group="presentation",
            ),
            ParameterField(
                name="layout",
                label="Layout",
                field_type="select",
                default="stint_bars",
                options=["stint_bars", "compound_steps"],
                group="Strategy",
                order=120,
                mode="advanced",
                reset_group="analysis",
            ),
            ParameterField(
                name="unknown_compound_policy",
                label="Unknown compounds",
                field_type="select",
                default="warn_skip",
                options=["error", "warn_skip", "silent_skip"],
                group="Strategy",
                order=130,
                mode="advanced",
                reset_group="analysis",
            ),
        ],
        "position_progression": [
            ParameterField(
                name="invert_position_axis",
                label="Invert position axis",
                field_type="checkbox",
                default=True,
                group="Position",
                order=100,
                reset_group="presentation",
            ),
            ParameterField(
                name="include_pit_laps",
                label="Include pit laps",
                field_type="checkbox",
                default=False,
                group="Position",
                order=110,
                mode="advanced",
                reset_group="filters",
            ),
            ParameterField(
                name="line_mode",
                label="Line mode",
                field_type="select",
                default="step",
                options=["step", "line"],
                group="Position",
                order=120,
                mode="advanced",
                reset_group="presentation",
            ),
        ],
    }
    fields = common_fields + specific_fields.get(recipe_id, [])
    return RecipeParameterSchema(
        recipe_id=recipe_id,
        schema_version=1,
        fields=fields,
    )


def list_global_presets() -> list[ParameterPreset]:
    presets = _builtin_parameter_presets()
    root = _global_preset_root()
    if not root.exists():
        return presets
    for path in sorted(root.glob("*/*.json")):
        try:
            presets.append(ParameterPreset.model_validate(json.loads(path.read_text(encoding="utf-8"))))
        except Exception:
            continue
    return presets


def _builtin_parameter_presets() -> list[ParameterPreset]:
    created_at = datetime(2026, 7, 22, tzinfo=timezone.utc)
    definitions = [
        (
            "builtin-fastest-lap-telemetry",
            "telemetry_trace",
            "Fastest-lap telemetry comparison",
            {"analysis": {"metric": "speed_kph"}, "selection": {"driver_selection_mode": "all_session"}},
        ),
        (
            "builtin-driver-input-comparison",
            "telemetry_trace",
            "Driver-input comparison",
            {"analysis": {"metric": "throttle_percent"}, "selection": {"driver_selection_mode": "selected"}},
        ),
        (
            "builtin-clean-race-pace",
            "lap_time_delta",
            "Clean race pace",
            {"filters": {"box_lap_policy": "exclude_in_and_out_laps", "missing_series_policy": "warn_skip"}},
        ),
        (
            "builtin-sector-comparison",
            "lap_time_delta",
            "Sector comparison",
            {"analysis": {"baseline_mode": "fastest_selected_per_lap"}, "filters": {"lap_validity": {"require_complete_sectors": True}}},
        ),
        (
            "builtin-tyre-strategy-overview",
            "tyre_strategy",
            "Tyre strategy overview",
            {"analysis": {"layout": "stint_bars"}, "presentation": {"show_pit_markers": True}},
        ),
        (
            "builtin-position-progression",
            "position_progression",
            "Position progression",
            {"presentation": {"invert_position_axis": True, "line_mode": "step"}},
        ),
        (
            "builtin-race-gain-loss",
            "position_progression",
            "Race gain/loss",
            {"presentation": {"invert_position_axis": True}, "filters": {"track_status_filter": {"mode": "all", "match": "any_overlap"}}},
        ),
        (
            "builtin-presentation-export",
            "lap_time_delta",
            "Presentation export",
            {"selection": {"driver_selection_mode": "selected"}, "presentation": {"colors": {"overrides": {}}}},
        ),
        (
            "builtin-dense-engineering-report",
            "telemetry_trace",
            "Dense engineering report",
            {"analysis": {"metric": "speed_kph", "telemetry_gap_policy": "preserve"}, "diagnostics": {"include_effective_configuration": True}},
        ),
    ]
    return [
        ParameterPreset(
            preset_id=preset_id,
            recipe_id=recipe_id,
            schema_version=recipe_parameter_schema(recipe_id).schema_version,
            display_name=display_name,
            scope="global",
            parameters=parameters,
            created_at=created_at,
            updated_at=created_at,
            notes="Built-in SPEC-006 analyst preset.",
        )
        for preset_id, recipe_id, display_name, parameters in definitions
    ]


def _find_preset(
    analysis: AnalysisWorkspace,
    preset_id: str | None,
) -> ParameterPreset | None:
    if preset_id is None:
        return None
    for preset in analysis.presets + list_global_presets():
        if preset.preset_id == preset_id:
            return preset
    return None


def _find_duplicate_preset(
    analysis: AnalysisWorkspace,
    recipe_id: str,
    scope: PresetScope,
    display_name: str,
    *,
    exclude_preset_id: str | None = None,
) -> ParameterPreset | None:
    presets = analysis.presets if scope == "analysis" else list_global_presets()
    for preset in presets:
        if preset.preset_id == exclude_preset_id:
            continue
        if (
            preset.recipe_id == recipe_id
            and preset.scope == scope
            and preset.display_name.casefold() == display_name.casefold()
        ):
            return preset
    return None


def _move(source: dict[str, Any], target: dict[str, Any], key: str) -> None:
    if key in source:
        target[key] = source[key]


def _map_include_pit_laps(
    source: dict[str, Any],
    filters: dict[str, Any],
    *,
    default: str,
) -> None:
    if "box_lap_policy" in filters:
        return
    if "include_pit_laps" in source:
        filters["box_lap_policy"] = (
            "include_all" if bool(source["include_pit_laps"]) else default
        )


def _validate_preset_reference(
    analysis: AnalysisWorkspace,
    recipe_id: str,
    preset_id: str | None,
) -> None:
    if preset_id is None:
        return
    preset = _find_preset(analysis, preset_id)
    if preset is None:
        raise ValueError(f"Unknown preset ID: {preset_id}")
    if preset.recipe_id != recipe_id:
        raise ValueError("Preset is not compatible with the selected chart template.")
    if preset.schema_version != recipe_parameter_schema(recipe_id).schema_version:
        raise ValueError("Preset schema version is not compatible with the selected chart template.")


def _diagnostics_error(
    recipe_id: str,
    field_name: str,
    message: str,
) -> ParameterDiagnosticsView:
    return ParameterDiagnosticsView(
        status="invalid",
        recipe_id=recipe_id,
        errors=[{"field": field_name, "message": message}],
    )


def _parameter_diagnostic_error(
    schema: RecipeParameterSchema,
    message: str,
) -> dict[str, str]:
    if ": " in message:
        candidate = message.rsplit(": ", 1)[-1].strip()
        if any(field.name == candidate for field in schema.fields):
            return {"field": candidate, "message": message}
    for field in sorted(schema.fields, key=lambda item: len(item.name), reverse=True):
        if field.name in message:
            return {"field": field.name, "message": message}
    return {"field": "parameters", "message": message}


def _validate_target_sessions(
    analysis: AnalysisWorkspace,
    target_session_ids: list[str],
    metadata: RecipeMetadata,
) -> None:
    sessions = {session.session_id: session for session in analysis.sessions}
    for session_id in target_session_ids:
        session = sessions[session_id]
        if session.load_state != "loaded" or session.snapshot is None:
            raise ValueError(f"Target session is not loaded: {session_id}")
        dataset = _read_snapshot_dataset(analysis.root_path, session.snapshot)
        missing = [
            field
            for field in metadata.required_dataset_fields
            if not _dataset_field_available(dataset, field)
        ]
        if missing:
            raise ValueError(
                "Target session is missing required template field(s): "
                + ", ".join(missing)
            )


def _dataset_field_available(dataset: SessionDataset, field: str) -> bool:
    value = getattr(dataset, field, None)
    if isinstance(value, list):
        return bool(value)
    return value is not None


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
    source_type = "built_in" if metadata.source == "core" else "plugin"
    source_label = "Built-in" if metadata.source == "core" else metadata.source
    schema = recipe_parameter_schema(metadata.recipe_id)
    return {
        "template_id": metadata.recipe_id,
        "recipe_id": metadata.recipe_id,
        "display_name": metadata.display_name,
        "description": None,
        "source_type": source_type,
        "source_label": source_label,
        "required_dataset_fields": list(metadata.required_dataset_fields),
        "output_artifact_types": list(metadata.output_artifact_types),
        "supported_session_count": {"minimum": 1, "maximum": 1},
        "parameter_schema_version": schema.schema_version,
        "availability_status": "available",
        "diagnostics": [],
        "source": metadata.source,
        "parameter_schema": schema.model_dump(mode="json"),
    }


def _validate_parameters(schema: RecipeParameterSchema, parameters: dict[str, Any]) -> None:
    known = {field.name for field in schema.fields}
    unknown = set(parameters) - known - _NORMALIZED_PARAMETER_SECTIONS
    if unknown:
        raise ValueError(f"Unknown parameter(s): {', '.join(sorted(unknown))}")
    values = {
        field.name: _parameter_value(parameters, field.name, field.default)
        for field in schema.fields
    }
    for field in schema.fields:
        active = _dependencies_match(field.visible_when, values)
        required = field.required or (
            bool(field.required_when) and _dependencies_match(field.required_when, values)
        )
        if not active:
            continue
        value = values[field.name]
        if required and value in (None, "", []):
            raise ValueError(f"Parameter is required: {field.name}")
        if value is None:
            continue
        if field.field_type == "number" and not isinstance(value, (int, float)):
            raise ValueError(f"Parameter must be numeric: {field.name}")
        if field.field_type == "number":
            if field.minimum is not None and value < field.minimum:
                raise ValueError(f"Parameter is below minimum: {field.name}")
            if field.maximum is not None and value > field.maximum:
                raise ValueError(f"Parameter is above maximum: {field.name}")
        if field.field_type in {"text", "color"} and not isinstance(value, str):
            raise ValueError(f"Parameter must be text: {field.name}")
        if field.field_type == "object":
            if not isinstance(value, dict):
                raise ValueError(f"Parameter must be an object: {field.name}")
            continue
        if field.field_type == "checkbox" and not isinstance(value, bool):
            raise ValueError(f"Parameter must be boolean: {field.name}")
        if field.field_type == "multi_select":
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise ValueError(f"Parameter must be a list of text values: {field.name}")
            unsupported = sorted(set(value) - set(field.options))
            if unsupported:
                raise ValueError(f"Parameter has unsupported option: {field.name}")
            continue
        if field.field_type == "driver_selector":
            if isinstance(value, str):
                continue
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise ValueError(f"Parameter must be a driver code or list of driver codes: {field.name}")
            continue
        if field.field_type in {"lap_range", "numeric_range"}:
            _validate_range_parameter(field.name, value)
            continue
        if field.field_type == "color_map":
            if not isinstance(value, dict) or not all(
                isinstance(key, str) and isinstance(color, str)
                for key, color in value.items()
            ):
                raise ValueError(f"Parameter must map labels to color strings: {field.name}")
            continue
        if field.options and value not in field.options:
            raise ValueError(f"Parameter has unsupported option: {field.name}")


def _dependencies_match(dependencies: dict[str, Any], values: dict[str, Any]) -> bool:
    for name, expected in dependencies.items():
        actual = values.get(name)
        if isinstance(expected, list):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


def _parameter_value(parameters: dict[str, Any], name: str, default: Any) -> Any:
    if name in parameters:
        return parameters[name]
    chart = parameters.get("chart") if isinstance(parameters.get("chart"), dict) else {}
    selection = (
        parameters.get("selection") if isinstance(parameters.get("selection"), dict) else {}
    )
    filters = parameters.get("filters") if isinstance(parameters.get("filters"), dict) else {}
    analysis = (
        parameters.get("analysis") if isinstance(parameters.get("analysis"), dict) else {}
    )
    presentation = (
        parameters.get("presentation")
        if isinstance(parameters.get("presentation"), dict)
        else {}
    )
    if name == "title":
        return chart.get("title", default)
    if name == "lap_range":
        laps = selection.get("laps")
        if isinstance(laps, dict) and "range" in laps:
            return laps["range"]
    if name == "series_colors":
        colors = presentation.get("colors")
        if isinstance(colors, dict) and "overrides" in colors:
            return colors["overrides"]
    driver_selection = selection.get("driver_selection")
    if isinstance(driver_selection, dict) and name in driver_selection:
        return driver_selection[name]
    selection_drivers = selection.get("drivers")
    if isinstance(selection_drivers, dict) and name in selection_drivers:
        return selection_drivers[name]
    for section_value in [selection, filters, analysis, presentation]:
        if name in section_value:
            return section_value[name]
    return default


def _validate_range_parameter(name: str, value: Any) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"Parameter must be a range object: {name}")
    unknown = set(value) - {"start", "end"}
    if unknown:
        raise ValueError(f"Parameter range has unsupported key: {name}")
    start = value.get("start")
    end = value.get("end")
    for bound_name, bound in {"start": start, "end": end}.items():
        if bound is not None and not isinstance(bound, (int, float)):
            raise ValueError(f"Parameter range bound must be numeric: {name}.{bound_name}")
    if start is not None and end is not None and start > end:
        raise ValueError(f"Parameter range start must be before end: {name}")


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


def _delete_global_preset(preset: ParameterPreset) -> None:
    path = _global_preset_root() / preset.recipe_id / f"{preset.preset_id}.json"
    if path.exists():
        path.unlink()


def _framework_version() -> str:
    try:
        return version("f1-telemetry-charts")
    except PackageNotFoundError:
        return "0.0.0+local"

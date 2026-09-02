"""Saved Analysis workspace models and staged generation helpers."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from f1_telemetry_charts.analysis.findings import (
    FreshnessLayer,
    PublicationEditorial,
    PublicationPlan,
    ReportContent,
    ReportFreshness,
    ReportPlan,
    ReportReviewEntry,
    ResultSource,
    build_report_content,
    reviews_are_current,
)
from f1_telemetry_charts.analysis.manifest import (
    ArtifactManifest,
    ChartArtifactEntry,
    RecipeRunEntry,
)
from f1_telemetry_charts.analysis.playback import (
    PlaybackPayload,
    build_playback_payload,
    playback_summary,
)
from f1_telemetry_charts.analysis.publication import (
    RACE_FOUNDATIONAL_RESULT_TYPES,
    editorial_fingerprint,
    evaluate_readiness,
    materialize_session_spine,
    preserve_editorial_on_refresh,
    propose_publication_plan,
    validate_publication_plan,
)
from f1_telemetry_charts.analysis.qualifying import (
    is_standard_qualifying,
    materialize_qualifying_results,
)
from f1_telemetry_charts.analysis.practice import (
    is_standard_practice,
    materialize_practice_results,
)
from f1_telemetry_charts.analysis.report import (
    PUBLICATION_EXPORT_CONTRACT_VERSION,
    write_publication_export_package,
    write_structured_report_package,
)
from f1_telemetry_charts.analysis.track_map import (
    DEFAULT_TRACK_MAP_POINT_LIMIT,
    TrackMapPayload,
    build_track_map_payload,
)
from f1_telemetry_charts.analysis.weekend import (
    WEEKEND_SYNTHESIS_SCHEMA_VERSION,
    WeekendClaimCandidate,
    WeekendEditorial,
    WeekendExpectation,
    WeekendSourceSession,
    WeekendSynthesis,
    bounded_weekend_payload,
    compose_standard_weekend,
    write_weekend_package,
)
from f1_telemetry_charts.charts.renderers import MatplotlibRenderer
from f1_telemetry_charts.config.models import (
    ChartRecipeConfig,
    DataCacheConfig,
    PluginConfig,
    SessionConfig,
    ThemeConfig,
)
from f1_telemetry_charts.data import DriverMetadata, SessionDataset, SessionQuery
from f1_telemetry_charts.data.gateways import FastF1SessionGateway, FixtureSessionGateway
from f1_telemetry_charts.data.track_geometry import ensure_track_geometry
from f1_telemetry_charts.plugins import build_recipe_registry
from f1_telemetry_charts.recipes.parameters import (
    ParameterDiagnostics,
    coverage_bounds,
    selected_driver_codes,
    validate_coverage_bounds,
)
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
    driver_details: list[DriverMetadata] = Field(default_factory=list)
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
    report_target_session_id: str | None = None
    report_content: ReportContent | None = None
    report_reviews: list[ReportReviewEntry] = Field(default_factory=list)
    report_freshness: ReportFreshness = Field(default_factory=ReportFreshness)
    report_package_path: str | None = None
    exported_package_path: str | None = None
    weekend_sources: list[WeekendSourceSession] = Field(default_factory=list)
    weekend_synthesis: WeekendSynthesis | None = None
    weekend_package_path: str | None = None
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
    coverage_bounds: dict[str, Any] = Field(default_factory=dict)
    style_sources: dict[str, Any] = Field(default_factory=dict)
    analytical_basis: dict[str, Any] = Field(default_factory=dict)
    analytical_results: dict[str, Any] = Field(default_factory=dict)


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
        analysis = _migrate_loaded_strategy_contracts(analysis)
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

    def compose_weekend(
        self,
        analysis: AnalysisWorkspace,
        *,
        sources: list[WeekendSourceSession],
        candidates: list[WeekendClaimCandidate],
        expectations: list[WeekendExpectation] | None = None,
        editorial: WeekendEditorial | None = None,
        expected_evidence_fingerprint: str | None = None,
    ) -> AnalysisWorkspace:
        """Persist one atomic synthesis over immutable session-report records."""

        if (
            expected_evidence_fingerprint is not None
            and analysis.weekend_synthesis is not None
            and analysis.weekend_synthesis.evidence_fingerprint
            != expected_evidence_fingerprint
        ):
            raise ValueError("Weekend evidence changed; refresh before saving edits.")
        synthesis = compose_standard_weekend(
            sources,
            candidates,
            expectations=expectations,
            editorial=editorial,
        )
        return self.save(
            analysis.model_copy(
                update={
                    "weekend_sources": [item.model_copy(deep=True) for item in sources],
                    "weekend_synthesis": synthesis,
                    "weekend_package_path": None,
                },
                deep=True,
            )
        )

    def inspect_weekend(
        self, analysis: AnalysisWorkspace, *, claim_limit: int = 20
    ) -> dict[str, Any]:
        if analysis.weekend_synthesis is None:
            raise ValueError("Compose weekend evidence before inspection.")
        return bounded_weekend_payload(
            analysis.weekend_synthesis, claim_limit=claim_limit
        )

    def export_weekend(self, analysis: AnalysisWorkspace) -> AnalysisWorkspace:
        if analysis.weekend_synthesis is None:
            raise ValueError("Compose weekend evidence before exporting.")
        if not analysis.weekend_synthesis.readiness.ready:
            raise ValueError(
                "Weekend synthesis is not ready: "
                + ", ".join(analysis.weekend_synthesis.readiness.blockers)
            )
        export_dir = (
            self.root
            / "weekend-exports"
            / f"{analysis.weekend_synthesis.package_hash[:16]}-v{WEEKEND_SYNTHESIS_SCHEMA_VERSION}"
        )
        if export_dir.exists():
            if not (export_dir / "manifest.json").is_file():
                raise ValueError(f"Existing weekend export is incomplete: {export_dir}")
        else:
            write_weekend_package(
                export_dir,
                analysis.weekend_synthesis,
                analysis.weekend_sources,
            )
        return self.save(
            analysis.model_copy(
                update={"weekend_package_path": str(export_dir)}, deep=True
            )
        )

    def coverage_bounds(self, analysis: AnalysisWorkspace | None = None) -> dict[str, Any]:
        current = analysis or self.open()
        sessions: dict[str, Any] = {}
        for session in current.sessions:
            if session.snapshot is None or session.load_state != "loaded":
                sessions[session.session_id] = {
                    "available": False,
                    "reason": "session_not_loaded",
                }
                continue
            dataset = _read_snapshot_dataset(self.root, session.snapshot)
            sessions[session.session_id] = {
                "available": True,
                "name": session.name,
                **coverage_bounds(dataset, selected_drivers=session.drivers),
                "playback": playback_summary(dataset),
            }
        return {"sessions": sessions}

    def track_map(
        self,
        analysis: AnalysisWorkspace,
        *,
        recipe_id: str,
        target_session_ids: list[str],
        parameters: dict[str, Any] | None = None,
        max_points: int = DEFAULT_TRACK_MAP_POINT_LIMIT,
    ) -> TrackMapPayload:
        registry = build_recipe_registry(analysis.plugins)
        if not registry.has_recipe(recipe_id):
            raise ValueError(f"Unknown chart template: {recipe_id}")
        if recipe_id != "telemetry_trace":
            raise ValueError("Track map selection is available for telemetry charts only.")
        if not target_session_ids:
            raise ValueError("Target session is required.")
        session = next(
            (item for item in analysis.sessions if item.session_id == target_session_ids[0]),
            None,
        )
        if session is None:
            raise ValueError("Unknown target session.")
        if session.snapshot is None or session.load_state != "loaded":
            return TrackMapPayload(
                status="unavailable",
                recipe_id=recipe_id,
                session_id=session.session_id,
                max_points=max_points,
                diagnostics=[
                    {
                        "field": "target_session_ids",
                        "message": "Target session is not loaded",
                    }
                ],
            )

        normalized = normalize_chart_parameters(recipe_id, parameters or {})
        schema = recipe_parameter_schema(recipe_id)
        _validate_parameters(schema, parameters or {})
        _validate_parameters(schema, normalized)
        _validate_chart_data_bounds_or_raise(
            analysis,
            recipe_id,
            target_session_ids,
            normalized,
        )
        dataset = _read_snapshot_dataset(self.root, session.snapshot)
        return build_track_map_payload(
            dataset,
            ChartRecipeConfig(
                recipe_id=recipe_id,
                title=_parameter_value(
                    normalized,
                    "title",
                    registry.get(recipe_id).display_name,
                ),
                parameters=normalized,
            ),
            session_id=session.session_id,
            max_points=max_points,
        )

    def open_for_playback(self) -> AnalysisWorkspace:
        """Open workspace metadata without loading session snapshot summaries."""
        path = _analysis_file(self.root)
        raw = json.loads(path.read_text(encoding="utf-8"))
        analysis = AnalysisWorkspace.model_validate(raw)
        analysis = _migrate_loaded_strategy_contracts(analysis)
        return analysis.model_copy(update={"root_path": self.root}, deep=True)

    def playback(
        self,
        analysis: AnalysisWorkspace,
        *,
        session_id: str,
        mode: Literal["time", "lap"] = "lap",
        cursor: float | None = None,
        start_lap: int | None = None,
        end_lap: int | None = None,
        selected_drivers: list[str] | None = None,
        max_frames: int = 12,
        max_markers: int = 30,
        max_points: int = DEFAULT_TRACK_MAP_POINT_LIMIT,
        maximum_sample_gap_seconds: float = 5.0,
        maximum_timing_sample_age_seconds: float = 10.0,
    ) -> PlaybackPayload:
        session = next(
            (item for item in analysis.sessions if item.session_id == session_id),
            None,
        )
        if session is None:
            raise ValueError("Unknown target session.")
        if session.snapshot is None or session.load_state != "loaded":
            return PlaybackPayload(
                status="unavailable",
                session_id=session.session_id,
                mode=mode,
                diagnostics=[
                    {
                        "field": "session_id",
                        "message": "Target session is not loaded",
                    }
                ],
            )
        dataset = _read_snapshot_dataset(self.root, session.snapshot)
        return build_playback_payload(
            dataset,
            cache_key=session.snapshot.dataset_hash,
            session_id=session.session_id,
            mode=mode,
            cursor=cursor,
            start_lap=start_lap,
            end_lap=end_lap,
            selected_drivers=selected_drivers,
            max_frames=max_frames,
            max_markers=max_markers,
            max_points=max_points,
            maximum_sample_gap_seconds=maximum_sample_gap_seconds,
            maximum_timing_sample_age_seconds=maximum_timing_sample_age_seconds,
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
                    update={
                        "drivers": effective_drivers,
                        "driver_details": dataset.drivers,
                        "available_teams": available_teams,
                    },
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
                "report_freshness": (
                    _stale_report_freshness(analysis.report_freshness)
                    if dependent_charts
                    else analysis.report_freshness
                ),
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
        _validate_chart_data_bounds_or_raise(
            analysis,
            recipe_id,
            target_session_ids,
            params,
        )
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
            next_target_session_ids = (
                target_session_ids
                if target_session_ids is not None
                else chart.target_session_ids
            )
            if parameters is not None:
                _validate_parameters(recipe_parameter_schema(chart.recipe_id), parameters)
            _validate_parameters(recipe_parameter_schema(chart.recipe_id), next_parameters)
            next_preset_id = chart.preset_id if preset_id is _KEEP_PRESET else preset_id
            _validate_preset_reference(analysis, chart.recipe_id, next_preset_id)
            _validate_chart_data_bounds_or_raise(
                analysis,
                chart.recipe_id,
                next_target_session_ids,
                next_parameters,
            )
            charts.append(
                chart.model_copy(
                    update={
                        "name": name if name is not None else chart.name,
                        "target_session_ids": next_target_session_ids,
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
            analysis.model_copy(
                update={
                    "charts": charts,
                    "review_stale": True,
                    "report_freshness": _stale_report_freshness(
                        analysis.report_freshness
                    ),
                },
                deep=True,
            )
        )

    def remove_chart(self, analysis: AnalysisWorkspace, chart_id: str) -> AnalysisWorkspace:
        updated = analysis.model_copy(
            update={
                "charts": [
                    chart for chart in analysis.charts if chart.chart_instance_id != chart_id
                ],
                "review_stale": True,
                "report_freshness": _stale_report_freshness(
                    analysis.report_freshness
                ),
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

        bound_diagnostics, bound_coverage = _chart_data_bounds_diagnostics(
            analysis,
            recipe_id,
            target_session_ids,
            normalized,
        )
        if bound_diagnostics.errors:
            return ParameterDiagnosticsView(
                status="invalid",
                recipe_id=recipe_id,
                schema_version=schema.schema_version,
                parameters=normalized,
                errors=bound_diagnostics.errors,
                warnings=bound_diagnostics.warnings,
                coverage_bounds=bound_coverage,
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
            coverage_bounds=dict(spec.metadata.get("coverage_bounds", bound_coverage)),
            style_sources=dict(spec.metadata.get("style_sources", {})),
            analytical_basis=dict(spec.metadata.get("analytical_basis", {})),
            analytical_results=_bounded_analytical_results(
                spec.metadata.get("analytical_results", {})
            ),
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
                _validate_chart_data_bounds_or_raise(
                    analysis,
                    chart.recipe_id,
                    chart.target_session_ids,
                    chart.parameters,
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
                update={
                    "charts": updated_charts,
                    "review_stale": True,
                    "report_freshness": analysis.report_freshness.model_copy(
                        update={
                            "evidence": FreshnessLayer(
                                status="stale",
                                input_fingerprint=analysis.report_freshness.evidence.input_fingerprint,
                            ),
                            "review": FreshnessLayer(
                                status="stale",
                                input_fingerprint=analysis.report_freshness.review.input_fingerprint,
                            ),
                            "selection": FreshnessLayer(
                                status="stale",
                                input_fingerprint=analysis.report_freshness.selection.input_fingerprint,
                            ),
                            "editorial": FreshnessLayer(
                                status="stale",
                                input_fingerprint=analysis.report_freshness.editorial.input_fingerprint,
                            ),
                            "publication": FreshnessLayer(
                                status="stale",
                                input_fingerprint=analysis.report_freshness.publication.input_fingerprint,
                            ),
                            "draft": FreshnessLayer(
                                status="stale",
                                input_fingerprint=analysis.report_freshness.draft.input_fingerprint,
                            ),
                            "export": FreshnessLayer(
                                status="stale",
                                input_fingerprint=analysis.report_freshness.export.input_fingerprint,
                            ),
                        },
                        deep=True,
                    ),
                },
                deep=True,
            )
        )

    def refresh_observations(self, analysis: AnalysisWorkspace) -> AnalysisWorkspace:
        package_dir = self.root / "package"
        package_dir.mkdir(parents=True, exist_ok=True)
        manifest = _analysis_manifest(self.root, analysis, status="succeeded")
        _materialize_package_artifacts(self.root, package_dir, manifest)
        target_session = _report_target_session(analysis)
        if target_session.snapshot is None:
            raise ValueError("A loaded Race, standard Qualifying, or standard Practice session is required to build the publication report.")
        dataset = _read_snapshot_dataset(self.root, target_session.snapshot)
        session_results = (
            materialize_qualifying_results(target_session.session_id, dataset)
            if is_standard_qualifying(dataset.metadata.session)
            else materialize_practice_results(target_session.session_id, dataset)
            if is_standard_practice(dataset.metadata.session)
            else materialize_session_spine(target_session.session_id, dataset)
        )
        content = build_report_content(
            target_session.session_id,
            _report_result_sources(self.root, analysis, target_session.session_id),
            session_results,
            foundational_result_types=_foundational_report_result_types(
                dataset.metadata.session
            ),
        )
        current_fingerprints = {item.result_fingerprint for item in content.results}
        prior_editorial = (
            analysis.report_content.publication_editorial
            if analysis.report_content is not None
            else content.publication_editorial
        )
        editorial = preserve_editorial_on_refresh(prior_editorial, current_fingerprints)
        content = content.model_copy(update={"publication_editorial": editorial}, deep=True)
        proposal = propose_publication_plan(content)
        if analysis.report_content and analysis.report_content.publication_plan:
            prior_charts = {
                item.chart_instance_id: item
                for item in analysis.report_content.publication_plan.charts
            }
            proposal = proposal.model_copy(
                update={
                    "charts": [
                        item.model_copy(
                            update={
                                "caption": prior_charts[item.chart_instance_id].caption,
                                "alt_text": prior_charts[item.chart_instance_id].alt_text,
                            },
                            deep=True,
                        )
                        if item.chart_instance_id in prior_charts
                        else item
                        for item in proposal.charts
                    ]
                },
                deep=True,
            )
        content = content.model_copy(update={"publication_plan": proposal}, deep=True)
        claims = {item.finding_id: item for item in [*content.findings, *content.conclusions]}
        prior_reviews = {item.item_id: item for item in analysis.report_reviews}
        reviews = [
            prior_reviews[item_id]
            for item_id, claim in claims.items()
            if item_id in prior_reviews
            and prior_reviews[item_id].reviewed_evidence_fingerprint
            == claim.evidence_fingerprint
        ]
        structured_paths = write_structured_report_package(
            package_dir, manifest, content, reviews
        )
        review_current = reviews_are_current(content, reviews)
        readiness = evaluate_readiness(
            content,
            reviews,
            evidence_current=True,
            review_current=review_current,
            publication_current=review_current,
            export_current=False,
            package_integrity=True,
        )
        content = content.model_copy(update={"publication_readiness": readiness}, deep=True)
        manifest = manifest.model_copy(
            update={
                "markdown_path": _relative_path(structured_paths.markdown_path, package_dir),
                "results_path": _relative_path(structured_paths.results_path, package_dir),
                "assessments_path": _relative_path(structured_paths.assessments_path, package_dir),
                "findings_path": _relative_path(structured_paths.findings_path, package_dir),
                "report_path": _relative_path(structured_paths.report_path, package_dir),
                "report_review_path": _relative_path(structured_paths.review_path, package_dir),
                "publication_plan_path": (
                    _relative_path(structured_paths.publication_plan_path, package_dir)
                    if structured_paths.publication_plan_path else None
                ),
                "analyst_markdown_path": _relative_path(structured_paths.analyst_markdown_path, package_dir),
                "evidence_sidecar_path": (
                    _relative_path(structured_paths.evidence_sidecar_path, package_dir)
                    if structured_paths.evidence_sidecar_path else None
                ),
                "publication_readiness": readiness.model_dump(mode="json"),
                "report_schema_version": content.schema_version,
                "report_evidence_fingerprint": content.evidence_fingerprint,
                "report_draft_fingerprint": structured_paths.draft_fingerprint,
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
                    "review_stale": not review_current,
                    "report_target_session_id": target_session.session_id,
                    "report_content": content,
                    "report_reviews": reviews,
                    "report_package_path": str(package_dir),
                    "report_freshness": ReportFreshness(
                        evidence=FreshnessLayer(
                            status="current",
                            input_fingerprint=content.evidence_fingerprint,
                        ),
                        review=FreshnessLayer(
                            status="current" if review_current else "stale",
                            input_fingerprint=content.evidence_fingerprint,
                        ),
                        selection=FreshnessLayer(
                            status="current",
                            input_fingerprint=content.evidence_fingerprint,
                        ),
                        editorial=FreshnessLayer(
                            status="stale" if any(
                                field.review_required
                                for field in [
                                    editorial.headline,
                                    editorial.standfirst,
                                    editorial.conclusion,
                                    *editorial.section_ledes.values(),
                                ]
                            ) else "current",
                            input_fingerprint=editorial_fingerprint(editorial, proposal),
                        ),
                        publication=FreshnessLayer(
                            status="current" if review_current else "stale",
                            input_fingerprint=structured_paths.draft_fingerprint,
                        ),
                        draft=FreshnessLayer(
                            status="current" if review_current else "stale",
                            input_fingerprint=structured_paths.draft_fingerprint,
                        ),
                        export=FreshnessLayer(
                            status="stale",
                            input_fingerprint=analysis.report_freshness.export.input_fingerprint,
                        ),
                    ),
                },
                deep=True,
            )
        )

    def export_package(self, analysis: AnalysisWorkspace) -> AnalysisWorkspace:
        current = analysis
        if (
            current.report_content is None
            or current.report_freshness.evidence.status != "current"
        ):
            current = self.refresh_observations(current)
        if current.report_freshness.review.status != "current":
            raise ValueError("Review included report claims before exporting.")
        if current.report_freshness.draft.status != "current":
            raise ValueError("Regenerate the current report draft before exporting.")
        if not current.report_content.publication_readiness.ready:
            raise ValueError(
                "Publication draft is not ready: "
                + ", ".join(current.report_content.publication_readiness.blockers)
            )
        if not current.report_package_path:
            raise ValueError("The current report package is unavailable.")
        source = Path(current.report_package_path).resolve()
        draft_fingerprint = current.report_freshness.draft.input_fingerprint
        if not draft_fingerprint:
            raise ValueError("The current report draft has no fingerprint.")
        export_dir = (
            self.root
            / "exports"
            / f"{draft_fingerprint[:16]}-v{PUBLICATION_EXPORT_CONTRACT_VERSION}"
        )
        readiness = evaluate_readiness(
            current.report_content,
            current.report_reviews,
            evidence_current=True,
            review_current=True,
            publication_current=True,
            export_current=True,
            package_integrity=True,
        )
        if export_dir.exists():
            if not export_dir.is_dir():
                raise ValueError(f"Export path is not a directory: {export_dir}")
            manifest_path = export_dir / "manifest.json"
            if not manifest_path.is_file():
                raise ValueError(f"Existing export is incomplete: {export_dir}")
        else:
            export_dir.parent.mkdir(parents=True, exist_ok=True)
            staging_dir = export_dir.parent / f".{export_dir.name}-{uuid4().hex}.tmp"
            try:
                source_manifest = ArtifactManifest.model_validate_json(
                    (source / "manifest.json").read_text(encoding="utf-8")
                )
                write_publication_export_package(
                    staging_dir,
                    source,
                    source_manifest,
                    current.report_content,
                    current.report_reviews,
                    readiness,
                )
                os.replace(staging_dir, export_dir)
            except Exception:
                if staging_dir.exists():
                    shutil.rmtree(staging_dir)
                raise
        return self.save(
            current.model_copy(
                update={
                    "exported_package_path": str(export_dir),
                    "report_content": current.report_content.model_copy(
                        update={"publication_readiness": readiness}, deep=True
                    ),
                    "report_freshness": current.report_freshness.model_copy(
                        update={
                            "export": FreshnessLayer(
                                status="current", input_fingerprint=draft_fingerprint
                            )
                        },
                        deep=True,
                    ),
                },
                deep=True,
            )
        )

    def review_report_item(
        self,
        analysis: AnalysisWorkspace,
        *,
        item_id: str,
        review_status: Literal["pending", "accepted", "edited", "rejected"],
        evidence_fingerprint: str,
        edited_text: str | None = None,
    ) -> AnalysisWorkspace:
        if analysis.report_content is None:
            raise ValueError("Refresh report evidence before reviewing claims.")
        claims = {
            item.finding_id: item
            for item in [
                *analysis.report_content.findings,
                *analysis.report_content.conclusions,
            ]
        }
        claim = claims.get(item_id)
        if claim is None:
            raise ValueError(f"Unknown report item ID: {item_id}")
        if claim.evidence_fingerprint != evidence_fingerprint:
            raise ValueError("The report item evidence changed; refresh before reviewing.")
        entry = ReportReviewEntry(
            item_id=item_id,
            reviewed_evidence_fingerprint=evidence_fingerprint,
            review_status=review_status,
            edited_text=edited_text,
        )
        reviews = [item for item in analysis.report_reviews if item.item_id != item_id]
        reviews.append(entry)
        reviews.sort(key=lambda item: item.item_id)
        review_current = reviews_are_current(analysis.report_content, reviews)
        readiness = evaluate_readiness(
            analysis.report_content,
            reviews,
            evidence_current=True,
            review_current=review_current,
            publication_current=False,
            export_current=False,
            package_integrity=True,
        )
        content = analysis.report_content.model_copy(
            update={"publication_readiness": readiness}, deep=True
        )
        if analysis.report_package_path:
            _write_json(
                Path(analysis.report_package_path) / "report-review.json",
                [item.model_dump(mode="json") for item in reviews],
            )
        return self.save(
            analysis.model_copy(
                update={
                    "report_reviews": reviews,
                    "report_content": content,
                    "review_stale": not review_current,
                    "report_freshness": analysis.report_freshness.model_copy(
                        update={
                            "review": FreshnessLayer(
                                status="current" if review_current else "stale",
                                input_fingerprint=analysis.report_content.evidence_fingerprint,
                            ),
                            "draft": FreshnessLayer(status="stale"),
                            "publication": FreshnessLayer(status="stale"),
                            "export": FreshnessLayer(
                                status="stale",
                                input_fingerprint=analysis.report_freshness.export.input_fingerprint,
                            ),
                        },
                        deep=True,
                    ),
                },
                deep=True,
            )
        )

    def regenerate_report_draft(self, analysis: AnalysisWorkspace) -> AnalysisWorkspace:
        if analysis.report_content is None or not analysis.report_package_path:
            raise ValueError("Refresh report evidence before regenerating the draft.")
        if analysis.report_freshness.review.status != "current":
            raise ValueError("Review included report claims before regenerating the draft.")
        package_dir = Path(analysis.report_package_path)
        manifest = ArtifactManifest.model_validate_json(
            (package_dir / "manifest.json").read_text(encoding="utf-8")
        )
        paths = write_structured_report_package(
            package_dir,
            manifest,
            analysis.report_content,
            analysis.report_reviews,
        )
        readiness = evaluate_readiness(
            analysis.report_content,
            analysis.report_reviews,
            evidence_current=True,
            review_current=True,
            publication_current=True,
            export_current=False,
            package_integrity=True,
        )
        content = analysis.report_content.model_copy(
            update={"publication_readiness": readiness}, deep=True
        )
        manifest = manifest.model_copy(
            update={
                "report_draft_fingerprint": paths.draft_fingerprint,
                "publication_readiness": readiness.model_dump(mode="json"),
            }, deep=True
        )
        manifest.write(package_dir / "manifest.json")
        return self.save(
            analysis.model_copy(
                update={
                    "report_content": content,
                    "report_freshness": analysis.report_freshness.model_copy(
                        update={
                            "publication": FreshnessLayer(
                                status="current", input_fingerprint=paths.draft_fingerprint
                            ),
                            "draft": FreshnessLayer(
                                status="current", input_fingerprint=paths.draft_fingerprint
                            ),
                            "export": FreshnessLayer(
                                status="stale",
                                input_fingerprint=analysis.report_freshness.export.input_fingerprint,
                            ),
                        },
                        deep=True,
                    )
                },
                deep=True,
            )
        )

    def update_publication(
        self,
        analysis: AnalysisWorkspace,
        *,
        plan: PublicationPlan,
        editorial: PublicationEditorial,
        evidence_fingerprint: str,
    ) -> AnalysisWorkspace:
        if analysis.report_content is None:
            raise ValueError("Refresh report evidence before editing publication fields.")
        if analysis.report_content.evidence_fingerprint != evidence_fingerprint:
            raise ValueError("The report evidence changed; refresh before editing publication fields.")
        if analysis.report_freshness.evidence.status != "current":
            raise ValueError("Publication fields cannot be changed against stale evidence.")
        validate_publication_plan(analysis.report_content, plan)
        content = analysis.report_content.model_copy(
            update={"publication_plan": plan, "publication_editorial": editorial},
            deep=True,
        )
        review_current = reviews_are_current(content, analysis.report_reviews)
        readiness = evaluate_readiness(
            content,
            analysis.report_reviews,
            evidence_current=True,
            review_current=review_current,
            publication_current=False,
            export_current=False,
            package_integrity=True,
        )
        content = content.model_copy(update={"publication_readiness": readiness}, deep=True)
        return self.save(
            analysis.model_copy(
                update={
                    "report_content": content,
                    "review_stale": not review_current,
                    "report_freshness": analysis.report_freshness.model_copy(
                        update={
                            "review": FreshnessLayer(
                                status="current" if review_current else "stale",
                                input_fingerprint=content.evidence_fingerprint,
                            ),
                            "selection": FreshnessLayer(
                                status="current", input_fingerprint=content.evidence_fingerprint
                            ),
                            "editorial": FreshnessLayer(
                                status="current",
                                input_fingerprint=editorial_fingerprint(editorial, plan),
                            ),
                            "publication": FreshnessLayer(status="stale"),
                            "draft": FreshnessLayer(status="stale"),
                            "export": FreshnessLayer(
                                status="stale",
                                input_fingerprint=analysis.report_freshness.export.input_fingerprint,
                            ),
                        },
                        deep=True,
                    ),
                },
                deep=True,
            )
        )

    def update_report_plan(
        self,
        analysis: AnalysisWorkspace,
        *,
        plan: ReportPlan,
        evidence_fingerprint: str,
    ) -> AnalysisWorkspace:
        if analysis.report_content is None:
            raise ValueError("Refresh report evidence before editing the report plan.")
        if analysis.report_content.evidence_fingerprint != evidence_fingerprint:
            raise ValueError("The report evidence changed; refresh before editing the plan.")
        if plan.target_session_id != analysis.report_content.target_session_id:
            raise ValueError("The report plan target session cannot be changed implicitly.")
        claim_ids = {
            item.finding_id
            for item in [
                *analysis.report_content.findings,
                *analysis.report_content.conclusions,
            ]
        }
        chart_ids = {
            evidence.chart_instance_id
            for result in analysis.report_content.results
            for evidence in result.chart_evidence
        }
        for section in plan.sections:
            referenced: set[tuple[str, str]] = set()
            for item in section.items:
                if item.item_type == "claim":
                    if item.reference_id not in claim_ids:
                        raise ValueError(
                            f"Report plan references an unknown claim: {item.reference_id}"
                        )
                elif item.item_type == "chart" and item.reference_id not in chart_ids:
                    raise ValueError(
                        f"Report plan references an unknown chart: {item.reference_id}"
                    )
                reference = (item.item_type, item.reference_id)
                if reference in referenced:
                    raise ValueError(
                        f"Report section references an item more than once: {item.reference_id}"
                    )
                referenced.add(reference)
        content = analysis.report_content.model_copy(update={"plan": plan}, deep=True)
        review_current = reviews_are_current(content, analysis.report_reviews)
        if analysis.report_package_path:
            _write_json(
                Path(analysis.report_package_path) / "report.json",
                plan.model_dump(mode="json"),
            )
        return self.save(
            analysis.model_copy(
                update={
                    "report_content": content,
                    "review_stale": not review_current,
                    "report_freshness": analysis.report_freshness.model_copy(
                        update={
                            "review": FreshnessLayer(
                                status="current" if review_current else "stale",
                                input_fingerprint=content.evidence_fingerprint,
                            ),
                            "draft": FreshnessLayer(status="stale"),
                            "export": FreshnessLayer(
                                status="stale",
                                input_fingerprint=analysis.report_freshness.export.input_fingerprint,
                            ),
                        },
                        deep=True,
                    ),
                },
                deep=True,
            )
        )

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
    if "lap_number" in parameters and parameters["lap_number"] is not None:
        lap = parameters["lap_number"]
        selection["laps"] = {"range": {"start": lap, "end": lap}}
    if "lap_range" in parameters:
        laps = dict(selection.get("laps") or {})
        laps["range"] = parameters["lap_range"]
        selection["laps"] = laps
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
    if recipe_id in {
        "tyre_strategy",
        "stint_pace",
        "pace_evolution",
        "compound_comparison",
        "race_time_delta_evolution",
        "pit_cycle_comparison",
        "driver_battle",
    }:
        for key in ["stints", "focal_driver", "rival_driver"]:
            _move(parameters, selection, key)
        _move(parameters, filters, "strategy_exclusion_policy")
        for key in [
            "compounds",
            "minimum_samples",
            "comparison_mode",
            "reference_driver",
            "tyre_age_range",
            "evolution_mode",
            "delta_mode",
            "pit_stop_lap",
            "post_stop_window",
        ]:
            _move(parameters, analysis, key)
        for key in [
            "presentation_mode",
            "x_axis_basis",
            "context_layer",
            "show_pit_markers",
            "show_tyre_age_labels",
            "show_rejoin_context",
            "show_execution_breakdown",
        ]:
            _move(parameters, presentation, key)
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
                name="lap_number",
                label="Lap",
                field_type="number",
                default=None,
                minimum=1,
                group="General",
                order=29,
                reset_group="filters",
            ),
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
                label="Legacy layout migration",
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
            ParameterField(
                name="context_layer",
                label="Context layer",
                field_type="select",
                default="race_context",
                options=["race_context", "conditions", "position", "gap"],
                group="Strategy",
                order=140,
                mode="advanced",
                reset_group="presentation",
            ),
            ParameterField(
                name="show_tyre_age_labels",
                label="Show tyre-age labels",
                field_type="checkbox",
                default=False,
                group="Strategy",
                order=150,
                mode="advanced",
                reset_group="presentation",
            ),
        ],
        "stint_pace": [
            ParameterField(name="stints", label="Driver stints", field_type="multi_select", default=[], group="Strategy", order=100, reset_group="selection"),
            ParameterField(name="compounds", label="Compounds", field_type="multi_select", default=[], options=["HARD", "MEDIUM", "SOFT", "INTERMEDIATE", "WET"], group="Strategy", order=105, reset_group="analysis"),
            ParameterField(name="presentation_mode", label="Presentation", field_type="select", default="progression", options=["progression", "consistency_summary"], group="Strategy", order=110, reset_group="presentation"),
            ParameterField(name="x_axis_basis", label="X-axis", field_type="select", default="stint_progress", options=["stint_progress", "tyre_age", "race_lap"], group="Strategy", order=115, visible_when={"presentation_mode": "progression"}, reset_group="presentation"),
            ParameterField(name="reference_driver", label="Same-lap reference", field_type="driver_selector", default=None, group="Strategy", order=120, mode="advanced", reset_group="analysis"),
            ParameterField(name="minimum_samples", label="Minimum representative samples", field_type="number", default=3, minimum=1, group="Strategy", order=130, mode="advanced", reset_group="analysis"),
        ],
        "pace_evolution": [
            ParameterField(name="stints", label="Driver stints", field_type="multi_select", default=[], group="Strategy", order=100, reset_group="selection"),
            ParameterField(name="compounds", label="Compounds", field_type="multi_select", default=[], options=["HARD", "MEDIUM", "SOFT", "INTERMEDIATE", "WET"], group="Strategy", order=105, reset_group="analysis"),
            ParameterField(name="evolution_mode", label="Evolution view", field_type="select", default="lap_time", options=["lap_time", "sector_evolution"], group="Strategy", order=110, reset_group="analysis"),
            ParameterField(name="minimum_samples", label="Minimum representative samples", field_type="number", default=5, minimum=5, group="Strategy", order=120, mode="advanced", reset_group="analysis"),
        ],
        "compound_comparison": [
            ParameterField(name="comparison_mode", label="Comparison mode", field_type="select", default="unrestricted_distribution", options=["within_driver", "matched_driver", "unrestricted_distribution"], group="Comparison", order=100, reset_group="analysis"),
            ParameterField(name="compounds", label="Compounds", field_type="multi_select", default=[], options=["HARD", "MEDIUM", "SOFT", "INTERMEDIATE", "WET"], group="Comparison", order=110, reset_group="analysis"),
            ParameterField(name="tyre_age_range", label="Tyre-age range", field_type="numeric_range", default=None, minimum=0, group="Comparison", order=120, mode="advanced", visible_when={"comparison_mode": ["within_driver", "matched_driver"]}, reset_group="analysis"),
            ParameterField(name="minimum_samples", label="Minimum representative samples", field_type="number", default=5, minimum=1, group="Comparison", order=130, mode="advanced", reset_group="analysis"),
        ],
        "race_time_delta_evolution": [
            ParameterField(name="focal_driver", label="Focal driver", field_type="driver_selector", required=True, default=None, group="Comparison", order=100, reset_group="selection"),
            ParameterField(name="delta_mode", label="Delta mode", field_type="select", default="derived_cumulative_pace_delta", options=["measured_gap_change", "derived_cumulative_pace_delta"], group="Comparison", order=110, reset_group="analysis"),
            ParameterField(name="reference_driver", label="Comparator", field_type="driver_selector", required=True, default=None, group="Comparison", order=120, reset_group="analysis"),
        ],
        "pit_cycle_comparison": [
            ParameterField(name="focal_driver", label="Focal driver", field_type="driver_selector", required=True, default=None, group="Pit cycle", order=100, reset_group="selection"),
            ParameterField(name="rival_driver", label="Rival driver", field_type="driver_selector", required=True, default=None, group="Pit cycle", order=110, reset_group="selection"),
            ParameterField(name="pit_stop_lap", label="Focal pit-in lap", field_type="number", required=True, default=None, minimum=1, group="Pit cycle", order=120, reset_group="analysis"),
            ParameterField(name="post_stop_window", label="Post-stop search window", field_type="number", default=3, minimum=1, maximum=5, group="Pit cycle", order=130, mode="advanced", reset_group="analysis"),
            ParameterField(name="show_rejoin_context", label="Show rejoin context", field_type="checkbox", default=False, group="Pit cycle", order=140, mode="advanced", reset_group="presentation"),
            ParameterField(name="show_execution_breakdown", label="Show execution breakdown", field_type="checkbox", default=False, group="Pit cycle", order=150, mode="advanced", reset_group="presentation"),
        ],
        "driver_battle": [
            ParameterField(name="minimum_samples", label="Minimum representative samples", field_type="number", default=3, minimum=1, group="Battle", order=100, mode="advanced", reset_group="analysis"),
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
    if recipe_id == "telemetry_trace":
        fields = [
            field.model_copy(update={"mode": "advanced"})
            if field.name == "lap_range"
            else field
            for field in fields
        ]
    strategy_recipe_ids = {
        "tyre_strategy",
        "stint_pace",
        "pace_evolution",
        "compound_comparison",
        "race_time_delta_evolution",
        "pit_cycle_comparison",
        "driver_battle",
    }
    if recipe_id in strategy_recipe_ids:
        fields = fields + [
            ParameterField(
                name="strategy_exclusion_policy",
                label="Representative-lap exclusions",
                field_type="object",
                default={
                    "exclude_first_race_lap": True,
                    "exclude_pit_in_laps": True,
                    "exclude_pit_out_laps": True,
                    "exclude_deleted_laps": True,
                    "exclude_generated_laps": True,
                    "exclude_inaccurate_laps": True,
                    "exclude_non_green_status": True,
                    "require_complete_sectors": False,
                    "green_track_status_codes": ["1"],
                },
                group="Representative laps",
                order=900,
                mode="advanced",
                reset_group="filters",
            )
        ]
    return RecipeParameterSchema(
        recipe_id=recipe_id,
        schema_version=2 if recipe_id == "tyre_strategy" else 1,
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
            {"presentation": {"show_pit_markers": True, "context_layer": "race_context"}},
        ),
        (
            "builtin-stint-pace-head-to-head",
            "stint_pace",
            "Stint pace head-to-head",
            {"presentation": {"presentation_mode": "progression", "x_axis_basis": "stint_progress"}},
        ),
        (
            "builtin-stint-pace-summary",
            "stint_pace",
            "Stint pace summary",
            {"presentation": {"presentation_mode": "consistency_summary"}},
        ),
        (
            "builtin-observed-pace-evolution",
            "pace_evolution",
            "Observed pace evolution",
            {"analysis": {"evolution_mode": "lap_time", "minimum_samples": 5}},
        ),
        (
            "builtin-compound-distributions",
            "compound_comparison",
            "Compound distributions",
            {"analysis": {"comparison_mode": "unrestricted_distribution"}},
        ),
        (
            "builtin-derived-race-pace-delta",
            "race_time_delta_evolution",
            "Derived cumulative pace delta",
            {"analysis": {"delta_mode": "derived_cumulative_pace_delta"}},
        ),
        (
            "builtin-pit-cycle-measured",
            "pit_cycle_comparison",
            "Measured pit-cycle comparison",
            {"analysis": {"post_stop_window": 3}},
        ),
        (
            "builtin-driver-battle",
            "driver_battle",
            "Driver battle",
            {},
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
            notes=(
                "Built-in SPEC-008 strategy preset."
                if recipe_id in {
                    "tyre_strategy",
                    "stint_pace",
                    "pace_evolution",
                    "compound_comparison",
                    "race_time_delta_evolution",
                    "pit_cycle_comparison",
                    "driver_battle",
                }
                else "Built-in SPEC-006 analyst preset."
            ),
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


def _validate_chart_data_bounds_or_raise(
    analysis: AnalysisWorkspace,
    recipe_id: str,
    target_session_ids: list[str],
    parameters: dict[str, Any],
) -> None:
    diagnostics, _ = _chart_data_bounds_diagnostics(
        analysis,
        recipe_id,
        target_session_ids,
        parameters,
    )
    if diagnostics.errors:
        first = diagnostics.errors[0]
        raise ValueError(f"{first['field']}: {first['message']}")


def _chart_data_bounds_diagnostics(
    analysis: AnalysisWorkspace,
    recipe_id: str,
    target_session_ids: list[str],
    parameters: dict[str, Any],
) -> tuple[ParameterDiagnostics, dict[str, Any]]:
    diagnostics = ParameterDiagnostics()
    if not target_session_ids:
        diagnostics.error("target_session_ids", "Target session is required")
        return diagnostics, {}
    session = next(
        (item for item in analysis.sessions if item.session_id == target_session_ids[0]),
        None,
    )
    if session is None:
        diagnostics.error("target_session_ids", "Unknown target session")
        return diagnostics, {}
    if session.snapshot is None or session.load_state != "loaded":
        diagnostics.error("target_session_ids", "Target session is not loaded")
        return diagnostics, {}

    dataset = _read_snapshot_dataset(analysis.root_path, session.snapshot)
    config = ChartRecipeConfig(
        recipe_id=recipe_id,
        title=_parameter_value(
            parameters,
            "title",
            build_recipe_registry(analysis.plugins).get(recipe_id).display_name,
        ),
        parameters=parameters,
    )
    try:
        selected_drivers = selected_driver_codes(dataset, config)
    except ValueError as exc:
        diagnostics.errors.append(
            _parameter_diagnostic_error(recipe_parameter_schema(recipe_id), str(exc))
        )
        return diagnostics, coverage_bounds(dataset)
    bounds = validate_coverage_bounds(
        dataset,
        config,
        selected_drivers=selected_drivers,
        diagnostics=diagnostics,
        include_distance_range=recipe_id == "telemetry_trace",
    )
    return diagnostics, bounds


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
    path = (analysis_root / snapshot.dataset_path).resolve()
    return _read_snapshot_dataset_cached(path, snapshot.dataset_hash)


@lru_cache(maxsize=4)
def _read_snapshot_dataset_cached(path: Path, dataset_hash: str) -> SessionDataset:
    return ensure_track_geometry(
        SessionDataset.model_validate(json.loads(path.read_text(encoding="utf-8")))
    )


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        temporary = Path(stream.name)
    os.replace(temporary, path)


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
        "description": metadata.description,
        "source_type": source_type,
        "source_label": source_label,
        "required_dataset_fields": list(metadata.required_dataset_fields),
        "output_artifact_types": list(metadata.output_artifact_types),
        "supported_session_types": list(metadata.supported_session_types),
        "preview_asset": metadata.preview_asset,
        "icon": metadata.icon,
        "supported_session_count": {"minimum": 1, "maximum": 1},
        "parameter_schema_version": schema.schema_version,
        "availability_status": "available",
        "diagnostics": [],
        "source": metadata.source,
        "parameter_schema": schema.model_dump(mode="json"),
    }


def _migrate_loaded_strategy_contracts(analysis: AnalysisWorkspace) -> AnalysisWorkspace:
    """Read legacy tyre-strategy instances through the approved v2 contract."""

    charts: list[ChartInstance] = []
    changed = False
    target_version = recipe_parameter_schema("tyre_strategy").schema_version
    for chart in analysis.charts:
        if chart.recipe_id != "tyre_strategy" or chart.schema_version >= target_version:
            charts.append(chart)
            continue
        normalized = normalize_chart_parameters("tyre_strategy", chart.parameters)
        diagnostics = dict(normalized.get("diagnostics") or {})
        diagnostics["migration"] = {
            "from_schema_version": chart.schema_version,
            "to_schema_version": target_version,
            "status": "mapped",
            "stable_recipe_id": "tyre_strategy",
        }
        normalized["diagnostics"] = diagnostics
        charts.append(
            chart.model_copy(
                update={
                    "parameters": normalized,
                    "parameter_hash": _hash_payload(normalized),
                    "schema_version": target_version,
                    "generation_state": "stale" if chart.generation_state == "generated" else chart.generation_state,
                    "stale": chart.generation_state == "generated" or chart.stale,
                },
                deep=True,
            )
        )
        changed = True
    presets = [
        preset.model_copy(update={"schema_version": target_version}, deep=True)
        if preset.recipe_id == "tyre_strategy" and preset.schema_version < target_version
        else preset
        for preset in analysis.presets
    ]
    if any(left is not right for left, right in zip(analysis.presets, presets)):
        changed = True
    if not changed:
        return analysis
    return analysis.model_copy(update={"charts": charts, "presets": presets}, deep=True)


def _bounded_analytical_results(value: Any) -> dict[str, Any]:
    """Expose deterministic headline results without returning raw sample streams."""

    if not isinstance(value, dict):
        return {}
    headline_keys = {
        "result_kind",
        "value_category",
        "value_categories",
        "status",
        "quality",
        "presentation_mode",
        "evolution_mode",
        "comparison_mode",
        "scalar_difference_seconds",
        "measured_gap_change_seconds",
        "overall_change_seconds",
        "coverage_percentage",
        "paired_sample_count",
        "pit_lane_duration_seconds",
        "panel_contract",
        "template_version",
        "stable_recipe_id",
    }
    bounded = {key: value[key] for key in sorted(value) if key in headline_keys}
    if not bounded and "status" not in value:
        bounded["summary_available"] = bool(value)
    return bounded


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
            unsupported = sorted(set(value) - set(field.options)) if field.options else []
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
    if name == "lap_number":
        laps = selection.get("laps")
        if isinstance(laps, dict) and isinstance(laps.get("range"), dict):
            lap_range = laps["range"]
            start = lap_range.get("start")
            end = lap_range.get("end")
            if start == end:
                return start
            return start if start is not None else default
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


def _report_target_session(analysis: AnalysisWorkspace) -> AnalysisSession:
    if analysis.report_target_session_id:
        selected = next(
            (
                session
                for session in analysis.sessions
                if session.session_id == analysis.report_target_session_id
            ),
            None,
        )
        if selected is None:
            raise ValueError("The selected report target session no longer exists.")
        if str(selected.session.session).strip().lower() not in {"race", "r", "qualifying", "q", "fp1", "fp2", "fp3", "practice 1", "practice 2", "practice 3"}:
            raise ValueError("Publication reports require one Race, standard Qualifying, or standard Practice session.")
        return selected
    supported = [
        session
        for session in analysis.sessions
        if str(session.session.session).strip().lower() in {"race", "r", "qualifying", "q", "fp1", "fp2", "fp3", "practice 1", "practice 2", "practice 3"}
        and session.snapshot is not None
    ]
    if not supported:
        raise ValueError("A loaded Race, standard Qualifying, or standard Practice session is required to build the report.")
    return supported[0]


def _report_result_sources(
    analysis_root: Path,
    analysis: AnalysisWorkspace,
    target_session_id: str,
) -> list[ResultSource]:
    sources: list[ResultSource] = []
    for chart in analysis.charts:
        if (
            chart.generation_state != "generated"
            or target_session_id not in chart.target_session_ids
            or not chart.metadata_path
        ):
            continue
        metadata_path = _resolve_relative_child(analysis_root, chart.metadata_path)
        if not metadata_path.exists():
            continue
        try:
            raw = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(raw, dict):
            continue
        sources.append(
            ResultSource(
                target_session_id=target_session_id,
                chart_instance_id=chart.chart_instance_id,
                artifact_id=chart.artifact_id,
                title=str(raw.get("title") or chart.name),
                image_path=chart.image_path,
                metadata_path=chart.metadata_path,
                metadata=raw,
            )
        )
    return sources


def _foundational_report_result_types(session_name: str) -> set[str]:
    """Return session facts kept for correctness outside narrative chart scope."""

    normalized = session_name.strip().lower()
    if normalized in {"race", "r"}:
        return set(RACE_FOUNDATIONAL_RESULT_TYPES)
    if normalized in {"qualifying", "q"}:
        return {
            "qualifying_segment_classification",
            "qualifying_conditions",
            "qualifying_deleted_laps",
            "qualifying_interruptions",
        }
    if normalized in {
        "fp1",
        "fp2",
        "fp3",
        "practice 1",
        "practice 2",
        "practice 3",
    }:
        return {
            "practice_classification",
            "practice_conditions",
            "practice_interruptions",
        }
    return set()


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


def _materialize_package_artifacts(
    analysis_root: Path,
    package_dir: Path,
    manifest: ArtifactManifest,
) -> None:
    charts_dir = _resolve_relative_child(package_dir, "charts")
    if charts_dir.exists():
        if not charts_dir.is_dir():
            raise ValueError(f"Package charts path is not a directory: {charts_dir}")
        shutil.rmtree(charts_dir)
    charts_dir.mkdir(parents=True, exist_ok=True)

    for artifact in manifest.artifacts:
        for relative_path in (artifact.image_path, artifact.metadata_path):
            if not relative_path:
                continue
            source = _resolve_relative_child(analysis_root, relative_path)
            if not source.exists() or not source.is_file():
                raise ValueError(f"Generated chart asset is missing: {relative_path}")
            destination = _resolve_relative_child(package_dir, relative_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


def _resolve_relative_child(root: Path, relative_path: str) -> Path:
    path = Path(relative_path)
    if path.is_absolute():
        raise ValueError(f"Expected a relative package path: {relative_path}")
    root_resolved = root.resolve()
    candidate = (root_resolved / path).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"Path escapes root: {relative_path}") from exc
    return candidate


def _stale_report_freshness(current: ReportFreshness) -> ReportFreshness:
    return ReportFreshness(
        evidence=FreshnessLayer(
            status="stale", input_fingerprint=current.evidence.input_fingerprint
        ),
        review=FreshnessLayer(
            status="stale", input_fingerprint=current.review.input_fingerprint
        ),
        selection=FreshnessLayer(
            status="stale", input_fingerprint=current.selection.input_fingerprint
        ),
        editorial=FreshnessLayer(
            status="stale", input_fingerprint=current.editorial.input_fingerprint
        ),
        publication=FreshnessLayer(
            status="stale", input_fingerprint=current.publication.input_fingerprint
        ),
        draft=FreshnessLayer(
            status="stale", input_fingerprint=current.draft.input_fingerprint
        ),
        export=FreshnessLayer(
            status="stale", input_fingerprint=current.export.input_fingerprint
        ),
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

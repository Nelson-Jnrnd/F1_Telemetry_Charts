"""FastAPI application for local package preview."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from f1_telemetry_charts.analysis.observations import (
    Observation,
    ObservationReviewEntry,
    ReviewStatus,
)
from f1_telemetry_charts.analysis.report import apply_observation_review, render_markdown_draft
from f1_telemetry_charts.analysis.orchestrator import run_analysis
from f1_telemetry_charts.analysis.workspace import (
    AnalysisService,
    AnalysisView,
    ParameterDiagnosticsView,
    PlaybackPayload,
    PresetScope,
    TrackMapPayload,
    list_recipe_metadata_payloads,
)
from f1_telemetry_charts.config.loader import load_config
from f1_telemetry_charts.config.models import DataCacheConfig, ProjectConfig, SessionConfig
from f1_telemetry_charts.config.validation import (
    ConfigValidationError,
    ValidationIssue,
    validate_config,
)
from f1_telemetry_charts.preview.reader import (
    PackagePreviewError,
    PackageView,
    read_package_view,
    resolve_package_asset,
)
from f1_telemetry_charts.plugins import PluginDiscoveryConfig, PluginManager, PluginStatus


class ReviewUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_status: ReviewStatus
    edited_text: str | None = None


class PluginValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    local_paths: list[Path] = Field(default_factory=list)
    entry_points_enabled: bool = False


class ConfigPathRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: Path


class ConfigDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config: dict


class ConfigSaveRequest(ConfigDraftRequest):
    path: Path


class ConfigValidationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    config: dict | None = None
    issues: list[dict[str, str]] = Field(default_factory=list)


class AnalysisPathRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: Path


class AnalysisCreateRequest(AnalysisPathRequest):
    name: str = "Untitled Analysis"


class AnalysisDirectoryPickRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    initial_path: Path | None = None


class AnalysisDirectoryPickResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["selected", "cancelled", "unavailable"]
    path: str | None = None
    message: str | None = None


class AnalysisSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    session: SessionConfig
    drivers: list[str] = Field(min_length=1)
    data_cache: DataCacheConfig = Field(default_factory=DataCacheConfig)
    load: bool = True


class AnalysisChartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipe_id: str | None = None
    template_id: str | None = None
    target_session_ids: list[str] = Field(min_length=1)
    name: str | None = None
    parameters: dict = Field(default_factory=dict)
    preset_id: str | None = None


class AnalysisChartUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    target_session_ids: list[str] | None = None
    parameters: dict | None = None
    preset_id: str | None = None


class ChartGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chart_ids: list[str] | None = None


class AnalysisChartDiagnosticsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipe_id: str | None = None
    template_id: str | None = None
    target_session_ids: list[str] = Field(min_length=1)
    parameters: dict = Field(default_factory=dict)


class AnalysisTrackMapRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipe_id: str | None = None
    template_id: str | None = None
    target_session_ids: list[str] = Field(min_length=1)
    parameters: dict = Field(default_factory=dict)
    max_points: int = Field(default=500, ge=2, le=1200)


class AnalysisPlaybackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1)
    mode: Literal["time", "lap"] = "lap"
    cursor: float | None = None
    start_lap: int | None = Field(default=None, ge=1)
    end_lap: int | None = Field(default=None, ge=1)
    selected_drivers: list[str] | None = None
    max_frames: int = Field(default=12, ge=1, le=60)
    max_markers: int = Field(default=30, ge=1, le=60)
    max_points: int = Field(default=500, ge=2, le=1200)
    maximum_sample_gap_seconds: float = Field(default=5.0, ge=0, le=300)
    maximum_timing_sample_age_seconds: float = Field(default=10.0, ge=0, le=300)


class PresetSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipe_id: str | None = None
    template_id: str | None = None
    display_name: str
    parameters: dict = Field(default_factory=dict)
    scope: PresetScope = "analysis"
    notes: str | None = None
    replace_existing: bool = False


class PresetUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = None
    parameters: dict | None = None
    replace_existing: bool = False


def create_app(initial_package: Path | None = None) -> FastAPI:
    app = FastAPI(title="F1 Telemetry Charts Local UI")
    state = {
        "package_path": initial_package.resolve() if initial_package else None,
        "analysis_path": None,
        "history": [],
    }
    if initial_package is not None:
        _remember_history(state["history"], initial_package.resolve(), "opened")

    static_dir = Path(__file__).with_name("static")
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
        assets_dir = static_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
        tyres_dir = static_dir / "tyres"
        if tyres_dir.exists():
            app.mount("/tyres", StaticFiles(directory=tyres_dir), name="tyres")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        index_path = static_dir / "index.html"
        if index_path.exists():
            return index_path.read_text(encoding="utf-8")
        return "<!doctype html><title>F1 Telemetry Charts</title><div id=\"root\"></div>"

    @app.get("/api/package", response_model=PackageView)
    def get_package() -> PackageView:
        package_path = state["package_path"]
        if package_path is None:
            raise HTTPException(status_code=404, detail="No package is currently open.")
        try:
            return read_package_view(package_path)
        except PackagePreviewError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/package/open", response_model=PackageView)
    def open_package(request: dict[str, str]) -> PackageView:
        raw_path = request.get("path")
        if not raw_path:
            raise HTTPException(status_code=422, detail="Package path is required.")
        try:
            view = read_package_view(raw_path)
        except PackagePreviewError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        state["package_path"] = Path(view.package_path)
        _remember_history(state["history"], Path(view.package_path), "opened")
        return view

    @app.get("/api/package/assets/{asset_path:path}")
    def get_asset(asset_path: str) -> FileResponse:
        package_path = state["package_path"]
        if package_path is None:
            raise HTTPException(status_code=404, detail="No package is currently open.")
        try:
            path = resolve_package_asset(package_path, asset_path)
        except PackagePreviewError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not path.exists() or not path.is_file():
            raise HTTPException(status_code=404, detail="Package asset not found.")
        return FileResponse(path)

    @app.put("/api/package/observations/{observation_id}/review", response_model=PackageView)
    def update_review(observation_id: str, request: ReviewUpdateRequest) -> PackageView:
        package_path = _require_package_path(state["package_path"])
        view = read_package_view(package_path)
        if view.manifest is None or view.manifest.observations_path is None:
            raise HTTPException(status_code=400, detail="Package observations are unavailable.")

        observations_path = resolve_package_asset(package_path, view.manifest.observations_path)
        observations = _read_observations(observations_path)
        observations = apply_observation_review(
            observations,
            observation_id=observation_id,
            review_status=request.review_status,
            edited_text=request.edited_text,
        )
        _write_observations(observations_path, observations)
        if view.manifest.review_path is not None:
            review_path = resolve_package_asset(package_path, view.manifest.review_path)
            _write_review(review_path, observations)
        return read_package_view(package_path)

    @app.post("/api/package/draft/regenerate", response_model=PackageView)
    def regenerate_draft() -> PackageView:
        package_path = _require_package_path(state["package_path"])
        view = read_package_view(package_path)
        if view.manifest is None:
            raise HTTPException(status_code=400, detail="Package manifest is unavailable.")
        if view.manifest.observations_path is None or view.manifest.markdown_path is None:
            raise HTTPException(status_code=400, detail="Package draft inputs are unavailable.")

        observations_path = resolve_package_asset(package_path, view.manifest.observations_path)
        draft_path = resolve_package_asset(package_path, view.manifest.markdown_path)
        observations = _read_observations(observations_path)
        draft_path.write_text(
            render_markdown_draft(view.manifest, observations),
            encoding="utf-8",
        )
        return read_package_view(package_path)

    @app.get("/healthz")
    def healthz() -> Response:
        return Response(status_code=204)

    @app.post("/api/plugins/validate", response_model=list[PluginStatus])
    def validate_plugins(request: PluginValidationRequest) -> list[PluginStatus]:
        manager = PluginManager(
            PluginDiscoveryConfig(
                enabled=request.enabled,
                local_paths=request.local_paths,
                entry_points_enabled=request.entry_points_enabled,
            )
        )
        return manager.discover()

    @app.post("/api/config/load", response_model=ConfigValidationResponse)
    def load_config_endpoint(request: ConfigPathRequest) -> ConfigValidationResponse:
        try:
            config = load_config(request.path)
        except ConfigValidationError as exc:
            return _invalid_config_response(exc.issues)
        return ConfigValidationResponse(
            status="valid",
            config=config.model_dump(mode="json"),
        )

    @app.post("/api/config/validate", response_model=ConfigValidationResponse)
    def validate_config_endpoint(request: ConfigDraftRequest) -> ConfigValidationResponse:
        try:
            config = validate_config(request.config)
        except ConfigValidationError as exc:
            return _invalid_config_response(exc.issues)
        return ConfigValidationResponse(
            status="valid",
            config=config.model_dump(mode="json"),
        )

    @app.post("/api/config/save", response_model=ConfigValidationResponse)
    def save_config_endpoint(request: ConfigSaveRequest) -> ConfigValidationResponse:
        try:
            config = validate_config(request.config)
        except ConfigValidationError as exc:
            return _invalid_config_response(exc.issues)
        _write_config_file(request.path, config)
        return ConfigValidationResponse(
            status="saved",
            config=config.model_dump(mode="json"),
        )

    @app.post("/api/config/run")
    def run_config_endpoint(request: ConfigDraftRequest) -> dict:
        try:
            config = validate_config(request.config)
        except ConfigValidationError as exc:
            return _invalid_config_response(exc.issues).model_dump(mode="json")
        result = run_analysis(config)
        state["package_path"] = result.output_dir.resolve()
        _remember_history(state["history"], result.output_dir.resolve(), "generated")
        return {
            "status": result.status,
            "output_dir": str(result.output_dir),
            "manifest_path": str(result.manifest_path),
            "package": read_package_view(result.output_dir).model_dump(mode="json"),
        }

    @app.get("/api/analysis", response_model=AnalysisView)
    def get_analysis() -> AnalysisView:
        service = _require_analysis_service(state["analysis_path"])
        return service.view()

    @app.get("/api/analysis/coverage")
    def get_analysis_coverage() -> dict:
        service = _require_analysis_service(state["analysis_path"])
        return service.coverage_bounds(service.open())

    @app.post("/api/analysis/create", response_model=AnalysisView)
    def create_analysis_endpoint(request: AnalysisCreateRequest) -> AnalysisView:
        service = AnalysisService(request.path)
        analysis = service.create(request.name)
        state["analysis_path"] = analysis.root_path
        return service.view(analysis)

    @app.post("/api/analysis/open", response_model=AnalysisView)
    def open_analysis_endpoint(request: AnalysisPathRequest) -> AnalysisView:
        service = AnalysisService(request.path)
        analysis = service.open()
        state["analysis_path"] = analysis.root_path
        return service.view(analysis)

    @app.post("/api/analysis/pick-directory", response_model=AnalysisDirectoryPickResponse)
    def pick_analysis_directory_endpoint(
        request: AnalysisDirectoryPickRequest,
    ) -> AnalysisDirectoryPickResponse:
        try:
            selected_path = _pick_analysis_directory(request.initial_path)
        except RuntimeError as exc:
            return AnalysisDirectoryPickResponse(
                status="unavailable",
                message=str(exc),
            )
        if selected_path is None:
            return AnalysisDirectoryPickResponse(status="cancelled")
        return AnalysisDirectoryPickResponse(
            status="selected",
            path=str(selected_path),
        )

    @app.post("/api/analysis/save", response_model=AnalysisView)
    def save_analysis_endpoint() -> AnalysisView:
        service = _require_analysis_service(state["analysis_path"])
        analysis = service.save(service.open())
        return service.view(analysis)

    @app.post("/api/analysis/sessions", response_model=AnalysisView)
    def add_analysis_session(request: AnalysisSessionRequest) -> AnalysisView:
        service = _require_analysis_service(state["analysis_path"])
        try:
            analysis = service.add_session(
                service.open(),
                session=request.session,
                drivers=request.drivers,
                data_cache=request.data_cache,
                name=request.name,
                load=request.load,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return service.view(analysis)

    @app.post("/api/analysis/sessions/{session_id}/load", response_model=AnalysisView)
    def load_analysis_session(session_id: str) -> AnalysisView:
        service = _require_analysis_service(state["analysis_path"])
        analysis = service.load_session(service.open(), session_id)
        return service.view(analysis)

    @app.delete("/api/analysis/sessions/{session_id}", response_model=AnalysisView)
    def remove_analysis_session(
        session_id: str,
        confirm_delete_dependents: bool = False,
    ) -> AnalysisView:
        service = _require_analysis_service(state["analysis_path"])
        try:
            analysis = service.remove_session(
                service.open(),
                session_id,
                confirm_delete_dependents=confirm_delete_dependents,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return service.view(analysis)

    @app.get("/api/analysis/recipes")
    def list_analysis_recipes() -> list[dict]:
        service = _optional_analysis_service(state["analysis_path"])
        if service is None:
            return list_recipe_metadata_payloads()
        return service.view().recipes

    @app.get("/api/analysis/templates")
    def list_analysis_templates() -> list[dict]:
        service = _optional_analysis_service(state["analysis_path"])
        if service is None:
            return list_recipe_metadata_payloads()
        return service.view().recipes

    @app.post("/api/analysis/charts", response_model=AnalysisView)
    def add_analysis_chart(request: AnalysisChartRequest) -> AnalysisView:
        service = _require_analysis_service(state["analysis_path"])
        recipe_id = _request_template_id(request.recipe_id, request.template_id)
        try:
            analysis = service.add_chart(
                service.open(),
                recipe_id=recipe_id,
                target_session_ids=request.target_session_ids,
                name=request.name,
                parameters=request.parameters,
                preset_id=request.preset_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return service.view(analysis)

    @app.put("/api/analysis/charts/{chart_id}", response_model=AnalysisView)
    def update_analysis_chart(
        chart_id: str,
        request: AnalysisChartUpdateRequest,
    ) -> AnalysisView:
        service = _require_analysis_service(state["analysis_path"])
        preset_update = {}
        if "preset_id" in request.model_fields_set:
            preset_update["preset_id"] = request.preset_id
        try:
            analysis = service.update_chart(
                service.open(),
                chart_id,
                name=request.name,
                target_session_ids=request.target_session_ids,
                parameters=request.parameters,
                **preset_update,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return service.view(analysis)

    @app.delete("/api/analysis/charts/{chart_id}", response_model=AnalysisView)
    def remove_analysis_chart(chart_id: str) -> AnalysisView:
        service = _require_analysis_service(state["analysis_path"])
        analysis = service.remove_chart(service.open(), chart_id)
        return service.view(analysis)

    @app.post("/api/analysis/charts/generate", response_model=AnalysisView)
    def generate_analysis_charts(request: ChartGenerationRequest) -> AnalysisView:
        service = _require_analysis_service(state["analysis_path"])
        analysis = service.generate_charts(service.open(), request.chart_ids)
        return service.view(analysis)

    @app.post("/api/analysis/charts/diagnostics", response_model=ParameterDiagnosticsView)
    def resolve_analysis_chart_diagnostics(
        request: AnalysisChartDiagnosticsRequest,
    ) -> ParameterDiagnosticsView:
        service = _require_analysis_service(state["analysis_path"])
        recipe_id = _request_template_id(request.recipe_id, request.template_id)
        return service.resolve_chart_diagnostics(
            service.open(),
            recipe_id=recipe_id,
            target_session_ids=request.target_session_ids,
            parameters=request.parameters,
        )

    @app.post("/api/analysis/track-map", response_model=TrackMapPayload)
    def get_analysis_track_map(request: AnalysisTrackMapRequest) -> TrackMapPayload:
        service = _require_analysis_service(state["analysis_path"])
        recipe_id = _request_template_id(request.recipe_id, request.template_id)
        try:
            return service.track_map(
                service.open(),
                recipe_id=recipe_id,
                target_session_ids=request.target_session_ids,
                parameters=request.parameters,
                max_points=request.max_points,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/analysis/playback", response_model=PlaybackPayload)
    def get_analysis_playback(request: AnalysisPlaybackRequest) -> PlaybackPayload:
        service = _require_analysis_service(state["analysis_path"])
        try:
            return service.playback(
                service.open(),
                session_id=request.session_id,
                mode=request.mode,
                cursor=request.cursor,
                start_lap=request.start_lap,
                end_lap=request.end_lap,
                selected_drivers=request.selected_drivers,
                max_frames=request.max_frames,
                max_markers=request.max_markers,
                max_points=request.max_points,
                maximum_sample_gap_seconds=request.maximum_sample_gap_seconds,
                maximum_timing_sample_age_seconds=request.maximum_timing_sample_age_seconds,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/analysis/review/refresh", response_model=AnalysisView)
    def refresh_analysis_review() -> AnalysisView:
        service = _require_analysis_service(state["analysis_path"])
        analysis = service.refresh_observations(service.open())
        state["package_path"] = Path(analysis.exported_package_path).resolve() if analysis.exported_package_path else None
        return service.view(analysis)

    @app.post("/api/analysis/export", response_model=AnalysisView)
    def export_analysis() -> AnalysisView:
        service = _require_analysis_service(state["analysis_path"])
        analysis = service.export_package(service.open())
        state["package_path"] = Path(analysis.exported_package_path).resolve() if analysis.exported_package_path else None
        if state["package_path"] is not None:
            _remember_history(state["history"], state["package_path"], "exported")
        return service.view(analysis)

    @app.post("/api/analysis/presets", response_model=AnalysisView)
    def save_analysis_preset(request: PresetSaveRequest) -> AnalysisView:
        service = _require_analysis_service(state["analysis_path"])
        recipe_id = _request_template_id(request.recipe_id, request.template_id)
        try:
            analysis, _preset = service.save_preset(
                service.open(),
                recipe_id=recipe_id,
                display_name=request.display_name,
                parameters=request.parameters,
                scope=request.scope,
                notes=request.notes,
                replace_existing=request.replace_existing,
            )
        except ValueError as exc:
            status_code = 409 if "already exists" in str(exc) else 400
            raise HTTPException(status_code=status_code, detail=str(exc)) from exc
        return service.view(analysis)

    @app.put("/api/analysis/presets/{preset_id}", response_model=AnalysisView)
    def update_analysis_preset(
        preset_id: str,
        request: PresetUpdateRequest,
    ) -> AnalysisView:
        service = _require_analysis_service(state["analysis_path"])
        try:
            analysis, _preset = service.update_preset(
                service.open(),
                preset_id,
                display_name=request.display_name,
                parameters=request.parameters,
                replace_existing=request.replace_existing,
            )
        except ValueError as exc:
            status_code = 409 if "already exists" in str(exc) else 400
            raise HTTPException(status_code=status_code, detail=str(exc)) from exc
        return service.view(analysis)

    @app.delete("/api/analysis/presets/{preset_id}", response_model=AnalysisView)
    def delete_analysis_preset(preset_id: str) -> AnalysisView:
        service = _require_analysis_service(state["analysis_path"])
        try:
            analysis = service.delete_preset(service.open(), preset_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return service.view(analysis)

    @app.get("/api/analysis/assets/{asset_path:path}")
    def get_analysis_asset(asset_path: str) -> FileResponse:
        service = _require_analysis_service(state["analysis_path"])
        path = _resolve_local_asset(service.root, asset_path)
        if not path.exists() or not path.is_file():
            raise HTTPException(status_code=404, detail="Analysis asset not found.")
        return FileResponse(path)

    @app.get("/api/history")
    def get_history() -> list[dict[str, str]]:
        return list(state["history"])

    @app.delete("/api/history")
    def clear_history() -> dict[str, str]:
        state["history"].clear()
        return {"status": "cleared"}

    return app


def _require_package_path(package_path: Path | None) -> Path:
    if package_path is None:
        raise HTTPException(status_code=404, detail="No package is currently open.")
    return package_path


def _require_analysis_service(analysis_path: Path | None) -> AnalysisService:
    service = _optional_analysis_service(analysis_path)
    if service is None:
        raise HTTPException(status_code=404, detail="No analysis is currently open.")
    return service


def _optional_analysis_service(analysis_path: Path | None) -> AnalysisService | None:
    if analysis_path is None:
        return None
    return AnalysisService(analysis_path)


def _pick_analysis_directory(initial_path: Path | None = None) -> Path | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:  # pragma: no cover - depends on local Python build.
        raise RuntimeError("Native folder picker is unavailable.") from exc

    try:
        root = tk.Tk()
        root.withdraw()
    except Exception as exc:
        raise RuntimeError("Native folder picker is unavailable.") from exc

    try:
        root.attributes("-topmost", True)
    except tk.TclError:
        pass

    options = {
        "title": "Open Analysis",
        "mustexist": True,
        "parent": root,
    }
    initial_directory = _existing_picker_directory(initial_path)
    if initial_directory is not None:
        options["initialdir"] = str(initial_directory)

    try:
        selected = filedialog.askdirectory(**options)
    except Exception as exc:
        raise RuntimeError("Native folder picker failed.") from exc
    finally:
        root.destroy()

    return Path(selected).resolve() if selected else None


def _existing_picker_directory(path: Path | None) -> Path | None:
    if path is None:
        return None
    candidate = path.expanduser()
    if candidate.is_file():
        return candidate.parent.resolve()
    if candidate.is_dir():
        return candidate.resolve()
    for parent in candidate.parents:
        if parent.is_dir():
            return parent.resolve()
    return None


def _request_template_id(recipe_id: str | None, template_id: str | None) -> str:
    value = template_id or recipe_id
    if not value:
        raise HTTPException(status_code=422, detail="Chart template is required.")
    return value


def _resolve_local_asset(root: Path, relative_path: str) -> Path:
    path = Path(relative_path)
    if path.is_absolute():
        raise HTTPException(status_code=400, detail="Asset path must be relative.")
    resolved = (root / path).resolve()
    if resolved != root and root not in resolved.parents:
        raise HTTPException(status_code=400, detail="Asset path escapes analysis root.")
    return resolved


def _read_observations(path: Path) -> list[Observation]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Observation.model_validate(item) for item in raw]


def _write_observations(path: Path, observations: list[Observation]) -> None:
    path.write_text(
        json.dumps(
            [observation.model_dump(mode="json") for observation in observations],
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _write_review(path: Path, observations: list[Observation]) -> None:
    entries = [
        ObservationReviewEntry(
            observation_id=observation.observation_id,
            review_status=observation.review_status,
            edited_text=observation.edited_text,
        ).model_dump(mode="json")
        for observation in observations
    ]
    path.write_text(json.dumps(entries, indent=2, sort_keys=True), encoding="utf-8")


def _invalid_config_response(issues: list[ValidationIssue]) -> ConfigValidationResponse:
    return ConfigValidationResponse(
        status="invalid",
        issues=[issue.to_dict() for issue in issues],
    )


def _write_config_file(path: Path, config: ProjectConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".toml":
        path.write_text(_config_to_toml(config), encoding="utf-8")
        return
    path.write_text(
        json.dumps(config.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _config_to_toml(config: ProjectConfig) -> str:
    raw = config.model_dump(mode="json")
    lines = [
        f"schema_version = {raw['schema_version']}",
        f"project_id = {json.dumps(raw['project_id'])}",
        f"output_dir = {json.dumps(raw['output_dir'])}",
        "",
        "[session]",
        f"season = {raw['session']['season']}",
        f"event = {json.dumps(raw['session']['event'])}",
        f"session = {json.dumps(raw['session']['session'])}",
        "",
        "[driver_selection]",
        f"drivers = {json.dumps(raw['driver_selection']['drivers'])}",
        "",
        "[data_cache]",
        f"directory = {json.dumps(raw['data_cache']['directory'])}",
        f"mode = {json.dumps(raw['data_cache']['mode'])}",
    ]
    if raw["data_cache"].get("fixture_path"):
        lines.append(f"fixture_path = {json.dumps(raw['data_cache']['fixture_path'])}")
    lines.extend(
        [
            "",
            "[theme]",
            f"name = {json.dumps(raw['theme']['name'])}",
            f"figure_width = {raw['theme']['figure_width']}",
            f"figure_height = {raw['theme']['figure_height']}",
            f"dpi = {raw['theme']['dpi']}",
            f"background_color = {json.dumps(raw['theme']['background_color'])}",
            f"foreground_color = {json.dumps(raw['theme']['foreground_color'])}",
            f"grid = {str(raw['theme']['grid']).lower()}",
            "",
            "[exports]",
            f"formats = {json.dumps(raw['exports']['formats'])}",
            "",
            "[plugins]",
            f"enabled = {str(raw['plugins']['enabled']).lower()}",
            f"local_paths = {json.dumps(raw['plugins']['local_paths'])}",
            f"entry_points_enabled = {str(raw['plugins']['entry_points_enabled']).lower()}",
            "",
        ]
    )
    for recipe in raw["recipes"]:
        lines.append("[[recipes]]")
        lines.append(f"recipe_id = {json.dumps(recipe['recipe_id'])}")
        lines.append(f"enabled = {str(recipe['enabled']).lower()}")
        if recipe.get("title") is not None:
            lines.append(f"title = {json.dumps(recipe['title'])}")
        lines.append("")
    return "\n".join(lines)


def _remember_history(history: list[dict[str, str]], path: Path, action: str) -> None:
    value = str(path)
    history[:] = [item for item in history if item["package_path"] != value]
    history.insert(0, {"package_path": value, "action": action})
    del history[20:]

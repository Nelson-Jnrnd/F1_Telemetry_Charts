"""FastAPI application for local package preview."""

from __future__ import annotations

import json
from pathlib import Path

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
from f1_telemetry_charts.config.loader import load_config
from f1_telemetry_charts.config.models import ProjectConfig
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


def create_app(initial_package: Path | None = None) -> FastAPI:
    app = FastAPI(title="F1 Telemetry Charts Local UI")
    state = {
        "package_path": initial_package.resolve() if initial_package else None,
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

"""Versioned LLM-facing contract for chart generation and artifact inspection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from f1_telemetry_charts.analysis.manifest import ArtifactManifest
from f1_telemetry_charts.analysis.orchestrator import run_analysis
from f1_telemetry_charts.analysis.workspace import AnalysisService
from f1_telemetry_charts.config.loader import load_config
from f1_telemetry_charts.config.validation import (
    ConfigValidationError,
    ValidationIssue,
    validate_config,
)


CONTRACT_VERSION = "1.0"


def generate_charts(request_json: dict[str, Any]) -> dict[str, Any]:
    compatibility_error = _validate_contract_version(request_json)
    if compatibility_error is not None:
        return compatibility_error

    try:
        config = _load_request_config(request_json)
        result = run_analysis(config)
    except ConfigValidationError as exc:
        return {
            "contract_version": CONTRACT_VERSION,
            "status": "invalid_request",
            "error": {
                "code": "configuration_invalid",
                "message": "Configuration validation failed.",
                "issues": [issue.to_dict() for issue in exc.issues],
            },
        }
    except Exception as exc:
        return {
            "contract_version": CONTRACT_VERSION,
            "status": "failed",
            "error": {"code": "generation_failed", "message": str(exc)},
        }

    return {
        "contract_version": CONTRACT_VERSION,
        "status": result.status,
        "run_id": result.manifest.run_id,
        "manifest_path": result.manifest_path.name,
        "observations_path": result.manifest.observations_path,
        "review_path": result.manifest.review_path,
        "markdown_path": result.manifest.markdown_path,
        "artifacts": [
            {
                "artifact_id": artifact.artifact_id,
                "recipe_id": artifact.recipe_id,
                "image_path": artifact.image_path,
                "metadata_path": artifact.metadata_path,
            }
            for artifact in result.manifest.artifacts
        ],
        "warnings": result.manifest.warnings,
        "errors": result.manifest.errors,
    }


def describe_artifact(request_json: dict[str, Any]) -> dict[str, Any]:
    compatibility_error = _validate_contract_version(request_json)
    if compatibility_error is not None:
        return compatibility_error

    manifest_path = request_json.get("manifest_path")
    artifact_id = request_json.get("artifact_id")
    if not isinstance(manifest_path, str) or not isinstance(artifact_id, str):
        return {
            "contract_version": CONTRACT_VERSION,
            "status": "invalid_request",
            "error": {
                "code": "missing_required_field",
                "message": "manifest_path and artifact_id are required strings.",
            },
        }

    path = Path(manifest_path)
    try:
        manifest = ArtifactManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "contract_version": CONTRACT_VERSION,
            "status": "failed",
            "error": {"code": "manifest_read_failed", "message": str(exc)},
        }

    artifact = next(
        (entry for entry in manifest.artifacts if entry.artifact_id == artifact_id),
        None,
    )
    if artifact is None:
        return {
            "contract_version": CONTRACT_VERSION,
            "status": "not_found",
            "error": {
                "code": "artifact_not_found",
                "message": f"Artifact not found: {artifact_id}",
            },
        }

    metadata_path = path.parent / artifact.metadata_path
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "contract_version": CONTRACT_VERSION,
            "status": "failed",
            "error": {"code": "metadata_read_failed", "message": str(exc)},
        }

    return {
        "contract_version": CONTRACT_VERSION,
        "status": "succeeded",
        "artifact": {
            "artifact_id": artifact.artifact_id,
            "recipe_id": artifact.recipe_id,
            "image_path": artifact.image_path,
            "metadata_path": artifact.metadata_path,
            "metadata": metadata,
        },
    }


def inspect_analysis(request_json: dict[str, Any]) -> dict[str, Any]:
    compatibility_error = _validate_contract_version(request_json)
    if compatibility_error is not None:
        return compatibility_error

    analysis_path = request_json.get("analysis_path")
    if not isinstance(analysis_path, str):
        return _invalid_request("analysis_path is required.")
    try:
        service = AnalysisService(analysis_path)
        analysis = service.open()
        view = service.view(analysis)
        coverage = service.coverage_bounds(analysis)
        track_map_summaries = _track_map_summaries(service, analysis)
        playback_summaries = _playback_summaries(service, analysis)
        strategy_summaries = _strategy_summaries(service, analysis)
        report_summary = _report_summary(analysis)
    except Exception as exc:
        return {
            "contract_version": CONTRACT_VERSION,
            "status": "failed",
            "error": {"code": "analysis_read_failed", "message": str(exc)},
        }
    return {
        "contract_version": CONTRACT_VERSION,
        "status": "succeeded",
        "analysis": view.analysis.model_dump(
            mode="json", exclude={"report_content", "report_reviews"}
        ),
        "chart_instances": [
            chart.model_dump(mode="json") for chart in view.analysis.charts
        ],
        "templates": [template for template in view.recipes],
        "recipes": [recipe for recipe in view.recipes],
        "recipe_schemas": [
            schema.model_dump(mode="json") for schema in view.recipe_schemas
        ],
        "template_schemas": [
            schema.model_dump(mode="json") for schema in view.recipe_schemas
        ],
        "analysis_presets": [
            preset.model_dump(mode="json") for preset in view.analysis.presets
        ],
        "global_presets": [
            preset.model_dump(mode="json") for preset in view.global_presets
        ],
        "coverage_bounds": coverage,
        "track_map_summaries": track_map_summaries,
        "playback_summaries": playback_summaries,
        "strategy_summaries": strategy_summaries,
        "report_summary": report_summary,
    }


def update_analysis_chart_parameters(request_json: dict[str, Any]) -> dict[str, Any]:
    compatibility_error = _validate_contract_version(request_json)
    if compatibility_error is not None:
        return compatibility_error

    analysis_path = request_json.get("analysis_path")
    chart_instance_id = request_json.get("chart_instance_id")
    parameters = request_json.get("parameters")
    if not isinstance(analysis_path, str):
        return _invalid_request("analysis_path is required.")
    if not isinstance(chart_instance_id, str):
        return _invalid_request("chart_instance_id is required.")
    if not isinstance(parameters, dict):
        return _invalid_request("parameters is required.")

    try:
        service = AnalysisService(analysis_path)
        analysis = service.update_chart(
            service.open(),
            chart_instance_id,
            parameters=parameters,
        )
        view = service.view(analysis)
    except Exception as exc:
        return {
            "contract_version": CONTRACT_VERSION,
            "status": "failed",
            "error": {"code": "analysis_update_failed", "message": str(exc)},
        }
    return {
        "contract_version": CONTRACT_VERSION,
        "status": "succeeded",
        "analysis": view.analysis.model_dump(mode="json"),
        "chart_instances": [
            chart.model_dump(mode="json") for chart in view.analysis.charts
        ],
    }


def _validate_contract_version(request_json: dict[str, Any]) -> dict[str, Any] | None:
    version = request_json.get("contract_version", CONTRACT_VERSION)
    if version == CONTRACT_VERSION:
        return None
    return {
        "contract_version": CONTRACT_VERSION,
        "status": "incompatible_contract",
        "error": {
            "code": "unsupported_contract_version",
            "message": (
                f"Unsupported contract_version {version!r}; "
                f"supported version is {CONTRACT_VERSION!r}."
            ),
        },
    }


def _invalid_request(message: str) -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "status": "invalid_request",
        "error": {"code": "missing_required_field", "message": message},
    }


def _track_map_summaries(service: AnalysisService, analysis: Any) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for chart in analysis.charts:
        if chart.recipe_id != "telemetry_trace":
            continue
        try:
            payload = service.track_map(
                analysis,
                recipe_id=chart.recipe_id,
                target_session_ids=chart.target_session_ids,
                parameters=chart.parameters,
                max_points=2,
            ).model_dump(mode="json")
        except Exception as exc:
            payload = {
                "status": "invalid",
                "recipe_id": chart.recipe_id,
                "session_id": chart.target_session_ids[0]
                if chart.target_session_ids
                else None,
                "diagnostics": [{"field": "track_map", "message": str(exc)}],
            }
        payload.pop("points", None)
        summaries.append(
            {
                "chart_instance_id": chart.chart_instance_id,
                **payload,
            }
        )
    return summaries


def _playback_summaries(service: AnalysisService, analysis: Any) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for session in analysis.sessions:
        try:
            payload = service.playback(
                analysis,
                session_id=session.session_id,
                mode="lap",
                max_frames=1,
                max_markers=5,
                max_points=2,
            ).model_dump(mode="json")
        except Exception as exc:
            payload = {
                "status": "invalid",
                "session_id": session.session_id,
                "diagnostics": [{"field": "playback", "message": str(exc)}],
            }
        payload.pop("points", None)
        payload.pop("frames", None)
        summaries.append(payload)
    return summaries


def _strategy_summaries(service: AnalysisService, analysis: Any) -> list[dict[str, Any]]:
    """Return bounded data-only strategy headlines from generated artifacts."""

    summaries: list[dict[str, Any]] = []
    strategy_ids = {
        "tyre_strategy",
        "stint_pace",
        "pace_evolution",
        "compound_comparison",
        "race_time_delta_evolution",
        "pit_cycle_comparison",
        "driver_battle",
        "practice_run_overview",
        "practice_long_run_pace_summary",
        "practice_observed_pace_evolution",
    }
    for chart in analysis.charts:
        if chart.recipe_id not in strategy_ids:
            continue
        summary: dict[str, Any] = {
            "chart_instance_id": chart.chart_instance_id,
            "recipe_id": chart.recipe_id,
            "generation_state": chart.generation_state,
        }
        if chart.metadata_path and chart.generation_state == "generated":
            try:
                path = (service.root / chart.metadata_path).resolve()
                path.relative_to(service.root.resolve())
                metadata = json.loads(path.read_text(encoding="utf-8"))
                results = metadata.get("analytical_results", {})
                headline_keys = {
                    "result_kind",
                    "value_category",
                    "value_categories",
                    "status",
                    "quality",
                    "scalar_difference_seconds",
                    "measured_gap_change_seconds",
                    "overall_change_seconds",
                    "coverage_percentage",
                    "paired_sample_count",
                    "pit_lane_duration_seconds",
                    "panel_contract",
                }
                summary.update(
                    {
                        "strategy_analysis_schema_version": metadata.get(
                            "strategy_analysis_schema_version"
                        ),
                        "result_kind": metadata.get("result_kind"),
                        "analytical_basis": metadata.get("analytical_basis", {}),
                        "headline_results": {
                            key: results[key]
                            for key in sorted(results)
                            if key in headline_keys
                        }
                        if isinstance(results, dict)
                        else {},
                        "warnings": list(metadata.get("strategy_warnings", []))[:10],
                        "limitations": list(metadata.get("strategy_limitations", []))[:10],
                    }
                )
            except Exception as exc:
                summary["diagnostics"] = [
                    {"field": "strategy_metadata", "message": str(exc)}
                ]
        summaries.append(summary)
    return summaries


def _report_summary(analysis: Any, *, maximum_items: int = 100) -> dict[str, Any] | None:
    """Return bounded, read-only report facts without raw analytical payloads."""

    content = analysis.report_content
    if content is None:
        return None
    claims = [*content.findings, *content.conclusions][:maximum_items]
    assessments = content.assessments[:maximum_items]
    results = content.results[:maximum_items]
    return {
        "schema_version": content.schema_version,
        "target_session_id": content.target_session_id,
        "evidence_fingerprint": content.evidence_fingerprint,
        "freshness": analysis.report_freshness.model_dump(mode="json"),
        "publication": {
            "readiness": content.publication_readiness.model_dump(mode="json"),
            "policy": (
                {
                    "policy_id": content.publication_plan.policy_id,
                    "policy_version": content.publication_plan.policy_version,
                    "section_order": content.publication_plan.section_order,
                    "selected_claim_count": len(
                        [item for item in content.publication_plan.claims if item.included]
                    ),
                    "selected_chart_count": len(
                        [item for item in content.publication_plan.charts if item.included]
                    ),
                }
                if content.publication_plan is not None
                else None
            ),
            "editorial_fields_present": {
                "headline": bool(content.publication_editorial.headline.value.strip()),
                "standfirst": bool(content.publication_editorial.standfirst.value.strip()),
                "conclusion": bool(content.publication_editorial.conclusion.value.strip()),
            },
        },
        "truncated": (
            len(content.findings) + len(content.conclusions) > maximum_items
            or len(content.assessments) > maximum_items
            or len(content.results) > maximum_items
        ),
        "results": [
            {
                "result_id": item.result_id,
                "result_type": item.result_type,
                "analytical_status": item.analytical_status,
                "measurement_category": item.measurement_category,
                "coverage": item.coverage,
                "quality": item.quality,
                "limitations": item.limitations,
                "result_fingerprint": item.result_fingerprint,
            }
            for item in results
        ],
        "assessments": [
            {
                "assessment_id": item.assessment_id,
                "result_type": item.result_type,
                "report_disposition": item.report_disposition,
                "reasons": item.reasons,
                "finding_ids": item.finding_ids,
            }
            for item in assessments
        ],
        "claims": [
            {
                "finding_id": item.finding_id,
                "finding_kind": item.finding_kind,
                "finding_type": item.finding_type,
                "text": item.text,
                "confidence": item.confidence,
                "comparison_basis": item.comparison_basis,
                "limitations": item.limitations,
                "evidence_fingerprint": item.evidence_fingerprint,
            }
            for item in claims
        ],
    }


def _load_request_config(request_json: dict[str, Any]):
    config_path = request_json.get("config_path")
    config_payload = request_json.get("config")
    if isinstance(config_path, str):
        return load_config(config_path)
    if isinstance(config_payload, dict):
        return validate_config(config_payload)
    raise ConfigValidationError(
        [ValidationIssue("request", "Either config_path or config is required.")]
    )

"""Versioned LLM-facing contract for chart generation and artifact inspection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from f1_telemetry_charts.analysis.manifest import ArtifactManifest
from f1_telemetry_charts.analysis.orchestrator import run_analysis
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

"""Read generated packages for local preview."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from f1_telemetry_charts.analysis.manifest import ArtifactManifest


IntegritySeverity = Literal["error", "warning", "info"]


class PackagePreviewError(Exception):
    """Raised when a directory cannot be opened as a package."""


class IntegrityFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severity: IntegritySeverity
    code: str
    message: str
    path: str | None = None


class PackageHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["healthy", "warning", "unhealthy"]
    findings: list[IntegrityFinding]


class PackageView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_path: str
    manifest: ArtifactManifest | None
    health: PackageHealth
    observations: list[dict[str, Any]]
    review: list[dict[str, Any]]
    draft_markdown: str | None


def read_package_view(package_path: str | Path) -> PackageView:
    root = Path(package_path).expanduser().resolve()
    if not root.exists():
        raise PackagePreviewError(f"Package directory does not exist: {root}")
    if not root.is_dir():
        raise PackagePreviewError(f"Package path is not a directory: {root}")

    findings: list[IntegrityFinding] = []
    manifest = _read_manifest(root, findings)
    observations: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    draft_markdown: str | None = None

    if manifest is not None:
        _check_artifacts(root, manifest, findings)
        observations = _read_optional_json_list(
            root,
            manifest.observations_path,
            "observations",
            findings,
        )
        review = _read_optional_json_list(root, manifest.review_path, "review", findings)
        draft_markdown = _read_optional_text(root, manifest.markdown_path, "draft", findings)
        _check_review_observation_links(observations, review, findings)

    return PackageView(
        package_path=str(root),
        manifest=manifest,
        health=PackageHealth(status=_health_status(findings), findings=findings),
        observations=observations,
        review=review,
        draft_markdown=draft_markdown,
    )


def resolve_package_asset(package_path: str | Path, relative_path: str) -> Path:
    root = Path(package_path).expanduser().resolve()
    return _resolve_package_relative(root, relative_path)


def _read_manifest(root: Path, findings: list[IntegrityFinding]) -> ArtifactManifest | None:
    path = root / "manifest.json"
    if not path.exists():
        findings.append(
            IntegrityFinding(
                severity="error",
                code="manifest_missing",
                message="Package manifest.json is missing.",
                path="manifest.json",
            )
        )
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return ArtifactManifest.model_validate(raw)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        findings.append(
            IntegrityFinding(
                severity="error",
                code="manifest_invalid",
                message=f"Package manifest.json is invalid: {exc}",
                path="manifest.json",
            )
        )
        return None


def _check_artifacts(
    root: Path,
    manifest: ArtifactManifest,
    findings: list[IntegrityFinding],
) -> None:
    for artifact in manifest.artifacts:
        for field_name, relative_path in (
            ("image_path", artifact.image_path),
            ("metadata_path", artifact.metadata_path),
        ):
            try:
                path = _resolve_package_relative(root, relative_path)
            except PackagePreviewError as exc:
                findings.append(
                    IntegrityFinding(
                        severity="error",
                        code="artifact_path_invalid",
                        message=str(exc),
                        path=relative_path,
                    )
                )
                continue

            if not path.exists():
                findings.append(
                    IntegrityFinding(
                        severity="error",
                        code=f"{field_name}_missing",
                        message=f"Referenced artifact file is missing: {relative_path}",
                        path=relative_path,
                    )
                )


def _read_optional_json_list(
    root: Path,
    relative_path: str | None,
    label: str,
    findings: list[IntegrityFinding],
) -> list[dict[str, Any]]:
    if relative_path is None:
        findings.append(
            IntegrityFinding(
                severity="warning",
                code=f"{label}_missing_reference",
                message=f"Manifest does not reference {label} data.",
            )
        )
        return []
    try:
        path = _resolve_package_relative(root, relative_path)
    except PackagePreviewError as exc:
        findings.append(
            IntegrityFinding(
                severity="error",
                code=f"{label}_path_invalid",
                message=str(exc),
                path=relative_path,
            )
        )
        return []
    if not path.exists():
        findings.append(
            IntegrityFinding(
                severity="warning",
                code=f"{label}_missing",
                message=f"Referenced {label} file is missing: {relative_path}",
                path=relative_path,
            )
        )
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        findings.append(
            IntegrityFinding(
                severity="error",
                code=f"{label}_invalid",
                message=f"Referenced {label} file is invalid: {exc}",
                path=relative_path,
            )
        )
        return []
    if not isinstance(raw, list):
        findings.append(
            IntegrityFinding(
                severity="error",
                code=f"{label}_invalid_shape",
                message=f"Referenced {label} file must contain a JSON list.",
                path=relative_path,
            )
        )
        return []
    return [item for item in raw if isinstance(item, dict)]


def _read_optional_text(
    root: Path,
    relative_path: str | None,
    label: str,
    findings: list[IntegrityFinding],
) -> str | None:
    if relative_path is None:
        findings.append(
            IntegrityFinding(
                severity="warning",
                code=f"{label}_missing_reference",
                message=f"Manifest does not reference {label} text.",
            )
        )
        return None
    try:
        path = _resolve_package_relative(root, relative_path)
    except PackagePreviewError as exc:
        findings.append(
            IntegrityFinding(
                severity="error",
                code=f"{label}_path_invalid",
                message=str(exc),
                path=relative_path,
            )
        )
        return None
    if not path.exists():
        findings.append(
            IntegrityFinding(
                severity="warning",
                code=f"{label}_missing",
                message=f"Referenced {label} file is missing: {relative_path}",
                path=relative_path,
            )
        )
        return None
    return path.read_text(encoding="utf-8")


def _check_review_observation_links(
    observations: list[dict[str, Any]],
    review: list[dict[str, Any]],
    findings: list[IntegrityFinding],
) -> None:
    observation_ids = {
        item.get("observation_id") for item in observations if item.get("observation_id")
    }
    for item in review:
        review_id = item.get("observation_id")
        if review_id and review_id not in observation_ids:
            findings.append(
                IntegrityFinding(
                    severity="warning",
                    code="review_unknown_observation",
                    message=f"Review references an unknown observation: {review_id}",
                    path="review.json",
                )
            )


def _resolve_package_relative(root: Path, relative_path: str) -> Path:
    path = Path(relative_path)
    if path.is_absolute():
        raise PackagePreviewError(f"Package path must be relative: {relative_path}")
    resolved = (root / path).resolve()
    if resolved != root and root not in resolved.parents:
        raise PackagePreviewError(f"Package path escapes package root: {relative_path}")
    return resolved


def _health_status(findings: list[IntegrityFinding]) -> Literal["healthy", "warning", "unhealthy"]:
    if any(finding.severity == "error" for finding in findings):
        return "unhealthy"
    if any(finding.severity == "warning" for finding in findings):
        return "warning"
    return "healthy"

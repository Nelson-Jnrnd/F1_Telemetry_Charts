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
    results: list[dict[str, Any]]
    assessments: list[dict[str, Any]]
    findings: list[dict[str, Any]]
    report: dict[str, Any] | None
    report_review: list[dict[str, Any]]
    publication_plan: dict[str, Any] | None = None
    publication_readiness: dict[str, Any] | None = None
    article: dict[str, Any] | None = None
    evidence: dict[str, Any] | None = None
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
    results: list[dict[str, Any]] = []
    assessments: list[dict[str, Any]] = []
    report_findings: list[dict[str, Any]] = []
    report: dict[str, Any] | None = None
    report_review: list[dict[str, Any]] = []
    publication_plan: dict[str, Any] | None = None
    article: dict[str, Any] | None = None
    evidence: dict[str, Any] | None = None
    draft_markdown: str | None = None

    if manifest is not None:
        _check_artifacts(root, manifest, findings)
        draft_markdown = _read_optional_text(root, manifest.markdown_path, "draft", findings)
        if manifest.article_json_path is not None:
            article = _read_optional_json_object(
                root, manifest.article_json_path, "article", findings
            )
            evidence = _read_optional_json_object(
                root, manifest.evidence_sidecar_path, "evidence", findings
            )
        elif manifest.report_schema_version is not None:
            results = _read_optional_json_list(
                root, manifest.results_path, "results", findings
            )
            assessments = _read_optional_json_list(
                root, manifest.assessments_path, "assessments", findings
            )
            report_findings = _read_optional_json_list(
                root, manifest.findings_path, "findings", findings
            )
            report = _read_optional_json_object(
                root, manifest.report_path, "report", findings
            )
            report_review = _read_optional_json_list(
                root, manifest.report_review_path, "report_review", findings
            )
            if manifest.publication_plan_path:
                publication_plan = _read_optional_json_object(
                    root, manifest.publication_plan_path, "publication_plan", findings
                )
            _check_report_links(
                results, assessments, report_findings, report, report_review, findings
            )
        else:
            observations = _read_optional_json_list(
                root,
                manifest.observations_path,
                "observations",
                findings,
            )
            review = _read_optional_json_list(
                root, manifest.review_path, "review", findings
            )
            _check_review_observation_links(observations, review, findings)

    return PackageView(
        package_path=str(root),
        manifest=manifest,
        health=PackageHealth(status=_health_status(findings), findings=findings),
        observations=observations,
        review=review,
        results=results,
        assessments=assessments,
        findings=report_findings,
        report=report,
        report_review=report_review,
        publication_plan=publication_plan,
        publication_readiness=manifest.publication_readiness if manifest else None,
        article=article,
        evidence=evidence,
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
        manifest = ArtifactManifest.model_validate(raw)
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
    findings.append(
        IntegrityFinding(
            severity="info",
            code="manifest_present",
            message="Package manifest.json is present and valid.",
            path="manifest.json",
        )
    )
    return manifest


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
                        severity="warning",
                        code=f"{field_name}_missing",
                        message=f"Referenced artifact file is missing: {relative_path}",
                        path=relative_path,
                    )
                )
                continue

            if field_name == "metadata_path":
                try:
                    json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    findings.append(
                        IntegrityFinding(
                            severity="error",
                            code="metadata_path_invalid",
                            message=f"Referenced artifact metadata is invalid: {exc}",
                            path=relative_path,
                        )
                    )
                    continue

            findings.append(
                IntegrityFinding(
                    severity="info",
                    code=f"{field_name}_present",
                    message=f"Referenced artifact file is present: {relative_path}",
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
    findings.append(
        IntegrityFinding(
            severity="info",
            code=f"{label}_present",
            message=f"Referenced {label} file is present and valid: {relative_path}",
            path=relative_path,
        )
    )
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
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        findings.append(
            IntegrityFinding(
                severity="error",
                code=f"{label}_invalid",
                message=f"Referenced {label} file cannot be read: {exc}",
                path=relative_path,
            )
        )
        return None
    findings.append(
        IntegrityFinding(
            severity="info",
            code=f"{label}_present",
            message=f"Referenced {label} file is present: {relative_path}",
            path=relative_path,
        )
    )
    return text


def _read_optional_json_object(
    root: Path,
    relative_path: str | None,
    label: str,
    findings: list[IntegrityFinding],
) -> dict[str, Any] | None:
    if relative_path is None:
        findings.append(
            IntegrityFinding(
                severity="warning",
                code=f"{label}_missing_reference",
                message=f"Manifest does not reference {label} data.",
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
        return None
    if not isinstance(raw, dict):
        findings.append(
            IntegrityFinding(
                severity="error",
                code=f"{label}_invalid_shape",
                message=f"Referenced {label} file must contain a JSON object.",
                path=relative_path,
            )
        )
        return None
    findings.append(
        IntegrityFinding(
            severity="info",
            code=f"{label}_present",
            message=f"Referenced {label} file is present and valid: {relative_path}",
            path=relative_path,
        )
    )
    return raw


def _check_report_links(
    results: list[dict[str, Any]],
    assessments: list[dict[str, Any]],
    report_findings: list[dict[str, Any]],
    report: dict[str, Any] | None,
    report_review: list[dict[str, Any]],
    findings: list[IntegrityFinding],
) -> None:
    result_fingerprints = {
        item.get("result_fingerprint") for item in results if item.get("result_fingerprint")
    }
    finding_ids = {
        item.get("finding_id") for item in report_findings if item.get("finding_id")
    }
    for assessment in assessments:
        if assessment.get("result_fingerprint") not in result_fingerprints:
            findings.append(
                IntegrityFinding(
                    severity="error",
                    code="assessment_unknown_result",
                    message="A report assessment references an unknown analytical result.",
                    path="assessments.json",
                )
            )
    for review in report_review:
        if review.get("item_id") not in finding_ids:
            findings.append(
                IntegrityFinding(
                    severity="warning",
                    code="report_review_unknown_finding",
                    message="A report review entry references an unknown finding.",
                    path="report-review.json",
                )
            )
    if report is not None:
        for section in report.get("sections") or []:
            for item in section.get("items") or []:
                if item.get("item_type") == "claim" and item.get("reference_id") not in finding_ids:
                    findings.append(
                        IntegrityFinding(
                            severity="error",
                            code="report_unknown_finding",
                            message="The report plan references an unknown finding.",
                            path="report.json",
                        )
                    )


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

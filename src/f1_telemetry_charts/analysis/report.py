"""Report package export and observation review helpers."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from f1_telemetry_charts.analysis.manifest import ArtifactManifest
from f1_telemetry_charts.analysis.findings import (
    REPORT_CONTENT_SCHEMA_VERSION,
    ReportContent,
    ReportFinding,
    ReportReviewEntry,
)
from f1_telemetry_charts.analysis.observations import (
    Observation,
    ObservationReviewEntry,
    ReviewStatus,
)


class ReportPackagePaths(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observations_path: Path
    review_path: Path
    markdown_path: Path


class StructuredReportPackagePaths(BaseModel):
    model_config = ConfigDict(extra="forbid")

    results_path: Path
    assessments_path: Path
    findings_path: Path
    report_path: Path
    review_path: Path
    markdown_path: Path
    draft_fingerprint: str


def write_structured_report_package(
    output_dir: Path,
    manifest: ArtifactManifest,
    content: ReportContent,
    reviews: list[ReportReviewEntry],
) -> StructuredReportPackagePaths:
    """Write the versioned report layer alongside legacy package files."""

    output_dir.mkdir(parents=True, exist_ok=True)
    for legacy_name in ("observations.json", "review.json"):
        legacy_path = output_dir / legacy_name
        if legacy_path.exists():
            legacy_path.unlink()
    paths = {
        "results": output_dir / "results.json",
        "assessments": output_dir / "assessments.json",
        "findings": output_dir / "findings.json",
        "report": output_dir / "report.json",
        "review": output_dir / "report-review.json",
        "markdown": output_dir / "draft.md",
    }
    _write_model_list(paths["results"], content.results)
    _write_model_list(paths["assessments"], content.assessments)
    _write_model_list(paths["findings"], [*content.findings, *content.conclusions])
    paths["report"].write_text(content.plan.model_dump_json(indent=2), encoding="utf-8")
    _write_model_list(paths["review"], reviews)
    markdown = render_structured_markdown(manifest, content, reviews)
    paths["markdown"].write_text(markdown, encoding="utf-8")
    from f1_telemetry_charts.analysis.findings import canonical_fingerprint

    return StructuredReportPackagePaths(
        results_path=paths["results"],
        assessments_path=paths["assessments"],
        findings_path=paths["findings"],
        report_path=paths["report"],
        review_path=paths["review"],
        markdown_path=paths["markdown"],
        draft_fingerprint=canonical_fingerprint(markdown),
    )


def _write_model_list(path: Path, values: list[BaseModel]) -> None:
    path.write_text(
        json.dumps(
            [value.model_dump(mode="json") for value in values],
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def render_structured_markdown(
    manifest: ArtifactManifest,
    content: ReportContent,
    reviews: list[ReportReviewEntry],
) -> str:
    """Render the report plan without deriving facts or reportability."""

    claims = {item.finding_id: item for item in [*content.findings, *content.conclusions]}
    charts = {
        evidence.chart_instance_id: evidence
        for result in content.results
        for evidence in result.chart_evidence
    }
    review_by_id = {item.item_id: item for item in reviews}
    session_name = str(manifest.session.get("session", "")).strip()
    report_kind = (
        "Race Strategy Report"
        if session_name.lower() in {"race", "r"}
        else f"{session_name} Strategy Report"
    )
    title = (
        f"{manifest.session.get('season', '')} {manifest.session.get('event', '')} "
        f"{report_kind}"
    ).strip()
    lines = [f"# {title}", "", "_Deterministic factual draft for human editorial review._", ""]
    embedded_charts: set[str] = set()
    included_claims: list[ReportFinding] = []
    for section in content.plan.sections:
        if not section.included:
            continue
        section_lines: list[str] = []
        for plan_item in section.items:
            if not plan_item.included:
                continue
            if plan_item.item_type == "chart":
                evidence = charts.get(plan_item.reference_id)
                if evidence is None or not evidence.image_path or evidence.chart_instance_id in embedded_charts:
                    continue
                embedded_charts.add(evidence.chart_instance_id)
                alt = _escape_alt(evidence.title or "Supporting analytical chart")
                section_lines.extend(["", f"![{alt}]({_safe_markdown_path(evidence.image_path)})"])
                if evidence.metadata_path:
                    section_lines.append(
                        f"[Chart metadata]({_safe_markdown_path(evidence.metadata_path)})"
                    )
                continue
            if plan_item.item_type != "claim":
                continue
            claim = claims.get(plan_item.reference_id)
            if claim is None:
                continue
            review = review_by_id.get(claim.finding_id)
            if review is not None and review.review_status == "rejected":
                continue
            publication_text = (
                review.edited_text
                if review is not None and review.review_status == "edited"
                else claim.text
            )
            section_lines.extend([f"- {publication_text}", f"  - Confidence: `{claim.confidence}`"])
            basis = _publication_basis(claim)
            if basis and section.section_id != "executive_summary":
                section_lines.append(f"  - Basis: {basis.rstrip('.')}.")
            if claim.limitations:
                section_lines.append("  - Limitations: " + " ".join(claim.limitations))
            included_claims.append(claim)
        if section_lines:
            lines.extend([f"## {section.title}", "", *section_lines, ""])

    non_publishable = [
        assessment
        for assessment in content.assessments
        if assessment.report_disposition != "reportable"
    ]
    if not included_claims:
        lines.extend(
            [
                "## Executive Summary",
                "",
                "No reviewed publishable claims are included.",
                "",
            ]
        )
    if non_publishable:
        if not any(line == "## Limitations and Evidence" for line in lines):
            lines.extend(["## Limitations and Evidence", ""])
        for assessment in non_publishable:
            lines.append(f"- {_publication_assessment_text(assessment.result_type, assessment.report_disposition, assessment.reasons)}")
        lines.append("")
    lines.extend(
        [
            "---",
            "",
            f"Report schema: `{REPORT_CONTENT_SCHEMA_VERSION}`  ",
            f"Evidence fingerprint: `{content.evidence_fingerprint}`",
            "",
        ]
    )
    return "\n".join(lines)


def _publication_basis(claim: ReportFinding) -> str:
    basis = claim.comparison_basis

    def interval_label(value: object) -> str | None:
        if not isinstance(value, dict):
            return None
        driver = value.get("driver")
        stint = value.get("stint")
        start = value.get("start_lap")
        end = value.get("end_lap")
        if driver and stint is not None and start is not None and end is not None:
            return f"{driver} stint {stint}, laps {start}-{end}"
        return None

    intervals = basis.get("intervals")
    if isinstance(intervals, list):
        labels = [label for value in intervals if (label := interval_label(value))]
        if labels:
            suffix = "; representative laps only" if basis.get("representative_laps_only", True) else ""
            return " vs ".join(labels) + suffix
    own_interval = interval_label(basis)
    if own_interval:
        suffix = "; representative laps only" if claim.finding_type in {
            "representative_pace_advantage", "observed_pace_evolution"
        } else ""
        return own_interval + suffix
    focal = basis.get("focal_driver") or basis.get("driver")
    reference = basis.get("reference_driver") or basis.get("benchmark")
    start = basis.get("start_lap")
    end = basis.get("end_lap")
    if claim.finding_type == "measured_pit_cycle_change" and focal and reference:
        pit_in = basis.get("pit_in_lap")
        pit_out = basis.get("pit_out_lap")
        if None not in (start, pit_in, pit_out, end):
            return (
                f"{focal} vs {reference}; pre-stop reference lap {start}, pit-in lap {pit_in}, "
                f"pit-out lap {pit_out}, post-stop reference lap {end}"
            )
    if focal and reference and start is not None and end is not None:
        return f"{focal} vs {reference}, laps {start}-{end}; measured direct timing gap"
    return ""


def _publication_assessment_text(
    result_type: str, disposition: str, reasons: list[str]
) -> str:
    if result_type in {
        "descriptive_within_driver_difference",
        "matched_driver_descriptive_difference",
        "unrestricted_descriptive_distribution",
    }:
        if disposition == "unavailable":
            return (
                "Compound comparison unavailable: the selected evidence did not "
                "support a defensible compound difference."
            )
        return "Compound comparison retained as supporting context without a publishable claim."
    if result_type == "strategy_timeline":
        return (
            "Strategy timeline retained as supporting context; it does not "
            "independently support a report claim."
        )
    label = result_type.replace("_", " ").capitalize()
    reason = " ".join(reasons)
    return f"{label} {disposition.replace('_', ' ')}: {reason}"


def _escape_alt(value: str) -> str:
    return value.replace("[", "\\[").replace("]", "\\]").replace("\n", " ")


def _safe_markdown_path(value: str) -> str:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe report asset path: {value}")
    return path.as_posix().replace(" ", "%20").replace("(", "%28").replace(")", "%29")


def write_report_package(
    output_dir: Path,
    manifest: ArtifactManifest,
    observations: list[Observation],
) -> ReportPackagePaths:
    observations_path = output_dir / "observations.json"
    review_path = output_dir / "review.json"
    markdown_path = output_dir / "draft.md"

    observations_path.write_text(
        json.dumps(
            [observation.model_dump(mode="json") for observation in observations],
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    review_entries = [
        ObservationReviewEntry(
            observation_id=observation.observation_id,
            review_status=observation.review_status,
            edited_text=observation.edited_text,
        ).model_dump(mode="json")
        for observation in observations
    ]
    review_path.write_text(
        json.dumps(review_entries, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_markdown_draft(manifest, observations),
        encoding="utf-8",
    )
    return ReportPackagePaths(
        observations_path=observations_path,
        review_path=review_path,
        markdown_path=markdown_path,
    )


def render_markdown_draft(
    manifest: ArtifactManifest,
    observations: list[Observation],
) -> str:
    lines = [
        f"# {manifest.session['season']} {manifest.session['event']} {manifest.session['session']} Analysis Draft",
        "",
        f"Run ID: `{manifest.run_id}`",
        f"Status: `{manifest.status}`",
        "",
        "## Charts",
        "",
    ]
    if manifest.artifacts:
        for artifact in manifest.artifacts:
            lines.append(
                f"- `{artifact.artifact_id}` ({artifact.recipe_id}): "
                f"`{artifact.image_path}`"
            )
    else:
        lines.append("- No chart artifacts were generated.")

    lines.extend(["", "## Observations", ""])
    publishable = [
        observation
        for observation in observations
        if observation.review_status != "rejected"
    ]
    if publishable:
        for observation in publishable:
            lines.append(f"- {observation.publication_text}")
            if observation.limitations:
                lines.append(
                    "  Limitations: " + " ".join(observation.limitations)
                )
    else:
        lines.append("- No supported observations were generated.")

    if manifest.warnings or manifest.errors:
        lines.extend(["", "## Run Notes", ""])
        for warning in manifest.warnings:
            lines.append(f"- Warning: {warning}")
        for error in manifest.errors:
            lines.append(f"- Error: {error}")

    return "\n".join(lines) + "\n"


def apply_observation_review(
    observations: list[Observation],
    observation_id: str,
    review_status: ReviewStatus,
    edited_text: str | None = None,
) -> list[Observation]:
    updated: list[Observation] = []
    found = False
    for observation in observations:
        if observation.observation_id != observation_id:
            updated.append(observation)
            continue
        found = True
        updated.append(
            observation.model_copy(
                update={
                    "review_status": review_status,
                    "edited_text": edited_text if review_status == "edited" else None,
                },
                deep=True,
            )
        )
    if not found:
        raise ValueError(f"Unknown observation ID: {observation_id}")
    return updated

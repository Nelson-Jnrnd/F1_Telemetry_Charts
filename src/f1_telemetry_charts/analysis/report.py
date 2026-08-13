"""Report package export and observation review helpers."""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile

from pydantic import BaseModel, ConfigDict

from f1_telemetry_charts.analysis.manifest import ArtifactManifest, ChartArtifactEntry
from f1_telemetry_charts.analysis.findings import (
    REPORT_CONTENT_SCHEMA_VERSION,
    ReportContent,
    ReportFinding,
    ReportReviewEntry,
    PublicationReadiness,
)
from f1_telemetry_charts.analysis.observations import (
    Observation,
    ObservationReviewEntry,
    ReviewStatus,
)

PUBLICATION_ARTICLE_SCHEMA_VERSION = 2
PUBLICATION_EXPORT_CONTRACT_VERSION = 3


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
    analyst_markdown_path: Path
    publication_plan_path: Path | None = None
    evidence_sidecar_path: Path | None = None
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
        "analyst_markdown": output_dir / "analyst-report.md",
        "publication_plan": output_dir / "publication-plan.json",
        "evidence_sidecar": output_dir / "evidence.json",
    }
    _write_model_list(paths["results"], content.results)
    _write_model_list(paths["assessments"], content.assessments)
    _write_model_list(paths["findings"], [*content.findings, *content.conclusions])
    _atomic_write_text(paths["report"], content.plan.model_dump_json(indent=2))
    _write_model_list(paths["review"], reviews)
    analyst_markdown = render_structured_markdown(manifest, content, reviews)
    _atomic_write_text(paths["analyst_markdown"], analyst_markdown)
    publication_plan_path = None
    evidence_sidecar_path = None
    if content.publication_plan is not None:
        _atomic_write_text(
            paths["publication_plan"], content.publication_plan.model_dump_json(indent=2)
        )
        evidence_sidecar = {
            "schema_version": content.schema_version,
            "results": [item.model_dump(mode="json") for item in content.results],
            "assessments": [item.model_dump(mode="json") for item in content.assessments],
            "findings": [item.model_dump(mode="json") for item in [*content.findings, *content.conclusions]],
            "reviews": [item.model_dump(mode="json") for item in reviews],
        }
        _atomic_write_text(
            paths["evidence_sidecar"], json.dumps(evidence_sidecar, indent=2, sort_keys=True)
        )
        markdown = render_publication_markdown(manifest, content, reviews)
        publication_plan_path = paths["publication_plan"]
        evidence_sidecar_path = paths["evidence_sidecar"]
    else:
        markdown = analyst_markdown
    _atomic_write_text(paths["markdown"], markdown)
    from f1_telemetry_charts.analysis.findings import canonical_fingerprint

    return StructuredReportPackagePaths(
        results_path=paths["results"],
        assessments_path=paths["assessments"],
        findings_path=paths["findings"],
        report_path=paths["report"],
        review_path=paths["review"],
        markdown_path=paths["markdown"],
        analyst_markdown_path=paths["analyst_markdown"],
        publication_plan_path=publication_plan_path,
        evidence_sidecar_path=evidence_sidecar_path,
        draft_fingerprint=canonical_fingerprint(markdown),
    )


def write_publication_export_package(
    output_dir: Path,
    source_dir: Path,
    manifest: ArtifactManifest,
    content: ReportContent,
    reviews: list[ReportReviewEntry],
    readiness: PublicationReadiness,
) -> ArtifactManifest:
    """Write the clean, web-oriented publication handoff package."""

    plan = content.publication_plan
    if plan is None:
        raise ValueError("Publication export requires a publication plan.")
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "assets").mkdir()
    evidence_by_chart = {
        evidence.chart_instance_id: evidence
        for result in content.results
        for evidence in result.chart_evidence
    }
    manifest_by_image = {item.image_path: item for item in manifest.artifacts}
    exported_artifacts: list[ChartArtifactEntry] = []
    asset_paths: dict[str, str] = {}
    selected_recipe_ids: list[str] = []
    for placement in (item for item in plan.charts if item.included):
        evidence = evidence_by_chart.get(placement.chart_instance_id)
        if evidence is None or not evidence.image_path or not evidence.metadata_path:
            raise ValueError(
                f"Selected publication chart is missing portable assets: {placement.chart_instance_id}"
            )
        source_image = _resolve_source_asset(source_dir, evidence.image_path)
        source_metadata = _resolve_source_asset(source_dir, evidence.metadata_path)
        asset_dir = output_dir / "assets" / placement.chart_instance_id
        asset_dir.mkdir(parents=True, exist_ok=True)
        image_relative = Path("assets") / placement.chart_instance_id / source_image.name
        metadata_relative = Path("assets") / placement.chart_instance_id / source_metadata.name
        shutil.copy2(source_image, output_dir / image_relative)
        shutil.copy2(source_metadata, output_dir / metadata_relative)
        source_artifact = manifest_by_image.get(evidence.image_path)
        recipe_id = source_artifact.recipe_id if source_artifact else "publication"
        selected_recipe_ids.append(recipe_id)
        exported_artifacts.append(
            ChartArtifactEntry(
                artifact_id=evidence.artifact_id or placement.chart_instance_id,
                recipe_id=recipe_id,
                image_path=image_relative.as_posix(),
                metadata_path=metadata_relative.as_posix(),
            )
        )
        asset_paths[placement.chart_instance_id] = image_relative.as_posix()

    article_markdown = render_publication_markdown(
        manifest, content, reviews, asset_paths=asset_paths
    )
    _atomic_write_text(output_dir / "article.md", article_markdown)
    _atomic_write_text(
        output_dir / "article.json",
        json.dumps(
            _publication_article_payload(content, reviews, asset_paths),
            indent=2,
            sort_keys=True,
        ),
    )
    publication_placements = _publication_claim_entries(content, reviews)
    evidence_sidecar = _publication_evidence_payload(
        content,
        reviews,
        publication_placements,
        asset_paths,
    )
    _atomic_write_text(
        output_dir / "evidence.json",
        json.dumps(evidence_sidecar, indent=2, sort_keys=True),
    )
    selected_recipes = [
        item for item in manifest.recipes if item.recipe_id in set(selected_recipe_ids)
    ]
    export_manifest = manifest.model_copy(
        update={
            "artifacts": exported_artifacts,
            "recipes": selected_recipes,
            "requested_recipes": list(dict.fromkeys(selected_recipe_ids)),
            "observations_path": None,
            "review_path": None,
            "markdown_path": "article.md",
            "article_json_path": "article.json",
            "results_path": None,
            "assessments_path": None,
            "findings_path": None,
            "report_path": None,
            "report_review_path": None,
            "publication_plan_path": None,
            "analyst_markdown_path": None,
            "evidence_sidecar_path": "evidence.json",
            "publication_readiness": readiness.model_dump(mode="json"),
            "report_schema_version": None,
            "analysis_path": None,
            "sessions": [],
            "chart_instances": [],
        },
        deep=True,
    )
    export_manifest.write(output_dir / "manifest.json")
    return export_manifest


def _resolve_source_asset(source_dir: Path, relative_path: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Unsafe publication asset path: {relative_path}")
    source_root = source_dir.resolve()
    source = (source_root / relative).resolve()
    try:
        source.relative_to(source_root)
    except ValueError as exc:
        raise ValueError(f"Publication asset escapes the package: {relative_path}") from exc
    if not source.is_file():
        raise ValueError(f"Publication asset is missing: {relative_path}")
    return source


def _publication_article_payload(
    content: ReportContent,
    reviews: list[ReportReviewEntry],
    asset_paths: dict[str, str],
) -> dict[str, object]:
    plan = content.publication_plan
    if plan is None:
        raise ValueError("Publication article requires a publication plan.")
    publication_claims = _publication_claim_entries(content, reviews)
    section_titles = {
        "how_the_race_developed": "How the Race Developed",
        "pace_and_strategy": "Pace and Strategy",
        "key_comparison": "Key Comparison",
    }
    sections: list[dict[str, object]] = []
    for section_id in ("how_the_race_developed", "pace_and_strategy", "key_comparison"):
        paragraphs = [
            {"paragraph": item["paragraph"], "claim_id": item["claim_id"]}
            for item in publication_claims
            if item["section"] == section_id
        ]
        charts = [
            {
                "asset": asset_paths[item.chart_instance_id],
                "purpose": item.purpose,
                "caption": item.caption.value,
                "alt_text": item.alt_text.value,
            }
            for item in plan.charts
            if item.included
            and item.section == section_id
            and item.chart_instance_id in asset_paths
        ]
        lede = content.publication_editorial.section_ledes.get(section_id)
        if paragraphs or charts or (lede and lede.value.strip()):
            sections.append(
                {
                    "section": section_id,
                    "title": section_titles[section_id],
                    "lede": lede.value if lede else "",
                    "paragraphs": paragraphs,
                    "charts": charts,
                }
            )
    return {
        "schema_version": PUBLICATION_ARTICLE_SCHEMA_VERSION,
        "headline": content.publication_editorial.headline.value,
        "standfirst": content.publication_editorial.standfirst.value,
        "at_a_glance": [
            {"text": item["summary_reference"], "claim_id": item["claim_id"]}
            for item in publication_claims
            if item["summary_reference"]
        ],
        "sections": sections,
        "conclusion": content.publication_editorial.conclusion.value,
    }


def _publication_claim_entries(
    content: ReportContent,
    reviews: list[ReportReviewEntry],
) -> list[dict[str, str | None]]:
    """Return the canonical exported bridge from publication placement to evidence."""

    plan = content.publication_plan
    if plan is None:
        raise ValueError("Publication claim mapping requires a publication plan.")
    claims = {item.finding_id: item for item in [*content.findings, *content.conclusions]}
    reviews_by_id = {item.item_id: item for item in reviews}
    entries: list[dict[str, str | None]] = []
    for placement in plan.claims:
        if not placement.included:
            continue
        claim = claims.get(placement.finding_id)
        review = reviews_by_id.get(placement.finding_id)
        if claim is None or review is None or review.review_status in {"pending", "rejected"}:
            continue
        paragraph = (
            review.edited_text
            if review.review_status == "edited" and review.edited_text
            else claim.text
        )
        entries.append(
            {
                "claim_id": claim.finding_id,
                "section": placement.section,
                "paragraph": paragraph,
                "summary_reference": placement.summary_reference,
            }
        )
    return entries


def _publication_evidence_payload(
    content: ReportContent,
    reviews: list[ReportReviewEntry],
    publication_placements: list[dict[str, str | None]],
    asset_paths: dict[str, str],
) -> dict[str, object]:
    """Build portable evidence with unambiguous package/source asset references."""

    def remap(value: object) -> object:
        if isinstance(value, list):
            return [remap(item) for item in value]
        if not isinstance(value, dict):
            return value
        output = {key: remap(item) for key, item in value.items()}
        chart_id = output.get("chart_instance_id")
        if not isinstance(chart_id, str) or not (
            "image_path" in output or "metadata_path" in output
        ):
            return output
        source_image = output.pop("image_path", None)
        source_metadata = output.pop("metadata_path", None)
        package_image = asset_paths.get(chart_id)
        if package_image:
            output["reference_scope"] = "package"
            output["image_path"] = package_image
            output["metadata_path"] = Path(package_image).with_suffix(".json").as_posix()
        else:
            output["reference_scope"] = "source_analysis"
            output["source_image_path"] = source_image
            output["source_metadata_path"] = source_metadata
        return output

    return {
        "schema_version": content.schema_version,
        "publication_export_contract_version": PUBLICATION_EXPORT_CONTRACT_VERSION,
        "results": remap([item.model_dump(mode="json") for item in content.results]),
        "assessments": [item.model_dump(mode="json") for item in content.assessments],
        "findings": remap(
            [
                item.model_dump(mode="json")
                for item in [*content.findings, *content.conclusions]
            ]
        ),
        "reviews": [item.model_dump(mode="json") for item in reviews],
        "publication_placements": publication_placements,
    }


def _write_model_list(path: Path, values: list[BaseModel]) -> None:
    _atomic_write_text(
        path,
        json.dumps(
            [value.model_dump(mode="json") for value in values],
            indent=2,
            sort_keys=True,
        ),
    )


def _atomic_write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        stream.write(value)
        temporary = Path(stream.name)
    os.replace(temporary, path)


def render_publication_markdown(
    manifest: ArtifactManifest,
    content: ReportContent,
    reviews: list[ReportReviewEntry],
    asset_paths: dict[str, str] | None = None,
) -> str:
    """Render the selective reader view without internal traceability scaffolding."""

    plan = content.publication_plan
    if plan is None:
        raise ValueError("Publication rendering requires a publication plan.")
    from f1_telemetry_charts.analysis.publication import validate_publication_plan

    validate_publication_plan(content, plan)
    editorial = content.publication_editorial
    claims = {item.finding_id: item for item in [*content.findings, *content.conclusions]}
    reviews_by_id = {item.item_id: item for item in reviews}
    placements = {item.finding_id: item for item in plan.claims if item.included}
    title = _safe_reader_text(editorial.headline.value) or (
        f"{manifest.session.get('season', '')} {manifest.session.get('event', '')} Race Report"
    ).strip()
    lines = [f"# {title}", ""]
    standfirst = _safe_reader_text(editorial.standfirst.value)
    if standfirst:
        lines.extend([standfirst, ""])
    summary = [item.summary_reference for item in plan.claims if item.included and item.summary_reference]
    if summary:
        lines.extend(["## At a Glance", "", *[f"- {_safe_reader_text(value)}" for value in summary], ""])

    section_titles = {
        "how_the_race_developed": "How the Race Developed",
        "pace_and_strategy": "Pace and Strategy",
        "key_comparison": "Key Comparison",
    }
    for section_id in ("how_the_race_developed", "pace_and_strategy", "key_comparison"):
        section_lines: list[str] = []
        reviewed_claim_texts: list[str] = []
        lede = editorial.section_ledes.get(section_id)
        if lede and lede.value.strip():
            section_lines.extend([_safe_reader_text(lede.value), ""])
        for placement in plan.claims:
            if not placement.included or placement.section != section_id:
                continue
            claim = claims.get(placement.finding_id)
            review = reviews_by_id.get(placement.finding_id)
            if claim is None or review is None or review.review_status in {"pending", "rejected"}:
                continue
            text = review.edited_text if review.review_status == "edited" else claim.text
            reviewed_claim_texts.append(_safe_reader_text(text or ""))
        if section_id == "how_the_race_developed" and reviewed_claim_texts:
            section_lines.extend([" ".join(reviewed_claim_texts), ""])
        else:
            for text in reviewed_claim_texts:
                section_lines.extend([text, ""])
        for chart in plan.charts:
            if not chart.included or chart.section != section_id:
                continue
            evidence = next(
                (
                    evidence
                    for result in content.results
                    for evidence in result.chart_evidence
                    if evidence.chart_instance_id == chart.chart_instance_id
                ),
                None,
            )
            if evidence is None or not evidence.image_path:
                continue
            alt = _escape_alt(_safe_reader_text(chart.alt_text.value) or "Race analysis chart")
            image_path = (asset_paths or {}).get(
                chart.chart_instance_id, evidence.image_path
            )
            section_lines.extend([f"![{alt}]({_safe_markdown_path(image_path)})", ""])
            if chart.caption.value.strip():
                section_lines.extend([f"*{_safe_reader_text(chart.caption.value)}*", ""])
        if section_lines:
            lines.extend([f"## {section_titles[section_id]}", "", *section_lines])
    if editorial.conclusion.value.strip():
        lines.extend(["## Conclusion", "", _safe_reader_text(editorial.conclusion.value), ""])
    included_claims = [claims[item_id] for item_id in placements if item_id in claims]
    methods = sorted(
        {
            basis.rstrip(".")
            for claim in included_claims
            if (basis := _publication_basis(claim))
        }
    )
    if methods:
        lines.extend(["## Methods and Evidence", "", *[f"- {_safe_reader_text(value)}." for value in methods], ""])
    output = "\n".join(lines).rstrip() + "\n"
    if "[object Object]" in output or re.search(r"(?:fingerprint|result-[0-9a-f]|finding-[0-9a-f])", output, re.I):
        raise ValueError("Internal-format leakage detected in publication Markdown.")
    return output


def _safe_reader_text(value: str) -> str:
    return " ".join(str(value).replace("<", "&lt;").replace(">", "&gt;").split())


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
        if claim.finding_type == "cumulative_pace_delta":
            return (
                f"{focal} vs {reference}, laps {start}-{end}; derived cumulative "
                "representative-lap pace difference, not elapsed race gap"
            )
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

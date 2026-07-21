"""Report package export and observation review helpers."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from f1_telemetry_charts.analysis.manifest import ArtifactManifest
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

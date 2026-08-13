"""Analysis run manifest models."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


RunStatus = Literal["succeeded", "partially_succeeded", "failed"]
RecipeStatus = Literal["produced", "skipped", "failed"]


class ChartArtifactEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    recipe_id: str
    image_path: str
    metadata_path: str


class RecipeRunEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipe_id: str
    status: RecipeStatus
    artifact_id: str | None = None
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class ArtifactManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    status: RunStatus
    framework_version: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    configuration_hash: str
    session: dict[str, str | int]
    requested_recipes: list[str]
    artifacts: list[ChartArtifactEntry] = Field(default_factory=list)
    recipes: list[RecipeRunEntry] = Field(default_factory=list)
    observations_path: str | None = None
    review_path: str | None = None
    markdown_path: str | None = None
    article_json_path: str | None = None
    results_path: str | None = None
    assessments_path: str | None = None
    findings_path: str | None = None
    report_path: str | None = None
    report_review_path: str | None = None
    publication_plan_path: str | None = None
    analyst_markdown_path: str | None = None
    evidence_sidecar_path: str | None = None
    publication_readiness: dict[str, Any] | None = None
    report_schema_version: int | None = None
    report_evidence_fingerprint: str | None = None
    report_draft_fingerprint: str | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    analysis_id: str | None = None
    analysis_path: str | None = None
    sessions: list[dict[str, Any]] = Field(default_factory=list)
    chart_instances: list[dict[str, Any]] = Field(default_factory=list)

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            stream.write(self.model_dump_json(indent=2))
            temporary = Path(stream.name)
        os.replace(temporary, path)

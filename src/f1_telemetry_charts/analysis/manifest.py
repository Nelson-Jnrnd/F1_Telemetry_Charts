"""Analysis run manifest models."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

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
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            self.model_dump_json(indent=2),
            encoding="utf-8",
        )

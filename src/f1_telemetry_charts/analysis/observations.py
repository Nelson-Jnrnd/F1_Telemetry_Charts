"""Structured observation models for report authoring."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ReviewStatus = Literal["accepted", "edited", "rejected", "unreviewed"]
Confidence = Literal["low", "medium", "high"]


class MetricValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    value: float | int | str
    unit: str | None = None
    driver: str | None = None


class EvidenceLink(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    recipe_id: str
    image_path: str
    metadata_path: str
    source_fields: list[str] = Field(default_factory=list)


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_id: str
    family: str
    text: str
    priority: int = Field(ge=1, le=5)
    confidence: Confidence
    evidence: list[EvidenceLink] = Field(default_factory=list)
    metrics: list[MetricValue] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    review_status: ReviewStatus = "unreviewed"
    edited_text: str | None = None

    @property
    def publication_text(self) -> str:
        if self.review_status == "edited" and self.edited_text:
            return self.edited_text
        return self.text


class ObservationReviewEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_id: str
    review_status: ReviewStatus = "unreviewed"
    edited_text: str | None = None

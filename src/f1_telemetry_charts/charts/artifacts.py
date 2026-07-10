"""Chart artifact models and metadata writing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict


class ChartArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    image_path: Path
    metadata_path: Path
    metadata: dict[str, Any]


def write_metadata(path: Path, metadata: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True),
        encoding="utf-8",
    )

"""Chart renderer contract."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from f1_telemetry_charts.charts.artifacts import ChartArtifact
from f1_telemetry_charts.charts.models import ChartSpec
from f1_telemetry_charts.config.models import ThemeConfig


class ChartRenderer(Protocol):
    def render(
        self,
        spec: ChartSpec,
        *,
        theme: ThemeConfig,
        output_dir: Path,
        artifact_id: str,
    ) -> ChartArtifact:
        """Render a chart spec into an artifact."""

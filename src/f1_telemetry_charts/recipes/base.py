"""Chart recipe contract."""

from __future__ import annotations

from typing import Protocol

from f1_telemetry_charts.charts.models import ChartSpec
from f1_telemetry_charts.config.models import ChartRecipeConfig
from f1_telemetry_charts.data.models import SessionDataset


class ChartRecipe(Protocol):
    recipe_id: str

    def build_spec(
        self, dataset: SessionDataset, config: ChartRecipeConfig
    ) -> ChartSpec:
        """Build a renderer-independent chart spec."""

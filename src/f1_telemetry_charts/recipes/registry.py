"""Chart recipe registry metadata and factories."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from f1_telemetry_charts.recipes.base import ChartRecipe
from f1_telemetry_charts.recipes.compound_comparison import CompoundComparisonRecipe
from f1_telemetry_charts.recipes.driver_battle import DriverBattleRecipe
from f1_telemetry_charts.recipes.lap_time_delta import LapTimeDeltaRecipe
from f1_telemetry_charts.recipes.pace_evolution import PaceEvolutionRecipe
from f1_telemetry_charts.recipes.pit_cycle_comparison import PitCycleComparisonRecipe
from f1_telemetry_charts.recipes.position_progression import PositionProgressionRecipe
from f1_telemetry_charts.recipes.race_time_delta_evolution import (
    RaceTimeDeltaEvolutionRecipe,
)
from f1_telemetry_charts.recipes.stint_pace import StintPaceRecipe
from f1_telemetry_charts.recipes.telemetry_trace import TelemetryTraceRecipe
from f1_telemetry_charts.recipes.tyre_strategy import TyreStrategyRecipe


@dataclass(frozen=True)
class RecipeMetadata:
    recipe_id: str
    display_name: str
    required_dataset_fields: tuple[str, ...]
    output_artifact_types: tuple[str, ...] = ("png", "json")
    source: str = "core"
    description: str | None = None


class RecipeRegistry:
    def __init__(
        self,
        recipes: list[RecipeMetadata] | None = None,
        factories: dict[str, Callable[[], ChartRecipe]] | None = None,
    ):
        self._recipes = {recipe.recipe_id: recipe for recipe in recipes or []}
        self._factories = factories or {}

    def has_recipe(self, recipe_id: str) -> bool:
        return recipe_id in self._recipes

    def get(self, recipe_id: str) -> RecipeMetadata:
        return self._recipes[recipe_id]

    def list_recipe_ids(self) -> list[str]:
        return sorted(self._recipes)

    def list_metadata(self) -> list[RecipeMetadata]:
        return [self._recipes[recipe_id] for recipe_id in self.list_recipe_ids()]

    def register(
        self,
        metadata: RecipeMetadata,
        factory: Callable[[], ChartRecipe],
    ) -> None:
        if metadata.recipe_id in self._recipes:
            raise ValueError(f"Duplicate recipe ID: {metadata.recipe_id}")
        self._recipes[metadata.recipe_id] = metadata
        self._factories[metadata.recipe_id] = factory

    def create(self, recipe_id: str) -> ChartRecipe:
        if recipe_id not in self._recipes:
            raise KeyError(f"Unknown recipe ID: {recipe_id}")
        if recipe_id not in self._factories:
            raise NotImplementedError(
                f"Recipe implementation is not available yet: {recipe_id}"
            )
        return self._factories[recipe_id]()


def default_recipe_registry() -> RecipeRegistry:
    recipes = [
        RecipeMetadata(
            recipe_id="telemetry_trace",
            display_name="Telemetry trace",
            required_dataset_fields=("telemetry",),
        ),
        RecipeMetadata(
            recipe_id="lap_time_delta",
            display_name="Lap time delta",
            required_dataset_fields=("laps",),
        ),
        RecipeMetadata(
            recipe_id="tyre_strategy",
            display_name="Strategy Timeline",
            required_dataset_fields=("laps",),
            description="Full-race compound stints, pit events, and shared race context.",
        ),
        RecipeMetadata(
            recipe_id="stint_pace",
            display_name="Stint Pace",
            required_dataset_fields=("laps",),
            description="Representative lap-time progression and robust driver-stint summaries.",
        ),
        RecipeMetadata(
            recipe_id="pace_evolution",
            display_name="Pace Evolution",
            required_dataset_fields=("laps",),
            description="Theil-Sen observed pace evolution by tyre age or stint progress.",
        ),
        RecipeMetadata(
            recipe_id="compound_comparison",
            display_name="Compound Comparison",
            required_dataset_fields=("laps",),
            description="Controlled descriptive compound samples without causal offsets.",
        ),
        RecipeMetadata(
            recipe_id="race_time_delta_evolution",
            display_name="Race-Time Delta Evolution",
            required_dataset_fields=("laps",),
            description="Measured direct-gap change or derived cumulative representative pace delta.",
        ),
        RecipeMetadata(
            recipe_id="pit_cycle_comparison",
            display_name="Pit-Cycle Comparison",
            required_dataset_fields=("laps",),
            description="Measured focal-versus-rival change across one bounded stop cycle.",
        ),
        RecipeMetadata(
            recipe_id="driver_battle",
            display_name="Driver Battle",
            required_dataset_fields=("laps",),
            description="Synchronized representative pace, direct gap, and tyre context for two drivers.",
        ),
        RecipeMetadata(
            recipe_id="position_progression",
            display_name="Position progression",
            required_dataset_fields=("laps",),
        ),
    ]
    return RecipeRegistry(
        recipes,
        factories={
            "lap_time_delta": LapTimeDeltaRecipe,
            "position_progression": PositionProgressionRecipe,
            "telemetry_trace": TelemetryTraceRecipe,
            "tyre_strategy": TyreStrategyRecipe,
            "stint_pace": StintPaceRecipe,
            "pace_evolution": PaceEvolutionRecipe,
            "compound_comparison": CompoundComparisonRecipe,
            "race_time_delta_evolution": RaceTimeDeltaEvolutionRecipe,
            "pit_cycle_comparison": PitCycleComparisonRecipe,
            "driver_battle": DriverBattleRecipe,
        },
    )

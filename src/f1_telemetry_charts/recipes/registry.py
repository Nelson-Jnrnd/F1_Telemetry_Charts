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
from f1_telemetry_charts.recipes.qualifying import (
    QualifyingMarginRecipe,
    QualifyingProgressionRecipe,
    QualifyingSectorContributionRecipe,
)
from f1_telemetry_charts.recipes.practice import (
    PracticeLongRunPaceRecipe,
    PracticeObservedPaceEvolutionRecipe,
    PracticeRunOverviewRecipe,
)
from f1_telemetry_charts.recipes.race_time_delta_evolution import (
    RaceTimeDeltaEvolutionRecipe,
)
from f1_telemetry_charts.recipes.stint_pace import StintPaceRecipe
from f1_telemetry_charts.recipes.telemetry_trace import TelemetryTraceRecipe
from f1_telemetry_charts.recipes.tyre_strategy import TyreStrategyRecipe

ALL_SUPPORTED_SESSION_TYPES = (
    "practice",
    "qualifying",
    "sprint_qualifying",
    "sprint",
    "race",
)


@dataclass(frozen=True)
class RecipeMetadata:
    recipe_id: str
    display_name: str
    required_dataset_fields: tuple[str, ...]
    output_artifact_types: tuple[str, ...] = ("png", "json")
    source: str = "core"
    description: str | None = None
    supported_session_types: tuple[str, ...] = ALL_SUPPORTED_SESSION_TYPES
    preview_asset: str | None = None
    icon: str | None = "chart"


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
            icon="activity",
        ),
        RecipeMetadata(
            recipe_id="lap_time_delta",
            display_name="Lap time delta",
            required_dataset_fields=("laps",),
            icon="timer",
        ),
        RecipeMetadata(
            recipe_id="tyre_strategy",
            display_name="Strategy Timeline",
            required_dataset_fields=("laps",),
            description="Full-race compound stints, pit events, and shared race context.",
            supported_session_types=("sprint", "race"),
            icon="tyre",
        ),
        RecipeMetadata(
            recipe_id="stint_pace",
            display_name="Stint Pace",
            required_dataset_fields=("laps",),
            description="Representative lap-time progression and robust driver-stint summaries.",
            supported_session_types=("sprint", "race"),
            icon="line-chart",
        ),
        RecipeMetadata(
            recipe_id="pace_evolution",
            display_name="Pace Evolution",
            required_dataset_fields=("laps",),
            description="Theil-Sen observed pace evolution by tyre age or stint progress.",
            supported_session_types=("sprint", "race"),
            icon="trending-up",
        ),
        RecipeMetadata(
            recipe_id="compound_comparison",
            display_name="Compound Comparison",
            required_dataset_fields=("laps",),
            description="Controlled descriptive compound samples without causal offsets.",
            supported_session_types=("sprint", "race"),
            icon="layers",
        ),
        RecipeMetadata(
            recipe_id="race_time_delta_evolution",
            display_name="Race-Time Delta Evolution",
            required_dataset_fields=("laps",),
            description="Measured direct-gap change or derived cumulative representative pace delta.",
            supported_session_types=("sprint", "race"),
            icon="git-compare",
        ),
        RecipeMetadata(
            recipe_id="pit_cycle_comparison",
            display_name="Pit-Cycle Comparison",
            required_dataset_fields=("laps",),
            description="Measured focal-versus-rival change across one bounded stop cycle.",
            supported_session_types=("sprint", "race"),
            icon="repeat",
        ),
        RecipeMetadata(
            recipe_id="driver_battle",
            display_name="Driver Battle",
            required_dataset_fields=("laps",),
            description="Synchronized representative pace, direct gap, and tyre context for two drivers.",
            supported_session_types=("sprint", "race"),
            icon="users",
        ),
        RecipeMetadata(
            recipe_id="position_progression",
            display_name="Position progression",
            required_dataset_fields=("laps",),
            supported_session_types=("sprint", "race"),
            icon="list-ordered",
        ),
        RecipeMetadata(recipe_id="qualifying_progression", display_name="Qualifying Progression", required_dataset_fields=("laps",), description="Q1/Q2/Q3 valid-best and attempt chronology.", supported_session_types=("qualifying",), icon="gauge"),
        RecipeMetadata(recipe_id="qualifying_margin_comparison", display_name="Pole and Cutoff Margins", required_dataset_fields=("laps",), description="Official within-segment pole and advancement margins.", supported_session_types=("qualifying",), icon="bar-chart"),
        RecipeMetadata(recipe_id="qualifying_sector_contribution", display_name="Qualifying Sector Contribution", required_dataset_fields=("laps",), description="Reconciled Q3 pole-to-P2 signed sector contributions.", supported_session_types=("qualifying",), icon="split"),
        RecipeMetadata(recipe_id="practice_run_overview", display_name="Practice Run Overview", required_dataset_fields=("laps",), description="Pit-bounded Practice run chronology with compound and representative coverage.", supported_session_types=("practice",), icon="calendar-clock"),
        RecipeMetadata(recipe_id="practice_long_run_pace_summary", display_name="Practice Long-Run Pace Summary", required_dataset_fields=("laps",), description="Representative-lap median, IQR, sample, and compatibility context.", supported_session_types=("practice",), icon="chart-no-axes-combined"),
        RecipeMetadata(recipe_id="practice_observed_pace_evolution", display_name="Practice Observed Pace Evolution", required_dataset_fields=("laps",), description="Representative laps and non-causal fitted run-progress trend.", supported_session_types=("practice",), icon="trending-up"),
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
            "qualifying_progression": QualifyingProgressionRecipe,
            "qualifying_margin_comparison": QualifyingMarginRecipe,
            "qualifying_sector_contribution": QualifyingSectorContributionRecipe,
            "practice_run_overview": PracticeRunOverviewRecipe,
            "practice_long_run_pace_summary": PracticeLongRunPaceRecipe,
            "practice_observed_pace_evolution": PracticeObservedPaceEvolutionRecipe,
        },
    )

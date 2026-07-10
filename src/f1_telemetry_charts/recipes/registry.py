"""Chart recipe registry metadata and factories."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from f1_telemetry_charts.recipes.base import ChartRecipe
from f1_telemetry_charts.recipes.lap_time_delta import LapTimeDeltaRecipe


@dataclass(frozen=True)
class RecipeMetadata:
    recipe_id: str
    display_name: str
    required_dataset_fields: tuple[str, ...]
    output_artifact_types: tuple[str, ...] = ("png", "json")


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

    def create(self, recipe_id: str) -> ChartRecipe:
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
            display_name="Tyre strategy",
            required_dataset_fields=("laps",),
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
        },
    )

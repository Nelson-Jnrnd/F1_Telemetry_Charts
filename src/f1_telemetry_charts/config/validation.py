"""Configuration validation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from f1_telemetry_charts.config.models import ProjectConfig
from f1_telemetry_charts.recipes.registry import default_recipe_registry


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "message": self.message}


class ConfigValidationError(Exception):
    def __init__(self, issues: list[ValidationIssue]):
        self.issues = issues
        super().__init__("; ".join(f"{issue.path}: {issue.message}" for issue in issues))


def validate_config(raw_config: dict[str, Any]) -> ProjectConfig:
    try:
        config = ProjectConfig.model_validate(raw_config)
    except ValidationError as exc:
        raise ConfigValidationError(_issues_from_pydantic(exc)) from exc

    registry = default_recipe_registry()
    recipe_issues = [
        ValidationIssue(
            path=f"$.recipes[{index}].recipe_id",
            message=f"Unknown recipe ID: {recipe.recipe_id}",
        )
        for index, recipe in enumerate(config.recipes)
        if not registry.has_recipe(recipe.recipe_id)
    ]
    if recipe_issues:
        raise ConfigValidationError(recipe_issues)

    return config


def _issues_from_pydantic(exc: ValidationError) -> list[ValidationIssue]:
    return [
        ValidationIssue(path=_format_path(error["loc"]), message=str(error["msg"]))
        for error in exc.errors()
    ]


def _format_path(location: tuple[str | int, ...]) -> str:
    if not location:
        return "$"

    path = "$"
    for item in location:
        if isinstance(item, int):
            path += f"[{item}]"
        else:
            path += f".{item}"
    return path

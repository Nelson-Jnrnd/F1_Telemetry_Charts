"""Configuration file loading."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

from f1_telemetry_charts.config.models import ProjectConfig
from f1_telemetry_charts.config.validation import (
    ConfigValidationError,
    ValidationIssue,
    validate_config,
)


def load_config(path: str | Path) -> ProjectConfig:
    config_path = Path(path)
    raw = _read_config(config_path)
    return validate_config(raw)


def _read_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigValidationError(
            [ValidationIssue(path="$", message=f"Configuration file not found: {path}")]
        )
    if not path.is_file():
        raise ConfigValidationError(
            [ValidationIssue(path="$", message=f"Configuration path is not a file: {path}")]
        )

    suffix = path.suffix.lower()
    try:
        if suffix == ".json":
            return json.loads(path.read_text(encoding="utf-8"))
        if suffix == ".toml":
            return tomllib.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigValidationError(
            [ValidationIssue(path="$", message=f"Could not parse {path.name}: {exc}")]
        ) from exc

    raise ConfigValidationError(
        [
            ValidationIssue(
                path="$",
                message=(
                    "Unsupported configuration format. Use .toml or .json for "
                    "the current MVP scaffold."
                ),
            )
        ]
    )

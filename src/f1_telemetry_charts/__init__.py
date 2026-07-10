"""Public API for the F1 Telemetry Charts framework."""

from f1_telemetry_charts.config.loader import load_config
from f1_telemetry_charts.config.models import ProjectConfig
from f1_telemetry_charts.config.validation import (
    ConfigValidationError,
    ValidationIssue,
    validate_config,
)
from f1_telemetry_charts.analysis.orchestrator import AnalysisResult, run_analysis

__all__ = [
    "AnalysisResult",
    "ConfigValidationError",
    "ProjectConfig",
    "ValidationIssue",
    "load_config",
    "run_analysis",
    "validate_config",
]

__version__ = "0.1.0"

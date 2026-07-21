"""Public API for the F1 Telemetry Charts framework."""

from f1_telemetry_charts.config.loader import load_config
from f1_telemetry_charts.config.models import ProjectConfig
from f1_telemetry_charts.config.validation import (
    ConfigValidationError,
    ValidationIssue,
    validate_config,
)
from f1_telemetry_charts.analysis.orchestrator import AnalysisResult, run_analysis
from f1_telemetry_charts.analysis.observations import Observation
from f1_telemetry_charts.llm import describe_artifact, generate_charts

__all__ = [
    "AnalysisResult",
    "ConfigValidationError",
    "Observation",
    "ProjectConfig",
    "ValidationIssue",
    "describe_artifact",
    "generate_charts",
    "load_config",
    "run_analysis",
    "validate_config",
]

__version__ = "0.1.0"

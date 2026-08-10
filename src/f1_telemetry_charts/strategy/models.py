"""Versioned, renderer-independent strategy analysis models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


STRATEGY_ANALYSIS_SCHEMA_VERSION = 1

ValueCategory = Literal[
    "measured",
    "derived",
    "descriptive",
    "estimated_reserved",
]
ResultStatus = Literal["available", "partial", "confounded", "unavailable"]
TyreAgeSource = Literal["source", "derived", "unavailable"]
FitBasis = Literal["tyre_age", "stint_progress"]
FitQuality = Literal["high", "medium", "low", "provisional", "unavailable"]


class StrategyExclusionPolicy(BaseModel):
    """Shared pace-eligibility policy used by every strategy template."""

    model_config = ConfigDict(extra="forbid")

    exclude_first_race_lap: bool = True
    exclude_pit_in_laps: bool = True
    exclude_pit_out_laps: bool = True
    exclude_deleted_laps: bool = True
    exclude_generated_laps: bool = True
    exclude_inaccurate_laps: bool = True
    exclude_non_green_status: bool = True
    require_complete_sectors: bool = False
    green_track_status_codes: list[str] = Field(default_factory=lambda: ["1"])


class StrategyLap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = STRATEGY_ANALYSIS_SCHEMA_VERSION
    driver: str
    lap_number: int = Field(ge=1)
    effective_stint: int | None = Field(default=None, ge=1)
    stint_source: Literal["source", "derived", "conflicting", "unavailable"]
    compound: str | None = None
    tyre_age: float | None = Field(default=None, ge=0)
    tyre_age_source: TyreAgeSource = "unavailable"
    stint_progress: int | None = Field(default=None, ge=1)
    lap_start_time_seconds: float | None = None
    lap_end_time_seconds: float | None = None
    lap_time_seconds: float | None = None
    sector_1_time_seconds: float | None = None
    sector_2_time_seconds: float | None = None
    sector_3_time_seconds: float | None = None
    position: int | None = None
    gap_to_leader_seconds: float | None = None
    gap_to_leader_laps: int | None = None
    track_status: str | None = None
    is_pit_in_lap: bool = False
    is_pit_out_lap: bool = False
    pit_in_time_seconds: float | None = None
    pit_out_time_seconds: float | None = None
    is_representative_for_pace: bool
    pace_exclusion_reasons: list[str] = Field(default_factory=list)
    is_visible_in_context: bool = True
    context_classifications: list[str] = Field(default_factory=list)


class DescriptiveStatistics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value_category: Literal["descriptive"] = "descriptive"
    unit: Literal["s"] = "s"
    sample_basis: Literal["representative_laps"] = "representative_laps"
    sample_count: int = Field(ge=0)
    effective_count: int = Field(ge=0)
    trim_count_per_tail: int = Field(ge=0)
    median: float | None = None
    q1: float | None = None
    q3: float | None = None
    iqr: float | None = None
    trimmed_mean: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    percentile_10: float | None = None
    percentile_90: float | None = None


class PaceEvolutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method_id: Literal["theil_sen"] = "theil_sen"
    method_version: int = 1
    result_kind: Literal["observed_pace_evolution"] = "observed_pace_evolution"
    value_category: Literal["derived"] = "derived"
    status: Literal["available", "unavailable"]
    basis: FitBasis
    units: Literal["s/tyre-age lap", "s/stint-progress lap"]
    slope: float | None = None
    intercept: float | None = None
    residual_mad_seconds: float | None = None
    sample_count: int = Field(ge=0)
    distinct_x_count: int = Field(ge=0)
    coverage: float = Field(ge=0, le=1)
    quality: FitQuality
    unavailable_reason: str | None = None
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class SectorEvolutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sector: Literal[1, 2, 3]
    raw_times_seconds: list[float] = Field(default_factory=list)
    fit: PaceEvolutionResult


class StintSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = STRATEGY_ANALYSIS_SCHEMA_VERSION
    driver: str
    effective_stint: int = Field(ge=1)
    start_lap: int = Field(ge=1)
    end_lap: int = Field(ge=1)
    compound: str | None = None
    stint_source: Literal["source", "derived", "conflicting", "unavailable"]
    tyre_age_source: TyreAgeSource
    tyre_age_coverage_numerator: int = Field(ge=0)
    tyre_age_coverage_denominator: int = Field(ge=0)
    measured_lap_count: int = Field(ge=0)
    representative_lap_count: int = Field(ge=0)
    included_lap_numbers: list[int] = Field(default_factory=list)
    excluded_lap_numbers_by_reason: dict[str, list[int]] = Field(default_factory=dict)
    statistics: DescriptiveStatistics
    pace_evolution: PaceEvolutionResult
    sector_evolution: list[SectorEvolutionResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class StrategyAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = STRATEGY_ANALYSIS_SCHEMA_VERSION
    method_versions: dict[str, int] = Field(
        default_factory=lambda: {
            "strategy_lap_classification": 1,
            "effective_stint_resolution": 1,
            "type_7_quantiles": 1,
            "trimmed_mean_10_percent": 1,
            "theil_sen": 1,
        }
    )
    requested_policy: StrategyExclusionPolicy
    effective_policy: StrategyExclusionPolicy
    laps: list[StrategyLap]
    stints: list[StintSummary]
    source_coverage: dict[str, float | int | bool | str | None] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ComparisonResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = STRATEGY_ANALYSIS_SCHEMA_VERSION
    result_kind: Literal[
        "descriptive_within_driver_difference",
        "matched_driver_descriptive_difference",
        "unrestricted_descriptive_distribution",
    ]
    value_category: Literal["descriptive"] = "descriptive"
    status: ResultStatus
    participants: list[str]
    compounds: list[str]
    interval: dict[str, int | float | None] = Field(default_factory=dict)
    control_rule: str
    weighting: str
    sample_counts: dict[str, int] = Field(default_factory=dict)
    scalar_difference_seconds: float | None = None
    per_driver_differences_seconds: dict[str, float] = Field(default_factory=dict)
    distributions_seconds: dict[str, list[float]] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def unrestricted_has_no_scalar(self) -> "ComparisonResult":
        if (
            self.result_kind == "unrestricted_descriptive_distribution"
            and self.scalar_difference_seconds is not None
        ):
            raise ValueError("Unrestricted distributions cannot carry a scalar difference")
        return self


class DeltaPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lap_number: int = Field(ge=1)
    value_seconds: float
    observed: bool = True


class RaceTimeDeltaResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = STRATEGY_ANALYSIS_SCHEMA_VERSION
    result_kind: Literal["measured_gap_change", "derived_cumulative_pace_delta"]
    value_category: Literal["measured", "derived"]
    status: ResultStatus
    focal_driver: str
    benchmark: str
    start_lap: int | None = None
    end_lap: int | None = None
    points: list[DeltaPoint] = Field(default_factory=list)
    direct_gap_points: list[DeltaPoint] = Field(default_factory=list)
    excluded_laps: list[int] = Field(default_factory=list)
    paired_sample_count: int = Field(ge=0)
    coverage_numerator: int = Field(ge=0)
    coverage_denominator: int = Field(ge=0)
    coverage_percentage: float = Field(ge=0, le=100)
    overall_change_seconds: float | None = None
    stint_changes_seconds: dict[str, float] = Field(default_factory=dict)
    green_running_change_seconds: float | None = None
    omitted_remainder_seconds: float | None = None
    sign_convention: str = "positive means focal driver lost time; negative means gained"
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class TrafficParticipant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    driver: str
    position: int | None = None
    relation: Literal["ahead", "focal", "behind"]
    focal_relative_seconds: float | None = None
    focal_relative_laps: int | None = None
    compound: str | None = None
    tyre_age: float | None = None
    tyre_age_source: TyreAgeSource = "unavailable"


class RejoinContextResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method_version: int = 1
    status: ResultStatus
    reference_precision: Literal["exact", "lap_bounded", "unavailable"]
    reference_time_seconds: float | None = None
    reference_lap: int | None = None
    participants: list[TrafficParticipant] = Field(default_factory=list)
    traffic_classification: Literal[
        "clean_air", "single_car", "traffic_group", "unavailable"
    ] = "unavailable"
    traffic_threshold_seconds: float = 3.0
    next_observed_event: str | None = None
    relative_position_after_three_laps: dict[str, int | None] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class StopExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method_version: int = 1
    status: ResultStatus
    title: Literal["Measured Pit-Lane Duration"] = "Measured Pit-Lane Duration"
    pit_lane_duration_seconds: float | None = None
    comparison_source: str | None = None
    comparison_duration_seconds: float | None = None
    signed_duration_delta_seconds: float | None = None
    ranking_allowed: bool = False
    compatibility_flags: list[str] = Field(default_factory=list)


class PitCycleResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = STRATEGY_ANALYSIS_SCHEMA_VERSION
    result_kind: Literal["measured_pit_cycle_comparison"] = "measured_pit_cycle_comparison"
    value_category: Literal["measured"] = "measured"
    status: ResultStatus
    focal_driver: str
    rival_driver: str
    focal_stop_number: int = Field(ge=1)
    pit_in_lap: int
    pit_out_lap: int | None = None
    pre_reference_lap: int | None = None
    post_reference_lap: int | None = None
    window_end_lap: int
    pre_direct_gap_seconds: float | None = None
    post_direct_gap_seconds: float | None = None
    measured_gap_change_seconds: float | None = None
    pre_positions: dict[str, int | None] = Field(default_factory=dict)
    post_positions: dict[str, int | None] = Field(default_factory=dict)
    pit_lane_duration_seconds: float | None = None
    pit_interval_precision: Literal["exact", "lap_bounded", "unavailable"]
    rival_stopped_in_window: bool = False
    neutralized_in_window: bool = False
    source_fields: list[str] = Field(default_factory=list)
    measured_values: dict[str, float | int | None] = Field(default_factory=dict)
    derived_values: dict[str, float | int | None] = Field(default_factory=dict)
    estimated_values_reserved: dict[str, float] = Field(default_factory=dict)
    rejoin_context: RejoinContextResult | None = None
    execution_breakdown: StopExecutionResult | None = None
    unavailable_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def no_initial_estimates(self) -> "PitCycleResult":
        if self.estimated_values_reserved:
            raise ValueError("Initial pit-cycle results cannot contain estimates")
        return self

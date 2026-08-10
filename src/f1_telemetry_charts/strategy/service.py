"""Shared retrospective race-strategy derivation and comparison services."""

from __future__ import annotations

from collections import defaultdict
from math import floor, isfinite
from statistics import fmean
from typing import Any, Iterable, Literal

from f1_telemetry_charts.strategy.models import (
    ComparisonResult,
    DeltaPoint,
    DescriptiveStatistics,
    PaceEvolutionResult,
    PitCycleResult,
    RaceTimeDeltaResult,
    RejoinContextResult,
    SectorEvolutionResult,
    StintSummary,
    StrategyAnalysisResult,
    StrategyExclusionPolicy,
    StrategyLap,
    StopExecutionResult,
    TrafficParticipant,
)
from f1_telemetry_charts.data.models import (
    LapRecord,
    SessionDataset,
    TimingAppRecord,
    TimingStreamRecord,
)


PACE_EXCLUSION_REASON_ORDER = (
    "missing_lap_time",
    "first_race_lap",
    "pit_in_lap",
    "pit_out_lap",
    "deleted_lap",
    "generated_lap",
    "inaccurate_lap",
    "incomplete_sectors",
    "non_green_track_status",
    "non_finite_lap_time",
)
CONTEXT_CLASSIFICATION_ORDER = (
    "pit_in",
    "pit_out",
    "neutralized",
    "red_flag_boundary",
    "compound_change",
    "conflicting_stint_evidence",
    "missing_track_status",
    "missing_data",
)
NEUTRALIZED_STATUS_CODES = frozenset({"2", "3", "4", "5", "6", "7"})
RED_FLAG_STATUS_CODES = frozenset({"5"})


def strategy_policy_from_parameters(parameters: dict[str, Any] | None) -> StrategyExclusionPolicy:
    """Build the shared typed policy from normalized or flat recipe parameters."""

    raw = parameters or {}
    filters = raw.get("filters") if isinstance(raw.get("filters"), dict) else {}
    candidate = filters.get("strategy_exclusion_policy")
    if candidate is None:
        candidate = raw.get("strategy_exclusion_policy")
    if candidate is None:
        candidate = {}
    if not isinstance(candidate, dict):
        raise ValueError("strategy_exclusion_policy must be an object")
    return StrategyExclusionPolicy.model_validate(candidate)


def derive_strategy_analysis(
    dataset: SessionDataset,
    policy: StrategyExclusionPolicy | None = None,
) -> StrategyAnalysisResult:
    """Derive the single shared strategy-lap and stint contract."""

    requested_policy = policy or StrategyExclusionPolicy()
    effective_policy = requested_policy.model_copy(deep=True)
    timing_by_driver = _group_timing(dataset.timing)
    app_by_driver = _group_timing_app(dataset.timing_app)
    strategy_laps: list[StrategyLap] = []
    warnings: list[str] = []

    status_lap_count = sum(1 for lap in dataset.laps if lap.track_status not in (None, ""))
    if dataset.laps and status_lap_count < len(dataset.laps):
        warnings.append(
            "Track-status coverage is incomplete; otherwise valid laps with missing status remain eligible."
        )

    laps_by_driver: dict[str, list[LapRecord]] = defaultdict(list)
    for lap in dataset.laps:
        laps_by_driver[lap.driver].append(lap)

    for driver in sorted(laps_by_driver):
        driver_laps = sorted(laps_by_driver[driver], key=lambda item: item.lap_number)
        stint_state = _resolve_effective_stints(driver_laps)
        tyre_ages = _resolve_tyre_ages(driver_laps, stint_state, app_by_driver.get(driver, []))
        previous_compound: str | None = None
        for index, lap in enumerate(driver_laps):
            effective_stint, stint_source, stint_progress, conflict = stint_state[index]
            tyre_age, tyre_age_source = tyre_ages[index]
            status_codes = _status_codes(lap.track_status)
            reasons = _pace_exclusion_reasons(lap, effective_policy, status_codes)
            contexts: list[str] = []
            if lap.is_pit_in_lap:
                contexts.append("pit_in")
            if lap.is_pit_out_lap:
                contexts.append("pit_out")
            if status_codes & NEUTRALIZED_STATUS_CODES:
                contexts.append("neutralized")
            if status_codes & RED_FLAG_STATUS_CODES:
                contexts.append("red_flag_boundary")
            normalized_compound = _compound(lap.compound)
            if previous_compound is not None and normalized_compound != previous_compound:
                contexts.append("compound_change")
            if conflict:
                contexts.append("conflicting_stint_evidence")
            if lap.track_status in (None, ""):
                contexts.append("missing_track_status")
            if lap.lap_time_seconds is None or normalized_compound is None:
                contexts.append("missing_data")
            timing = _timing_at_lap_end(timing_by_driver.get(driver, []), lap)
            strategy_laps.append(
                StrategyLap(
                    driver=driver,
                    lap_number=lap.lap_number,
                    effective_stint=effective_stint,
                    stint_source=stint_source,
                    compound=normalized_compound,
                    tyre_age=tyre_age,
                    tyre_age_source=tyre_age_source,
                    stint_progress=stint_progress,
                    lap_start_time_seconds=lap.lap_start_time_seconds,
                    lap_end_time_seconds=lap.lap_end_time_seconds,
                    lap_time_seconds=lap.lap_time_seconds,
                    sector_1_time_seconds=lap.sector_1_time_seconds,
                    sector_2_time_seconds=lap.sector_2_time_seconds,
                    sector_3_time_seconds=lap.sector_3_time_seconds,
                    position=(timing.position if timing and timing.position is not None else lap.position),
                    gap_to_leader_seconds=timing.gap_to_leader_seconds if timing else None,
                    gap_to_leader_laps=timing.gap_to_leader_laps if timing else None,
                    track_status=lap.track_status,
                    is_pit_in_lap=lap.is_pit_in_lap,
                    is_pit_out_lap=lap.is_pit_out_lap,
                    pit_in_time_seconds=lap.pit_in_time_seconds,
                    pit_out_time_seconds=lap.pit_out_time_seconds,
                    is_representative_for_pace=not reasons,
                    pace_exclusion_reasons=reasons,
                    is_visible_in_context=True,
                    context_classifications=_ordered(contexts, CONTEXT_CLASSIFICATION_ORDER),
                )
            )
            if normalized_compound is not None:
                previous_compound = normalized_compound

    strategy_laps.sort(key=lambda item: (item.driver, item.lap_number))
    stints = _build_stint_summaries(strategy_laps)
    tyre_age_numerator = sum(1 for lap in strategy_laps if lap.tyre_age is not None)
    timing_numerator = sum(1 for lap in strategy_laps if lap.gap_to_leader_seconds is not None)
    denominator = len(strategy_laps)
    return StrategyAnalysisResult(
        requested_policy=requested_policy,
        effective_policy=effective_policy,
        laps=strategy_laps,
        stints=stints,
        source_coverage={
            "lap_count": denominator,
            "track_status_numerator": status_lap_count,
            "track_status_denominator": denominator,
            "track_status_percentage": _percentage(status_lap_count, denominator),
            "tyre_age_numerator": tyre_age_numerator,
            "tyre_age_denominator": denominator,
            "tyre_age_percentage": _percentage(tyre_age_numerator, denominator),
            "timing_gap_numerator": timing_numerator,
            "timing_gap_denominator": denominator,
            "timing_gap_percentage": _percentage(timing_numerator, denominator),
            "weather_available": bool(dataset.weather),
        },
        warnings=warnings,
        limitations=[
            "Representative laps may still include traffic, management, weather, damage, and deployment effects.",
            "Observed pace evolution is descriptive and is not fuel-corrected or causal tyre degradation.",
        ],
    )


def type7_quantile(values: Iterable[float], probability: float) -> float | None:
    finite = sorted(float(value) for value in values if isfinite(float(value)))
    if not finite:
        return None
    if not 0 <= probability <= 1:
        raise ValueError("probability must be between 0 and 1")
    if len(finite) == 1:
        return finite[0]
    h = (len(finite) - 1) * probability
    lower = floor(h)
    fraction = h - lower
    if lower >= len(finite) - 1:
        return finite[-1]
    return finite[lower] + fraction * (finite[lower + 1] - finite[lower])


def descriptive_statistics(values: Iterable[float]) -> DescriptiveStatistics:
    finite = sorted(float(value) for value in values if isfinite(float(value)))
    count = len(finite)
    trim_count = floor(0.10 * count)
    trimmed = finite[trim_count : count - trim_count] if trim_count else finite
    q1 = type7_quantile(finite, 0.25)
    q3 = type7_quantile(finite, 0.75)
    return DescriptiveStatistics(
        sample_count=count,
        effective_count=len(trimmed),
        trim_count_per_tail=trim_count,
        median=type7_quantile(finite, 0.5),
        q1=q1,
        q3=q3,
        iqr=(q3 - q1) if q1 is not None and q3 is not None else None,
        trimmed_mean=fmean(trimmed) if trimmed else None,
        minimum=finite[0] if finite else None,
        maximum=finite[-1] if finite else None,
        percentile_10=type7_quantile(finite, 0.10),
        percentile_90=type7_quantile(finite, 0.90),
    )


def observed_pace_evolution(
    samples: Iterable[tuple[float, float]],
    *,
    basis: Literal["tyre_age", "stint_progress"],
    expected_count: int,
) -> PaceEvolutionResult:
    pairs = [
        (float(x), float(y))
        for x, y in samples
        if isfinite(float(x)) and isfinite(float(y))
    ]
    distinct_x = len({x for x, _ in pairs})
    coverage = len(pairs) / expected_count if expected_count else 0.0
    units: Literal["s/tyre-age lap", "s/stint-progress lap"] = (
        "s/tyre-age lap" if basis == "tyre_age" else "s/stint-progress lap"
    )
    if len(pairs) < 5 or distinct_x < 5:
        reason = "requires at least five representative samples and five distinct x values"
        return PaceEvolutionResult(
            status="unavailable",
            basis=basis,
            units=units,
            sample_count=len(pairs),
            distinct_x_count=distinct_x,
            coverage=coverage,
            quality="unavailable",
            unavailable_reason=reason,
            limitations=["Observed pace evolution is not a causal tyre-degradation estimate."],
        )
    slopes = [
        (y_j - y_i) / (x_j - x_i)
        for index, (x_i, y_i) in enumerate(pairs)
        for x_j, y_j in pairs[index + 1 :]
        if x_j > x_i
    ]
    slope = type7_quantile(slopes, 0.5)
    if slope is None:
        return PaceEvolutionResult(
            status="unavailable",
            basis=basis,
            units=units,
            sample_count=len(pairs),
            distinct_x_count=distinct_x,
            coverage=coverage,
            quality="unavailable",
            unavailable_reason="no increasing-x pairwise slopes were available",
        )
    intercept = type7_quantile((y - slope * x for x, y in pairs), 0.5)
    residuals = [y - (slope * x + (intercept or 0.0)) for x, y in pairs]
    residual_median = type7_quantile(residuals, 0.5) or 0.0
    residual_mad = type7_quantile(
        (abs(residual - residual_median) for residual in residuals), 0.5
    )
    quality = _fit_quality(len(pairs), coverage, residual_mad or 0.0)
    return PaceEvolutionResult(
        status="available",
        basis=basis,
        units=units,
        slope=slope,
        intercept=intercept,
        residual_mad_seconds=residual_mad,
        sample_count=len(pairs),
        distinct_x_count=distinct_x,
        coverage=coverage,
        quality=quality,
        limitations=[
            "Observed pace evolution may include fuel load, traffic, track evolution, weather, management, damage, and deployment effects."
        ],
    )


def compare_compounds(
    analysis: StrategyAnalysisResult,
    *,
    mode: Literal["within_driver", "matched_driver", "unrestricted_distribution"],
    compounds: list[str],
    drivers: list[str],
    lap_range: tuple[int | None, int | None] | None = None,
    tyre_age_range: tuple[float | None, float | None] | None = None,
    minimum_samples: int = 5,
) -> ComparisonResult:
    normalized_compounds = [_compound(value) or "UNKNOWN" for value in compounds]
    if mode in {"within_driver", "matched_driver"} and len(normalized_compounds) != 2:
        raise ValueError(f"{mode} requires exactly two compounds")
    if mode == "within_driver" and len(drivers) != 1:
        raise ValueError("within_driver requires exactly one driver")
    if mode in {"within_driver", "matched_driver"} and lap_range is None and tyre_age_range is None:
        raise ValueError("difference modes require a race-lap range or tyre-age range")
    filtered = [
        lap
        for lap in analysis.laps
        if lap.is_representative_for_pace
        and lap.lap_time_seconds is not None
        and lap.compound in normalized_compounds
        and (not drivers or lap.driver in drivers)
        and _inside(lap.lap_number, lap_range)
        and _inside(lap.tyre_age, tyre_age_range)
    ]
    distributions: dict[str, list[float]] = defaultdict(list)
    for lap in filtered:
        distributions[
            f"{lap.driver}:S{lap.effective_stint or 0}:{lap.compound}"
        ].append(lap.lap_time_seconds or 0.0)
    control = "race_lap_range" if lap_range is not None else "tyre_age_range"
    interval_values = lap_range if lap_range is not None else tyre_age_range
    interval = {
        "start": interval_values[0] if interval_values else None,
        "end": interval_values[1] if interval_values else None,
    }
    if mode == "unrestricted_distribution":
        return ComparisonResult(
            result_kind="unrestricted_descriptive_distribution",
            status="available" if distributions else "unavailable",
            participants=sorted(set(lap.driver for lap in filtered)),
            compounds=normalized_compounds,
            interval=interval,
            control_rule="selected interval only",
            weighting="raw laps remain grouped by driver and stint; no scalar aggregation",
            sample_counts={key: len(value) for key, value in sorted(distributions.items())},
            distributions_seconds=dict(sorted(distributions.items())),
            limitations=["No scalar compound difference is emitted in unrestricted mode."],
        )

    eligible_drivers = drivers or sorted({lap.driver for lap in filtered})
    per_driver: dict[str, float] = {}
    sample_counts: dict[str, int] = {}
    for driver in eligible_drivers:
        compound_groups: dict[str, dict[int, list[float]]] = {
            compound: defaultdict(list) for compound in normalized_compounds
        }
        for lap in filtered:
            if lap.driver == driver and lap.compound in compound_groups:
                compound_groups[lap.compound][lap.effective_stint or 0].append(
                    lap.lap_time_seconds or 0.0
                )
        compound_values: dict[str, list[float]] = {}
        ambiguous = False
        for compound, stint_groups in compound_groups.items():
            for stint, values in sorted(stint_groups.items()):
                sample_counts[f"{driver}:S{stint}:{compound}"] = len(values)
            if len(stint_groups) != 1:
                ambiguous = True
                continue
            compound_values[compound] = next(iter(stint_groups.values()))
        if ambiguous or set(compound_values) != set(normalized_compounds):
            continue
        if any(len(values) < minimum_samples for values in compound_values.values()):
            continue
        reference_median = type7_quantile(compound_values[normalized_compounds[0]], 0.5)
        second_median = type7_quantile(compound_values[normalized_compounds[1]], 0.5)
        if reference_median is not None and second_median is not None:
            per_driver[driver] = second_median - reference_median
    if mode == "within_driver":
        scalar = per_driver.get(drivers[0])
        return ComparisonResult(
            result_kind="descriptive_within_driver_difference",
            status="available" if scalar is not None else "unavailable",
            participants=drivers,
            compounds=normalized_compounds,
            interval=interval,
            control_rule=control,
            weighting="one driver; independent compound-stint samples",
            sample_counts=sample_counts,
            scalar_difference_seconds=scalar,
            per_driver_differences_seconds=per_driver,
            distributions_seconds=dict(sorted(distributions.items())),
            limitations=["The descriptive difference does not isolate a causal compound effect."],
        )
    scalar = type7_quantile(per_driver.values(), 0.5) if len(per_driver) >= 3 else None
    return ComparisonResult(
        result_kind="matched_driver_descriptive_difference",
        status="available" if scalar is not None else "unavailable",
        participants=sorted(per_driver),
        compounds=normalized_compounds,
        interval=interval,
        control_rule=control,
        weighting="equal driver weight; raw laps are not pooled across drivers",
        sample_counts=sample_counts,
        scalar_difference_seconds=scalar,
        per_driver_differences_seconds=dict(sorted(per_driver.items())),
        distributions_seconds=dict(sorted(distributions.items())),
        warnings=[] if scalar is not None else ["At least three eligible drivers are required."],
        limitations=["The matched descriptive difference does not isolate a causal compound effect."],
    )


def race_time_delta(
    dataset: SessionDataset,
    analysis: StrategyAnalysisResult,
    *,
    mode: Literal["measured_gap_change", "derived_cumulative_pace_delta"],
    focal_driver: str,
    benchmark: str,
    lap_range: tuple[int | None, int | None] | None = None,
) -> RaceTimeDeltaResult:
    if mode == "measured_gap_change":
        return _measured_gap_delta(dataset, analysis, focal_driver, benchmark, lap_range)
    return _derived_pace_delta(analysis, focal_driver, benchmark, lap_range)


def compare_pit_cycle(
    dataset: SessionDataset,
    analysis: StrategyAnalysisResult,
    *,
    focal_driver: str,
    rival_driver: str,
    pit_in_lap: int,
    post_stop_window: int = 3,
) -> PitCycleResult:
    if post_stop_window < 1 or post_stop_window > 5:
        raise ValueError("post_stop_window must be between 1 and 5")
    focal_laps = [lap for lap in analysis.laps if lap.driver == focal_driver]
    rival_laps = [lap for lap in analysis.laps if lap.driver == rival_driver]
    selected = next(
        (lap for lap in focal_laps if lap.lap_number == pit_in_lap and lap.is_pit_in_lap),
        None,
    )
    if selected is None:
        raise ValueError("Selected focal pit-in lap is not present")
    focal_pit_in_laps = sorted(
        lap.lap_number for lap in focal_laps if lap.is_pit_in_lap
    )
    focal_stop_number = focal_pit_in_laps.index(pit_in_lap) + 1
    pit_out = next(
        (lap for lap in focal_laps if lap.lap_number >= pit_in_lap and lap.is_pit_out_lap),
        None,
    )
    pit_out_lap = pit_out.lap_number if pit_out else pit_in_lap + 1
    window_end = pit_out_lap + post_stop_window
    post_lap = next(
        (
            lap
            for lap in focal_laps
            if pit_out_lap <= lap.lap_number <= window_end and lap.is_representative_for_pace
        ),
        None,
    )
    pre_time = selected.lap_start_time_seconds
    post_time = post_lap.lap_end_time_seconds if post_lap else None
    pre_pair = _paired_timing_at_or_before(dataset.timing, focal_driver, rival_driver, pre_time)
    post_pair = _paired_timing_at_or_after(dataset.timing, focal_driver, rival_driver, post_time)
    pre_gap = _direct_gap(pre_pair)
    post_gap = _direct_gap(post_pair)
    change = post_gap - pre_gap if pre_gap is not None and post_gap is not None else None
    unavailable_reasons: list[str] = []
    if pre_gap is None:
        unavailable_reasons.append(_pit_gap_unavailable_reason("pre_stop", pre_pair))
    if post_lap is None:
        unavailable_reasons.append("eligible_post_stop_lap_unavailable")
    elif post_gap is None:
        unavailable_reasons.append(_pit_gap_unavailable_reason("post_stop", post_pair))
    if pit_out is None:
        unavailable_reasons.append("pit_out_boundary_unavailable")
    rival_stopped = any(
        pit_in_lap <= lap.lap_number <= window_end
        and (lap.is_pit_in_lap or lap.is_pit_out_lap)
        for lap in rival_laps
    )
    neutralized = any(
        pit_in_lap <= lap.lap_number <= window_end
        and bool(_status_codes(lap.track_status) & NEUTRALIZED_STATUS_CODES)
        for lap in analysis.laps
    )
    exact_start = selected.pit_in_time_seconds
    exact_end = pit_out.pit_out_time_seconds if pit_out else None
    pit_duration = (
        exact_end - exact_start
        if exact_start is not None and exact_end is not None and exact_end >= exact_start
        else None
    )
    precision: Literal["exact", "lap_bounded", "unavailable"] = (
        "exact" if pit_duration is not None else "lap_bounded" if pit_out else "unavailable"
    )
    status: Literal["available", "partial", "confounded", "unavailable"]
    if pre_gap is None and post_gap is None:
        status = "unavailable"
    elif change is None:
        status = "partial"
    elif rival_stopped or neutralized:
        status = "confounded"
    elif change is not None:
        status = "available"
    else:
        status = "unavailable"
    warnings: list[str] = []
    if rival_stopped:
        warnings.append("The rival stopped inside the comparison window.")
    if neutralized:
        warnings.append("The comparison window includes neutralized running.")
    if change is None:
        warnings.append("Numeric direct-gap coverage is insufficient for measured gap change.")
    rejoin_context = _build_rejoin_context(
        dataset,
        analysis,
        focal_driver=focal_driver,
        pit_out_lap=pit_out_lap,
        pit_out_time_seconds=exact_end,
    )
    execution = _build_stop_execution_result(
        analysis,
        focal_driver=focal_driver,
        rival_driver=rival_driver,
        selected_pit_in_lap=pit_in_lap,
        pit_duration=pit_duration,
    )
    return PitCycleResult(
        status=status,
        focal_driver=focal_driver,
        rival_driver=rival_driver,
        focal_stop_number=focal_stop_number,
        pit_in_lap=pit_in_lap,
        pit_out_lap=pit_out.lap_number if pit_out else None,
        pre_reference_lap=max(1, pit_in_lap - 1),
        post_reference_lap=post_lap.lap_number if post_lap else None,
        window_end_lap=window_end,
        pre_direct_gap_seconds=pre_gap,
        post_direct_gap_seconds=post_gap,
        measured_gap_change_seconds=change,
        pre_positions=_pair_positions(pre_pair),
        post_positions=_pair_positions(post_pair),
        pit_lane_duration_seconds=pit_duration,
        pit_interval_precision=precision,
        rival_stopped_in_window=rival_stopped,
        neutralized_in_window=neutralized,
        source_fields=[
            "timing.gap_to_leader_seconds",
            "laps.pit_in_time_seconds",
            "laps.pit_out_time_seconds",
            "laps.track_status",
        ],
        measured_values={
            "pre_direct_gap_seconds": pre_gap,
            "post_direct_gap_seconds": post_gap,
            "measured_gap_change_seconds": change,
            "pit_lane_duration_seconds": pit_duration,
        },
        rejoin_context=rejoin_context,
        execution_breakdown=execution,
        unavailable_reasons=unavailable_reasons,
        warnings=warnings,
        limitations=[
            "This retrospective comparison does not estimate a counterfactual no-stop outcome.",
            "Observed gap change across the selected pit-cycle window does not establish that the pit stop caused the change.",
        ],
    )


def _pit_gap_unavailable_reason(
    prefix: str,
    pair: tuple[TimingStreamRecord, TimingStreamRecord] | None,
) -> str:
    if pair is None:
        return f"{prefix}_paired_timing_unavailable"
    if pair[0].gap_to_leader_laps is not None or pair[1].gap_to_leader_laps is not None:
        return f"{prefix}_gap_is_lap_valued"
    return f"{prefix}_numeric_gap_unavailable"


def _build_stop_execution_result(
    analysis: StrategyAnalysisResult,
    *,
    focal_driver: str,
    rival_driver: str,
    selected_pit_in_lap: int,
    pit_duration: float | None,
) -> StopExecutionResult:
    if pit_duration is None:
        return StopExecutionResult(
            method_version=2,
            status="unavailable",
            compatibility_flags=["exact_pit_in_or_pit_out_timestamp_missing"],
        )
    candidates: list[tuple[int, int, str, int, float, list[str]]] = []
    for driver_priority, driver in enumerate((focal_driver, rival_driver)):
        driver_laps = sorted(
            (lap for lap in analysis.laps if lap.driver == driver),
            key=lambda lap: lap.lap_number,
        )
        pit_ins = [lap for lap in driver_laps if lap.is_pit_in_lap]
        for stop_index, pit_in in enumerate(pit_ins, start=1):
            if driver == focal_driver and pit_in.lap_number == selected_pit_in_lap:
                continue
            pit_out = next(
                (
                    lap
                    for lap in driver_laps
                    if lap.lap_number >= pit_in.lap_number and lap.is_pit_out_lap
                ),
                None,
            )
            if (
                pit_out is None
                or pit_in.pit_in_time_seconds is None
                or pit_out.pit_out_time_seconds is None
                or pit_out.pit_out_time_seconds < pit_in.pit_in_time_seconds
            ):
                continue
            duration = pit_out.pit_out_time_seconds - pit_in.pit_in_time_seconds
            flags = ["queue_or_double_stack_status_unavailable"]
            if any(
                bool(_status_codes(lap.track_status) & NEUTRALIZED_STATUS_CODES)
                for lap in (pit_in, pit_out)
            ):
                flags.append("neutralized_running")
            candidates.append(
                (
                    driver_priority,
                    abs(pit_in.lap_number - selected_pit_in_lap),
                    driver,
                    stop_index,
                    duration,
                    flags,
                )
            )
    if not candidates:
        return StopExecutionResult(
            method_version=2,
            status="available",
            pit_lane_duration_seconds=pit_duration,
            ranking_allowed=False,
            compatibility_flags=["measured_comparison_stop_unavailable"],
        )
    _, _, driver, stop_index, comparison_duration, flags = min(
        candidates,
        key=lambda item: (item[0], item[1], item[2], item[3]),
    )
    return StopExecutionResult(
        method_version=2,
        status="available",
        pit_lane_duration_seconds=pit_duration,
        comparison_source=f"{driver} Stop {stop_index}",
        comparison_duration_seconds=comparison_duration,
        signed_duration_delta_seconds=pit_duration - comparison_duration,
        ranking_allowed=False,
        compatibility_flags=flags,
    )


def strategy_metadata(
    analysis: StrategyAnalysisResult,
    *,
    result_kind: str,
    results: dict[str, Any] | None = None,
    maximum_laps: int = 500,
) -> dict[str, Any]:
    """Return bounded, deterministic artifact metadata shared by recipes."""

    included = [lap.lap_number for lap in analysis.laps if lap.is_representative_for_pace]
    excluded: dict[str, list[int]] = defaultdict(list)
    for lap in analysis.laps:
        for reason in lap.pace_exclusion_reasons:
            excluded[reason].append(lap.lap_number)
    bounded_laps = analysis.laps[:maximum_laps]
    return {
        "strategy_analysis_schema_version": analysis.schema_version,
        "strategy_method_versions": analysis.method_versions,
        "result_kind": result_kind,
        "requested_policy": analysis.requested_policy.model_dump(mode="json"),
        "effective_policy": analysis.effective_policy.model_dump(mode="json"),
        "source_coverage": analysis.source_coverage,
        "included_lap_numbers": included[:maximum_laps],
        "excluded_lap_numbers_by_reason": {
            reason: values[:maximum_laps] for reason, values in sorted(excluded.items())
        },
        "strategy_laps": [lap.model_dump(mode="json") for lap in bounded_laps],
        "strategy_laps_truncated": len(analysis.laps) > maximum_laps,
        "stint_summaries": [stint.model_dump(mode="json") for stint in analysis.stints],
        "analytical_results": results or {},
        "analytical_basis": {
            "representative_sample_count": len(included),
            "excluded_sample_count": sum(
                1 for lap in analysis.laps if not lap.is_representative_for_pace
            ),
            "stint_count": len(analysis.stints),
        },
        "strategy_warnings": analysis.warnings,
        "strategy_limitations": analysis.limitations,
    }


def _resolve_effective_stints(
    laps: list[LapRecord],
) -> list[tuple[int, Literal["source", "derived", "conflicting", "unavailable"], int, bool]]:
    result: list[tuple[int, Literal["source", "derived", "conflicting", "unavailable"], int, bool]] = []
    effective_stint = 0
    progress = 0
    previous: LapRecord | None = None
    for lap in laps:
        source_change = previous is not None and lap.stint != previous.stint
        compound_change = previous is not None and _compound(lap.compound) != _compound(previous.compound)
        pit_boundary = bool(previous and previous.is_pit_in_lap) or lap.is_pit_out_lap
        new_stint = previous is None or source_change or compound_change or pit_boundary
        if new_stint:
            effective_stint += 1
            progress = 1
        else:
            progress += max(1, lap.lap_number - (previous.lap_number if previous else lap.lap_number))
        conflict = False
        if previous is not None:
            if compound_change and not source_change and not pit_boundary:
                conflict = True
            if lap.stint is not None and previous.stint is not None and lap.stint < previous.stint:
                conflict = True
        if conflict:
            source: Literal["source", "derived", "conflicting", "unavailable"] = "conflicting"
        elif lap.stint is not None:
            source = "source"
        elif effective_stint:
            source = "derived"
        else:
            source = "unavailable"
        result.append((effective_stint, source, progress, conflict))
        previous = lap
    return result


def _resolve_tyre_ages(
    laps: list[LapRecord],
    stint_state: list[tuple[int, str, int, bool]],
    records: list[TimingAppRecord],
) -> list[tuple[float | None, Literal["source", "derived", "unavailable"]]]:
    result: list[tuple[float | None, Literal["source", "derived", "unavailable"]]] = [
        (None, "unavailable") for _ in laps
    ]
    by_stint: dict[int, list[int]] = defaultdict(list)
    for index, state in enumerate(stint_state):
        by_stint[state[0]].append(index)
    for indices in by_stint.values():
        candidate_records = [
            record
            for record in records
            if record.total_laps is not None
            and any(
                (record.stint is not None and record.stint == laps[index].stint)
                or (record.lap_number is not None and record.lap_number == laps[index].lap_number)
                for index in indices
            )
        ]
        anchors: list[tuple[int, float]] = []
        for record in candidate_records:
            if record.lap_number is not None and record.total_laps is not None:
                anchors.append((record.lap_number, float(record.total_laps)))
        for index in indices:
            lap = laps[index]
            exact = next((age for number, age in anchors if number == lap.lap_number), None)
            if exact is not None:
                result[index] = (max(0.0, exact), "source")
                continue
            if anchors:
                number, age = min(anchors, key=lambda pair: abs(pair[0] - lap.lap_number))
                derived = age + (lap.lap_number - number)
                if derived >= 0:
                    result[index] = (derived, "derived")
                    continue
            start_age = next(
                (
                    float(record.start_laps)
                    for record in candidate_records
                    if record.start_laps is not None
                ),
                None,
            )
            if start_age is not None:
                first_lap = laps[indices[0]].lap_number
                result[index] = (start_age + lap.lap_number - first_lap, "derived")
    return result


def _build_stint_summaries(laps: list[StrategyLap]) -> list[StintSummary]:
    grouped: dict[tuple[str, int], list[StrategyLap]] = defaultdict(list)
    for lap in laps:
        if lap.effective_stint is not None:
            grouped[(lap.driver, lap.effective_stint)].append(lap)
    summaries: list[StintSummary] = []
    for (driver, stint), group in sorted(grouped.items()):
        ordered = sorted(group, key=lambda item: item.lap_number)
        representative = [
            lap
            for lap in ordered
            if lap.is_representative_for_pace
            and lap.lap_time_seconds is not None
            and lap.stint_source != "conflicting"
        ]
        tyre_samples = [(lap.tyre_age, lap.lap_time_seconds) for lap in representative if lap.tyre_age is not None]
        tyre_monotonic = all(
            tyre_samples[index][0] <= tyre_samples[index + 1][0]
            for index in range(len(tyre_samples) - 1)
        )
        if tyre_samples and tyre_monotonic:
            fit = observed_pace_evolution(
                ((x or 0.0, y or 0.0) for x, y in tyre_samples),
                basis="tyre_age",
                expected_count=len(ordered),
            )
            if fit.status == "unavailable":
                fit = observed_pace_evolution(
                    ((lap.stint_progress or 0, lap.lap_time_seconds or 0.0) for lap in representative),
                    basis="stint_progress",
                    expected_count=len(ordered),
                )
        else:
            fit = observed_pace_evolution(
                ((lap.stint_progress or 0, lap.lap_time_seconds or 0.0) for lap in representative),
                basis="stint_progress",
                expected_count=len(ordered),
            )
            if tyre_samples and not tyre_monotonic:
                fit.warnings.append("Source tyre age was non-monotonic; used stint-progress fallback.")
        sectors = [
            SectorEvolutionResult(
                sector=sector,
                raw_times_seconds=[
                    value
                    for lap in representative
                    if (value := getattr(lap, f"sector_{sector}_time_seconds")) is not None
                ],
                fit=observed_pace_evolution(
                    (
                        (
                            lap.tyre_age if fit.basis == "tyre_age" else lap.stint_progress or 0,
                            value,
                        )
                        for lap in representative
                        if (value := getattr(lap, f"sector_{sector}_time_seconds")) is not None
                        and (fit.basis != "tyre_age" or lap.tyre_age is not None)
                    ),
                    basis=fit.basis,
                    expected_count=len(ordered),
                ),
            )
            for sector in (1, 2, 3)
        ]
        exclusions: dict[str, list[int]] = defaultdict(list)
        for lap in ordered:
            for reason in lap.pace_exclusion_reasons:
                exclusions[reason].append(lap.lap_number)
        compounds = [lap.compound for lap in ordered if lap.compound]
        tyre_sources = {lap.tyre_age_source for lap in ordered if lap.tyre_age is not None}
        tyre_source: Literal["source", "derived", "unavailable"] = (
            "source" if tyre_sources == {"source"} else "derived" if tyre_sources else "unavailable"
        )
        summaries.append(
            StintSummary(
                driver=driver,
                effective_stint=stint,
                start_lap=ordered[0].lap_number,
                end_lap=ordered[-1].lap_number,
                compound=compounds[0] if compounds and len(set(compounds)) == 1 else None,
                stint_source=(
                    "conflicting"
                    if any(lap.stint_source == "conflicting" for lap in ordered)
                    else ordered[0].stint_source
                ),
                tyre_age_source=tyre_source,
                tyre_age_coverage_numerator=sum(1 for lap in ordered if lap.tyre_age is not None),
                tyre_age_coverage_denominator=len(ordered),
                measured_lap_count=len(ordered),
                representative_lap_count=len(representative),
                included_lap_numbers=[lap.lap_number for lap in representative],
                excluded_lap_numbers_by_reason=dict(sorted(exclusions.items())),
                statistics=descriptive_statistics(
                    lap.lap_time_seconds or 0.0 for lap in representative
                ),
                pace_evolution=fit,
                sector_evolution=sectors,
                warnings=(
                    ["Compound evidence conflicts inside the effective stint."]
                    if not compounds or len(set(compounds)) != 1
                    else []
                ),
                limitations=["Statistics use representative laps only."],
            )
        )
    return summaries


def _pace_exclusion_reasons(
    lap: LapRecord,
    policy: StrategyExclusionPolicy,
    status_codes: set[str],
) -> list[str]:
    reasons: list[str] = []
    if lap.lap_time_seconds is None:
        reasons.append("missing_lap_time")
    if policy.exclude_first_race_lap and lap.lap_number == 1:
        reasons.append("first_race_lap")
    if policy.exclude_pit_in_laps and lap.is_pit_in_lap:
        reasons.append("pit_in_lap")
    if policy.exclude_pit_out_laps and lap.is_pit_out_lap:
        reasons.append("pit_out_lap")
    if policy.exclude_deleted_laps and lap.is_deleted:
        reasons.append("deleted_lap")
    if policy.exclude_generated_laps and lap.is_generated:
        reasons.append("generated_lap")
    if policy.exclude_inaccurate_laps and lap.is_accurate is False:
        reasons.append("inaccurate_lap")
    if policy.require_complete_sectors and any(
        value is None
        for value in (
            lap.sector_1_time_seconds,
            lap.sector_2_time_seconds,
            lap.sector_3_time_seconds,
        )
    ):
        reasons.append("incomplete_sectors")
    if (
        policy.exclude_non_green_status
        and status_codes
        and any(code not in set(policy.green_track_status_codes) for code in status_codes)
    ):
        reasons.append("non_green_track_status")
    if lap.lap_time_seconds is not None and not isfinite(lap.lap_time_seconds):
        reasons.append("non_finite_lap_time")
    return _ordered(reasons, PACE_EXCLUSION_REASON_ORDER)


def _measured_gap_delta(
    dataset: SessionDataset,
    analysis: StrategyAnalysisResult,
    focal: str,
    reference: str,
    lap_range: tuple[int | None, int | None] | None,
) -> RaceTimeDeltaResult:
    focal_laps = [lap for lap in analysis.laps if lap.driver == focal and _inside(lap.lap_number, lap_range)]
    expected = [lap for lap in focal_laps]
    raw_points: list[tuple[int, float]] = []
    lap_by_number = {lap.lap_number: lap for lap in focal_laps}
    excluded: list[int] = []
    for lap in expected:
        pair = _paired_timing_at_or_before(
            dataset.timing, focal, reference, lap.lap_end_time_seconds
        )
        gap = _direct_gap(pair)
        if (
            pair is not None
            and lap.lap_start_time_seconds is not None
            and pair[0].session_time_seconds < lap.lap_start_time_seconds
        ):
            gap = None
        if gap is None:
            excluded.append(lap.lap_number)
        else:
            raw_points.append((lap.lap_number, gap))
    baseline = raw_points[0][1] if raw_points else None
    points = [DeltaPoint(lap_number=lap, value_seconds=gap - (baseline or 0.0)) for lap, gap in raw_points]
    overall = raw_points[-1][1] - raw_points[0][1] if len(raw_points) >= 2 else None
    denominator = len(expected)
    stint_changes: dict[str, float] = {}
    green_change = 0.0
    green_pair_count = 0
    raw_by_lap = dict(raw_points)
    by_stint: dict[int, list[int]] = defaultdict(list)
    for lap_number, _ in raw_points:
        lap = lap_by_number[lap_number]
        if lap.effective_stint is not None:
            by_stint[lap.effective_stint].append(lap_number)
    for stint, lap_numbers in sorted(by_stint.items()):
        if len(lap_numbers) >= 2:
            stint_changes[f"stint_{stint}"] = raw_by_lap[lap_numbers[-1]] - raw_by_lap[lap_numbers[0]]
    for (previous_lap, previous_gap), (current_lap, current_gap) in zip(raw_points, raw_points[1:]):
        previous = lap_by_number[previous_lap]
        current = lap_by_number[current_lap]
        if (
            current_lap == previous_lap + 1
            and previous.effective_stint == current.effective_stint
            and not previous.is_pit_in_lap
            and not previous.is_pit_out_lap
            and not current.is_pit_in_lap
            and not current.is_pit_out_lap
            and not (_status_codes(previous.track_status) & NEUTRALIZED_STATUS_CODES)
            and not (_status_codes(current.track_status) & NEUTRALIZED_STATUS_CODES)
        ):
            green_change += current_gap - previous_gap
            green_pair_count += 1
    omitted = overall - green_change if overall is not None and green_pair_count else overall
    return RaceTimeDeltaResult(
        result_kind="measured_gap_change",
        value_category="measured",
        status="available" if overall is not None else "unavailable",
        focal_driver=focal,
        benchmark=reference,
        start_lap=raw_points[0][0] if raw_points else None,
        end_lap=raw_points[-1][0] if raw_points else None,
        points=points,
        direct_gap_points=[
            DeltaPoint(lap_number=lap, value_seconds=gap)
            for lap, gap in raw_points
        ],
        excluded_laps=excluded,
        paired_sample_count=len(points),
        coverage_numerator=len(points),
        coverage_denominator=denominator,
        coverage_percentage=_percentage(len(points), denominator),
        overall_change_seconds=overall,
        stint_changes_seconds=stint_changes,
        green_running_change_seconds=green_change if green_pair_count else None,
        omitted_remainder_seconds=omitted,
        limitations=["Measured direct-gap change depends on reliable numeric timing-stream coverage."],
    )


def _derived_pace_delta(
    analysis: StrategyAnalysisResult,
    focal: str,
    benchmark: str,
    lap_range: tuple[int | None, int | None] | None,
) -> RaceTimeDeltaResult:
    by_lap: dict[int, list[StrategyLap]] = defaultdict(list)
    for lap in analysis.laps:
        if _inside(lap.lap_number, lap_range):
            by_lap[lap.lap_number].append(lap)
    cumulative = 0.0
    baseline_difference: float | None = None
    points: list[DeltaPoint] = []
    excluded: list[int] = []
    expected_laps = sorted(by_lap)
    for lap_number in expected_laps:
        laps = [lap for lap in by_lap[lap_number] if lap.is_representative_for_pace and lap.lap_time_seconds is not None]
        focal_lap = next((lap for lap in laps if lap.driver == focal), None)
        benchmark_time: float | None
        if benchmark == "field_median":
            benchmark_time = type7_quantile((lap.lap_time_seconds or 0.0 for lap in laps if lap.driver != focal), 0.5)
        elif benchmark == "fastest_representative":
            values = [lap.lap_time_seconds or 0.0 for lap in laps if lap.driver != focal]
            benchmark_time = min(values) if values else None
        else:
            reference = next((lap for lap in laps if lap.driver == benchmark), None)
            benchmark_time = reference.lap_time_seconds if reference else None
        if focal_lap is None or benchmark_time is None:
            excluded.append(lap_number)
            continue
        paired_difference = (focal_lap.lap_time_seconds or 0.0) - benchmark_time
        if baseline_difference is None:
            baseline_difference = paired_difference
        else:
            cumulative += paired_difference
        points.append(DeltaPoint(lap_number=lap_number, value_seconds=cumulative))
    denominator = len(expected_laps)
    return RaceTimeDeltaResult(
        result_kind="derived_cumulative_pace_delta",
        value_category="derived",
        status="available" if points else "unavailable",
        focal_driver=focal,
        benchmark=benchmark,
        start_lap=points[0].lap_number if points else None,
        end_lap=points[-1].lap_number if points else None,
        points=points,
        excluded_laps=excluded,
        paired_sample_count=len(points),
        coverage_numerator=len(points),
        coverage_denominator=denominator,
        coverage_percentage=_percentage(len(points), denominator),
        overall_change_seconds=points[-1].value_seconds if points else None,
        limitations=["Pit and neutralized laps are excluded; this is not measured race gap."],
    )


def _group_timing(records: list[TimingStreamRecord]) -> dict[str, list[TimingStreamRecord]]:
    grouped: dict[str, list[TimingStreamRecord]] = defaultdict(list)
    for record in records:
        grouped[record.driver].append(record)
    return {key: sorted(value, key=lambda item: item.session_time_seconds) for key, value in grouped.items()}


def _group_timing_app(records: list[TimingAppRecord]) -> dict[str, list[TimingAppRecord]]:
    grouped: dict[str, list[TimingAppRecord]] = defaultdict(list)
    for record in records:
        grouped[record.driver].append(record)
    return {key: sorted(value, key=lambda item: item.session_time_seconds) for key, value in grouped.items()}


def _timing_at_lap_end(records: list[TimingStreamRecord], lap: LapRecord) -> TimingStreamRecord | None:
    if not records:
        return None
    boundary = lap.lap_end_time_seconds
    if boundary is None:
        return None
    candidates = [record for record in records if record.session_time_seconds <= boundary]
    return candidates[-1] if candidates else None


def _paired_timing_at_or_before(
    records: list[TimingStreamRecord], focal: str, rival: str, time: float | None
) -> tuple[TimingStreamRecord, TimingStreamRecord] | None:
    if time is None:
        return None
    state: dict[str, TimingStreamRecord] = {}
    candidate: tuple[TimingStreamRecord, TimingStreamRecord] | None = None
    for record in sorted(records, key=lambda item: item.session_time_seconds):
        if record.session_time_seconds > time:
            break
        if record.driver not in {focal, rival}:
            continue
        state[record.driver] = record
        pair = _timing_pair_from_state(state, focal, rival)
        if _direct_gap(pair) is not None:
            candidate = pair
    return candidate


def _paired_timing_at_or_after(
    records: list[TimingStreamRecord], focal: str, rival: str, time: float | None
) -> tuple[TimingStreamRecord, TimingStreamRecord] | None:
    if time is None:
        return None
    ordered = sorted(records, key=lambda item: item.session_time_seconds)
    state = _timing_state_at_or_before(ordered, time)
    for record in ordered:
        if record.session_time_seconds < time:
            continue
        state[record.driver] = record
        pair = _timing_pair_from_state(state, focal, rival)
        if _direct_gap(pair) is not None:
            return pair
    return None


def _timing_pair_from_state(
    state: dict[str, TimingStreamRecord], focal: str, rival: str
) -> tuple[TimingStreamRecord, TimingStreamRecord] | None:
    if focal not in state or rival not in state:
        return None
    return state[focal], state[rival]


def _timing_state_at_or_before(
    records: list[TimingStreamRecord], time: float
) -> dict[str, TimingStreamRecord]:
    state: dict[str, TimingStreamRecord] = {}
    for record in sorted(records, key=lambda item: item.session_time_seconds):
        if record.session_time_seconds > time:
            break
        state[record.driver] = record
    return state


def _direct_gap(pair: tuple[TimingStreamRecord, TimingStreamRecord] | None) -> float | None:
    if pair is None:
        return None
    focal, rival = pair
    if focal.gap_to_leader_laps is not None or rival.gap_to_leader_laps is not None:
        return None
    if focal.gap_to_leader_seconds is None or rival.gap_to_leader_seconds is None:
        return None
    return focal.gap_to_leader_seconds - rival.gap_to_leader_seconds


def _pair_positions(
    pair: tuple[TimingStreamRecord, TimingStreamRecord] | None,
) -> dict[str, int | None]:
    if pair is None:
        return {}
    return {pair[0].driver: pair[0].position, pair[1].driver: pair[1].position}


def _build_rejoin_context(
    dataset: SessionDataset,
    analysis: StrategyAnalysisResult,
    *,
    focal_driver: str,
    pit_out_lap: int,
    pit_out_time_seconds: float | None,
) -> RejoinContextResult:
    focal_lap = next(
        (
            lap
            for lap in analysis.laps
            if lap.driver == focal_driver and lap.lap_number == pit_out_lap
        ),
        None,
    )
    boundary = pit_out_time_seconds
    precision: Literal["exact", "lap_bounded", "unavailable"] = "exact"
    if boundary is None:
        boundary = focal_lap.lap_start_time_seconds if focal_lap else None
        precision = "lap_bounded" if boundary is not None else "unavailable"
    if boundary is None:
        return RejoinContextResult(
            method_version=2,
            status="unavailable",
            reference_precision="unavailable",
            reference_lap=pit_out_lap,
            warnings=["Pit-out timing is unavailable."],
        )
    focal_records = sorted(
        (
            record
            for record in dataset.timing
            if record.driver == focal_driver and record.session_time_seconds >= boundary
        ),
        key=lambda record: record.session_time_seconds,
    )
    if not focal_records:
        return RejoinContextResult(
            method_version=2,
            status="unavailable",
            reference_precision=precision,
            reference_lap=pit_out_lap,
            warnings=["No timing sample is available at or after pit-out."],
        )
    reference = focal_records[0]
    state = [
        record
        for record in _timing_state_at_or_before(
            dataset.timing,
            reference.session_time_seconds,
        ).values()
        if record.position is not None
    ]
    state.sort(key=lambda record: (record.position or 999, record.driver))
    focal_index = next(
        (index for index, record in enumerate(state) if record.driver == focal_driver),
        None,
    )
    if focal_index is None:
        return RejoinContextResult(
            method_version=2,
            status="unavailable",
            reference_precision=precision,
            reference_time_seconds=reference.session_time_seconds,
            reference_lap=pit_out_lap,
            warnings=["Focal running order is unavailable at the rejoin reference."],
        )
    selected_state = state[max(0, focal_index - 2) : focal_index + 3]
    strategy_by_driver = {
        lap.driver: lap
        for lap in analysis.laps
        if lap.lap_number == pit_out_lap
    }
    participants: list[TrafficParticipant] = []
    for record in selected_state:
        relation: Literal["ahead", "focal", "behind"] = (
            "focal"
            if record.driver == focal_driver
            else "ahead"
            if (record.position or 999) < (reference.position or 999)
            else "behind"
        )
        relative_seconds = None
        if (
            record.gap_to_leader_seconds is not None
            and reference.gap_to_leader_seconds is not None
        ):
            relative_seconds = abs(
                record.gap_to_leader_seconds - reference.gap_to_leader_seconds
            )
        context_lap = strategy_by_driver.get(record.driver)
        participants.append(
            TrafficParticipant(
                driver=record.driver,
                position=record.position,
                relation=relation,
                focal_relative_seconds=relative_seconds,
                focal_relative_laps=record.gap_to_leader_laps,
                compound=context_lap.compound if context_lap else None,
                tyre_age=context_lap.tyre_age if context_lap else None,
                tyre_age_source=context_lap.tyre_age_source if context_lap else "unavailable",
            )
        )
    ahead = [participant for participant in participants if participant.relation == "ahead"]
    if ahead and any(participant.focal_relative_seconds is None for participant in ahead):
        traffic = "unavailable"
    else:
        close_ahead = [
            participant
            for participant in ahead
            if participant.focal_relative_seconds is not None
            and participant.focal_relative_seconds <= 3.0
        ]
        traffic = (
            "clean_air"
            if not close_ahead
            else "single_car"
            if len(close_ahead) == 1
            else "traffic_group"
        )
    event = None
    window_end = pit_out_lap + 3
    nearby_drivers = {participant.driver for participant in participants if participant.driver != focal_driver}
    later_pit = next(
        (
            lap
            for lap in analysis.laps
            if lap.driver in nearby_drivers
            and pit_out_lap < lap.lap_number <= window_end
            and (lap.is_pit_in_lap or lap.is_pit_out_lap)
        ),
        None,
    )
    if later_pit:
        event = f"{later_pit.driver} pitted within {later_pit.lap_number - pit_out_lap} laps"
    target_lap = pit_out_lap + 3
    after_positions = {
        driver: next(
            (
                lap.position
                for lap in analysis.laps
                if lap.driver == driver and lap.lap_number == target_lap
            ),
            None,
        )
        for driver in sorted({participant.driver for participant in participants})
    }
    return RejoinContextResult(
        method_version=2,
        status="available" if participants else "unavailable",
        reference_precision=precision,
        reference_time_seconds=reference.session_time_seconds,
        reference_lap=pit_out_lap,
        participants=participants,
        traffic_classification=traffic,  # type: ignore[arg-type]
        next_observed_event=event,
        relative_position_after_three_laps=after_positions,
    )


def _fit_quality(sample_count: int, coverage: float, mad: float) -> Literal["high", "medium", "low", "provisional"]:
    if sample_count >= 12 and coverage >= 0.85 and mad <= 0.350:
        return "high"
    if sample_count >= 8 and coverage >= 0.75 and mad <= 0.750:
        return "medium"
    if sample_count >= 8:
        return "low"
    return "provisional"


def _status_codes(value: str | None) -> set[str]:
    if value is None:
        return set()
    return {character for character in str(value).strip() if character.isalnum()}


def _compound(value: str | None) -> str | None:
    normalized = str(value).strip().upper() if value is not None else ""
    return normalized or None


def _ordered(values: Iterable[str], order: Iterable[str]) -> list[str]:
    unique = set(values)
    rank = {value: index for index, value in enumerate(order)}
    return sorted(unique, key=lambda value: (rank.get(value, len(rank)), value))


def _inside(value: int | float | None, bounds: tuple[Any, Any] | None) -> bool:
    if bounds is None:
        return True
    if value is None:
        return False
    start, end = bounds
    return (start is None or value >= start) and (end is None or value <= end)


def _percentage(numerator: int, denominator: int) -> float:
    return (100.0 * numerator / denominator) if denominator else 0.0

"""Shared helpers for chart recipe parameters."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from typing import Any

from f1_telemetry_charts.config.models import ChartRecipeConfig
from f1_telemetry_charts.data.models import LapRecord, SessionDataset, TelemetrySample

BOX_LAP_POLICIES = {
    "include_all",
    "exclude_in_laps",
    "exclude_out_laps",
    "exclude_in_and_out_laps",
    "only_in_laps",
    "only_out_laps",
}

DRIVER_SELECTION_MODES = {"all_session", "selected", "top_n", "teams"}
DRIVER_ORDERS = {
    "classification",
    "fastest_lap",
    "team",
    "grid",
    "selection_order",
    "custom",
}

LAP_DELETED_POLICIES = {"exclude", "include"}
LAP_GENERATED_POLICIES = {"exclude", "include"}
ACCURACY_FILTERS = {"all", "accurate_only"}
TRACK_STATUS_FILTERS = {
    "all",
    "green_only",
    "green_or_yellow",
    "exclude_sc",
    "exclude_sc_and_vsc",
    "custom",
}
TRACK_STATUS_MATCHES = {"any_overlap", "full_lap", "status_at_lap_end"}
MISSING_SERIES_POLICIES = {"error", "warn_skip", "silent_skip"}
TELEMETRY_GAP_POLICIES = {"preserve", "interpolate_continuous", "resample"}
CONTINUOUS_TELEMETRY_METRICS = {"speed_kph", "throttle_percent", "rpm"}
TRACK_STATUS_CODES = {
    "green": {"1"},
    "yellow": {"2"},
    "sc": {"4"},
    "red": {"5"},
    "vsc": {"6", "7"},
}
FALLBACK_COLORS = [
    "#1F77B4",
    "#FF7F0E",
    "#2CA02C",
    "#D62728",
    "#9467BD",
    "#8C564B",
    "#E377C2",
    "#7F7F7F",
    "#BCBD22",
    "#17BECF",
]
DEFAULT_COMPOUND_COLORS = {
    "SOFT": "#DA291C",
    "MEDIUM": "#FFD12E",
    "HARD": "#F0F0EC",
    "INTERMEDIATE": "#43B02A",
    "WET": "#0067AD",
}


@dataclass
class ParameterDiagnostics:
    warnings: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    exclusion_counts: dict[str, int] = field(default_factory=dict)
    active_filter_summary: list[str] = field(default_factory=list)

    def warn(self, field_name: str, message: str, **extra: Any) -> None:
        self.warnings.append({"field": field_name, "message": message, **extra})

    def error(self, field_name: str, message: str, **extra: Any) -> None:
        self.errors.append({"field": field_name, "message": message, **extra})

    def count(self, reason: str) -> None:
        self.exclusion_counts[reason] = self.exclusion_counts.get(reason, 0) + 1


@dataclass
class LapFilterResult:
    laps: list[LapRecord]
    diagnostics: ParameterDiagnostics
    effective: dict[str, Any]


@dataclass
class ResolvedStyle:
    color: str
    source: str
    label: str | None = None
    fallback: bool = False

    def as_metadata(self) -> dict[str, Any]:
        return {
            "color": self.color,
            "source": self.source,
            "label": self.label,
            "fallback": self.fallback,
        }


def parameters(config: ChartRecipeConfig) -> dict[str, Any]:
    return config.parameters or {}


def section(config: ChartRecipeConfig, name: str) -> dict[str, Any]:
    value = parameters(config).get(name)
    if value in (None, {}):
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def parameter_value(
    config: ChartRecipeConfig,
    name: str,
    *,
    section_name: str | None = None,
    default: Any = None,
) -> Any:
    params = parameters(config)
    if name in params:
        return params[name]
    if section_name is not None:
        scoped = section(config, section_name)
        if name in scoped:
            return scoped[name]
    return default


def nested_parameter_value(
    config: ChartRecipeConfig,
    section_name: str,
    object_name: str,
    name: str,
    *,
    default: Any = None,
) -> Any:
    params = parameters(config)
    if name in params:
        return params[name]
    scoped = section(config, section_name)
    nested = scoped.get(object_name)
    if isinstance(nested, dict) and name in nested:
        return nested[name]
    if name in scoped:
        return scoped[name]
    return default


def selected_driver_codes(dataset: SessionDataset, config: ChartRecipeConfig) -> list[str]:
    available = [driver.abbreviation for driver in dataset.drivers]
    params = parameters(config)
    selection = section(config, "selection")
    driver_selection = _driver_selection_object(selection)
    mode = (
        driver_selection.get("driver_selection_mode")
        or driver_selection.get("mode")
        or selection.get("driver_selection_mode")
        or params.get("driver_selection_mode")
    )
    requested = None
    for source in (driver_selection, selection, params):
        if "drivers" in source:
            requested = source["drivers"]
            break

    if mode is None:
        mode = "selected" if requested not in (None, []) else "all_session"
    mode = str(mode)
    if mode not in DRIVER_SELECTION_MODES:
        raise ValueError(f"driver_selection_mode unsupported value: {mode}")

    if mode == "all_session":
        selected = available
    elif mode == "selected":
        selected = _requested_driver_list(requested, available)
        if not selected:
            raise ValueError("drivers must include at least one selected driver")
    elif mode == "teams":
        teams = driver_selection.get("teams") or selection.get("teams") or params.get("teams")
        if not isinstance(teams, list) or not teams:
            raise ValueError("teams is required when driver_selection_mode is teams")
        selected = [
            driver.abbreviation
            for driver in dataset.drivers
            if driver.team_name in {str(team) for team in teams}
        ]
    else:
        top_n = driver_selection.get("top_n") or selection.get("top_n") or params.get("top_n")
        if top_n is None:
            raise ValueError("top_n is required when driver_selection_mode is top_n")
        selected = available[: int(top_n)]

    selected = _apply_driver_order(dataset, selected, config, requested)
    limited = _apply_driver_limit(selected, config)
    if not limited:
        raise ValueError("driver selection produced no drivers")
    return limited


def driver_selection_mode(config: ChartRecipeConfig) -> str:
    params = parameters(config)
    selection = section(config, "selection")
    driver_selection = _driver_selection_object(selection)
    mode = (
        driver_selection.get("driver_selection_mode")
        or driver_selection.get("mode")
        or selection.get("driver_selection_mode")
        or params.get("driver_selection_mode")
    )
    if mode is None:
        return "selected" if params.get("drivers") not in (None, []) else "all_session"
    return str(mode)


def lap_in_range(lap_number: int, config: ChartRecipeConfig) -> bool:
    lap_range = effective_lap_range(config)
    if lap_range in (None, {}):
        return True
    if not isinstance(lap_range, dict):
        raise ValueError("lap_range must contain start and end values")
    start = lap_range.get("start")
    end = lap_range.get("end")
    if start is not None and lap_number < int(start):
        return False
    if end is not None and lap_number > int(end):
        return False
    return True


def effective_lap_range(config: ChartRecipeConfig) -> Any:
    params = parameters(config)
    if "lap_range" in params:
        return params.get("lap_range")
    selection = section(config, "selection")
    laps = selection.get("laps")
    if isinstance(laps, dict) and "range" in laps:
        return laps.get("range")
    return selection.get("lap_range")


def filter_laps(laps: list[LapRecord], config: ChartRecipeConfig) -> list[LapRecord]:
    return apply_lap_filters(laps, config).laps


def apply_lap_filters(
    laps: list[LapRecord],
    config: ChartRecipeConfig,
    *,
    require_lap_time: bool | None = None,
    box_policy: str | None = None,
) -> LapFilterResult:
    diagnostics = ParameterDiagnostics()
    lap_validity = lap_validity_policy(config, require_lap_time=require_lap_time)
    track_filter = track_status_filter(config)
    kept: list[LapRecord] = []
    for lap in laps:
        reason = _lap_exclusion_reason(
            lap,
            config,
            lap_validity=lap_validity,
            track_filter=track_filter,
            box_policy=box_policy,
        )
        if reason is None:
            kept.append(lap)
        else:
            diagnostics.count(reason)

    if effective_lap_range(config) not in (None, {}):
        diagnostics.active_filter_summary.append(_range_summary(effective_lap_range(config)))
    if box_policy is not None:
        diagnostics.active_filter_summary.append(f"Box laps: {box_policy}")
    if track_filter["mode"] != "all":
        diagnostics.active_filter_summary.append(f"Track status: {track_filter['mode']}")
    if any(diagnostics.exclusion_counts.values()):
        excluded = sum(diagnostics.exclusion_counts.values())
        diagnostics.active_filter_summary.append(f"Excluded laps: {excluded}")
    if not kept:
        diagnostics.error("filters", "Filtering removed all laps")

    return LapFilterResult(
        laps=kept,
        diagnostics=diagnostics,
        effective={
            "lap_range": effective_lap_range(config),
            "lap_validity": lap_validity,
            "track_status_filter": track_filter,
            "box_lap_policy": box_policy,
            "exclusion_counts": diagnostics.exclusion_counts,
        },
    )


def filter_telemetry(
    samples: list[TelemetrySample], config: ChartRecipeConfig
) -> list[TelemetrySample]:
    return [sample for sample in samples if lap_in_range(sample.lap_number, config)]


def validate_coverage_bounds(
    dataset: SessionDataset,
    config: ChartRecipeConfig,
    *,
    selected_drivers: list[str],
    diagnostics: ParameterDiagnostics,
    include_distance_range: bool = False,
) -> dict[str, Any]:
    bounds = coverage_bounds(dataset, selected_drivers=selected_drivers, config=config)
    _validate_lap_range_bounds(bounds, config, diagnostics, selected_drivers)
    if include_distance_range:
        _validate_distance_range_bounds(bounds, config, diagnostics, selected_drivers)
    return bounds


def coverage_bounds(
    dataset: SessionDataset,
    *,
    selected_drivers: list[str] | None = None,
    config: ChartRecipeConfig | None = None,
) -> dict[str, Any]:
    drivers = selected_drivers or [driver.abbreviation for driver in dataset.drivers]
    driver_set = set(drivers)
    laps = [lap for lap in dataset.laps if lap.driver in driver_set]
    telemetry = [
        sample
        for sample in dataset.telemetry
        if sample.driver in driver_set
        and (config is None or lap_in_range(sample.lap_number, config))
    ]
    track_geometry = dataset.track_geometry
    track_map_available = track_geometry is not None and track_geometry.point_count >= 2
    circuit_info = dataset.circuit_info
    corner_count = len(circuit_info.corners) if circuit_info is not None else 0
    return {
        "drivers": drivers,
        "laps": _integer_bounds(
            [lap.lap_number for lap in laps],
            per_driver={
                driver: [lap.lap_number for lap in laps if lap.driver == driver]
                for driver in drivers
            },
        ),
        "telemetry_distance_m": _float_bounds(
            [sample.distance_m for sample in telemetry],
            per_driver={
                driver: [
                    sample.distance_m for sample in telemetry if sample.driver == driver
                ]
                for driver in drivers
            },
        ),
        "session_time": {
            "available": False,
            "minimum": None,
            "maximum": None,
            "reason": "session-time coverage is not available in normalized snapshots",
        },
        "track_map": {
            "available": track_map_available,
            "source": "session_track_geometry"
            if track_map_available
            else None,
            "reason": None
            if track_map_available
            else "session track geometry is unavailable in the loaded snapshot",
            "source_driver": track_geometry.source_driver
            if track_geometry is not None
            else None,
            "source_lap": track_geometry.source_lap
            if track_geometry is not None
            else None,
            "positioned_sample_count": track_geometry.original_sample_count
            if track_geometry is not None
            else 0,
            "geometry": {
                "algorithm_version": track_geometry.algorithm_version,
                "aggregation_method": track_geometry.aggregation_method,
                "contributing_driver_count": track_geometry.contributing_driver_count,
                "contributing_lap_count": track_geometry.contributing_lap_count,
                "original_closure_gap": track_geometry.original_closure_gap,
                "closure_adjusted": track_geometry.closure_adjusted,
            }
            if track_geometry is not None
            else None,
            "corners": {
                "available": corner_count > 0,
                "count": corner_count,
                "source": circuit_info.source
                if circuit_info is not None and corner_count > 0
                else None,
                "reason": None
                if corner_count > 0
                else "FastF1 circuit corner metadata is unavailable in the loaded snapshot",
            },
        },
    }


def resolve_driver_style(
    dataset: SessionDataset,
    config: ChartRecipeConfig,
    driver_code: str,
    diagnostics: ParameterDiagnostics,
) -> ResolvedStyle:
    override = series_color(config, driver_code)
    if override is not None:
        return ResolvedStyle(color=override, source="user_override", label=driver_code)

    style = dataset.style.driver_colors.get(driver_code)
    if style is not None:
        return ResolvedStyle(color=style.color, source=style.source, label=style.label)

    driver = next(
        (item for item in dataset.drivers if item.abbreviation == driver_code),
        None,
    )
    if driver is not None and driver.team_color:
        color = _normalized_hex_color(driver.team_color)
        if color is not None:
            return ResolvedStyle(
                color=color,
                source="session_team_color",
                label=driver.team_name,
            )

    color = deterministic_fallback_color(driver_code)
    diagnostics.warn(
        "series_colors",
        f"{driver_code} uses deterministic fallback color because no FastF1/session style color is available",
        series=driver_code,
        source="deterministic_fallback",
    )
    return ResolvedStyle(
        color=color,
        source="deterministic_fallback",
        label=driver_code,
        fallback=True,
    )


def resolve_compound_style(
    dataset: SessionDataset,
    config: ChartRecipeConfig,
    compound: str,
    diagnostics: ParameterDiagnostics,
) -> ResolvedStyle:
    label = compound.upper()
    override = series_color(config, label)
    if override is not None:
        return ResolvedStyle(color=override, source="user_override", label=label)

    style = dataset.style.compound_colors.get(label)
    if style is not None:
        return ResolvedStyle(color=style.color, source=style.source, label=label)

    default_color = DEFAULT_COMPOUND_COLORS.get(label)
    if default_color is not None:
        return ResolvedStyle(
            color=default_color,
            source="default_compound_color",
            label=label,
        )

    color = deterministic_fallback_color(label)
    diagnostics.warn(
        "series_colors",
        f"{label} uses deterministic fallback color because no FastF1 compound color is available",
        series=label,
        source="deterministic_fallback",
    )
    return ResolvedStyle(
        color=color,
        source="deterministic_fallback",
        label=label,
        fallback=True,
    )


def deterministic_fallback_color(label: str) -> str:
    digest = hashlib.sha256(label.encode("utf-8")).hexdigest()
    index = int(digest[:8], 16) % len(FALLBACK_COLORS)
    return FALLBACK_COLORS[index]


def first_diagnostic_error(diagnostics: ParameterDiagnostics) -> str:
    first = next(
        (
            error
            for error in diagnostics.errors
            if error.get("field") in {"lap_range", "distance_range_m"}
        ),
        diagnostics.errors[0],
    )
    return str(first["message"])


def lap_validity_policy(
    config: ChartRecipeConfig,
    *,
    require_lap_time: bool | None = None,
) -> dict[str, Any]:
    filters = section(config, "filters")
    value = filters.get("lap_validity") or parameters(config).get("lap_validity") or {}
    if not isinstance(value, dict):
        raise ValueError("lap_validity must be an object")
    policy = {
        "require_lap_time": (
            bool(value.get("require_lap_time"))
            if "require_lap_time" in value
            else bool(require_lap_time)
        ),
        "deleted_laps": str(value.get("deleted_laps") or "exclude"),
        "generated_laps": str(value.get("generated_laps") or "exclude"),
        "accuracy_filter": str(value.get("accuracy_filter") or "all"),
        "require_complete_sectors": bool(value.get("require_complete_sectors", False)),
    }
    if policy["deleted_laps"] not in LAP_DELETED_POLICIES:
        raise ValueError("lap_validity.deleted_laps unsupported value")
    if policy["generated_laps"] not in LAP_GENERATED_POLICIES:
        raise ValueError("lap_validity.generated_laps unsupported value")
    if policy["accuracy_filter"] not in ACCURACY_FILTERS:
        raise ValueError("lap_validity.accuracy_filter unsupported value")
    return policy


def track_status_filter(config: ChartRecipeConfig) -> dict[str, Any]:
    filters = section(config, "filters")
    value = (
        filters.get("track_status_filter")
        or parameters(config).get("track_status_filter")
        or {}
    )
    if not isinstance(value, dict):
        mode = str(value)
        value = {"mode": mode}
    mode = str(value.get("mode") or "all")
    match = str(value.get("match") or value.get("track_status_match") or "any_overlap")
    if mode not in TRACK_STATUS_FILTERS:
        raise ValueError(f"track_status_filter.mode unsupported value: {mode}")
    if match not in TRACK_STATUS_MATCHES:
        raise ValueError(f"track_status_match unsupported value: {match}")
    custom_codes = value.get("custom_codes") or []
    if mode == "custom" and (
        not isinstance(custom_codes, list)
        or not all(isinstance(item, str) for item in custom_codes)
    ):
        raise ValueError("track_status_filter.custom_codes must be a list of status codes")
    included, excluded = _track_status_code_sets(mode, custom_codes)
    return {
        "mode": mode,
        "match": match,
        "custom_codes": list(custom_codes),
        "included_codes": sorted(included),
        "excluded_codes": sorted(excluded),
    }


def missing_series_policy(config: ChartRecipeConfig) -> str:
    filters = section(config, "filters")
    policy = filters.get("missing_series_policy") or parameters(config).get(
        "missing_series_policy"
    )
    policy = str(policy or "warn_skip")
    if policy not in MISSING_SERIES_POLICIES:
        raise ValueError(f"missing_series_policy unsupported value: {policy}")
    return policy


def telemetry_gap_policy(config: ChartRecipeConfig, metric: str) -> dict[str, Any]:
    analysis = section(config, "analysis")
    policy = analysis.get("telemetry_gap_policy") or parameters(config).get(
        "telemetry_gap_policy"
    )
    policy = str(policy or "preserve")
    if policy not in TELEMETRY_GAP_POLICIES:
        raise ValueError(f"telemetry_gap_policy unsupported value: {policy}")
    maximum_gap = analysis.get("maximum_interpolation_gap_ms") or parameters(config).get(
        "maximum_interpolation_gap_ms"
    )
    if policy in {"interpolate_continuous", "resample"} and metric not in CONTINUOUS_TELEMETRY_METRICS:
        raise ValueError(f"telemetry_gap_policy {policy} is not supported for {metric}")
    return {
        "policy": policy,
        "maximum_interpolation_gap_ms": maximum_gap,
        "interpolation_enabled": policy == "interpolate_continuous",
    }


def box_lap_policy(config: ChartRecipeConfig, *, default: str) -> str:
    params = parameters(config)
    filters = section(config, "filters")
    analysis = section(config, "analysis")
    policy = (
        filters.get("box_lap_policy")
        or analysis.get("box_lap_policy")
        or params.get("box_lap_policy")
    )
    if policy is None and "include_pit_laps" in params:
        policy = "include_all" if bool(params.get("include_pit_laps")) else default
    if policy is None:
        policy = default
    policy = str(policy)
    if policy not in BOX_LAP_POLICIES:
        raise ValueError(f"box_lap_policy unsupported value: {policy}")
    return policy


def box_lap_allowed(lap: LapRecord, policy: str) -> bool:
    if policy == "include_all":
        return True
    if policy == "exclude_in_laps":
        return not lap.is_pit_in_lap
    if policy == "exclude_out_laps":
        return not lap.is_pit_out_lap
    if policy == "exclude_in_and_out_laps":
        return not lap.is_pit_in_lap and not lap.is_pit_out_lap
    if policy == "only_in_laps":
        return lap.is_pit_in_lap
    if policy == "only_out_laps":
        return lap.is_pit_out_lap
    raise ValueError(f"box_lap_policy unsupported value: {policy}")


def series_color(config: ChartRecipeConfig, label: str) -> str | None:
    colors = parameters(config).get("series_colors")
    if colors in (None, {}):
        presentation = section(config, "presentation")
        presentation_colors = presentation.get("colors")
        if isinstance(presentation_colors, dict):
            colors = presentation_colors.get("overrides")
    if colors in (None, {}):
        return None
    if not isinstance(colors, dict):
        raise ValueError("series_colors must map series labels to colors")
    color = colors.get(label)
    if color is None:
        return None
    if not isinstance(color, str):
        raise ValueError(f"series_colors.{label} must be a color string")
    return color


def series_colors(config: ChartRecipeConfig) -> dict[str, str]:
    colors = parameters(config).get("series_colors")
    if colors in (None, {}):
        presentation = section(config, "presentation")
        presentation_colors = presentation.get("colors")
        if isinstance(presentation_colors, dict):
            colors = presentation_colors.get("overrides")
    if colors in (None, {}):
        return {}
    if not isinstance(colors, dict):
        raise ValueError("series_colors must map series labels to colors")
    return {str(label): str(color) for label, color in colors.items()}


def numeric_range_contains(
    value: float, range_value: object, *, parameter_name: str
) -> bool:
    if range_value in (None, {}):
        return True
    if not isinstance(range_value, dict):
        raise ValueError(f"{parameter_name} must contain start and end values")
    start = range_value.get("start")
    end = range_value.get("end")
    if start is not None and value < float(start):
        return False
    if end is not None and value > float(end):
        return False
    return True


def effective_configuration_metadata(
    dataset: SessionDataset,
    config: ChartRecipeConfig,
    *,
    selected_drivers: list[str],
    box_policy: str | None = None,
    diagnostics: ParameterDiagnostics | None = None,
    filters: dict[str, Any] | None = None,
    coverage: dict[str, Any] | None = None,
    style_sources: dict[str, Any] | None = None,
    extra_effective: dict[str, Any] | None = None,
) -> dict[str, Any]:
    effective_filters: dict[str, Any] = {"lap_range": effective_lap_range(config)}
    if filters:
        effective_filters.update(filters)
    if box_policy is not None:
        effective_filters["box_lap_policy"] = box_policy
    diagnostics = diagnostics or ParameterDiagnostics()
    selection = section(config, "selection")
    playback_interval = selection.get("playback_interval")
    effective_configuration = {
        "selection": {
            "driver_selection_mode": driver_selection_mode(config),
            "drivers": selected_drivers,
            "driver_order": _driver_order(config),
            "available_drivers": [driver.abbreviation for driver in dataset.drivers],
        },
        "filters": effective_filters,
        "presentation": {
            "series_colors": series_colors(config),
            "style_sources": style_sources or {},
        },
        "coverage_bounds": coverage
        if coverage is not None
        else coverage_bounds(dataset, selected_drivers=selected_drivers, config=config),
    }
    if isinstance(playback_interval, dict):
        effective_configuration["selection"]["playback_interval"] = playback_interval
    if extra_effective:
        effective_configuration.update(extra_effective)
    return {
        "requested_configuration": parameters(config),
        "effective_configuration": effective_configuration,
        "coverage_bounds": effective_configuration["coverage_bounds"],
        "style_sources": style_sources or {},
        "diagnostics": {
            "warnings": diagnostics.warnings,
            "errors": diagnostics.errors,
            "exclusion_counts": diagnostics.exclusion_counts,
            "active_filter_summary": diagnostics.active_filter_summary,
        },
    }


def _validate_lap_range_bounds(
    bounds: dict[str, Any],
    config: ChartRecipeConfig,
    diagnostics: ParameterDiagnostics,
    selected_drivers: list[str],
) -> None:
    lap_range = effective_lap_range(config)
    lap_bounds = bounds.get("laps", {})
    if not lap_bounds.get("available"):
        diagnostics.error("lap_range", "Loaded session has no laps for the selected drivers")
        return
    if lap_range in (None, {}):
        return
    if not isinstance(lap_range, dict):
        diagnostics.error("lap_range", "lap_range must contain start and end values")
        return
    start = lap_range.get("start")
    end = lap_range.get("end")
    minimum = lap_bounds["minimum"]
    maximum = lap_bounds["maximum"]
    if start is not None and int(start) < minimum:
        diagnostics.error("lap_range", f"lap_range start must be at least {minimum}")
    if end is not None and int(end) > maximum:
        diagnostics.error("lap_range", f"lap_range end must be at most {maximum}")
    _warn_partial_lap_coverage(
        lap_bounds.get("per_driver", {}),
        lap_range,
        diagnostics,
        selected_drivers,
    )


def _validate_distance_range_bounds(
    bounds: dict[str, Any],
    config: ChartRecipeConfig,
    diagnostics: ParameterDiagnostics,
    selected_drivers: list[str],
) -> None:
    distance_range = parameter_value(
        config,
        "distance_range_m",
        section_name="analysis",
    )
    distance_bounds = bounds.get("telemetry_distance_m", {})
    if distance_range in (None, {}):
        return
    if not distance_bounds.get("available"):
        diagnostics.error(
            "distance_range_m",
            "Loaded session has no telemetry distance samples for the selected drivers and laps",
        )
        return
    if not isinstance(distance_range, dict):
        diagnostics.error("distance_range_m", "distance_range_m must contain start and end values")
        return
    start = distance_range.get("start")
    end = distance_range.get("end")
    minimum = float(distance_bounds["minimum"])
    maximum = float(distance_bounds["maximum"])
    if start is not None and float(start) < minimum:
        diagnostics.error(
            "distance_range_m",
            f"distance_range_m start must be at least {minimum:g} m",
        )
    if end is not None and float(end) > maximum:
        diagnostics.error(
            "distance_range_m",
            f"distance_range_m end must be at most {maximum:g} m",
        )
    _warn_partial_distance_coverage(
        distance_bounds.get("per_driver", {}),
        distance_range,
        diagnostics,
        selected_drivers,
    )


def _warn_partial_lap_coverage(
    per_driver: dict[str, Any],
    lap_range: dict[str, Any],
    diagnostics: ParameterDiagnostics,
    selected_drivers: list[str],
) -> None:
    start = lap_range.get("start")
    end = lap_range.get("end")
    for driver in selected_drivers:
        driver_bounds = per_driver.get(driver, {})
        if not driver_bounds.get("available"):
            diagnostics.warn("lap_range", f"{driver} has no loaded laps in this session")
            continue
        minimum = driver_bounds["minimum"]
        maximum = driver_bounds["maximum"]
        if (start is not None and int(start) < minimum) or (
            end is not None and int(end) > maximum
        ):
            diagnostics.warn(
                "lap_range",
                f"{driver} only has loaded laps {minimum}-{maximum}",
                driver=driver,
            )


def _warn_partial_distance_coverage(
    per_driver: dict[str, Any],
    distance_range: dict[str, Any],
    diagnostics: ParameterDiagnostics,
    selected_drivers: list[str],
) -> None:
    start = distance_range.get("start")
    end = distance_range.get("end")
    for driver in selected_drivers:
        driver_bounds = per_driver.get(driver, {})
        if not driver_bounds.get("available"):
            diagnostics.warn(
                "distance_range_m",
                f"{driver} has no telemetry distance samples in the selected laps",
                driver=driver,
            )
            continue
        minimum = float(driver_bounds["minimum"])
        maximum = float(driver_bounds["maximum"])
        if (start is not None and float(start) < minimum) or (
            end is not None and float(end) > maximum
        ):
            diagnostics.warn(
                "distance_range_m",
                f"{driver} telemetry distance coverage is {minimum:g}-{maximum:g} m",
                driver=driver,
            )


def _integer_bounds(values: list[int], *, per_driver: dict[str, list[int]]) -> dict[str, Any]:
    return {
        **_bounds(values),
        "per_driver": {driver: _bounds(driver_values) for driver, driver_values in per_driver.items()},
    }


def _float_bounds(values: list[float], *, per_driver: dict[str, list[float]]) -> dict[str, Any]:
    return {
        **_bounds(values),
        "per_driver": {driver: _bounds(driver_values) for driver, driver_values in per_driver.items()},
    }


def _bounds(values: list[int] | list[float]) -> dict[str, Any]:
    if not values:
        return {"available": False, "minimum": None, "maximum": None}
    return {
        "available": True,
        "minimum": min(values),
        "maximum": max(values),
    }


def _normalized_hex_color(value: str) -> str | None:
    text = value.strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) != 6 or any(character not in "0123456789abcdefABCDEF" for character in text):
        return None
    return f"#{text.upper()}"


def series_policy_action(
    diagnostics: ParameterDiagnostics,
    *,
    field_name: str,
    message: str,
    policy: str,
) -> bool:
    if policy == "error":
        diagnostics.error(field_name, message)
        return False
    if policy == "warn_skip":
        diagnostics.warn(field_name, message)
    return True


def _driver_selection_object(selection: dict[str, Any]) -> dict[str, Any]:
    value = selection.get("driver_selection")
    if isinstance(value, dict):
        return value
    value = selection.get("drivers")
    if isinstance(value, dict):
        return value
    return {}


def _requested_driver_list(requested: Any, available: list[str]) -> list[str]:
    if requested is None:
        return available
    if requested == []:
        return []
    if not isinstance(requested, list) or not all(isinstance(item, str) for item in requested):
        raise ValueError("drivers must be a list of driver codes")
    unknown = sorted(set(requested) - set(available))
    if unknown:
        raise ValueError(f"drivers contains unknown driver(s): {', '.join(unknown)}")
    return [driver for driver in available if driver in requested]


def _driver_order(config: ChartRecipeConfig) -> str:
    params = parameters(config)
    selection = section(config, "selection")
    order = selection.get("driver_order") or params.get("driver_order") or "classification"
    order = str(order)
    if order not in DRIVER_ORDERS:
        raise ValueError(f"driver_order unsupported value: {order}")
    return order


def _apply_driver_order(
    dataset: SessionDataset,
    selected: list[str],
    config: ChartRecipeConfig,
    requested: Any,
) -> list[str]:
    selected_set = set(selected)
    order = _driver_order(config)
    if order in {"classification", "grid"}:
        return [driver.abbreviation for driver in dataset.drivers if driver.abbreviation in selected_set]
    if order == "selection_order" and isinstance(requested, list):
        return [driver for driver in requested if driver in selected_set]
    if order == "custom":
        params = parameters(config)
        selection = section(config, "selection")
        custom = selection.get("custom_driver_order") or params.get("custom_driver_order")
        if not isinstance(custom, list) or not all(isinstance(item, str) for item in custom):
            raise ValueError("custom_driver_order must be a list of driver codes")
        if len(set(custom)) != len(custom):
            raise ValueError("custom_driver_order must not contain duplicates")
        unknown = sorted(set(custom) - selected_set)
        if unknown:
            raise ValueError(
                f"custom_driver_order contains unselected driver(s): {', '.join(unknown)}"
            )
        remainder = [driver for driver in selected if driver not in custom]
        return list(custom) + remainder
    if order == "fastest_lap":
        fastest = {
            driver: min(
                (
                    lap.lap_time_seconds
                    for lap in dataset.laps
                    if lap.driver == driver and lap.lap_time_seconds is not None
                ),
                default=float("inf"),
            )
            for driver in selected
        }
        return sorted(selected, key=lambda driver: (fastest[driver], selected.index(driver)))
    if order == "team":
        teams = {
            driver.abbreviation: driver.team_name or ""
            for driver in dataset.drivers
        }
        return sorted(selected, key=lambda driver: (teams.get(driver, ""), driver))
    return selected


def _apply_driver_limit(selected: list[str], config: ChartRecipeConfig) -> list[str]:
    params = parameters(config)
    selection = section(config, "selection")
    limit = selection.get("driver_limit") or params.get("driver_limit")
    if limit in (None, 0, ""):
        return selected
    limit_value = int(limit)
    if limit_value < 1:
        raise ValueError("driver_limit must be at least 1")
    kept = selected[:limit_value]
    analysis = section(config, "analysis")
    presentation = section(config, "presentation")
    protected = {
        str(driver)
        for driver in (
            params.get("highlight_drivers")
            or presentation.get("highlight_drivers")
            or []
        )
    }
    reference_driver = params.get("reference_driver") or analysis.get("reference_driver")
    if reference_driver:
        protected.add(str(reference_driver))
    for driver in selected:
        if driver in protected and driver not in kept:
            kept.append(driver)
    return kept


def _lap_exclusion_reason(
    lap: LapRecord,
    config: ChartRecipeConfig,
    *,
    lap_validity: dict[str, Any],
    track_filter: dict[str, Any],
    box_policy: str | None,
) -> str | None:
    if not lap_in_range(lap.lap_number, config):
        return "outside_lap_range"
    if box_policy is not None and not box_lap_allowed(lap, box_policy):
        return "box_lap_policy"
    if lap_validity["require_lap_time"] and lap.lap_time_seconds is None:
        return "missing_lap_time"
    if lap_validity["deleted_laps"] == "exclude" and lap.is_deleted:
        return "deleted_lap"
    if lap_validity["generated_laps"] == "exclude" and lap.is_generated:
        return "generated_lap"
    if lap_validity["accuracy_filter"] == "accurate_only" and lap.is_accurate is False:
        return "inaccurate_lap"
    if lap_validity["require_complete_sectors"] and not all(
        value is not None
        for value in (
            lap.sector_1_time_seconds,
            lap.sector_2_time_seconds,
            lap.sector_3_time_seconds,
        )
    ):
        return "incomplete_sectors"
    if not _track_status_allowed(lap.track_status, track_filter):
        return "track_status"
    return None


def _track_status_allowed(status: str | None, track_filter: dict[str, Any]) -> bool:
    mode = track_filter["mode"]
    if mode == "all":
        return True
    if status is None:
        return False
    codes = set(str(status))
    included = set(track_filter["included_codes"])
    excluded = set(track_filter["excluded_codes"])
    if excluded and codes.intersection(excluded):
        return False
    if included:
        return bool(codes.intersection(included))
    return True


def _track_status_code_sets(mode: str, custom_codes: list[str]) -> tuple[set[str], set[str]]:
    if mode == "green_only":
        return set(TRACK_STATUS_CODES["green"]), set()
    if mode == "green_or_yellow":
        return TRACK_STATUS_CODES["green"] | TRACK_STATUS_CODES["yellow"], set()
    if mode == "exclude_sc":
        return set(), set(TRACK_STATUS_CODES["sc"])
    if mode == "exclude_sc_and_vsc":
        return set(), TRACK_STATUS_CODES["sc"] | TRACK_STATUS_CODES["vsc"]
    if mode == "custom":
        return set(custom_codes), set()
    return set(), set()


def _range_summary(lap_range: Any) -> str:
    if not isinstance(lap_range, dict):
        return "Lap range: custom"
    start = lap_range.get("start")
    end = lap_range.get("end")
    if start is not None and end is not None:
        return f"Laps {start}-{end}"
    if start is not None:
        return f"Laps from {start}"
    if end is not None:
        return f"Laps through {end}"
    return "All laps"

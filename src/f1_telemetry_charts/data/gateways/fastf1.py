"""FastF1-backed session gateway.

FastF1 is imported lazily inside the gateway so framework models, recipes, and
tests do not depend on FastF1 unless this gateway is used.
"""

from __future__ import annotations

from math import isfinite
from pathlib import Path
from typing import Any

from f1_telemetry_charts.data.gateways.base import DataGatewayError
from f1_telemetry_charts.data.models import (
    CircuitCorner,
    CircuitInfo,
    DriverMetadata,
    LapRecord,
    MissingDataField,
    PracticeClassificationEntry,
    QualifyingClassificationEntry,
    QualifyingSegmentClassification,
    SessionDataset,
    SessionMetadata,
    SessionQuery,
    SessionStatusRecord,
    SessionStyleMetadata,
    SourceProvenance,
    StyleColor,
    TelemetrySample,
    TimingAppRecord,
    TimingStreamRecord,
    WeatherSample,
    requests_all_drivers,
)
from f1_telemetry_charts.data.track_geometry import derive_canonical_track_geometry

MAX_TELEMETRY_SAMPLES_PER_LAP = 50


class FastF1SessionGateway:
    def __init__(self, cache_dir: str | Path, *, cache_only: bool = False):
        self.cache_dir = Path(cache_dir)
        self.cache_only = cache_only

    def load_session(self, query: SessionQuery) -> SessionDataset:
        try:
            import fastf1
        except ImportError as exc:
            raise DataGatewayError(
                "FastF1 is not installed. Install the FastF1 dependency before "
                "using FastF1SessionGateway."
            ) from exc

        if self.cache_only and not self.cache_dir.exists():
            raise DataGatewayError(
                f"FastF1 cache directory does not exist in cache-only mode: {self.cache_dir}"
            )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        fastf1.Cache.enable_cache(str(self.cache_dir))
        offline_mode = getattr(fastf1.Cache, "offline_mode", None)
        if offline_mode is not None:
            offline_mode(self.cache_only)

        try:
            session = fastf1.get_session(query.season, query.event, query.session)
            session.load(
                laps=True,
                telemetry=True,
                weather=True,
                messages=query.session.strip().lower() in {"qualifying", "q"},
            )
        except Exception as exc:
            raise DataGatewayError(
                f"FastF1 could not load {query.season} {query.event} {query.session}: {exc}"
            ) from exc
        finally:
            if self.cache_only and offline_mode is not None:
                offline_mode(False)

        return _session_to_dataset(
            session=session,
            query=query,
            cache_only=self.cache_only,
            fastf1_module=fastf1,
        )


def _session_to_dataset(
    *, session: Any, query: SessionQuery, cache_only: bool, fastf1_module: Any | None = None
) -> SessionDataset:
    all_laps = session.laps
    laps = all_laps
    all_driver_codes = _selected_driver_codes(
        all_laps,
        query.model_copy(update={"drivers": ["*"]}),
    )
    selected_driver_codes = _selected_driver_codes(laps, query)
    if not requests_all_drivers(query.drivers):
        laps = laps.pick_drivers(query.drivers)
        selected_driver_codes = query.drivers

    driver_rows = getattr(session, "results", None)
    drivers = _drivers_from_results(driver_rows, selected_driver_codes)
    qualifying_split_times = _qualifying_split_times(session, query.session)
    lap_records = _lap_records_from_laps(laps, qualifying_split_times=qualifying_split_times)
    telemetry = _telemetry_samples_from_laps(laps, session=session)
    timing = _timing_stream_records_from_session(
        session,
        drivers,
        fastf1_module=fastf1_module,
    )
    timing_app = _timing_app_records_from_session(
        session,
        drivers,
        fastf1_module=fastf1_module,
    )
    geometry_telemetry = (
        telemetry
        if requests_all_drivers(query.drivers)
        else _telemetry_samples_from_laps(all_laps, session=session)
    )
    weather = _weather_samples_from_session(session)
    style = _style_metadata_from_session(
        session=session,
        fastf1_module=fastf1_module,
        drivers=drivers,
    )
    circuit_info = _circuit_info_from_session(session)
    missing_data = []
    if not weather:
        missing_data.append(
            MissingDataField(field="weather", reason="No weather samples available")
        )
    if not telemetry:
        missing_data.append(
            MissingDataField(
                field="telemetry",
                reason="No telemetry samples available",
            )
        )

    dataset = SessionDataset(
        metadata=SessionMetadata(
            season=query.season,
            event=query.event,
            session=query.session,
            round_number=getattr(getattr(session, "event", None), "RoundNumber", None),
            official_name=str(getattr(session, "name", query.session)),
        ),
        drivers=drivers,
        laps=lap_records,
        telemetry=telemetry,
        timing=timing,
        timing_app=timing_app,
        weather=weather,
        session_status=_session_status_records_from_session(session),
        qualifying_segments=_qualifying_segments_from_results(driver_rows, query.session),
        practice_classification=_practice_classification_from_results(driver_rows, query.session),
        style=style,
        circuit_info=circuit_info,
        provenance=SourceProvenance(
            provider="FastF1",
            cache_status="cache-only" if cache_only else "hit",
            source_path=None,
            fetched_from_network=not cache_only,
        ),
        missing_data=missing_data,
    )
    geometry_dataset = dataset.model_copy(
        update={
            "drivers": _drivers_from_results(driver_rows, all_driver_codes),
            "laps": _lap_records_from_laps(all_laps, qualifying_split_times=qualifying_split_times),
            "telemetry": geometry_telemetry,
        },
        deep=True,
    )
    return dataset.model_copy(
        update={"track_geometry": derive_canonical_track_geometry(geometry_dataset)},
        deep=True,
    )


def _style_metadata_from_session(
    *,
    session: Any,
    fastf1_module: Any | None,
    drivers: list[DriverMetadata],
) -> SessionStyleMetadata:
    plotting = getattr(fastf1_module, "plotting", None)
    driver_colors: dict[str, StyleColor] = {}
    team_colors: dict[str, StyleColor] = {}
    compound_colors: dict[str, StyleColor] = {}

    for driver in drivers:
        team_color = _normalized_hex_color(driver.team_color)
        team_name = driver.team_name
        if team_name and team_color and team_name not in team_colors:
            team_colors[team_name] = StyleColor(
                color=team_color,
                source="fastf1_session_team_color",
                label=team_name,
            )

        plotted_driver_color = _plotting_color(
            plotting,
            "get_driver_color",
            driver.abbreviation,
            session=session,
        )
        plotted_team_color = (
            _plotting_color(plotting, "get_team_color", team_name, session=session)
            if team_name
            else None
        )
        color = plotted_driver_color or plotted_team_color or team_color
        if color:
            driver_colors[driver.abbreviation] = StyleColor(
                color=color,
                source=(
                    "fastf1_driver_color"
                    if plotted_driver_color
                    else "fastf1_team_color"
                    if plotted_team_color
                    else "fastf1_session_team_color"
                ),
                label=team_name,
            )

    compound_mapping = _plotting_compound_mapping(plotting, session=session)
    for compound, color in compound_mapping.items():
        normalized = _normalized_hex_color(color)
        if normalized:
            compound_colors[str(compound).upper()] = StyleColor(
                color=normalized,
                source="fastf1_compound_mapping",
                label=str(compound).upper(),
            )

    return SessionStyleMetadata(
        driver_colors=driver_colors,
        team_colors=team_colors,
        compound_colors=compound_colors,
    )


def _circuit_info_from_session(session: Any) -> CircuitInfo | None:
    get_circuit_info = getattr(session, "get_circuit_info", None)
    if get_circuit_info is None:
        return None
    try:
        raw = get_circuit_info()
    except Exception:
        return None
    if raw is None:
        return None

    corners = _corners_from_circuit_info(raw)
    if not corners:
        return None
    return CircuitInfo(
        source="fastf1_circuit_info",
        reason="session_get_circuit_info",
        rotation_degrees=_float_or_none(getattr(raw, "rotation", None)),
        corners=corners,
    )


def _corners_from_circuit_info(raw: Any) -> list[CircuitCorner]:
    rows = getattr(raw, "corners", None)
    if rows is None:
        return []
    corners: list[CircuitCorner] = []
    try:
        iterator = rows.iterrows()
    except Exception:
        return []
    for _, row in iterator:
        number = _int_or_none(_row_value(row, "Number"))
        x = _float_or_none(_row_value(row, "X"))
        y = _float_or_none(_row_value(row, "Y"))
        if number is None or x is None or y is None:
            continue
        letter = _string_or_none(_row_value(row, "Letter"))
        label = f"{number}{letter or ''}"
        corners.append(
            CircuitCorner(
                number=number,
                letter=letter,
                label=label,
                x=x,
                y=y,
                angle_degrees=_float_or_none(_row_value(row, "Angle")),
                distance_m=_float_or_none(_row_value(row, "Distance")),
            )
        )
    return sorted(corners, key=lambda corner: (corner.number, corner.letter or ""))


def _plotting_color(
    plotting: Any,
    function_name: str,
    identifier: str | None,
    *,
    session: Any,
) -> str | None:
    if plotting is None or identifier is None:
        return None
    func = getattr(plotting, function_name, None)
    if func is None:
        return None
    try:
        return _normalized_hex_color(func(identifier, session=session))
    except Exception:
        return None


def _plotting_compound_mapping(plotting: Any, *, session: Any) -> dict[str, str]:
    if plotting is None:
        return {}
    func = getattr(plotting, "get_compound_mapping", None)
    if func is None:
        return {}
    try:
        raw = func(session=session)
    except Exception:
        return {}
    if isinstance(raw, dict):
        return {str(key): str(value) for key, value in raw.items()}
    return {}


def _row_value(row: Any, key: str) -> Any:
    if hasattr(row, "get"):
        return row.get(key)
    return getattr(row, key, None)


def _normalized_hex_color(value: Any) -> str | None:
    text = _string_or_none(value)
    if text is None:
        return None
    text = text.strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) != 6 or any(character not in "0123456789abcdefABCDEF" for character in text):
        return None
    return f"#{text.upper()}"


def _selected_driver_codes(laps: Any, query: SessionQuery) -> list[str]:
    if not requests_all_drivers(query.drivers):
        return query.drivers

    try:
        columns = set(getattr(laps, "columns", []))
        if "Driver" in columns:
            raw_drivers = laps["Driver"].dropna().tolist()
            return list(dict.fromkeys(str(driver) for driver in raw_drivers))
    except Exception:
        pass

    rows = getattr(laps, "_rows", None)
    if isinstance(rows, list):
        return list(
            dict.fromkeys(str(row["Driver"]) for row in rows if row.get("Driver") is not None)
        )
    return query.drivers


def _drivers_from_results(results: Any, fallback_drivers: list[str]) -> list[DriverMetadata]:
    drivers: list[DriverMetadata] = []
    if results is not None:
        for _, row in results.iterrows():
            abbreviation = _string_or_none(row.get("Abbreviation"))
            if abbreviation and abbreviation in fallback_drivers:
                drivers.append(
                    DriverMetadata(
                        driver_number=_string_or_none(row.get("DriverNumber")),
                        abbreviation=abbreviation,
                        full_name=_string_or_none(row.get("FullName")),
                        team_name=_string_or_none(row.get("TeamName")),
                        team_color=_string_or_none(row.get("TeamColor")),
                        headshot_url=_string_or_none(row.get("HeadshotUrl")),
                        country_code=_string_or_none(row.get("CountryCode")),
                        classification_position=_int_or_none(row.get("Position")),
                        grid_position=_int_or_none(row.get("GridPosition")),
                        result_status=_string_or_none(row.get("Status")),
                    )
                )
    if drivers:
        return drivers
    return [DriverMetadata(abbreviation=driver) for driver in fallback_drivers]


def _lap_records_from_laps(
    laps: Any, *, qualifying_split_times: list[float] | None = None
) -> list[LapRecord]:
    records: list[LapRecord] = []
    for _, row in laps.iterrows():
        lap_time = row.get("LapTime")
        lap_time_seconds = _duration_seconds_or_none(lap_time)
        lap_end_seconds = _duration_seconds_or_none(row.get("Time"))
        explicit_segment = _qualifying_segment_or_none(row.get("QualifyingSegment"))
        records.append(
            LapRecord(
                driver=str(row.get("Driver")),
                lap_number=int(row.get("LapNumber")),
                lap_start_time_seconds=_duration_seconds_or_none(row.get("LapStartTime")),
                lap_end_time_seconds=lap_end_seconds,
                lap_time_seconds=lap_time_seconds,
                compound=_string_or_none(row.get("Compound")),
                tyre_age=_float_or_none(row.get("TyreLife")),
                stint=_int_or_none(row.get("Stint")),
                position=_int_or_none(row.get("Position")),
                is_pit_in_lap=_has_value(row.get("PitInTime")),
                is_pit_out_lap=_has_value(row.get("PitOutTime")),
                pit_in_time_seconds=_duration_seconds_or_none(row.get("PitInTime")),
                pit_out_time_seconds=_duration_seconds_or_none(row.get("PitOutTime")),
                is_deleted=_bool_or_false(row.get("Deleted")),
                deletion_reason=_string_or_none(row.get("DeletedReason")),
                qualifying_segment=explicit_segment or _segment_from_split_times(lap_end_seconds, qualifying_split_times),
                is_generated=_bool_or_false(row.get("IsGenerated")),
                is_accurate=_bool_or_none(row.get("IsAccurate")),
                sector_1_time_seconds=_duration_seconds_or_none(row.get("Sector1Time")),
                sector_2_time_seconds=_duration_seconds_or_none(row.get("Sector2Time")),
                sector_3_time_seconds=_duration_seconds_or_none(row.get("Sector3Time")),
                track_status=_string_or_none(row.get("TrackStatus")),
            )
        )
    return records


def _session_status_records_from_session(session: Any) -> list[SessionStatusRecord]:
    rows = getattr(session, "session_status", None)
    if rows is None:
        return []
    records: list[SessionStatusRecord] = []
    try:
        iterator = rows.iterrows()
    except Exception:
        return []
    for _, row in iterator:
        time_seconds = _duration_seconds_or_none(row.get("Time"))
        status = _string_or_none(row.get("Status"))
        if time_seconds is not None and status:
            records.append(SessionStatusRecord(time_seconds=time_seconds, status=status))
    return records


def _practice_classification_from_results(
    results: Any, session_name: str
) -> list[PracticeClassificationEntry]:
    if session_name.strip().lower() not in {
        "fp1", "fp2", "fp3", "practice 1", "practice 2", "practice 3",
    } or results is None:
        return []
    rows: list[PracticeClassificationEntry] = []
    leader_time: float | None = None
    for _, row in results.iterrows():
        driver = _string_or_none(row.get("Abbreviation"))
        position = _int_or_none(row.get("Position"))
        if not driver or position is None:
            continue
        fastest = _duration_seconds_or_none(row.get("FastestLapTime"))
        if fastest is None:
            fastest = _duration_seconds_or_none(row.get("Time"))
        if position == 1 and fastest is not None:
            leader_time = fastest
        rows.append(
            PracticeClassificationEntry(
                driver=driver,
                position=position,
                fastest_time_seconds=fastest,
                gap_seconds=(fastest - leader_time if fastest is not None and leader_time is not None else None),
                lap_count=_int_or_none(row.get("Laps")),
                status=_string_or_none(row.get("Status")),
            )
        )
    return sorted(rows, key=lambda item: (item.position, item.driver))


def _qualifying_segments_from_results(
    results: Any, session_name: str
) -> list[QualifyingSegmentClassification]:
    if session_name.strip().lower() not in {"qualifying", "q"} or results is None:
        return []
    raw_rows = list(results.iterrows())
    segments: list[QualifyingSegmentClassification] = []
    advancement_cutoffs = {"Q1": 15, "Q2": 10, "Q3": None}
    participation_cutoffs = {"Q1": len(raw_rows), "Q2": min(15, len(raw_rows)), "Q3": min(10, len(raw_rows))}
    for segment in ("Q1", "Q2", "Q3"):
        rows: list[tuple[str, float | None, str | None, bool | None, int | None]] = []
        for _, row in raw_rows:
            driver = _string_or_none(row.get("Abbreviation"))
            if not driver:
                continue
            time_value = _duration_seconds_or_none(row.get(segment))
            official_position = _int_or_none(row.get("Position"))
            cutoff = advancement_cutoffs[segment]
            advanced = (
                official_position <= cutoff
                if cutoff is not None and official_position is not None
                else None
            )
            participates = official_position is not None and official_position <= participation_cutoffs[segment]
            if time_value is not None or participates:
                rows.append((driver, time_value, _string_or_none(row.get("Status")), advanced, official_position))
        timed = sorted(
            (item for item in rows if item[1] is not None),
            key=lambda item: (item[1], item[4] or 999, item[0]),
        )
        untimed = sorted((item for item in rows if item[1] is None), key=lambda item: (item[4] or 999, item[0]))
        ordered = [*timed, *untimed]
        time_counts: dict[float, int] = {}
        for _, time_seconds, _, _, _ in timed:
            if time_seconds is not None:
                time_counts[time_seconds] = time_counts.get(time_seconds, 0) + 1
        ties = any(count > 1 for count in time_counts.values())
        entries = [
            QualifyingClassificationEntry(
                driver=driver,
                position=index,
                time_seconds=time_seconds,
                status=status,
                advanced=advanced,
                advancement_basis=(
                    "not_applicable"
                    if segment == "Q3"
                    else "tie"
                    if time_seconds is not None and time_counts.get(time_seconds, 0) > 1
                    else "time"
                ),
            )
            for index, (driver, time_seconds, status, advanced, _) in enumerate(ordered, start=1)
        ]
        segments.append(
            QualifyingSegmentClassification(
                segment=segment,
                entries=entries,
                status=("complete" if len(entries) == participation_cutoffs[segment] else "partial"),
            )
        )
    return segments


def _qualifying_segment_or_none(value: Any) -> str | None:
    normalized = _string_or_none(value)
    if normalized is None:
        return None
    normalized = normalized.upper()
    return normalized if normalized in {"Q1", "Q2", "Q3"} else None


def _qualifying_split_times(session: Any, session_name: str) -> list[float] | None:
    if session_name.strip().lower() not in {"qualifying", "q"}:
        return None
    values = getattr(session, "_session_split_times", None)
    if not values:
        return None
    converted = [
        seconds
        for value in values
        if (seconds := _duration_seconds_or_none(value)) is not None and seconds > 0
    ]
    return sorted(converted)[:2] if len(converted) >= 2 else None


def _segment_from_split_times(
    lap_end_seconds: float | None, split_times: list[float] | None
) -> str | None:
    if lap_end_seconds is None or not split_times or len(split_times) < 2:
        return None
    if lap_end_seconds <= split_times[0]:
        return "Q1"
    if lap_end_seconds <= split_times[1]:
        return "Q2"
    return "Q3"


def _weather_samples_from_session(session: Any) -> list[WeatherSample]:
    weather_data = getattr(session, "weather_data", None)
    if weather_data is None:
        return []

    samples: list[WeatherSample] = []
    for _, row in weather_data.iterrows():
        time_value = row.get("Time")
        time_seconds = (
            float(time_value.total_seconds()) if hasattr(time_value, "total_seconds") else 0
        )
        samples.append(
            WeatherSample(
                time_seconds=time_seconds,
                air_temp_c=_float_or_none(row.get("AirTemp")),
                track_temp_c=_float_or_none(row.get("TrackTemp")),
                humidity_percent=_float_or_none(row.get("Humidity")),
                rainfall=_bool_or_none(row.get("Rainfall")),
            )
        )
    return samples


def _timing_stream_records_from_session(
    session: Any,
    drivers: list[DriverMetadata],
    *,
    fastf1_module: Any | None = None,
) -> list[TimingStreamRecord]:
    api_module = getattr(fastf1_module, "api", None)
    if api_module is None:
        if fastf1_module is not None and getattr(fastf1_module, "__name__", None) != "fastf1":
            return []
        try:
            import fastf1.api as api_module
        except Exception:
            return []

    timing_data = getattr(api_module, "timing_data", None)
    api_path = getattr(session, "api_path", None)
    if timing_data is None or not api_path:
        return []

    try:
        _, stream_data = timing_data(api_path)
    except Exception:
        return []
    if stream_data is None or getattr(stream_data, "empty", True):
        return []

    columns = set(getattr(stream_data, "columns", []))
    required = {"Time", "Driver"}
    if not required.issubset(columns):
        return []

    number_to_driver = {
        str(driver.driver_number): driver.abbreviation
        for driver in drivers
        if driver.driver_number is not None
    }
    selected_drivers = {driver.abbreviation for driver in drivers}

    records: list[TimingStreamRecord] = []
    for _, row in stream_data.iterrows():
        driver_key = _string_or_none(row.get("Driver"))
        if driver_key is None:
            continue
        driver = number_to_driver.get(driver_key, driver_key)
        if selected_drivers and driver not in selected_drivers:
            continue
        time_seconds = _duration_seconds_or_none(row.get("Time"))
        if time_seconds is None:
            continue
        position = _int_or_none(row.get("Position"))
        gap_value = row.get("GapToLeader")
        interval_value = row.get("IntervalToPositionAhead")
        gap_seconds, gap_status = _timing_delta_seconds(gap_value)
        gap_laps = _timing_lap_delta(gap_value)
        if position == 1 and gap_seconds is None and gap_status in {"missing", "unparseable"}:
            gap_seconds = 0.0
            gap_status = "leader"
        interval_seconds, interval_status = _timing_delta_seconds(
            interval_value,
        )
        interval_laps = _timing_lap_delta(interval_value)
        if position == 1 and interval_seconds is None and interval_status in {"missing", "unparseable"}:
            interval_status = "leader"
        records.append(
            TimingStreamRecord(
                driver=driver,
                session_time_seconds=time_seconds,
                position=position,
                gap_to_leader_seconds=gap_seconds,
                interval_to_ahead_seconds=interval_seconds,
                gap_to_leader_laps=gap_laps,
                interval_to_ahead_laps=interval_laps,
                gap_parse_status=gap_status,
                interval_parse_status=interval_status,
            )
        )

    return sorted(
        records,
        key=lambda record: (
            record.session_time_seconds,
            record.position if record.position is not None else 999,
            record.driver,
        ),
    )


def _timing_app_records_from_session(
    session: Any,
    drivers: list[DriverMetadata],
    *,
    fastf1_module: Any | None = None,
) -> list[TimingAppRecord]:
    api_module = getattr(fastf1_module, "api", None)
    if api_module is None:
        if fastf1_module is not None and getattr(fastf1_module, "__name__", None) != "fastf1":
            return []
        try:
            import fastf1.api as api_module
        except Exception:
            return []

    timing_app_data = getattr(api_module, "timing_app_data", None)
    api_path = getattr(session, "api_path", None)
    if timing_app_data is None or not api_path:
        return []

    try:
        rows = timing_app_data(api_path)
    except Exception:
        return []
    if rows is None or getattr(rows, "empty", True):
        return []

    columns = set(getattr(rows, "columns", []))
    if not {"Time", "Driver"}.issubset(columns):
        return []

    number_to_driver = {
        str(driver.driver_number): driver.abbreviation
        for driver in drivers
        if driver.driver_number is not None
    }
    selected_drivers = {driver.abbreviation for driver in drivers}
    records: list[TimingAppRecord] = []
    for _, row in rows.iterrows():
        driver_key = _string_or_none(row.get("Driver"))
        if driver_key is None:
            continue
        driver = number_to_driver.get(driver_key, driver_key)
        if selected_drivers and driver not in selected_drivers:
            continue
        time_seconds = _duration_seconds_or_none(row.get("Time"))
        if time_seconds is None:
            continue
        records.append(
            TimingAppRecord(
                driver=driver,
                session_time_seconds=time_seconds,
                lap_number=_int_or_none(row.get("LapNumber")),
                lap_time_seconds=_duration_seconds_or_none(row.get("LapTime")),
                stint=_int_or_none(row.get("Stint")),
                total_laps=_float_or_none(row.get("TotalLaps")),
                compound=_string_or_none(row.get("Compound")),
                start_laps=_float_or_none(row.get("StartLaps")),
            )
        )
    return sorted(
        records,
        key=lambda record: (record.session_time_seconds, record.driver),
    )


def _telemetry_samples_from_laps(
    laps: Any, *, session: Any | None = None
) -> list[TelemetrySample]:
    samples = _telemetry_samples_from_session_car_data(session=session, laps=laps)
    if samples:
        return samples
    return _telemetry_samples_from_lap_methods(laps)


def _telemetry_samples_from_session_car_data(
    *, session: Any | None, laps: Any
) -> list[TelemetrySample]:
    if session is None:
        return []

    car_data_by_driver = getattr(session, "car_data", None)
    position_data_by_driver = getattr(session, "pos_data", None)
    if not car_data_by_driver:
        return []

    try:
        import pandas as pd
    except ImportError:
        return []

    required_lap_columns = {"Driver", "DriverNumber", "LapNumber", "LapStartTime", "Time"}
    if not required_lap_columns.issubset(set(getattr(laps, "columns", []))):
        return []

    samples: list[TelemetrySample] = []
    try:
        driver_groups = laps.groupby("Driver", sort=False)
    except Exception:
        return []

    for driver, driver_laps in driver_groups:
        if driver_laps.empty:
            continue

        driver_number = str(driver_laps["DriverNumber"].iloc[0])
        car_data = car_data_by_driver.get(driver_number)
        if car_data is None or car_data.empty:
            continue
        position_data = (
            position_data_by_driver.get(driver_number)
            if position_data_by_driver is not None
            and hasattr(position_data_by_driver, "get")
            else None
        )

        required_car_columns = {"SessionTime", "Speed", "Throttle", "Brake", "nGear"}
        if not required_car_columns.issubset(set(getattr(car_data, "columns", []))):
            continue

        lap_windows = (
            driver_laps.loc[:, ["LapNumber", "LapStartTime", "Time"]]
            .dropna(subset=["LapStartTime", "Time"])
            .rename(columns={"Time": "LapEndTime"})
            .sort_values("LapStartTime")
        )
        if lap_windows.empty:
            continue

        car_columns = set(getattr(car_data, "columns", []))
        telemetry_columns = [
            column
            for column in ["SessionTime", "Date", "Speed", "Throttle", "Brake", "nGear"]
            if column in car_columns
        ]
        telemetry = (
            car_data.loc[:, telemetry_columns]
            .dropna(subset=["SessionTime"])
            .sort_values("SessionTime")
            .copy()
        )
        telemetry = _merge_position_columns(
            telemetry,
            position_data,
            pd_module=pd,
        )
        telemetry = telemetry[
            (telemetry["SessionTime"] >= lap_windows["LapStartTime"].iloc[0])
            & (telemetry["SessionTime"] <= lap_windows["LapEndTime"].iloc[-1])
        ].copy()
        if telemetry.empty:
            continue

        telemetry["__row_order"] = range(len(telemetry))
        primary_rows = pd.merge_asof(
            telemetry,
            lap_windows,
            left_on="SessionTime",
            right_on="LapStartTime",
            direction="backward",
        )
        primary_rows = primary_rows[
            primary_rows["SessionTime"] <= primary_rows["LapEndTime"]
        ]

        end_windows = lap_windows.rename(
            columns={"LapEndTime": "SessionTime"}
        ).loc[:, ["SessionTime", "LapNumber", "LapStartTime"]]
        end_windows["LapEndTime"] = end_windows["SessionTime"]
        boundary_rows = telemetry.merge(end_windows, on="SessionTime", how="inner")

        merged = (
            pd.concat([primary_rows, boundary_rows], ignore_index=True)
            .drop_duplicates(subset=["__row_order", "LapNumber"])
            .sort_values(["LapStartTime", "__row_order"])
            .copy()
        )
        if merged.empty:
            continue

        elapsed_seconds = (
            merged["SessionTime"] - merged["LapStartTime"]
        ).dt.total_seconds()
        delta_seconds = elapsed_seconds.groupby(merged["LapNumber"]).diff()
        delta_seconds = delta_seconds.fillna(elapsed_seconds)
        distance_step = merged["Speed"].astype(float) / 3.6 * delta_seconds
        merged["Distance"] = distance_step.groupby(merged["LapNumber"]).cumsum()

        for lap_number, lap_samples in merged.groupby("LapNumber", sort=True):
            row_count = len(lap_samples)
            if row_count == 0:
                continue

            step = max(1, row_count // MAX_TELEMETRY_SAMPLES_PER_LAP)
            sample_indices = list(range(0, row_count, step))
            if sample_indices[-1] != row_count - 1:
                sample_indices.append(row_count - 1)

            for row in lap_samples.iloc[sample_indices].itertuples(index=False):
                samples.append(
                    TelemetrySample(
                        driver=str(driver),
                        lap_number=int(lap_number),
                        distance_m=float(row.Distance),
                        session_time_seconds=_duration_seconds_or_none(
                            getattr(row, "SessionTime", None)
                        ),
                        x=_float_or_none(getattr(row, "X", None)),
                        y=_float_or_none(getattr(row, "Y", None)),
                        z=_float_or_none(getattr(row, "Z", None)),
                        position_status=_string_or_none(
                            getattr(row, "PositionStatus", None)
                        ),
                        speed_kph=_float_or_none(row.Speed),
                        throttle_percent=_percentage_or_none(row.Throttle),
                        brake=_bool_or_none(row.Brake),
                        gear=_int_or_none(row.nGear),
                    )
                )

    return samples


def _telemetry_samples_from_lap_methods(laps: Any) -> list[TelemetrySample]:
    samples: list[TelemetrySample] = []
    for _, lap in laps.iterrows():
        get_car_data = getattr(lap, "get_car_data", None)
        if get_car_data is None:
            continue
        try:
            car_data = get_car_data()
            add_distance = getattr(car_data, "add_distance", None)
            if add_distance is not None:
                car_data = add_distance()
        except Exception:
            continue

        row_count = len(car_data)
        step = max(1, row_count // MAX_TELEMETRY_SAMPLES_PER_LAP)
        for index, (_, row) in enumerate(car_data.iterrows()):
            if index % step != 0 and index != row_count - 1:
                continue
            time_value = row.get("Time")
            fallback_distance = (
                float(time_value.total_seconds())
                if hasattr(time_value, "total_seconds")
                else float(index)
            )
            distance = _float_or_none(row.get("Distance"))
            samples.append(
                TelemetrySample(
                    driver=str(lap.get("Driver")),
                    lap_number=int(lap.get("LapNumber")),
                    distance_m=distance if distance is not None else fallback_distance,
                    session_time_seconds=_duration_seconds_or_none(row.get("SessionTime")),
                    x=_float_or_none(row.get("X")),
                    y=_float_or_none(row.get("Y")),
                    z=_float_or_none(row.get("Z")),
                    position_status=_string_or_none(row.get("Status")),
                    speed_kph=_float_or_none(row.get("Speed")),
                    throttle_percent=_percentage_or_none(row.get("Throttle")),
                    brake=_bool_or_none(row.get("Brake")),
                    gear=_int_or_none(row.get("nGear")),
                )
            )
    return samples


def _merge_position_columns(
    telemetry: Any,
    position_data: Any,
    *,
    pd_module: Any,
) -> Any:
    telemetry = telemetry.copy()
    for column in ["X", "Y", "Z", "PositionStatus"]:
        if column not in telemetry.columns:
            telemetry[column] = None
    if position_data is None or getattr(position_data, "empty", True):
        return telemetry

    position_columns = set(getattr(position_data, "columns", []))
    if not {"X", "Y"}.issubset(position_columns):
        return telemetry

    if "SessionTime" in position_columns:
        raw_position = position_data.loc[
            :,
            [
                column
                for column in ["SessionTime", "X", "Y", "Z", "Status"]
                if column in position_columns
            ],
        ].dropna(subset=["SessionTime", "X", "Y"])
        if raw_position.empty:
            return telemetry
        position = raw_position.rename(columns={"Status": "PositionStatus"}).sort_values(
            "SessionTime"
        )
        merged = pd_module.merge_asof(
            telemetry.sort_values("SessionTime"),
            position,
            on="SessionTime",
            direction="nearest",
            suffixes=("", "_position"),
        )
        return _coalesced_position_columns(merged)

    car_columns = set(getattr(telemetry, "columns", []))
    if "Date" not in car_columns or "Date" not in position_columns:
        return telemetry

    raw_position = position_data.loc[
        :,
        [
            column
            for column in ["Date", "X", "Y", "Z", "Status"]
            if column in position_columns
        ],
    ].dropna(subset=["Date", "X", "Y"])
    if raw_position.empty:
        return telemetry
    position = raw_position.rename(columns={"Status": "PositionStatus"}).sort_values(
        "Date"
    )
    merged = pd_module.merge_asof(
        telemetry.sort_values("Date"),
        position,
        on="Date",
        direction="nearest",
        suffixes=("", "_position"),
    )
    return _coalesced_position_columns(merged)


def _coalesced_position_columns(telemetry: Any) -> Any:
    for column in ["X", "Y", "Z", "PositionStatus"]:
        position_column = f"{column}_position"
        if position_column in telemetry.columns:
            telemetry[column] = telemetry[position_column]
            telemetry = telemetry.drop(columns=[position_column])
    return telemetry


def _string_or_none(value: Any) -> str | None:
    if _is_missing(value):
        return None
    text = str(value)
    return text if text else None


def _timing_delta_seconds(value: Any) -> tuple[float | None, str]:
    if _is_missing(value):
        return None, "missing"
    seconds = _duration_seconds_or_none(value)
    if seconds is not None:
        return seconds, "parsed"

    text = str(value).strip().upper().replace("+", "")
    if text in {"", "PIT", "STOP"}:
        return None, "missing"
    if "LAP" in text:
        return None, "unparseable"
    try:
        return float(text), "parsed"
    except ValueError:
        return None, "unparseable"


def _timing_lap_delta(value: Any) -> int | None:
    if _is_missing(value):
        return None
    text = str(value).strip().upper().replace("+", "")
    if "LAP" not in text:
        return None
    token = text.split("LAP", 1)[0].strip()
    try:
        laps = int(token)
    except ValueError:
        return None
    return laps if laps > 0 else None


def _int_or_none(value: Any) -> int | None:
    if _is_missing(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    if _is_missing(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _percentage_or_none(value: Any) -> float | None:
    number = _float_or_none(value)
    if number is None or not isfinite(number):
        return None
    return min(100.0, max(0.0, number))


def _duration_seconds_or_none(value: Any) -> float | None:
    if hasattr(value, "total_seconds"):
        return _float_or_none(value.total_seconds())
    return _float_or_none(value)


def _bool_or_none(value: Any) -> bool | None:
    if _is_missing(value):
        return None
    return bool(value)


def _bool_or_false(value: Any) -> bool:
    return bool(_bool_or_none(value))


def _has_value(value: Any) -> bool:
    return not _is_missing(value)


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        if value != value:
            return True
    except Exception:
        pass
    return str(value).strip().lower() in {"", "nan", "nat", "none"}

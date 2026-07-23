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
    DriverMetadata,
    LapRecord,
    MissingDataField,
    SessionDataset,
    SessionMetadata,
    SessionQuery,
    SourceProvenance,
    TelemetrySample,
    WeatherSample,
    requests_all_drivers,
)

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
            session.load(laps=True, telemetry=True, weather=True, messages=False)
        except Exception as exc:
            raise DataGatewayError(
                f"FastF1 could not load {query.season} {query.event} {query.session}: {exc}"
            ) from exc
        finally:
            if self.cache_only and offline_mode is not None:
                offline_mode(False)

        return _session_to_dataset(session=session, query=query, cache_only=self.cache_only)


def _session_to_dataset(
    *, session: Any, query: SessionQuery, cache_only: bool
) -> SessionDataset:
    laps = session.laps
    selected_driver_codes = _selected_driver_codes(laps, query)
    if not requests_all_drivers(query.drivers):
        laps = laps.pick_drivers(query.drivers)
        selected_driver_codes = query.drivers

    driver_rows = getattr(session, "results", None)
    drivers = _drivers_from_results(driver_rows, selected_driver_codes)
    lap_records = _lap_records_from_laps(laps)
    telemetry = _telemetry_samples_from_laps(laps, session=session)
    weather = _weather_samples_from_session(session)
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

    return SessionDataset(
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
        weather=weather,
        provenance=SourceProvenance(
            provider="FastF1",
            cache_status="cache-only" if cache_only else "hit",
            source_path=None,
            fetched_from_network=not cache_only,
        ),
        missing_data=missing_data,
    )


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
                    )
                )
    if drivers:
        return drivers
    return [DriverMetadata(abbreviation=driver) for driver in fallback_drivers]


def _lap_records_from_laps(laps: Any) -> list[LapRecord]:
    records: list[LapRecord] = []
    for _, row in laps.iterrows():
        lap_time = row.get("LapTime")
        lap_time_seconds = (
            float(lap_time.total_seconds()) if hasattr(lap_time, "total_seconds") else None
        )
        records.append(
            LapRecord(
                driver=str(row.get("Driver")),
                lap_number=int(row.get("LapNumber")),
                lap_time_seconds=lap_time_seconds,
                compound=_string_or_none(row.get("Compound")),
                stint=_int_or_none(row.get("Stint")),
                position=_int_or_none(row.get("Position")),
                is_pit_in_lap=_has_value(row.get("PitInTime")),
                is_pit_out_lap=_has_value(row.get("PitOutTime")),
                is_deleted=_bool_or_false(row.get("Deleted")),
                is_generated=_bool_or_false(row.get("IsGenerated")),
                is_accurate=_bool_or_none(row.get("IsAccurate")),
                sector_1_time_seconds=_duration_seconds_or_none(row.get("Sector1Time")),
                sector_2_time_seconds=_duration_seconds_or_none(row.get("Sector2Time")),
                sector_3_time_seconds=_duration_seconds_or_none(row.get("Sector3Time")),
                track_status=_string_or_none(row.get("TrackStatus")),
            )
        )
    return records


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

        telemetry = (
            car_data.loc[:, ["SessionTime", "Speed", "Throttle", "Brake", "nGear"]]
            .dropna(subset=["SessionTime"])
            .sort_values("SessionTime")
            .copy()
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
                    speed_kph=_float_or_none(row.get("Speed")),
                    throttle_percent=_percentage_or_none(row.get("Throttle")),
                    brake=_bool_or_none(row.get("Brake")),
                    gear=_int_or_none(row.get("nGear")),
                )
            )
    return samples


def _string_or_none(value: Any) -> str | None:
    if _is_missing(value):
        return None
    text = str(value)
    return text if text else None


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
        return float(value.total_seconds())
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

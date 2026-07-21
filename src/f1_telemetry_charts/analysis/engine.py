"""Deterministic observation extraction from normalized data and artifacts."""

from __future__ import annotations

from collections.abc import Iterable

from f1_telemetry_charts.analysis.manifest import ChartArtifactEntry
from f1_telemetry_charts.analysis.observations import (
    EvidenceLink,
    MetricValue,
    Observation,
)
from f1_telemetry_charts.data.models import LapRecord, SessionDataset, TelemetrySample


def extract_observations(
    dataset: SessionDataset,
    artifacts: Iterable[ChartArtifactEntry],
) -> list[Observation]:
    artifact_map = {artifact.recipe_id: artifact for artifact in artifacts}
    observations: list[Observation] = []

    fastest_lap = _fastest_lap(dataset.laps)
    if fastest_lap is not None:
        observations.append(_fastest_lap_observation(fastest_lap, artifact_map))

    final_position_lap = _best_final_position_lap(dataset.laps)
    if final_position_lap is not None:
        observations.append(
            _final_position_observation(final_position_lap, dataset, artifact_map)
        )

    peak_speed = _peak_speed_sample(dataset.telemetry)
    if peak_speed is not None:
        observations.append(_peak_speed_observation(peak_speed, artifact_map))

    compounds = sorted(
        {
            lap.compound.upper()
            for lap in dataset.laps
            if lap.compound is not None and lap.compound.strip()
        }
    )
    if compounds:
        observations.append(_compound_observation(compounds, artifact_map))

    return observations


def _fastest_lap(laps: Iterable[LapRecord]) -> LapRecord | None:
    timed_laps = [lap for lap in laps if lap.lap_time_seconds is not None]
    if not timed_laps:
        return None
    return min(timed_laps, key=lambda lap: lap.lap_time_seconds or float("inf"))


def _best_final_position_lap(laps: Iterable[LapRecord]) -> LapRecord | None:
    latest_by_driver: dict[str, LapRecord] = {}
    for lap in laps:
        if lap.position is None:
            continue
        current = latest_by_driver.get(lap.driver)
        if current is None or lap.lap_number > current.lap_number:
            latest_by_driver[lap.driver] = lap
    if not latest_by_driver:
        return None
    return min(latest_by_driver.values(), key=lambda lap: lap.position or 99)


def _peak_speed_sample(samples: Iterable[TelemetrySample]) -> TelemetrySample | None:
    speed_samples = [sample for sample in samples if sample.speed_kph is not None]
    if not speed_samples:
        return None
    return max(speed_samples, key=lambda sample: sample.speed_kph or 0)


def _fastest_lap_observation(
    lap: LapRecord,
    artifact_map: dict[str, ChartArtifactEntry],
) -> Observation:
    lap_time = round(lap.lap_time_seconds or 0, 3)
    return Observation(
        observation_id=f"obs-fastest-lap-{lap.driver.lower()}-{lap.lap_number}",
        family="lap_time",
        text=(
            f"{lap.driver} recorded the fastest selected-driver lap at "
            f"{lap_time:.3f}s on lap {lap.lap_number}."
        ),
        priority=1,
        confidence="high",
        evidence=_evidence(artifact_map, "lap_time_delta", ["laps.lap_time_seconds"]),
        metrics=[
            MetricValue(
                name="fastest_lap_time",
                value=lap_time,
                unit="s",
                driver=lap.driver,
            ),
            MetricValue(name="lap_number", value=lap.lap_number, driver=lap.driver),
        ],
        limitations=[
            "Comparison is limited to selected drivers and available lap records."
        ],
    )


def _final_position_observation(
    lap: LapRecord,
    dataset: SessionDataset,
    artifact_map: dict[str, ChartArtifactEntry],
) -> Observation:
    expected_drivers = {driver.abbreviation for driver in dataset.drivers}
    drivers_with_position = {item.driver for item in dataset.laps if item.position is not None}
    missing = sorted(expected_drivers - drivers_with_position)
    limitations = [
        "Final position is based on the last available lap position per selected driver."
    ]
    if missing:
        limitations.append(
            "Position data are missing for selected drivers: " + ", ".join(missing)
        )

    return Observation(
        observation_id=f"obs-final-position-{lap.driver.lower()}",
        family="position",
        text=(
            f"{lap.driver} held the best final recorded selected-driver position: "
            f"P{lap.position} on lap {lap.lap_number}."
        ),
        priority=2,
        confidence="medium" if missing else "high",
        evidence=_evidence(
            artifact_map,
            "position_progression",
            ["laps.position", "laps.lap_number"],
        ),
        metrics=[
            MetricValue(name="position", value=lap.position or 0, driver=lap.driver),
            MetricValue(name="lap_number", value=lap.lap_number, driver=lap.driver),
        ],
        limitations=limitations,
    )


def _peak_speed_observation(
    sample: TelemetrySample,
    artifact_map: dict[str, ChartArtifactEntry],
) -> Observation:
    speed = round(sample.speed_kph or 0, 1)
    return Observation(
        observation_id=f"obs-peak-speed-{sample.driver.lower()}-{sample.lap_number}",
        family="telemetry",
        text=(
            f"{sample.driver} reached the highest recorded selected-driver speed "
            f"at {speed:.1f} km/h on lap {sample.lap_number}."
        ),
        priority=3,
        confidence="medium",
        evidence=_evidence(
            artifact_map,
            "telemetry_trace",
            ["telemetry.speed_kph", "telemetry.distance_m"],
        ),
        metrics=[
            MetricValue(name="peak_speed", value=speed, unit="km/h", driver=sample.driver),
            MetricValue(name="lap_number", value=sample.lap_number, driver=sample.driver),
            MetricValue(
                name="distance",
                value=round(sample.distance_m, 1),
                unit="m",
                driver=sample.driver,
            ),
        ],
        limitations=[
            "Telemetry sampling may miss the absolute session peak speed.",
            "This observation describes recorded data only and does not infer causality.",
        ],
    )


def _compound_observation(
    compounds: list[str],
    artifact_map: dict[str, ChartArtifactEntry],
) -> Observation:
    return Observation(
        observation_id="obs-tyre-compounds-selected",
        family="tyre_strategy",
        text="Selected drivers used these recorded tyre compounds: "
        + ", ".join(compounds)
        + ".",
        priority=4,
        confidence="high",
        evidence=_evidence(artifact_map, "tyre_strategy", ["laps.compound"]),
        metrics=[MetricValue(name="compound_count", value=len(compounds))],
        limitations=[
            "Compound coverage depends on available lap-level tyre data.",
            "This observation does not explain why a compound was selected.",
        ],
    )


def _evidence(
    artifact_map: dict[str, ChartArtifactEntry],
    recipe_id: str,
    source_fields: list[str],
) -> list[EvidenceLink]:
    artifact = artifact_map.get(recipe_id)
    if artifact is None:
        return []
    return [
        EvidenceLink(
            artifact_id=artifact.artifact_id,
            recipe_id=artifact.recipe_id,
            image_path=artifact.image_path,
            metadata_path=artifact.metadata_path,
            source_fields=source_fields,
        )
    ]

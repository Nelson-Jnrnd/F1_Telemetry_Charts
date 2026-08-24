"""Practice-only analytical providers for SPEC-012.

The module keeps official classification separate from lap timing and treats
run pace as observed, programme-unknown evidence.  It intentionally exposes no
fuel, engine-mode, setup, intent, degradation, or weekend prediction model.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import Any

from f1_telemetry_charts.analysis.findings import (
    AnalyticalResultRecord,
    MeasurementCategory,
    canonical_fingerprint,
    stable_id,
)
from f1_telemetry_charts.data import SessionDataset
from f1_telemetry_charts.data.models import LapRecord
from f1_telemetry_charts.strategy import (
    descriptive_statistics,
    observed_pace_evolution,
    type7_quantile,
)


PRACTICE_RESULT_SCHEMA_VERSION = 1
PRACTICE_RUN_POLICY_ID = "practice-representative-run-policy"
PRACTICE_RUN_POLICY_VERSION = 1
PRACTICE_COMPARISON_POLICY_ID = "practice-paired-tyre-age-comparison"
PRACTICE_COMPARISON_POLICY_VERSION = 1
PRACTICE_RESULT_TYPES = (
    "practice_classification",
    "practice_run_chronology",
    "practice_long_run_pace",
    "practice_observed_pace_evolution",
    "practice_long_run_comparison",
    "practice_conditions",
    "practice_interruptions",
    "practice_traffic_context",
)
_PRACTICE_NAMES = {"fp1", "fp2", "fp3", "practice 1", "practice 2", "practice 3"}
_UNKNOWN_PROGRAMME = (
    "Fuel load, engine mode, setup, tyre preparation, and programme intent are unknown."
)


def is_standard_practice(session_name: str) -> bool:
    return session_name.strip().lower() in _PRACTICE_NAMES


def materialize_practice_results(
    target_session_id: str, dataset: SessionDataset
) -> list[AnalyticalResultRecord]:
    if not is_standard_practice(dataset.metadata.session):
        raise ValueError(
            "Practice publication reports support one standard FP1, FP2, or FP3 "
            "session only; Qualifying, Sprint, Sprint Qualifying, Race, testing, "
            "and multi-session targets are unsupported."
        )
    provenance = _provenance(dataset)
    chronology, runs = _chronology_result(target_session_id, dataset, provenance)
    pace_results: list[AnalyticalResultRecord] = []
    evolution_results: list[AnalyticalResultRecord] = []
    eligible_runs: list[dict[str, Any]] = []
    for run in runs:
        representative = run["representative_laps"]
        if len(representative) < 5:
            continue
        pace = _pace_result(target_session_id, run, provenance)
        pace_results.append(pace)
        if len(representative) >= 8:
            eligible_runs.append(run)
        evolution_results.extend(_evolution_results(target_session_id, run, provenance))
    comparisons = [
        _comparison_result(target_session_id, left, right, dataset, provenance)
        for left, right in combinations(eligible_runs, 2)
        if left["driver"] != right["driver"]
    ]
    results = [
        _classification_result(target_session_id, dataset, provenance),
        chronology,
        *pace_results,
        *evolution_results,
        *comparisons,
        _conditions_result(target_session_id, dataset, provenance),
        _interruptions_result(target_session_id, dataset, provenance),
        _traffic_result(target_session_id, dataset, provenance),
    ]
    return sorted(results, key=lambda item: (item.result_type, item.result_id))


def _classification_result(target: str, dataset: SessionDataset, provenance: dict[str, Any]) -> AnalyticalResultRecord:
    entries = [item.model_dump(mode="json") for item in sorted(dataset.practice_classification, key=lambda item: (item.position, item.driver))]
    status = "available" if entries and len(entries) == len(dataset.drivers) else "partial" if entries else "unavailable"
    leader = entries[0] if entries else None
    summary = (
        f"{leader['driver']} led the official {dataset.metadata.session.upper()} classification with {_format_lap_time(float(leader['fastest_time_seconds']))}."
        if leader and leader.get("fastest_time_seconds") is not None
        else "The official Practice classification is unavailable."
    )
    limitations = [] if status == "available" else ["Official Practice classification coverage is incomplete; lap timing was not substituted."]
    return _record(target, "practice_classification", payload={"entries": entries, "summary": summary}, subjects=[row["driver"] for row in entries], boundaries={"session": dataset.metadata.session.upper(), "source": "official_session_results"}, provenance=provenance, coverage={"available": len(entries), "expected": len(dataset.drivers)}, quality=_quality(len(entries), len(dataset.drivers)), status=status, measurement_category="measured", limitations=limitations)


def _chronology_result(target: str, dataset: SessionDataset, provenance: dict[str, Any]) -> tuple[AnalyticalResultRecord, list[dict[str, Any]]]:
    runs: list[dict[str, Any]] = []
    by_driver: dict[str, list[LapRecord]] = defaultdict(list)
    for lap in dataset.laps:
        by_driver[lap.driver].append(lap)
    for driver, laps in sorted(by_driver.items()):
        current: list[LapRecord] = []
        ordinal = 0
        opened_by_pit = False
        for lap in sorted(laps, key=lambda item: (item.lap_end_time_seconds if item.lap_end_time_seconds is not None else float(item.lap_number), item.lap_number)):
            if lap.is_pit_out_lap and current:
                ordinal += 1
                runs.append(_run_payload(driver, ordinal, current, opened_by_pit, False))
                current = []
            if not current:
                opened_by_pit = lap.is_pit_out_lap
            current.append(lap)
            if lap.is_pit_in_lap:
                ordinal += 1
                runs.append(_run_payload(driver, ordinal, current, opened_by_pit, True))
                current = []
        if current:
            ordinal += 1
            runs.append(_run_payload(driver, ordinal, current, opened_by_pit, False))
    partial = sum(run["boundary_confidence"] == "partial" for run in runs)
    payload_runs = [{key: value for key, value in run.items() if key != "_laps"} for run in runs]
    record = _record(target, "practice_run_chronology", payload={"runs": payload_runs, "summary": f"Reconstructed {len(runs)} neutral pit-bounded Practice runs; {partial} have partial boundaries."}, subjects=sorted(by_driver), boundaries={"chronology": "session_time", "run_label": "Run N"}, provenance=provenance, coverage={"runs": len(runs), "partial_boundaries": partial, "timed_laps": sum(1 for lap in dataset.laps if lap.lap_time_seconds is not None)}, quality={"level": "high" if runs and not partial else "medium" if runs else "unavailable"}, status="available" if runs and not partial else "partial" if runs else "unavailable", limitations=[] if not partial else ["Incomplete pit boundaries remain partial; no pit event was invented."])
    return record, runs


def _run_payload(driver: str, ordinal: int, laps: list[LapRecord], opened: bool, closed: bool) -> dict[str, Any]:
    timed = [lap for lap in laps if lap.lap_time_seconds is not None]
    preliminary: list[tuple[LapRecord, list[str]]] = [(lap, _exclusion_reasons(lap)) for lap in timed]
    representative: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for progress, (lap, reasons) in enumerate(preliminary, start=1):
        row = _lap_payload(lap, progress)
        if reasons:
            excluded.append({**row, "exclusion_reasons": reasons})
        else:
            representative.append(row)
    compounds = sorted({str(row["compound"]).upper() for row in representative if row.get("compound")})
    start = min((lap.lap_start_time_seconds for lap in laps if lap.lap_start_time_seconds is not None), default=None)
    end = max((lap.lap_end_time_seconds for lap in laps if lap.lap_end_time_seconds is not None), default=None)
    return {"run_id": stable_id("practice-run", driver, str(ordinal), str(start), str(end)), "driver": driver, "ordinal": ordinal, "label": f"Run {ordinal}", "pit_out_recorded": opened, "pit_in_recorded": closed, "boundary_confidence": "complete" if opened and closed else "partial", "session_start_seconds": start, "session_end_seconds": end, "compound": compounds[0] if len(compounds) == 1 else None, "compound_state": "known" if len(compounds) == 1 else "confounded" if len(compounds) > 1 else "unknown", "representative_laps": representative, "excluded_laps": excluded, "representative_count": len(representative), "excluded_count": len(excluded), "coverage": len(representative) / len(timed) if timed else 0.0, "_laps": laps}


def _lap_payload(lap: LapRecord, progress: int) -> dict[str, Any]:
    return {"driver": lap.driver, "lap_number": lap.lap_number, "run_progress": progress, "lap_time_seconds": lap.lap_time_seconds, "session_time_seconds": lap.lap_end_time_seconds, "compound": lap.compound, "tyre_age": lap.tyre_age, "track_status": lap.track_status}


def _exclusion_reasons(lap: LapRecord) -> list[str]:
    reasons: list[str] = []
    if lap.is_pit_in_lap: reasons.append("pit_in_lap")
    if lap.is_pit_out_lap: reasons.append("pit_out_lap")
    if lap.is_deleted: reasons.append("deleted_lap")
    if lap.is_generated: reasons.append("generated_lap")
    if lap.is_accurate is False: reasons.append("inaccurate_lap")
    if lap.track_status and any(code not in {"1"} for code in str(lap.track_status)): reasons.append("non_green_track_status")
    return reasons


def _pace_result(target: str, run: dict[str, Any], provenance: dict[str, Any]) -> AnalyticalResultRecord:
    rows = run["representative_laps"]
    statistics = descriptive_statistics(float(row["lap_time_seconds"]) for row in rows).model_dump(mode="json")
    count = len(rows)
    run_status = "long_run" if count >= 8 else "sustained_run"
    coverage = float(run["coverage"])
    quality = "high" if coverage >= 0.9 else "medium" if coverage >= 0.75 else "low"
    summary = (
        f"{run['driver']} {run['label']} recorded a {run_status.replace('_', ' ')} of {count} representative laps on {run.get('compound') or 'an unknown compound'}, with a median of {_format_lap_time(float(statistics['median']))}. {_UNKNOWN_PROGRAMME}"
    )
    payload = {key: run[key] for key in ("run_id", "driver", "ordinal", "label", "boundary_confidence", "session_start_seconds", "session_end_seconds", "compound", "compound_state", "representative_laps", "excluded_laps", "representative_count", "excluded_count", "coverage")}
    payload.update({"run_status": run_status, "statistics": statistics, "tyre_age_coverage": sum(row.get("tyre_age") is not None for row in rows), "summary": summary})
    return _record(target, "practice_long_run_pace", payload=payload, subjects=[run["driver"]], boundaries={"run_id": run["run_id"], "session_time_window": [run["session_start_seconds"], run["session_end_seconds"]]}, provenance=provenance, coverage={"representative": count, "excluded": run["excluded_count"], "ratio": coverage}, quality={"level": quality}, status="available" if run_status == "long_run" else "partial", limitations=[_UNKNOWN_PROGRAMME, "Observed lap times are not fuel-corrected and do not establish competitive order."])


def _evolution_results(target: str, run: dict[str, Any], provenance: dict[str, Any]) -> list[AnalyticalResultRecord]:
    rows = run["representative_laps"]
    bases: list[tuple[str, list[tuple[float, float]]]] = [("stint_progress", [(float(row["run_progress"]), float(row["lap_time_seconds"])) for row in rows])]
    tyre_rows = [row for row in rows if row.get("tyre_age") is not None]
    monotonic = all(float(tyre_rows[index]["tyre_age"]) <= float(tyre_rows[index + 1]["tyre_age"]) for index in range(len(tyre_rows) - 1))
    if len(tyre_rows) == len(rows) and monotonic and len({row["tyre_age"] for row in tyre_rows}) == len(rows):
        bases.append(("tyre_age", [(float(row["tyre_age"]), float(row["lap_time_seconds"])) for row in tyre_rows]))
    results: list[AnalyticalResultRecord] = []
    for basis, samples in bases:
        fit = observed_pace_evolution(samples, basis=basis, expected_count=len(rows)).model_dump(mode="json")
        count = len(rows)
        publishable = count >= 8 and fit["status"] == "available" and fit["quality"] in {"medium", "high"}
        change = (float(fit["slope"]) * (max(x for x, _ in samples) - min(x for x, _ in samples))) if fit.get("slope") is not None else None
        summary = (
            f"{run['driver']} {run['label']} showed an observed {change:+.3f}-second change from the fitted start to end on the {basis.replace('_', ' ')} basis. {_UNKNOWN_PROGRAMME}"
            if change is not None else f"Observed pace evolution is unavailable for {run['driver']} {run['label']}."
        )
        results.append(_record(target, "practice_observed_pace_evolution", payload={"run_id": run["run_id"], "driver": run["driver"], "label": run["label"], "compound": run["compound"], "basis": basis, "fit": fit, "samples": [{"x": x, "lap_time_seconds": y} for x, y in samples], "publishable": publishable, "effect_size_seconds": abs(change) if change is not None else None, "summary": summary}, subjects=[run["driver"]], boundaries={"run_id": run["run_id"], "basis": basis}, provenance=provenance, coverage={"representative": count, "ratio": run["coverage"]}, quality={"level": fit["quality"]}, status="available" if fit["status"] == "available" else "unavailable", limitations=[_UNKNOWN_PROGRAMME, "The fitted slope is observed pace evolution, not causal tyre degradation."]))
    return results


def _comparison_result(target: str, left: dict[str, Any], right: dict[str, Any], dataset: SessionDataset, provenance: dict[str, Any]) -> AnalyticalResultRecord:
    overlap_start = max(value for value in (left["session_start_seconds"], right["session_start_seconds"]) if value is not None) if left["session_start_seconds"] is not None and right["session_start_seconds"] is not None else None
    overlap_end = min(value for value in (left["session_end_seconds"], right["session_end_seconds"]) if value is not None) if left["session_end_seconds"] is not None and right["session_end_seconds"] is not None else None
    same_compound = left["compound"] is not None and left["compound"] == right["compound"]
    same_condition = _compound_class(left["compound"]) == _compound_class(right["compound"]) and _compound_class(left["compound"]) is not None
    overlap = overlap_start is not None and overlap_end is not None and overlap_start <= overlap_end
    boundary = overlap and _material_status_boundary(dataset, float(overlap_start), float(overlap_end))
    left_age = _age_rows(left, overlap_start, overlap_end)
    right_age = _age_rows(right, overlap_start, overlap_end)
    shared = sorted(set(left_age) & set(right_age))
    pairs = [{"tyre_age": age, "left": left_age[age], "right": right_age[age], "difference_seconds": left_age[age]["lap_time_seconds"] - right_age[age]["lap_time_seconds"]} for age in shared]
    if not same_compound or not same_condition or not overlap or boundary:
        status = "confounded"
    elif not _reliable_age(left) or not _reliable_age(right) or len(pairs) < 8:
        status = "unknown"
    else:
        status = "comparable"
    scalar = type7_quantile((float(pair["difference_seconds"]) for pair in pairs), 0.5) if status == "comparable" else None
    summary = (
        f"Across {len(pairs)} paired {left['compound']} tyre-age samples, {left['driver']} {left['label']} was {abs(float(scalar)):.3f} seconds {'slower than' if float(scalar) > 0 else 'faster than'} {right['driver']} {right['label']} by the paired median. {_UNKNOWN_PROGRAMME}"
        if scalar is not None else f"{left['driver']} {left['label']} and {right['driver']} {right['label']} are {status}; no scalar pace ranking is available."
    )
    return _record(target, "practice_long_run_comparison", payload={"left_run_id": left["run_id"], "right_run_id": right["run_id"], "drivers": [left["driver"], right["driver"]], "run_labels": [left["label"], right["label"]], "compound": left["compound"] if same_compound else None, "overlap_window_seconds": [overlap_start, overlap_end], "tyre_age_state": "reliable" if _reliable_age(left) and _reliable_age(right) else "unknown", "condition_state": "compatible" if same_condition else "confounded", "track_status_boundary": boundary, "comparison_status": status, "paired_samples": pairs, "paired_sample_count": len(pairs), "shared_tyre_age_range": [shared[0], shared[-1]] if shared else None, "paired_median_difference_seconds": scalar, "effect_size_seconds": abs(float(scalar)) if scalar is not None else None, "summary": summary}, subjects=sorted([left["driver"], right["driver"]]), boundaries={"run_ids": [left["run_id"], right["run_id"]], "session_time_window": [overlap_start, overlap_end]}, provenance=provenance, coverage={"paired_samples": len(pairs), "required": 8}, quality={"level": "high" if status == "comparable" else "low" if status == "confounded" else "provisional"}, status=status, limitations=[_UNKNOWN_PROGRAMME, "This is an observed-sample comparison, not a fuel-corrected ranking."])


def _age_rows(run: dict[str, Any], start: float | None, end: float | None) -> dict[float, dict[str, Any]]:
    rows: dict[float, dict[str, Any]] = {}
    for row in run["representative_laps"]:
        age, time = row.get("tyre_age"), row.get("session_time_seconds")
        if age is None or time is None or start is None or end is None or not start <= float(time) <= end:
            continue
        rows.setdefault(float(age), row)
    return rows


def _reliable_age(run: dict[str, Any]) -> bool:
    ages = [row.get("tyre_age") for row in run["representative_laps"]]
    return all(age is not None for age in ages) and len(set(ages)) == len(ages) and all(float(ages[index]) <= float(ages[index + 1]) for index in range(len(ages) - 1))


def _conditions_result(target: str, dataset: SessionDataset, provenance: dict[str, Any]) -> AnalyticalResultRecord:
    compounds = sorted({str(lap.compound).upper() for lap in dataset.laps if lap.compound})
    rain = [sample for sample in dataset.weather if sample.rainfall]
    mixed = bool(rain) or len({_compound_class(value) for value in compounds if _compound_class(value)}) > 1
    material = mixed
    summary = f"Recorded Practice conditions were {'wet or mixed' if mixed else 'dry or not recorded as wet'}; compounds observed: {', '.join(compounds) or 'unknown'}."
    return _record(target, "practice_conditions", payload={"weather_samples": [sample.model_dump(mode="json") for sample in dataset.weather], "compounds": compounds, "material": material, "condition_state": "mixed_or_wet" if mixed else "dry" if compounds else "unknown", "effect_size_seconds": _weather_duration(dataset.weather), "summary": summary}, subjects=[], boundaries={"session": dataset.metadata.session.upper()}, provenance={**provenance, "source": "weather_and_compound_records"}, coverage={"weather_samples": len(dataset.weather), "compound_laps": sum(lap.compound is not None for lap in dataset.laps)}, quality={"level": "high" if dataset.weather and compounds else "medium" if dataset.weather or compounds else "unavailable"}, status="available" if dataset.weather or compounds else "unavailable", measurement_category="measured", limitations=[] if dataset.weather else ["Recorded weather samples are unavailable."])


def _interruptions_result(target: str, dataset: SessionDataset, provenance: dict[str, Any]) -> AnalyticalResultRecord:
    statuses = sorted(dataset.session_status, key=lambda row: row.time_seconds)
    events = []
    for index, row in enumerate(statuses):
        if row.status.strip().lower() not in {"aborted", "suspended", "red flag", "red flagged"}:
            continue
        end = statuses[index + 1].time_seconds if index + 1 < len(statuses) else row.time_seconds
        events.append({"status": row.status, "start_time_seconds": row.time_seconds, "end_time_seconds": end, "duration_seconds": max(0.0, end - row.time_seconds)})
    affected = sum(float(event["duration_seconds"]) for event in events)
    material = bool(events)
    summary = f"Recorded session control shows {len(events)} Practice interruption state changes affecting approximately {affected:.0f} seconds." if events else "No recorded Practice interruption was available."
    return _record(target, "practice_interruptions", payload={"events": events, "material": material, "effect_size_seconds": affected, "summary": summary}, subjects=[], boundaries={"session": dataset.metadata.session.upper()}, provenance={**provenance, "source": "session_status"}, coverage={"events": len(events)}, quality={"level": "high" if dataset.session_status else "unavailable"}, status="available" if dataset.session_status else "unavailable", measurement_category="measured", limitations=[] if dataset.session_status else ["Session-control timing is unavailable."])


def _traffic_result(target: str, dataset: SessionDataset, provenance: dict[str, Any]) -> AnalyticalResultRecord:
    aligned = []
    for lap in dataset.laps:
        if lap.lap_end_time_seconds is None:
            continue
        nearby = [row for row in dataset.timing if row.driver != lap.driver and abs(row.session_time_seconds - lap.lap_end_time_seconds) <= 2.0 and row.interval_to_ahead_seconds is not None and abs(row.interval_to_ahead_seconds) <= 1.0]
        if nearby:
            aligned.append({"driver": lap.driver, "lap_number": lap.lap_number, "session_time_seconds": lap.lap_end_time_seconds, "nearby_drivers": sorted({row.driver for row in nearby}), "assessment": "proximity_recorded; time loss not inferred"})
    return _record(target, "practice_traffic_context", payload={"lap_specific_proximity": aligned, "summary": "Lap-specific aligned proximity remains inspectable evidence; no traffic loss is inferred."}, subjects=sorted({row["driver"] for row in aligned}), boundaries={"alignment_seconds": 2.0, "proximity_seconds": 1.0}, provenance={**provenance, "source": "aligned_timing"}, coverage={"aligned_laps": len(aligned), "timing_records": len(dataset.timing)}, quality={"level": "medium" if aligned else "unavailable"}, status="available" if aligned else "unavailable", limitations=["Generic proximity counts do not become findings and lap time alone does not establish traffic."])


def _material_status_boundary(dataset: SessionDataset, start: float, end: float) -> bool:
    if any(start <= row.time_seconds <= end and row.status.strip().lower() not in {"started", "green", "finished"} for row in dataset.session_status):
        return True
    return any(lap.lap_end_time_seconds is not None and start <= lap.lap_end_time_seconds <= end and lap.track_status and any(code not in {"1"} for code in str(lap.track_status)) for lap in dataset.laps)


def _weather_duration(samples: list[Any]) -> float:
    wet = [sample.time_seconds for sample in samples if sample.rainfall]
    return max(wet) - min(wet) if len(wet) > 1 else 0.0


def _compound_class(compound: str | None) -> str | None:
    if not compound: return None
    value = compound.upper()
    if value in {"WET", "INTERMEDIATE", "W", "I"}: return "wet"
    if value in {"SOFT", "MEDIUM", "HARD", "S", "M", "H", "C1", "C2", "C3", "C4", "C5", "C6"}: return "dry"
    return None


def _format_lap_time(seconds: float) -> str:
    minutes, remainder = divmod(seconds, 60)
    return f"{int(minutes)}:{remainder:06.3f}"


def _provenance(dataset: SessionDataset) -> dict[str, Any]:
    return {"provider": dataset.provenance.provider, "cache_status": dataset.provenance.cache_status, "source_path": str(dataset.provenance.source_path) if dataset.provenance.source_path else None, "fetched_from_network": dataset.provenance.fetched_from_network}


def _quality(available: int, expected: int) -> dict[str, Any]:
    ratio = available / expected if expected else 0.0
    return {"level": "high" if ratio == 1 else "medium" if ratio >= 0.5 else "low" if ratio > 0 else "unavailable", "coverage_ratio": ratio}


def _record(target: str, result_type: str, *, payload: dict[str, Any], subjects: list[str], boundaries: dict[str, Any], provenance: dict[str, Any], coverage: dict[str, Any], quality: dict[str, Any], status: str, measurement_category: MeasurementCategory = "derived", limitations: list[str]) -> AnalyticalResultRecord:
    semantic = {"result_type": result_type, "schema_version": PRACTICE_RESULT_SCHEMA_VERSION, "target_session_id": target, "payload": payload, "subjects": subjects, "boundaries": boundaries, "provenance": provenance, "coverage": coverage, "quality": quality, "status": status, "measurement_category": measurement_category, "limitations": limitations}
    fingerprint = canonical_fingerprint(semantic)
    return AnalyticalResultRecord(result_id=stable_id("result", result_type, target, fingerprint), result_type=result_type, result_schema_version=PRACTICE_RESULT_SCHEMA_VERSION, target_session_id=target, result_fingerprint=fingerprint, analytical_status=status, value_category="descriptive", measurement_category=measurement_category, subjects=subjects, boundaries=boundaries, provenance=provenance, coverage=coverage, quality=quality, payload=payload, analytical_basis={"run_policy_id": PRACTICE_RUN_POLICY_ID, "run_policy_version": PRACTICE_RUN_POLICY_VERSION, "comparison_policy_id": PRACTICE_COMPARISON_POLICY_ID, "comparison_policy_version": PRACTICE_COMPARISON_POLICY_VERSION}, limitations=limitations)

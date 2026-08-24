"""Qualifying-only analytical providers for SPEC-011.

The providers deliberately consume official segment records separately from lap
timing.  They never reconstruct an official advancement outcome from laps.
"""

from __future__ import annotations

from collections import defaultdict
from math import hypot
from statistics import median
from typing import Any, Literal

from f1_telemetry_charts.analysis.findings import (
    AnalyticalResultRecord,
    MeasurementCategory,
    canonical_fingerprint,
    stable_id,
)
from f1_telemetry_charts.data import SessionDataset
from f1_telemetry_charts.data.models import LapRecord, QualifyingSegmentClassification


QUALIFYING_RESULT_SCHEMA_VERSION = 1
QUALIFYING_TEMPORAL_POLICY_ID = "qualifying-observed-temporal-evolution"
QUALIFYING_TEMPORAL_POLICY_VERSION = 2
QUALIFYING_SECTOR_RECONCILIATION_TOLERANCE_SECONDS = 0.003
QUALIFYING_RESULT_TYPES = (
    "qualifying_segment_classification",
    "qualifying_attempt_progression",
    "qualifying_margin_comparison",
    "qualifying_sector_contribution",
    "qualifying_temporal_evolution",
    "qualifying_interruptions",
    "qualifying_traffic_context",
    "qualifying_deleted_laps",
    "qualifying_conditions",
)


def is_standard_qualifying(session_name: str) -> bool:
    return session_name.strip().lower() in {"qualifying", "q"}


def materialize_qualifying_results(
    target_session_id: str, dataset: SessionDataset
) -> list[AnalyticalResultRecord]:
    if not is_standard_qualifying(dataset.metadata.session):
        raise ValueError(
            "Qualifying publication reports support standard Qualifying only; "
            "Race, Practice, Sprint, and Sprint Qualifying are unsupported."
        )
    segments = {item.segment: item for item in dataset.qualifying_segments}
    provenance = _provenance(dataset)
    classification = _classification_result(target_session_id, dataset, segments, provenance)
    integrity_conflicts = _deletion_integrity_conflicts(dataset, segments)
    progression = _progression_result(target_session_id, dataset, segments, integrity_conflicts, provenance)
    margins = _margin_result(target_session_id, segments, provenance)
    sectors = _sector_result(target_session_id, dataset, segments, provenance)
    temporal = _temporal_result(target_session_id, dataset, integrity_conflicts, provenance)
    interruptions = _interruptions_result(target_session_id, dataset, provenance)
    traffic = _traffic_result(target_session_id, dataset, provenance)
    deleted = _deleted_result(target_session_id, dataset, integrity_conflicts, provenance)
    conditions = _conditions_result(target_session_id, dataset, provenance)
    return sorted(
        [classification, progression, margins, sectors, temporal, interruptions, traffic, deleted, conditions],
        key=lambda item: item.result_type,
    )


def _classification_result(target: str, dataset: SessionDataset, segments: dict[str, QualifyingSegmentClassification], provenance: dict[str, Any]) -> AnalyticalResultRecord:
    payload_segments = []
    for segment_name in ("Q1", "Q2", "Q3"):
        segment = segments.get(segment_name)
        if segment is None:
            payload_segments.append({"segment": segment_name, "status": "unavailable", "official_segment_order": [], "official_advancement_outcome": []})
            continue
        ordered = [entry.model_dump(mode="json") for entry in sorted(segment.entries, key=lambda entry: entry.position)]
        payload_segments.append(
            {
                "segment": segment_name,
                "status": segment.status,
                "source_conflicts": segment.source_conflicts,
                "official_segment_order": ordered,
                "official_advancement_outcome": [
                    {"driver": entry.driver, "advanced": entry.advanced, "basis": entry.advancement_basis}
                    for entry in segment.entries
                    if segment_name != "Q3"
                ],
            }
        )
    final = [
        {
            "driver": driver.abbreviation,
            "position": driver.classification_position,
            "status": driver.result_status,
        }
        for driver in sorted(
            (driver for driver in dataset.drivers if driver.classification_position is not None),
            key=lambda driver: (driver.classification_position, driver.abbreviation),
        )
    ]
    complete = all(name in segments and segments[name].status == "complete" for name in ("Q1", "Q2", "Q3"))
    available = sum(name in segments for name in ("Q1", "Q2", "Q3"))
    q3 = segments.get("Q3")
    pole_entry = next((entry for entry in q3.entries if entry.position == 1), None) if q3 else None
    pole = {"driver": pole_entry.driver, "time_seconds": pole_entry.time_seconds} if pole_entry else None
    summary = (
        f"{pole['driver']} took pole with an official Q3 time of {_format_lap_time(float(pole['time_seconds']))}."
        if pole and pole.get("time_seconds") is not None
        else "The official Q3 pole result is unavailable."
    )
    conflicts = [conflict for segment in segments.values() for conflict in segment.source_conflicts]
    status = "source_conflict" if conflicts else "available" if complete and len(final) == len(dataset.drivers) else "partial" if available or final else "unavailable"
    limitations = [] if status == "available" else ["Official segment or session classification coverage is incomplete or conflicting; lap timing was not substituted."]
    limitations.extend(conflicts)
    return _record(target, "qualifying_segment_classification", payload={"segments": payload_segments, "official_session_classification": final, "summary": summary}, subjects=[entry["driver"] for entry in final], boundaries={"segments": ["Q1", "Q2", "Q3"]}, provenance=provenance, coverage={"segments_available": available, "segments_expected": 3, "session_entries_available": len(final), "session_entries_expected": len(dataset.drivers)}, quality=_quality(available + len(final), 3 + len(dataset.drivers)), status=status, measurement_category="measured", limitations=limitations)


def _progression_result(
    target: str,
    dataset: SessionDataset,
    segments: dict[str, QualifyingSegmentClassification],
    integrity_conflicts: list[dict[str, Any]],
    provenance: dict[str, Any],
) -> AnalyticalResultRecord:
    conflict_keys = {
        (str(item["driver"]), str(item["segment"]), int(item["lap_number"]))
        for item in integrity_conflicts
    }
    by_driver_segment: dict[tuple[str, str], list[LapRecord]] = defaultdict(list)
    unassigned = 0
    for lap in dataset.laps:
        if lap.qualifying_segment:
            by_driver_segment[(lap.driver, lap.qualifying_segment)].append(lap)
        elif lap.lap_time_seconds is not None:
            unassigned += 1
    records: list[dict[str, Any]] = []
    for (driver, segment), laps in sorted(by_driver_segment.items()):
        best: float | None = None
        attempt_number = 0
        run_number = 0
        in_run = False
        for lap in sorted(laps, key=lambda item: (item.lap_end_time_seconds or float(item.lap_number), item.lap_number)):
            if lap.is_pit_out_lap or not in_run:
                run_number += 1
                in_run = True
            integrity_conflict = (driver, segment, lap.lap_number) in conflict_keys
            valid = bool(lap.lap_time_seconds is not None and not lap.is_deleted and not integrity_conflict and lap.is_accurate is not False and not lap.is_pit_in_lap and not lap.is_pit_out_lap)
            role = "context"
            if valid:
                attempt_number += 1
                role = "best_update" if best is None or lap.lap_time_seconds < best else "valid_no_update"
                if role == "best_update":
                    best = lap.lap_time_seconds
            if lap.lap_time_seconds is not None:
                records.append({"driver": driver, "segment": segment, "lap_number": lap.lap_number, "session_time_seconds": lap.lap_end_time_seconds, "lap_time_seconds": lap.lap_time_seconds, "compound": lap.compound, "track_status": lap.track_status, "valid": valid, "deleted": lap.is_deleted, "deletion_reason": lap.deletion_reason, "integrity_conflict": integrity_conflict, "run_number": run_number, "attempt_number": attempt_number if valid else None, "attempt_role": role, "best_after_seconds": best})
            if lap.is_pit_in_lap:
                in_run = False
    limitations = []
    if unassigned:
        limitations.append(f"{unassigned} timed laps lack authoritative qualifying-segment assignment and were excluded.")
    if any(not lap.is_pit_in_lap and not lap.is_pit_out_lap for lap in dataset.laps) and not any(lap.is_pit_in_lap or lap.is_pit_out_lap for lap in dataset.laps):
        limitations.append("Pit boundaries are unavailable; run grouping is partial.")
    if integrity_conflicts:
        limitations.append("Official segment results conflict with unflagged lap timing; affected laps cannot update progression.")
    status = "source_conflict" if integrity_conflicts else "available" if records and not unassigned else "partial" if records else "unavailable"
    return _record(target, "qualifying_attempt_progression", payload={"timed_lap_records": records, "integrity_conflicts": integrity_conflicts, "summary": _progression_summary(records)}, subjects=sorted({row["driver"] for row in records}), boundaries={"basis": "source-assigned qualifying segment", "chronology": "session_time"}, provenance=provenance, coverage={"available": len(records), "excluded_unassigned": unassigned, "integrity_conflicts": len(integrity_conflicts), "expected": len([lap for lap in dataset.laps if lap.lap_time_seconds is not None])}, quality={"level": "invalid" if integrity_conflicts else _quality(len(records), len(records) + unassigned)["level"]}, status=status, limitations=limitations)


def _margin_result(target: str, segments: dict[str, QualifyingSegmentClassification], provenance: dict[str, Any]) -> AnalyticalResultRecord:
    comparisons: list[dict[str, Any]] = []
    q3 = segments.get("Q3")
    q3_rows = sorted(q3.entries, key=lambda item: item.position) if q3 else []
    comparisons.append(_official_pair("pole", "Q3", q3_rows[:2]))
    for segment_name in ("Q1", "Q2"):
        segment = segments.get(segment_name)
        entries = segment.entries if segment else []
        advancers = sorted((entry for entry in entries if entry.advanced is True), key=lambda item: item.position)
        eliminated = sorted((entry for entry in entries if entry.advanced is False), key=lambda item: item.position)
        pair = [advancers[-1], eliminated[0]] if advancers and eliminated else []
        comparisons.append(_official_pair("advancement_cutoff", segment_name, pair))
    available = sum(row["status"] == "available" for row in comparisons)
    close_cutoffs = [row for row in comparisons if row["kind"] == "advancement_cutoff" and row.get("margin_seconds") is not None and abs(row["margin_seconds"]) <= 0.100]
    summary_rows = [
        row for row in comparisons
        if row["status"] == "available"
        and (
            row["kind"] == "pole"
            or (row.get("margin_seconds") is not None and abs(row["margin_seconds"]) <= 0.100)
        )
    ]
    summary = "; ".join(_margin_text(row) for row in summary_rows)
    return _record(target, "qualifying_margin_comparison", payload={"comparisons": comparisons, "reportable_cutoffs": [row["segment"] for row in close_cutoffs], "summary": summary}, subjects=sorted({driver for row in comparisons for driver in row.get("drivers", [])}), boundaries={"basis": "within-segment official best times"}, provenance=provenance, coverage={"available": available, "expected": 3}, quality=_quality(available, 3), status="available" if available == 3 else "partial" if available else "unavailable", limitations=["Ties and non-time-based advancement outcomes retain the official outcome without a numeric margin."])


def _sector_result(target: str, dataset: SessionDataset, segments: dict[str, QualifyingSegmentClassification], provenance: dict[str, Any]) -> AnalyticalResultRecord:
    q3 = segments.get("Q3")
    ordered = sorted(q3.entries, key=lambda item: item.position) if q3 else []
    if len(ordered) < 2:
        return _record(target, "qualifying_sector_contribution", payload={"comparison_status": "unavailable", "summary": "Pole-to-P2 sector evidence is unavailable."}, subjects=[], boundaries={"segment": "Q3"}, provenance=provenance, coverage={"available": 0, "expected": 2}, quality=_quality(0, 2), status="unavailable", limitations=["Official Q3 pole and P2 are required."])
    selected: list[LapRecord] = []
    for entry in ordered[:2]:
        candidates = [lap for lap in dataset.laps if lap.driver == entry.driver and lap.qualifying_segment == "Q3" and lap.lap_time_seconds is not None and not lap.is_deleted and lap.is_accurate is not False]
        selected.append(min(candidates, key=lambda lap: lap.lap_time_seconds) if candidates else None)  # type: ignore[arg-type]
    if any(lap is None for lap in selected):
        return _record(target, "qualifying_sector_contribution", payload={"comparison_status": "unavailable", "summary": "Pole-to-P2 lap evidence is unavailable."}, subjects=[entry.driver for entry in ordered[:2]], boundaries={"segment": "Q3"}, provenance=provenance, coverage={"available": sum(lap is not None for lap in selected), "expected": 2}, quality=_quality(sum(lap is not None for lap in selected), 2), status="unavailable", limitations=["Both selected valid Q3 laps are required."])
    left, right = selected  # type: ignore[misc]
    sectors_left = [left.sector_1_time_seconds, left.sector_2_time_seconds, left.sector_3_time_seconds]
    sectors_right = [right.sector_1_time_seconds, right.sector_2_time_seconds, right.sector_3_time_seconds]
    complete = all(value is not None for value in [*sectors_left, *sectors_right])
    lap_delta = right.lap_time_seconds - left.lap_time_seconds
    deltas = [b - a for a, b in zip(sectors_left, sectors_right)] if complete else []  # type: ignore[operator]
    reconciled = complete and abs(sum(deltas) - lap_delta) <= QUALIFYING_SECTOR_RECONCILIATION_TOLERANCE_SECONDS
    invalid_status = any("5" in (lap.track_status or "") for lap in (left, right))
    classes = [_compound_class(lap.compound) for lap in (left, right)]
    condition = "unknown" if None in classes else "confounded" if classes[0] != classes[1] else "comparable"
    comparison_status = "unavailable" if not complete or not reconciled or invalid_status else condition
    limitations = []
    if not complete: limitations.append("Complete recorded sectors are required.")
    if complete and not reconciled: limitations.append("Sector deltas do not reconcile to the recorded lap delta within 0.003 seconds.")
    if invalid_status: limitations.append("An invalidating track-status boundary affects a selected lap.")
    if condition == "unknown": limitations.append("Wet/dry compound class is unknown; automatic publication is excluded.")
    if condition == "confounded": limitations.append("Selected laps use different wet/dry compound classes.")
    summary = _sector_interpretation(ordered[0].driver, ordered[1].driver, lap_delta, deltas) if comparison_status == "comparable" else "Pole-to-P2 sector evidence is not automatically publishable."
    return _record(target, "qualifying_sector_contribution", payload={"comparison_status": comparison_status, "segment": "Q3", "laps": [{"driver": ordered[index].driver, "lap_number": lap.lap_number, "lap_time_seconds": lap.lap_time_seconds} for index, lap in enumerate((left, right))], "lap_delta_seconds": lap_delta, "sector_deltas_seconds": deltas, "reconciliation_error_seconds": abs(sum(deltas) - lap_delta) if deltas else None, "summary": summary}, subjects=[entry.driver for entry in ordered[:2]], boundaries={"segment": "Q3", "tolerance_seconds": QUALIFYING_SECTOR_RECONCILIATION_TOLERANCE_SECONDS}, provenance=provenance, coverage={"available": 2 if complete else 0, "expected": 2}, quality=_quality(2 if comparison_status == "comparable" else 0, 2), status="available" if comparison_status == "comparable" else "partial" if comparison_status in {"unknown", "confounded"} else "unavailable", limitations=limitations)


def _temporal_result(target: str, dataset: SessionDataset, integrity_conflicts: list[dict[str, Any]], provenance: dict[str, Any]) -> AnalyticalResultRecord:
    conflict_keys = {(str(item["driver"]), str(item["segment"]), int(item["lap_number"])) for item in integrity_conflicts}
    rows = [lap for lap in dataset.laps if lap.qualifying_segment and lap.lap_time_seconds is not None and not lap.is_deleted and lap.is_accurate is not False and (lap.driver, lap.qualifying_segment, lap.lap_number) not in conflict_keys]
    by_segment: dict[str, list[LapRecord]] = defaultdict(list)
    for lap in rows: by_segment[lap.qualifying_segment].append(lap)  # type: ignore[index]
    patterns = []
    same_driver_changes = []
    competitive_benchmarks = []
    for segment, laps in sorted(by_segment.items()):
        ordered = sorted(laps, key=lambda lap: lap.lap_end_time_seconds or float(lap.lap_number))
        by_driver: dict[str, list[LapRecord]] = defaultdict(list)
        for lap in ordered:
            by_driver[lap.driver].append(lap)
        for driver, driver_laps in sorted(by_driver.items()):
            if len(driver_laps) < 2:
                continue
            first = float(driver_laps[0].lap_time_seconds)
            final = min(float(lap.lap_time_seconds) for lap in driver_laps)
            same_driver_changes.append({"segment": segment, "driver": driver, "first_valid_seconds": first, "final_best_seconds": final, "improvement_seconds": first - final, "attempt_count": len(driver_laps)})
        running_best: float | None = None
        for lap in ordered:
            lap_time = float(lap.lap_time_seconds)
            if running_best is None or lap_time < running_best:
                running_best = lap_time
                competitive_benchmarks.append({"segment": segment, "session_time_seconds": lap.lap_end_time_seconds, "driver": lap.driver, "benchmark_seconds": running_best})
        half = len(ordered) // 2
        if half < 3: continue
        early = median(lap.lap_time_seconds for lap in ordered[:half] if lap.lap_time_seconds is not None)
        late = median(lap.lap_time_seconds for lap in ordered[-half:] if lap.lap_time_seconds is not None)
        patterns.append({"segment": segment, "early_median_seconds": early, "late_median_seconds": late, "observed_change_seconds": late - early, "sample_count": len(ordered), "confounders": ["driver_mix", "tyre_state", "fuel", "traffic", "weather", "interruptions", "execution"]})
    segment_improvements = []
    for segment in ("Q1", "Q2", "Q3"):
        values = [row["improvement_seconds"] for row in same_driver_changes if row["segment"] == segment]
        if values:
            segment_improvements.append(f"{segment} same-driver median improvement was {median(values):.3f} seconds")
    summary = "; ".join(segment_improvements) or "Same-driver temporal evolution is unavailable."
    return _record(target, "qualifying_temporal_evolution", payload={"policy_id": QUALIFYING_TEMPORAL_POLICY_ID, "policy_version": QUALIFYING_TEMPORAL_POLICY_VERSION, "same_driver_changes": same_driver_changes, "competitive_benchmarks": competitive_benchmarks, "field_median_support": patterns, "summary": summary}, subjects=sorted({lap.driver for lap in rows}), boundaries={"primary_comparison": "same-driver first valid to final running best", "supporting_comparison": "field early-versus-late median"}, provenance=provenance, coverage={"same_driver_comparisons": len(same_driver_changes), "segments_with_support": len(patterns), "expected_segments": 3}, quality=_quality(len({row["segment"] for row in same_driver_changes}), 3), status="available" if len({row["segment"] for row in same_driver_changes}) == 3 else "partial" if same_driver_changes else "unavailable", measurement_category="descriptive", limitations=["Observed temporal change is not a track-only correction or causal estimate.", "Field-wide early-versus-late medians are supporting context only."])


def _interruptions_result(target: str, dataset: SessionDataset, provenance: dict[str, Any]) -> AnalyticalResultRecord:
    payload_events = []
    statuses = sorted(dataset.session_status, key=lambda item: item.time_seconds)
    for index, item in enumerate(statuses):
        if item.status.lower() != "aborted":
            continue
        resumed = next((later.time_seconds for later in statuses[index + 1:] if later.status.lower() == "started"), None)
        payload_events.append({"segment": _segment_at_time(dataset, item.time_seconds), "start_time_seconds": item.time_seconds, "end_time_seconds": resumed, "kind": "recorded_suspension"})
    if not payload_events:
        events = sorted({(lap.qualifying_segment, lap.track_status) for lap in dataset.laps if lap.track_status and "5" in lap.track_status})
        payload_events = [{"segment": segment, "track_status": status, "kind": "recorded_suspension", "start_time_seconds": None, "end_time_seconds": None} for segment, status in events]
    by_segment: dict[str, int] = defaultdict(int)
    for event in payload_events:
        by_segment[str(event.get("segment") or "unknown")] += 1
    summaries = []
    for segment, count in sorted(by_segment.items()):
        segment_events = [event for event in payload_events if str(event.get("segment") or "unknown") == segment]
        durations = [float(event["end_time_seconds"]) - float(event["start_time_seconds"]) for event in segment_events if event.get("start_time_seconds") is not None and event.get("end_time_seconds") is not None]
        if count == 1 and durations and durations[0] >= 300:
            summaries.append(f"A {round(durations[0] / 60):.0f}-minute {segment} red flag split the segment before the restart")
        else:
            summaries.append(f"{count} {segment} red flag{'s' if count != 1 else ''} split the segment's running")
    summary = "; ".join(summaries) + "." if summaries else "No recorded red-flag evidence is available."
    return _record(target, "qualifying_interruptions", payload={"events": payload_events, "material": bool(payload_events), "summary": summary}, subjects=[], boundaries={"source": "session-control timing with lap track-status fallback"}, provenance=provenance, coverage={"available": len(payload_events), "expected": 1}, quality=_quality(min(len(payload_events), 1), 1), status="available" if payload_events else "unavailable", measurement_category="measured", limitations=[] if payload_events else ["No recorded red-flag or control-timing evidence was available."])


def _traffic_result(target: str, dataset: SessionDataset, provenance: dict[str, Any]) -> AnalyticalResultRecord:
    samples = [sample for sample in dataset.telemetry if sample.session_time_seconds is not None and sample.x is not None and sample.y is not None]
    buckets: dict[int, list[Any]] = defaultdict(list)
    for sample in samples: buckets[round(sample.session_time_seconds)].append(sample)
    proximities = []
    for second, values in sorted(buckets.items()):
        for index, left in enumerate(values):
            for right in values[index + 1:]:
                if left.driver == right.driver: continue
                distance = hypot(left.x - right.x, left.y - right.y)
                if distance <= 100:
                    proximities.append({"session_time_seconds": second, "drivers": sorted([left.driver, right.driver]), "distance_source_units": distance})
    return _record(target, "qualifying_traffic_context", payload={"proximities": proximities[:100], "attempt_assessments": [], "summary": "No specific valid attempt has a supported traffic-compromise assessment."}, subjects=sorted({driver for item in proximities for driver in item["drivers"]}), boundaries={"alignment_seconds": 1, "proximity_source_units": 100, "reader_visibility": "audit_only"}, provenance=provenance, coverage={"raw_proximity_samples": len(proximities), "attempt_assessments": 0, "telemetry_samples": len(samples)}, quality={"level": "unavailable"}, status="unavailable", measurement_category="descriptive", limitations=["Raw proximity counts are audit evidence only and do not establish that a push lap was compromised."])


def _deleted_result(target: str, dataset: SessionDataset, integrity_conflicts: list[dict[str, Any]], provenance: dict[str, Any]) -> AnalyticalResultRecord:
    deleted = [{"driver": lap.driver, "segment": lap.qualifying_segment, "lap_number": lap.lap_number, "raw_time_seconds": lap.lap_time_seconds, "reason": lap.deletion_reason} for lap in dataset.laps if lap.is_deleted]
    reasons = sum(row["reason"] is not None for row in deleted)
    if integrity_conflicts:
        summary = f"Deletion integrity failed: {len(integrity_conflicts)} unflagged lap records conflict with the official segment results."
    elif deleted:
        summary = f"{len(deleted)} deleted laps were recorded; {reasons} include a source reason."
    else:
        summary = "No deleted laps were recorded, and lap timing reconciles with the official segment results."
    limitations = [] if reasons == len(deleted) else ["One or more deleted-lap reasons are unavailable."]
    if integrity_conflicts:
        limitations.append("The report cannot assert complete deleted-lap coverage until the official-versus-lap conflict is resolved.")
    return _record(target, "qualifying_deleted_laps", payload={"deleted_laps": deleted, "integrity_conflicts": integrity_conflicts, "summary": summary}, subjects=sorted({row["driver"] for row in [*deleted, *integrity_conflicts]}), boundaries={"effect_on_classification": "official result remains authoritative", "integrity_tolerance_seconds": 0.001}, provenance=provenance, coverage={"available": len(deleted), "reasons_available": reasons, "integrity_conflicts": len(integrity_conflicts)}, quality={"level": "invalid" if integrity_conflicts else "high" if deleted and reasons == len(deleted) else "medium" if deleted else "high"}, status="source_conflict" if integrity_conflicts else "available", measurement_category="measured", limitations=limitations)


def _conditions_result(target: str, dataset: SessionDataset, provenance: dict[str, Any]) -> AnalyticalResultRecord:
    wet_laps = [lap for lap in dataset.laps if _compound_class(lap.compound) == "wet"]
    rainfall = [sample for sample in dataset.weather if sample.rainfall is not None]
    compounds = sorted({str(lap.compound).upper() for lap in wet_laps if lap.compound})
    rainfall_states = {sample.rainfall for sample in rainfall}
    material = bool(wet_laps) and (len(compounds) > 1 or len(rainfall_states) > 1)
    segment_sequences = {
        segment: _dominant_compound_sequence([lap for lap in wet_laps if lap.qualifying_segment == segment])
        for segment in ("Q1", "Q2", "Q3")
    }
    ordered_compounds = []
    for segment in ("Q1", "Q2", "Q3"):
        for compound in segment_sequences[segment]:
            if not ordered_compounds or ordered_compounds[-1] != compound:
                ordered_compounds.append(compound)
    if material and ordered_compounds[:4] == ["WET", "INTERMEDIATE", "WET", "INTERMEDIATE"]:
        summary = "Qualifying opened on full wets before the field moved to intermediates; Q3 returned to full wets before later intermediate running."
    elif material and ordered_compounds[:2] == ["WET", "INTERMEDIATE"]:
        summary = "Qualifying opened on full wets before the field moved to intermediates as the recorded session evolved."
    elif material:
        summary = f"Changing conditions produced a recorded {'-to-'.join(ordered_compounds).lower()} tyre sequence."
    elif wet_laps:
        summary = f"Wet-compound running was recorded on {len(wet_laps)} laps."
    else:
        summary = "Qualifying condition evidence is unavailable."
    payload = {"wet_lap_count": len(wet_laps), "wet_compounds": compounds, "compound_sequence": ordered_compounds, "segment_compound_sequences": segment_sequences, "material": material, "rainfall_samples": [{"time_seconds": sample.time_seconds, "rainfall": sample.rainfall} for sample in rainfall], "summary": summary}
    available = int(bool(wet_laps)) + int(bool(rainfall))
    return _record(target, "qualifying_conditions", payload=payload, subjects=sorted({lap.driver for lap in wet_laps}), boundaries={"basis": "recorded compounds and weather"}, provenance=provenance, coverage={"available_components": available, "expected_components": 2}, quality=_quality(available, 2), status="available" if available == 2 else "partial" if available else "unavailable", measurement_category="measured", limitations=[] if available == 2 else ["Condition coverage is incomplete."])


def _dominant_compound_sequence(laps: list[Any]) -> list[str]:
    """Reduce driver-level lap ordering to the field's dominant tyre state."""

    buckets: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for lap in laps:
        if lap.lap_end_time_seconds is None or not lap.compound:
            continue
        buckets[int(lap.lap_end_time_seconds // 180)][str(lap.compound).upper()] += 1
    sequence: list[str] = []
    for counts in (buckets[index] for index in sorted(buckets)):
        compound = max(sorted(counts), key=lambda item: counts[item])
        if not sequence or sequence[-1] != compound:
            sequence.append(compound)
    return sequence


def _deletion_integrity_conflicts(
    dataset: SessionDataset,
    segments: dict[str, QualifyingSegmentClassification],
) -> list[dict[str, Any]]:
    """Find lap timing that the official segment result necessarily excludes.

    The official result stays authoritative.  This check does not invent a
    deletion reason; it blocks publication when the lap feed failed to carry
    the validity/deletion decision needed to explain the official outcome.
    """

    conflicts: list[dict[str, Any]] = []
    for segment_name, segment in sorted(segments.items()):
        official = {entry.driver: entry for entry in segment.entries}
        for lap in dataset.laps:
            if (
                lap.qualifying_segment != segment_name
                or lap.lap_time_seconds is None
                or lap.is_deleted
                or lap.is_accurate is False
                or lap.is_pit_in_lap
                or lap.is_pit_out_lap
            ):
                continue
            entry = official.get(lap.driver)
            reason: str | None = None
            official_time: float | None = None
            if entry is None:
                reason = "timed lap exists in a segment where the official result records no participation"
            else:
                official_time = entry.time_seconds
                if official_time is None:
                    reason = "timed lap exists although the official segment result records no time"
                elif lap.lap_time_seconds < official_time - 0.001:
                    reason = "unflagged lap is faster than the official segment best"
            if reason:
                conflicts.append(
                    {
                        "driver": lap.driver,
                        "segment": segment_name,
                        "lap_number": lap.lap_number,
                        "lap_time_seconds": lap.lap_time_seconds,
                        "official_time_seconds": official_time,
                        "reason": reason,
                    }
                )
    return sorted(conflicts, key=lambda item: (item["segment"], item["driver"], item["lap_number"]))


def _segment_at_time(dataset: SessionDataset, time_seconds: float) -> str | None:
    timed = [
        lap for lap in dataset.laps
        if lap.qualifying_segment and lap.lap_end_time_seconds is not None
    ]
    if not timed:
        return None
    return min(timed, key=lambda lap: abs(float(lap.lap_end_time_seconds) - time_seconds)).qualifying_segment


def _sector_interpretation(
    pole_driver: str,
    p2_driver: str,
    lap_delta: float,
    deltas: list[float],
) -> str:
    dominant_index = max(range(len(deltas)), key=lambda index: abs(deltas[index]))
    dominant = deltas[dominant_index]
    remainder = lap_delta - dominant
    sector = dominant_index + 1
    if dominant > 0 and abs(remainder) <= 0.010:
        return (
            f"{pole_driver} secured pole in S{sector}, gaining {dominant:.3f} seconds there; "
            f"{p2_driver} was essentially level across the other two sectors combined "
            f"({remainder:+.3f} seconds)."
        )
    if (
        len(deltas) == 3
        and deltas[0] < -0.010
        and deltas[1] > 0.010
        and deltas[2] > 0.010
    ):
        return (
            f"{p2_driver} gained {abs(deltas[0]):.3f} seconds in S1; "
            f"{pole_driver} recovered {deltas[1]:.3f} seconds in S2 and another "
            f"{deltas[2]:.3f} seconds in S3 to take pole by {lap_delta:.3f} seconds."
        )
    beneficiary = pole_driver if dominant > 0 else p2_driver
    return (
        f"S{sector} made the largest contribution to the pole margin, worth "
        f"{abs(dominant):.3f} seconds to {beneficiary}; the other sectors combined "
        f"for {remainder:+.3f} seconds of the {lap_delta:.3f}-second margin."
    )


def _official_pair(kind: str, segment: str, pair: list[Any]) -> dict[str, Any]:
    if len(pair) != 2:
        return {"kind": kind, "segment": segment, "status": "unavailable", "drivers": [], "margin_seconds": None}
    left, right = pair
    basis_ok = kind == "pole" or (left.advancement_basis == "time" and right.advancement_basis == "time")
    timed = left.time_seconds is not None and right.time_seconds is not None
    return {"kind": kind, "segment": segment, "status": "available" if basis_ok and timed else "unavailable", "drivers": [left.driver, right.driver], "margin_seconds": right.time_seconds - left.time_seconds if basis_ok and timed else None, "official_outcome": {left.driver: left.advanced, right.driver: right.advanced}, "basis": "official_same_segment_times" if basis_ok else "official_non_time_or_tie_outcome"}


def _margin_text(row: dict[str, Any]) -> str:
    return f"{row['segment']} {row['kind'].replace('_', ' ')}: {row['drivers'][1]} was {row['margin_seconds']:.3f} seconds behind {row['drivers'][0]}"


def _progression_summary(records: list[dict[str, Any]]) -> str:
    stories: list[str] = []
    for segment in ("Q1", "Q2", "Q3"):
        ordered = sorted(
            (
                row for row in records
                if row["segment"] == segment
                and row["valid"]
                and row.get("session_time_seconds") is not None
            ),
            key=lambda row: float(row["session_time_seconds"]),
        )
        benchmark_updates: list[dict[str, Any]] = []
        benchmark: float | None = None
        for row in ordered:
            lap_time = float(row["lap_time_seconds"])
            if benchmark is None or lap_time < benchmark:
                benchmark = lap_time
                benchmark_updates.append(row)
        if not benchmark_updates:
            continue
        final = benchmark_updates[-1]
        previous = next(
            (row for row in reversed(benchmark_updates[:-1]) if row["driver"] != final["driver"]),
            None,
        )
        time_minutes = float(final["session_time_seconds"]) / 60
        if previous:
            stories.append(
                f"{segment}: {previous['driver']} held the benchmark before "
                f"{final['driver']} lowered it to {_format_lap_time(float(final['lap_time_seconds']))} "
                f"at {time_minutes:.1f} minutes"
            )
        else:
            stories.append(
                f"{segment}: {final['driver']} set the final recorded benchmark of "
                f"{_format_lap_time(float(final['lap_time_seconds']))} at {time_minutes:.1f} minutes"
            )
    return "; ".join(stories) + "." if stories else "Running-best progression is unavailable."


def _format_lap_time(seconds: float) -> str:
    minutes, remainder = divmod(seconds, 60)
    return f"{int(minutes)}:{remainder:06.3f}"


def _compound_class(compound: str | None) -> Literal["wet", "dry"] | None:
    if not compound: return None
    value = compound.upper()
    if value in {"WET", "INTERMEDIATE", "I", "W"}: return "wet"
    if value in {"SOFT", "MEDIUM", "HARD", "S", "M", "H", "C1", "C2", "C3", "C4", "C5", "C6"}: return "dry"
    return None


def _provenance(dataset: SessionDataset) -> dict[str, Any]:
    return {"provider": dataset.provenance.provider, "cache_status": dataset.provenance.cache_status, "source_path": str(dataset.provenance.source_path) if dataset.provenance.source_path else None, "fetched_from_network": dataset.provenance.fetched_from_network}


def _quality(available: int, expected: int) -> dict[str, Any]:
    ratio = available / expected if expected else 0
    return {"level": "high" if ratio == 1 else "medium" if ratio >= 0.5 else "low" if ratio > 0 else "unavailable", "coverage_ratio": ratio}


def _record(target: str, result_type: str, *, payload: dict[str, Any], subjects: list[str], boundaries: dict[str, Any], provenance: dict[str, Any], coverage: dict[str, Any], quality: dict[str, Any], status: str, measurement_category: MeasurementCategory = "derived", limitations: list[str]) -> AnalyticalResultRecord:
    semantic = {"result_type": result_type, "schema_version": QUALIFYING_RESULT_SCHEMA_VERSION, "target_session_id": target, "payload": payload, "subjects": subjects, "boundaries": boundaries, "provenance": provenance, "coverage": coverage, "quality": quality, "status": status, "measurement_category": measurement_category, "limitations": limitations}
    fingerprint = canonical_fingerprint(semantic)
    return AnalyticalResultRecord(result_id=stable_id("result", result_type, target, fingerprint), result_type=result_type, result_schema_version=QUALIFYING_RESULT_SCHEMA_VERSION, target_session_id=target, result_fingerprint=fingerprint, analytical_status=status, value_category="descriptive", measurement_category=measurement_category, subjects=subjects, boundaries=boundaries, provenance=provenance, coverage=coverage, quality=quality, payload=payload, analytical_basis={"policy_version": 1}, limitations=limitations)

"""Race-session publication planning built on the SPEC-009 report authority."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from f1_telemetry_charts.analysis.findings import (
    AnalyticalResultRecord,
    EditorialField,
    MeasurementCategory,
    PublicationChartPlacement,
    PublicationClaimPlacement,
    PublicationEditorial,
    PublicationPlan,
    PublicationReadiness,
    ReportContent,
    ReportFinding,
    ReportReviewEntry,
    canonical_fingerprint,
    stable_id,
)
from f1_telemetry_charts.data import SessionDataset


PUBLICATION_SECTION_ORDER = [
    "headline",
    "standfirst",
    "at_a_glance",
    "how_the_race_developed",
    "pace_and_strategy",
    "key_comparison",
    "conclusion",
    "methods_and_evidence",
]
QUALIFYING_PUBLICATION_SECTION_ORDER = [
    "headline",
    "standfirst",
    "at_a_glance",
    "session_context",
    "how_qualifying_unfolded",
    "pole_and_cutoff_battles",
    "sector_comparison",
    "conclusion",
    "methods_and_evidence",
]
QUALIFYING_SELECTION_POLICY_ID = "qualifying-publication-selection"
QUALIFYING_SELECTION_POLICY_VERSION = 4
PRACTICE_PUBLICATION_SECTION_ORDER = [
    "headline",
    "standfirst",
    "session_context",
    "official_classification",
    "relevant_runs",
    "matched_long_run_comparison",
    "observed_run_trend",
    "conclusion",
    "methods_and_evidence",
]
PRACTICE_SELECTION_POLICY_ID = "practice-publication-selection"
PRACTICE_SELECTION_POLICY_VERSION = 1
SESSION_SPINE_TYPES = (
    "race_classification",
    "grid_to_finish_movement",
    "pit_stop_sequence",
    "neutralisation_periods",
    "retirement_status",
    "position_change_interval",
)


def materialize_session_spine(
    target_session_id: str, dataset: SessionDataset
) -> list[AnalyticalResultRecord]:
    """Materialize the six versioned chronology results for one Race."""

    if dataset.metadata.session.strip().lower() not in {"race", "r"}:
        raise ValueError(
            "Publication reports support Race sessions only; the selected session is unsupported."
        )
    provenance = {
        "provider": dataset.provenance.provider,
        "cache_status": dataset.provenance.cache_status,
        "source_path": str(dataset.provenance.source_path) if dataset.provenance.source_path else None,
        "fetched_from_network": dataset.provenance.fetched_from_network,
    }
    laps_by_driver: dict[str, list[Any]] = {}
    for lap in dataset.laps:
        laps_by_driver.setdefault(lap.driver, []).append(lap)
    for laps in laps_by_driver.values():
        laps.sort(key=lambda item: item.lap_number)

    driver_rows = []
    for driver in dataset.drivers:
        laps = laps_by_driver.get(driver.abbreviation, [])
        final_position = driver.classification_position
        classification_source = "official"
        if final_position is None:
            final_position = next((lap.position for lap in reversed(laps) if lap.position), None)
            classification_source = (
                "last_recorded_lap" if final_position is not None else "unavailable"
            )
        grid_position = driver.grid_position
        grid_source = "official"
        grid_context = "pit_lane" if grid_position == 0 else "grid_slot"
        if grid_position is None:
            grid_position = next((lap.position for lap in laps if lap.position), None)
            grid_source = "first_recorded_lap" if grid_position is not None else "unavailable"
            grid_context = "recorded_running_position" if grid_position is not None else "unavailable"
        driver_rows.append(
            {
                "driver": driver.abbreviation,
                "full_name": driver.full_name,
                "team": driver.team_name,
                "classification_position": final_position,
                "classification_source": classification_source,
                "grid_position": grid_position,
                "grid_source": grid_source,
                "grid_context": grid_context,
                "status": driver.result_status,
            }
        )
    classified = sorted(
        (row for row in driver_rows if row["classification_position"] is not None),
        key=lambda row: (row["classification_position"], row["driver"]),
    )
    classification_summary = _classification_summary(classified)
    inferred_classification = any(
        row["classification_source"] == "last_recorded_lap" for row in classified
    )
    classification_limitations = []
    if inferred_classification:
        classification_limitations.append(
            "Official classification was unavailable for one or more drivers; substituted positions are the last recorded running order."
        )
    if len(classified) != len(dataset.drivers):
        classification_limitations.append("Classification coverage is partial.")
    classification = _record(
        target_session_id,
        "race_classification",
        payload={"entries": driver_rows, "summary": classification_summary},
        subjects=[row["driver"] for row in driver_rows],
        boundaries={
            "start": "race_start",
            "end": "last_recorded_running_order" if inferred_classification else "official_classification",
        },
        provenance=provenance,
        coverage={"available": len(classified), "expected": len(dataset.drivers)},
        quality=_quality(len(classified), len(dataset.drivers), inferred=inferred_classification),
        status=_availability(classified, len(classified) == len(dataset.drivers)),
        limitations=classification_limitations,
        measurement_category="derived" if inferred_classification else "measured",
    )

    movements = [
        {
            "driver": row["driver"],
            "full_name": row["full_name"],
            "grid_position": row["grid_position"],
            "finish_position": row["classification_position"],
            "places": row["grid_position"] - row["classification_position"],
            "grid_source": row["grid_source"],
            "finish_source": row["classification_source"],
        }
        for row in driver_rows
        if row["grid_position"] is not None
        and row["grid_position"] > 0
        and row["classification_position"] is not None
    ]
    movements.sort(key=lambda row: (-abs(row["places"]), row["driver"]))
    pit_lane_starters = [
        row["driver"] for row in driver_rows if row["grid_context"] == "pit_lane"
    ]
    movement_limitations = []
    if any(row["grid_source"] != "official" for row in movements):
        movement_limitations.append(
            "Some grid positions use the first recorded race lap because official grid data was unavailable."
        )
    if any(row["finish_source"] != "official" for row in movements):
        movement_limitations.append(
            "Some finish positions use the last recorded running order because official classification was unavailable."
        )
    if pit_lane_starters:
        movement_limitations.append(
            "Pit-lane starters are contextual and excluded from grid-position arithmetic."
        )
    movement = _record(
        target_session_id,
        "grid_to_finish_movement",
        payload={
            "entries": movements,
            "pit_lane_starters": pit_lane_starters,
            "summary": _movement_summary(movements),
        },
        subjects=[row["driver"] for row in movements],
        boundaries={"start": "grid", "end": "classified_finish"},
        provenance=provenance,
        coverage={
            "available": len(movements),
            "expected": len(dataset.drivers) - len(pit_lane_starters),
            "pit_lane_starters": len(pit_lane_starters),
        },
        quality=_quality(
            len(movements),
            len(dataset.drivers) - len(pit_lane_starters),
            inferred=any(
                row["grid_source"] != "official" or row["finish_source"] != "official"
                for row in movements
            ),
        ),
        status=_availability(
            movements,
            len(movements) + len(pit_lane_starters) == len(dataset.drivers),
        ),
        limitations=movement_limitations,
        measurement_category=(
            "derived"
            if any(
                row["grid_source"] != "official" or row["finish_source"] != "official"
                for row in movements
            )
            else "measured"
        ),
    )

    stops = []
    for driver, laps in sorted(laps_by_driver.items()):
        for lap in laps:
            if lap.is_pit_in_lap or lap.is_pit_out_lap or lap.pit_in_time_seconds is not None or lap.pit_out_time_seconds is not None:
                stops.append(
                    {
                        "driver": driver,
                        "full_name": next(
                            (
                                row["full_name"]
                                for row in driver_rows
                                if row["driver"] == driver
                            ),
                            driver,
                        ),
                        "lap": lap.lap_number,
                        "pit_in": lap.is_pit_in_lap or lap.pit_in_time_seconds is not None,
                        "pit_out": lap.is_pit_out_lap or lap.pit_out_time_seconds is not None,
                        "pit_in_time_seconds": lap.pit_in_time_seconds,
                        "pit_out_time_seconds": lap.pit_out_time_seconds,
                    }
                )
    stops.sort(key=lambda row: (row["lap"], row["driver"], not row["pit_in"]))
    pit_sequence = _record(
        target_session_id,
        "pit_stop_sequence",
        payload={"events": stops, "summary": _pit_summary(stops)},
        subjects=sorted(laps_by_driver),
        boundaries={"start_lap": 1, "end_lap": max((lap.lap_number for lap in dataset.laps), default=None)},
        provenance=provenance,
        coverage={"lap_records": len(dataset.laps)},
        quality={"level": "high" if dataset.laps else "unavailable"},
        status="available" if dataset.laps else "unavailable",
        limitations=[],
    )

    neutralisation_laps: dict[int, set[str]] = {}
    track_status_covered = 0
    for lap in dataset.laps:
        if lap.track_status is None:
            continue
        track_status_covered += 1
        labels = _neutralisation_labels(lap.track_status)
        if labels:
            neutralisation_laps.setdefault(lap.lap_number, set()).update(labels)
    periods = _periods(neutralisation_laps)
    neutralisations = _record(
        target_session_id,
        "neutralisation_periods",
        payload={"periods": periods, "summary": _neutralisation_summary(periods)},
        subjects=[],
        boundaries={"start_lap": 1, "end_lap": max((lap.lap_number for lap in dataset.laps), default=None)},
        provenance=provenance,
        coverage={"track_status_laps": track_status_covered, "lap_records": len(dataset.laps)},
        quality={"level": "high" if track_status_covered == len(dataset.laps) and dataset.laps else "medium" if track_status_covered else "unavailable"},
        status="available" if track_status_covered else "unavailable",
        limitations=[] if track_status_covered == len(dataset.laps) else ["Neutralisation coverage is partial or unavailable."],
    )

    statuses = [
        {
            "driver": row["driver"],
            "status": row["status"],
            "finish_category": _finish_category(row["status"]),
        }
        for row in driver_rows
        if row["status"]
    ]
    retirements = _record(
        target_session_id,
        "retirement_status",
        payload={"entries": statuses, "summary": _retirement_summary(statuses)},
        subjects=[row["driver"] for row in statuses],
        boundaries={"end": "classified_finish"},
        provenance=provenance,
        coverage={"available": len(statuses), "expected": len(dataset.drivers)},
        quality=_quality(len(statuses), len(dataset.drivers)),
        status=_availability(statuses, len(statuses) == len(dataset.drivers)),
        limitations=[] if len(statuses) == len(dataset.drivers) else ["Official result-status coverage is partial or unavailable."],
    )

    intervals = []
    for driver, laps in sorted(laps_by_driver.items()):
        positioned = [lap for lap in laps if lap.position is not None]
        if not positioned:
            continue
        intervals.append(
            {
                "driver": driver,
                "start_lap": positioned[0].lap_number,
                "start_position": positioned[0].position,
                "end_lap": positioned[-1].lap_number,
                "end_position": positioned[-1].position,
                "places": positioned[0].position - positioned[-1].position,
            }
        )
    intervals.sort(key=lambda row: (-abs(row["places"]), row["driver"]))
    position_intervals = _record(
        target_session_id,
        "position_change_interval",
        payload={"intervals": intervals, "summary": _position_interval_summary(intervals)},
        subjects=[row["driver"] for row in intervals],
        boundaries={"basis": "first_to_last_recorded_position"},
        provenance=provenance,
        coverage={"available": len(intervals), "expected": len(laps_by_driver)},
        quality=_quality(len(intervals), len(laps_by_driver)),
        status=_availability(intervals, len(intervals) == len(laps_by_driver)),
        limitations=[] if len(intervals) == len(laps_by_driver) else ["Position interval coverage is partial."],
    )
    return sorted(
        [classification, movement, pit_sequence, neutralisations, retirements, position_intervals],
        key=lambda item: item.result_type,
    )


def propose_publication_plan(content: ReportContent) -> PublicationPlan:
    """Apply the named deterministic selection policy to current evidence."""

    if _is_qualifying_content(content):
        return _propose_qualifying_publication_plan(content)
    if _is_practice_content(content):
        return _propose_practice_publication_plan(content)

    all_claims = sorted(
        [*content.findings, *content.conclusions],
        key=lambda item: (-item.priority, item.finding_id),
    )
    result_by_id = {result.result_id: result for result in content.results}
    synthesis_components = {
        finding_id
        for claim in content.conclusions
        if _claim_eligible(claim, result_by_id)
        for finding_id in claim.supporting_finding_ids
    }
    eligible = [
        claim
        for claim in all_claims
        if claim.finding_id not in synthesis_components
        and _claim_eligible(claim, result_by_id)
        and _publication_default_included(claim, result_by_id)
    ]
    chronology_order = {
        "race_classification": 0,
        "grid_to_finish_movement": 1,
        "neutralisation_periods": 2,
    }
    eligible.sort(
        key=lambda item: (
            0 if item.finding_type in chronology_order else 1,
            chronology_order.get(item.finding_type, 99),
            -item.priority,
            item.finding_id,
        )
    )
    placements: list[PublicationClaimPlacement] = []
    for claim in eligible:
        section = _publication_section(claim)
        if section == "key_comparison" and claim.finding_kind != "conclusion":
            section = "pace_and_strategy"
        placements.append(
            PublicationClaimPlacement(
                finding_id=claim.finding_id,
                section=section,
                summary_reference=(
                    _summary_reference(claim, result_by_id)
                    if claim.finding_type in chronology_order
                    else None
                ),
            )
        )

    candidate_charts: list[PublicationChartPlacement] = []
    used_primary_results: set[str] = set()
    for claim in eligible:
        primary_result = claim.result_ids[0] if claim.result_ids else ""
        for evidence in sorted(claim.evidence, key=lambda item: item.chart_instance_id):
            if not evidence.image_path or primary_result in used_primary_results:
                continue
            candidate_charts.append(
                PublicationChartPlacement(
                    chart_instance_id=evidence.chart_instance_id,
                    section=_publication_section(claim),
                    purpose=_chart_purpose(claim),
                    finding_ids=[claim.finding_id],
                    result_ids=claim.result_ids,
                )
            )
            used_primary_results.add(primary_result)
            break
        if len(candidate_charts) >= 4:
            break
    return PublicationPlan(
        target_session_id=content.target_session_id,
        section_order=list(PUBLICATION_SECTION_ORDER),
        claims=placements,
        charts=candidate_charts,
    )


def validate_publication_plan(content: ReportContent, plan: PublicationPlan) -> None:
    qualifying = _is_qualifying_content(content)
    practice = _is_practice_content(content)
    expected_policy = QUALIFYING_SELECTION_POLICY_ID if qualifying else PRACTICE_SELECTION_POLICY_ID if practice else "race-publication-selection"
    expected_version = QUALIFYING_SELECTION_POLICY_VERSION if qualifying else PRACTICE_SELECTION_POLICY_VERSION if practice else 2
    expected_order = QUALIFYING_PUBLICATION_SECTION_ORDER if qualifying else PRACTICE_PUBLICATION_SECTION_ORDER if practice else PUBLICATION_SECTION_ORDER
    if plan.schema_version != 1 or plan.policy_id != expected_policy or plan.policy_version != expected_version:
        raise ValueError("Unsupported publication plan or selection policy version.")
    if plan.target_session_id != content.target_session_id:
        raise ValueError("The publication target session cannot be changed implicitly.")
    if plan.section_order != expected_order:
        raise ValueError("Publication sections must use the approved article order.")
    claims_by_id = {item.finding_id: item for item in [*content.findings, *content.conclusions]}
    claim_ids = set(claims_by_id)
    seen_claims: set[str] = set()
    for placement in plan.claims:
        if placement.finding_id not in claim_ids:
            raise ValueError(f"Publication plan references an unknown claim: {placement.finding_id}")
        if placement.included and placement.finding_id in seen_claims:
            raise ValueError("A claim may have only one canonical detailed placement.")
        if placement.included:
            seen_claims.add(placement.finding_id)
        summary_for_metric_check = re.sub(r"\bQ[123]\b", "", placement.summary_reference or "")
        if (
            placement.summary_reference
            and re.search(r"\d", summary_for_metric_check)
            and placement.summary_reference.strip() != claims_by_id[placement.finding_id].text.strip()
        ):
            raise ValueError("At a Glance references cannot introduce numeric assertions.")
    chart_ids = {
        evidence.chart_instance_id
        for result in content.results
        for evidence in result.chart_evidence
    }
    included_charts = [chart for chart in plan.charts if chart.included]
    for chart in included_charts:
        if chart.chart_instance_id not in chart_ids:
            raise ValueError(f"Publication plan references an unknown chart: {chart.chart_instance_id}")
        if not chart.purpose.strip():
            raise ValueError("Every included chart requires an editorial purpose.")
    automatic = [chart for chart in included_charts if chart.selection_mode == "automatic"]
    maximum = 3 if qualifying or practice else 4
    if len(automatic) > maximum:
        raise ValueError(f"More than {maximum} charts requires explicit inclusion.")
    primary = [chart.result_ids[0] for chart in automatic if chart.result_ids]
    if len(primary) != len(set(primary)):
        raise ValueError("Automatic chart selection cannot repeat the same primary result.")


def evaluate_readiness(
    content: ReportContent,
    reviews: Iterable[ReportReviewEntry],
    *,
    evidence_current: bool,
    review_current: bool,
    publication_current: bool,
    export_current: bool,
    package_integrity: bool,
) -> PublicationReadiness:
    plan = content.publication_plan or propose_publication_plan(content)
    editorial = content.publication_editorial
    review_by_id = {item.item_id: item for item in reviews}
    included_claims = [item for item in plan.claims if item.included]
    included_charts = [item for item in plan.charts if item.included]
    if _is_qualifying_content(content):
        return _evaluate_qualifying_readiness(
            content,
            review_by_id,
            plan,
            evidence_current=evidence_current,
            review_current=review_current,
            publication_current=publication_current,
            export_current=export_current,
            package_integrity=package_integrity,
        )
    if _is_practice_content(content):
        return _evaluate_practice_readiness(
            content,
            reviews,
            evidence_current=evidence_current,
            review_current=review_current,
            publication_current=publication_current,
            export_current=export_current,
            package_integrity=package_integrity,
        )
    race_development_required = any(
        item.section == "how_the_race_developed" for item in included_claims
    ) or any(item.section == "how_the_race_developed" for item in included_charts)
    pace_strategy_required = any(
        item.section == "pace_and_strategy" for item in included_claims
    ) or any(item.section == "pace_and_strategy" for item in included_charts)
    checks = {
        "session_spine_current": evidence_current
        and set(SESSION_SPINE_TYPES) <= {result.result_type for result in content.results},
        "included_evidence_current": evidence_current,
        "included_claims_reviewed": review_current
        and all(
            placement.finding_id in review_by_id
            and review_by_id[placement.finding_id].review_status in {"accepted", "edited"}
            for placement in included_claims
        ),
        "editorial_headline": _headline_is_editorial(editorial.headline.value),
        "publication_standfirst": _minimum_words(editorial.standfirst.value, 15),
        "race_development_lede": not race_development_required or _minimum_words(
            editorial.section_ledes.get("how_the_race_developed", EditorialField()).value,
            8,
        ),
        "pace_strategy_lede": not pace_strategy_required or _minimum_words(
            editorial.section_ledes.get("pace_and_strategy", EditorialField()).value,
            8,
        ),
        "conclusion_present": _minimum_words(editorial.conclusion.value, 8),
        "publication_captions": all(
            _caption_is_informative(content, chart) for chart in included_charts
        ),
        "accessible_alt_text": all(
            _alt_text_is_visual(content, chart) for chart in included_charts
        ),
        "editorial_current": not any(
            field.review_required
            for field in [editorial.headline, editorial.standfirst, editorial.conclusion, *editorial.section_ledes.values()]
        ) and all(not chart.caption.review_required and not chart.alt_text.review_required for chart in included_charts),
        "canonical_placement": len({item.finding_id for item in included_claims}) == len(included_claims),
        "safe_default_selection": all(placement.selection_mode == "explicit" or _placement_is_safe(content, placement) for placement in included_claims),
        "preview_current": publication_current,
        "package_integrity": package_integrity,
    }
    blockers = [name.replace("_", " ").capitalize() for name, passed in checks.items() if not passed]
    ready = not blockers
    if export_current and ready:
        state, next_action = "export_current", "Copy Markdown or download the current package"
    elif ready:
        state, next_action = "publication_draft_ready", "Export publication package"
    elif not evidence_current:
        state, next_action = "evidence_ready", "Refresh report evidence"
    elif not all(
        checks[name]
        for name in (
            "editorial_headline",
            "publication_standfirst",
            "race_development_lede",
            "pace_strategy_lede",
            "conclusion_present",
            "publication_captions",
            "accessible_alt_text",
        )
    ):
        state, next_action = "editorial_work_required", "Complete required editorial fields"
    else:
        state, next_action = "review_required", "Review included claims and dependent editorial copy"
    return PublicationReadiness(
        ready=ready,
        state=state,
        next_action=next_action,
        blockers=blockers,
        checks=checks,
        package_integrity="valid" if package_integrity else "invalid",
    )


def _is_qualifying_content(content: ReportContent) -> bool:
    return any(result.result_type == "qualifying_segment_classification" for result in content.results)


def _is_practice_content(content: ReportContent) -> bool:
    return any(result.result_type == "practice_classification" for result in content.results)


def _propose_practice_publication_plan(content: ReportContent) -> PublicationPlan:
    """Apply SPEC-012's fixed category, quality, effect, and stable-ID order."""

    result_by_id = {result.result_id: result for result in content.results}
    assessment_by_result = {item.result_id: item for item in content.assessments}
    claims = [
        claim for claim in [*content.findings, *content.conclusions]
        if _claim_eligible(claim, result_by_id)
        and all(assessment_by_result.get(result_id) is not None and assessment_by_result[result_id].report_disposition == "reportable" for result_id in claim.result_ids)
    ]
    category = {
        "practice_conditions": 0,
        "practice_interruptions": 0,
        "practice_long_run_comparison": 1,
        "practice_long_run_pace": 2,
        "practice_observed_pace_evolution": 2,
        "practice_classification": 4,
    }
    quality_order = {"high": 0, "medium": 1, "low": 2, "provisional": 3, "unavailable": 4}

    def rank(claim: ReportFinding) -> tuple[Any, ...]:
        result = result_by_id[claim.result_ids[0]]
        effect = claim.metrics.get("effect_size_seconds")
        finite_effect = float(effect) if isinstance(effect, (int, float)) else None
        return (category.get(claim.finding_type, 99), quality_order.get(claim.confidence, 4), 0 if finite_effect is not None else 1, -(abs(finite_effect) if finite_effect is not None else 0.0), result.result_id)

    ordered = sorted(claims, key=rank)
    classification = next((claim for claim in ordered if claim.finding_type == "practice_classification"), None)
    lead = ordered[0] if ordered else None
    selected: list[ReportFinding] = []
    for candidate in [lead, classification]:
        if candidate is not None and candidate.finding_id not in {item.finding_id for item in selected}:
            selected.append(candidate)
    for finding_type in ("practice_long_run_pace", "practice_long_run_comparison", "practice_observed_pace_evolution"):
        candidate = next((claim for claim in ordered if claim.finding_type == finding_type), None)
        if candidate is not None and candidate.finding_id not in {item.finding_id for item in selected}:
            selected.append(candidate)
    section_by_type = {
        "practice_conditions": "session_context",
        "practice_interruptions": "session_context",
        "practice_classification": "official_classification",
        "practice_long_run_pace": "relevant_runs",
        "practice_long_run_comparison": "matched_long_run_comparison",
        "practice_observed_pace_evolution": "observed_run_trend",
    }
    placements = [PublicationClaimPlacement(finding_id=claim.finding_id, section=section_by_type[claim.finding_type], summary_reference=claim.text if claim is lead else None) for claim in selected]
    charts: list[PublicationChartPlacement] = []
    used_results: set[str] = set()
    for claim in selected:
        primary = claim.result_ids[0] if claim.result_ids else ""
        if primary in used_results:
            continue
        for evidence in sorted(claim.evidence, key=lambda item: item.chart_instance_id):
            if evidence.image_path:
                charts.append(PublicationChartPlacement(chart_instance_id=evidence.chart_instance_id, section=section_by_type[claim.finding_type], purpose=_chart_purpose(claim), finding_ids=[claim.finding_id], result_ids=claim.result_ids))
                used_results.add(primary)
                break
        if len(charts) == 3:
            break
    return PublicationPlan(policy_id=PRACTICE_SELECTION_POLICY_ID, policy_version=PRACTICE_SELECTION_POLICY_VERSION, target_session_id=content.target_session_id, section_order=list(PRACTICE_PUBLICATION_SECTION_ORDER), claims=placements, charts=charts)


def _evaluate_practice_readiness(
    content: ReportContent,
    reviews: Iterable[ReportReviewEntry],
    *,
    evidence_current: bool,
    review_current: bool,
    publication_current: bool,
    export_current: bool,
    package_integrity: bool,
) -> PublicationReadiness:
    plan = content.publication_plan or _propose_practice_publication_plan(content)
    editorial = content.publication_editorial
    review_by_id = {item.item_id: item for item in reviews}
    included_claims = [item for item in plan.claims if item.included]
    included_charts = [item for item in plan.charts if item.included]
    classification = next((result for result in content.results if result.result_type == "practice_classification"), None)
    required_ledes = {item.section for item in included_claims if item.section in {"session_context", "official_classification", "relevant_runs", "matched_long_run_comparison", "observed_run_trend"}}
    unsafe = re.compile(r"\b(fuel[- ]corrected|engine mode|setup advantage|tyre preparation|traffic loss|programme intent|race simulation|qualifying simulation|tyre degradation|race pace ranking|will qualify|will win|weekend prediction)\b", re.I)
    editorial_values = [editorial.headline.value, editorial.standfirst.value, editorial.conclusion.value, *[field.value for field in editorial.section_ledes.values()], *[chart.caption.value for chart in included_charts], *[chart.alt_text.value for chart in included_charts], *[(review_by_id[item.finding_id].edited_text or "") for item in included_claims if item.finding_id in review_by_id and review_by_id[item.finding_id].review_status == "edited"]]
    checks = {
        "official_practice_classification_current": bool(evidence_current and classification and classification.analytical_status == "available"),
        "included_evidence_current": evidence_current,
        "included_claims_reviewed": review_current and all(item.finding_id in review_by_id and review_by_id[item.finding_id].review_status in {"accepted", "edited"} for item in included_claims),
        "editorial_headline": _headline_is_editorial(editorial.headline.value),
        "publication_standfirst": _minimum_words(editorial.standfirst.value, 15),
        "practice_section_ledes": all(_minimum_words(editorial.section_ledes.get(section, EditorialField()).value, 8) for section in required_ledes),
        "conclusion_present": _minimum_words(editorial.conclusion.value, 8),
        "publication_captions": all(_caption_is_informative(content, chart) for chart in included_charts),
        "accessible_alt_text": all(_alt_text_is_visual(content, chart) for chart in included_charts),
        "editorial_current": not any(field.review_required for field in [editorial.headline, editorial.standfirst, editorial.conclusion, *editorial.section_ledes.values()]) and all(not chart.caption.review_required and not chart.alt_text.review_required for chart in included_charts),
        "canonical_placement": len({item.finding_id for item in included_claims}) == len(included_claims),
        "supported_language": not any(unsafe.search(value) for value in editorial_values),
        "preview_current": publication_current,
        "package_integrity": package_integrity,
    }
    blockers = [name.replace("_", " ").capitalize() for name, passed in checks.items() if not passed]
    ready = not blockers
    if export_current and ready: state, next_action = "export_current", "Copy Markdown or download the current package"
    elif ready: state, next_action = "publication_draft_ready", "Export publication package"
    elif not checks["official_practice_classification_current"]: state, next_action = "evidence_ready", "Refresh official Practice classification"
    elif not all(checks[name] for name in ("editorial_headline", "publication_standfirst", "practice_section_ledes", "conclusion_present", "publication_captions", "accessible_alt_text")): state, next_action = "editorial_work_required", "Complete required Practice editorial fields"
    else: state, next_action = "review_required", "Review included Practice claims and dependent editorial copy"
    return PublicationReadiness(ready=ready, state=state, next_action=next_action, blockers=blockers, checks=checks, package_integrity="valid" if package_integrity else "invalid")


def _propose_qualifying_publication_plan(content: ReportContent) -> PublicationPlan:
    result_by_id = {result.result_id: result for result in content.results}
    eligible = [
        claim
        for claim in [*content.findings, *content.conclusions]
        if _claim_eligible(claim, result_by_id)
    ]
    order = {
        "qualifying_segment_classification": 0,
        "qualifying-session-context": 1,
        "qualifying_conditions": 2,
        "qualifying_interruptions": 3,
        "qualifying_sector_contribution": 4,
        "qualifying_margin_comparison": 5,
        "qualifying_attempt_progression": 6,
    }
    eligible.sort(key=lambda claim: (order.get(claim.finding_type, 99), -claim.priority, claim.finding_id))
    section_by_type = {
        "qualifying_segment_classification": "how_qualifying_unfolded",
        "qualifying_attempt_progression": "how_qualifying_unfolded",
        "qualifying_margin_comparison": "pole_and_cutoff_battles",
        "qualifying_sector_contribution": "sector_comparison",
        "qualifying-session-context": "session_context",
        "qualifying_conditions": "session_context",
        "qualifying_interruptions": "session_context",
    }
    combined_context = any(claim.finding_type == "qualifying-session-context" for claim in eligible)
    placements = [
        PublicationClaimPlacement(
            finding_id=claim.finding_id,
            section=section_by_type[claim.finding_type],
            summary_reference=(
                claim.text.strip()
                if claim.finding_type
                in {
                    "qualifying_segment_classification",
                    "qualifying_margin_comparison",
                    "qualifying_sector_contribution",
                    "qualifying-session-context",
                }
                else None
            ),
        )
        for claim in eligible
        if claim.finding_type in section_by_type
        and not (combined_context and claim.finding_type in {"qualifying_conditions", "qualifying_interruptions"})
    ]
    charts: list[PublicationChartPlacement] = []
    seen_results: set[str] = set()
    for claim in eligible:
        # Margin values read faster as labelled findings than as separately
        # scaled bars.  Keep the recipe available as inspectable evidence, but
        # do not select it for the reader article.
        if claim.finding_type == "qualifying_margin_comparison":
            continue
        primary = claim.result_ids[0] if claim.result_ids else ""
        if primary in seen_results:
            continue
        evidence = next((item for item in sorted(claim.evidence, key=lambda item: item.chart_instance_id) if item.image_path), None)
        if evidence is None:
            continue
        charts.append(
            PublicationChartPlacement(
                chart_instance_id=evidence.chart_instance_id,
                section=section_by_type.get(claim.finding_type, "session_context"),
                purpose=_chart_purpose(claim),
                finding_ids=[claim.finding_id],
                result_ids=claim.result_ids,
            )
        )
        seen_results.add(primary)
        if len(charts) == 3:
            break
    return PublicationPlan(
        policy_id=QUALIFYING_SELECTION_POLICY_ID,
        policy_version=QUALIFYING_SELECTION_POLICY_VERSION,
        target_session_id=content.target_session_id,
        section_order=list(QUALIFYING_PUBLICATION_SECTION_ORDER),
        claims=placements,
        charts=charts,
    )


def _evaluate_qualifying_readiness(
    content: ReportContent,
    review_by_id: dict[str, ReportReviewEntry],
    plan: PublicationPlan,
    *,
    evidence_current: bool,
    review_current: bool,
    publication_current: bool,
    export_current: bool,
    package_integrity: bool,
) -> PublicationReadiness:
    editorial = content.publication_editorial
    included_claims = [item for item in plan.claims if item.included]
    included_charts = [item for item in plan.charts if item.included]
    classification = next((result for result in content.results if result.result_type == "qualifying_segment_classification"), None)
    deleted_laps = next((result for result in content.results if result.result_type == "qualifying_deleted_laps"), None)
    official_complete = bool(
        classification
        and classification.analytical_status == "available"
        and len(classification.payload.get("official_session_classification", [])) >= 2
    )
    required_ledes = {
        item.section
        for item in [*included_claims, *included_charts]
        if item.section in {"how_qualifying_unfolded", "pole_and_cutoff_battles", "sector_comparison", "session_context"}
    }
    if any(
        item.section == "session_context"
        and (review := review_by_id.get(item.finding_id)) is not None
        and review.review_status == "edited"
        and bool((review.edited_text or "").strip())
        for item in included_claims
    ):
        required_ledes.discard("session_context")
    unsafe = re.compile(r"\b(setup|driver error|tyre preparation|traffic loss|track gain|strategy intent|would have advanced|would have taken pole)\b", re.I)
    editorial_values = [editorial.headline.value, editorial.standfirst.value, editorial.conclusion.value, *[field.value for field in editorial.section_ledes.values()], *[chart.caption.value for chart in included_charts]]
    checks = {
        "official_qualifying_outcome_current": evidence_current and official_complete,
        "deleted_lap_integrity": bool(deleted_laps and deleted_laps.analytical_status != "source_conflict"),
        "included_evidence_current": evidence_current,
        "included_claims_reviewed": review_current and all(item.finding_id in review_by_id and review_by_id[item.finding_id].review_status in {"accepted", "edited"} for item in included_claims),
        "editorial_headline": _headline_is_editorial(editorial.headline.value),
        "publication_standfirst": _minimum_words(editorial.standfirst.value, 15),
        "qualifying_section_ledes": all(_minimum_words(editorial.section_ledes.get(section, EditorialField()).value, 8) for section in required_ledes),
        "conclusion_present": _minimum_words(editorial.conclusion.value, 8),
        "publication_captions": all(_caption_is_informative(content, chart) for chart in included_charts),
        "accessible_alt_text": all(_alt_text_is_visual(content, chart) for chart in included_charts),
        "editorial_current": not any(field.review_required for field in [editorial.headline, editorial.standfirst, editorial.conclusion, *editorial.section_ledes.values()]) and all(not chart.caption.review_required and not chart.alt_text.review_required for chart in included_charts),
        "canonical_placement": len({item.finding_id for item in included_claims}) == len(included_claims),
        "supported_language": not any(unsafe.search(value) for value in editorial_values),
        "preview_current": publication_current,
        "package_integrity": package_integrity,
    }
    blockers = [name.replace("_", " ").capitalize() for name, passed in checks.items() if not passed]
    ready = not blockers
    if export_current and ready: state, next_action = "export_current", "Copy Markdown or download the current package"
    elif ready: state, next_action = "publication_draft_ready", "Export publication package"
    elif not evidence_current or not official_complete: state, next_action = "evidence_ready", "Refresh official qualifying evidence"
    elif not all(checks[name] for name in ("editorial_headline", "publication_standfirst", "qualifying_section_ledes", "conclusion_present", "publication_captions", "accessible_alt_text")): state, next_action = "editorial_work_required", "Complete required qualifying editorial fields"
    else: state, next_action = "review_required", "Review included qualifying claims and dependent editorial copy"
    return PublicationReadiness(ready=ready, state=state, next_action=next_action, blockers=blockers, checks=checks, package_integrity="valid" if package_integrity else "invalid")


def preserve_editorial_on_refresh(
    prior: PublicationEditorial,
    current_result_fingerprints: set[str],
) -> PublicationEditorial:
    def update(field: EditorialField) -> EditorialField:
        changed = bool(field.dependency_fingerprints) and not set(field.dependency_fingerprints) <= current_result_fingerprints
        return field.model_copy(update={"review_required": field.review_required or changed})

    return PublicationEditorial(
        headline=update(prior.headline),
        standfirst=update(prior.standfirst),
        section_ledes={key: update(value) for key, value in prior.section_ledes.items()},
        conclusion=update(prior.conclusion),
    )


def editorial_fingerprint(editorial: PublicationEditorial, plan: PublicationPlan) -> str:
    return canonical_fingerprint(
        {"editorial": editorial.model_dump(mode="json"), "plan": plan.model_dump(mode="json")}
    )


def _record(
    session_id: str,
    result_type: str,
    *,
    payload: dict[str, Any],
    subjects: list[str],
    boundaries: dict[str, Any],
    provenance: dict[str, Any],
    coverage: dict[str, Any],
    quality: dict[str, Any],
    status: str,
    limitations: list[str],
    measurement_category: MeasurementCategory = "measured",
) -> AnalyticalResultRecord:
    semantic = {
        "result_type": result_type,
        "result_schema_version": 1,
        "target_session_id": session_id,
        "measurement_category": measurement_category,
        "subjects": subjects,
        "boundaries": boundaries,
        "payload": payload,
        "provenance": provenance,
        "coverage": coverage,
        "quality": quality,
        "status": status,
        "limitations": limitations,
    }
    fingerprint = canonical_fingerprint(semantic)
    return AnalyticalResultRecord(
        result_id=stable_id("result", fingerprint),
        result_type=result_type,
        result_schema_version=1,
        target_session_id=session_id,
        result_fingerprint=fingerprint,
        analytical_status=status,
        measurement_category=measurement_category,
        subjects=subjects,
        boundaries=boundaries,
        provenance=provenance,
        coverage=coverage,
        quality=quality,
        payload=payload,
        analytical_basis={
            "measurement": (
                "official session data"
                if measurement_category == "measured"
                else "derived from recorded session running order"
            )
        },
        limitations=limitations,
    )


def _quality(available: int, expected: int, inferred: bool = False) -> dict[str, Any]:
    ratio = available / expected if expected else 0.0
    level = "high" if ratio == 1 and not inferred else "medium" if ratio > 0 else "unavailable"
    return {"level": level, "coverage_ratio": ratio, "inferred_boundary": inferred}


def _availability(values: list[Any], complete: bool) -> str:
    return "available" if values and complete else "partial" if values else "unavailable"


def _classification_summary(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    leaders = rows[:3]
    official = all(row.get("classification_source") == "official" for row in leaders)
    if len(leaders) >= 3 and official:
        names = [row.get("full_name") or row["driver"] for row in leaders]
        return f"{names[0]} won ahead of {names[1]} and {names[2]}."
    label = "The official classification placed" if official else "The last recorded running order placed"
    return label + " " + ", ".join(
        f"{row.get('full_name') or row['driver']} P{row['classification_position']}"
        for row in leaders
    ) + "."


def _movement_summary(rows: list[dict[str, Any]]) -> str:
    changed = [row for row in rows if row["places"]]
    if not changed:
        return "The available grid and finish records show no position movement."
    row = changed[0]
    direction = "gained" if row["places"] > 0 else "lost"
    driver = row.get("full_name") or row["driver"]
    if row["places"] > 0:
        return f"{driver} made the largest field recovery, gaining {abs(row['places'])} places from grid to finish."
    return f"{driver} had the largest grid-to-finish change, losing {abs(row['places'])} places."


def _pit_summary(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No pit-stop event was present in the available lap records."
    first = rows[0]
    return f"{first.get('full_name') or first['driver']} made the first recorded pit visit on lap {first['lap']}."


def _neutralisation_labels(value: str) -> set[str]:
    codes = {character for character in str(value) if character.isdigit()}
    labels: set[str] = set()
    if "4" in codes:
        labels.add("Safety Car")
    if codes & {"6", "7"}:
        labels.add("Virtual Safety Car")
    if "5" in codes:
        labels.add("Red flag")
    return labels


def _periods(values: dict[int, set[str]]) -> list[dict[str, Any]]:
    periods: list[dict[str, Any]] = []
    for lap in sorted(values):
        labels = sorted(values[lap])
        if periods and periods[-1]["end_lap"] + 1 == lap and periods[-1]["types"] == labels:
            periods[-1]["end_lap"] = lap
        else:
            periods.append({"start_lap": lap, "end_lap": lap, "types": labels})
    return periods


def _neutralisation_summary(periods: list[dict[str, Any]]) -> str:
    if not periods:
        return "No neutralisation period was identified in the available track-status records."
    first = periods[0]
    types = " and ".join(first["types"])
    return f"A {types} period ran from laps {first['start_lap']} to {first['end_lap']}."


def _retirement_summary(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    non_finishers = [row for row in rows if row.get("finish_category") != "finisher"]
    if not non_finishers:
        return "The available official statuses record all covered drivers as finishers."
    return f"The available official statuses identify {len(non_finishers)} non-finishing or non-classified entries."


def _finish_category(status: object) -> str:
    normalized = " ".join(str(status or "").strip().lower().split())
    if normalized in {"finished", "lapped", "lapping"}:
        return "finisher"
    if re.fullmatch(r"\+\s*\d+\s+laps?", normalized):
        return "finisher"
    return "non_finisher"


def _position_interval_summary(rows: list[dict[str, Any]]) -> str:
    changed = [row for row in rows if row["places"]]
    if not changed:
        return "The first and last recorded positions were unchanged for the covered drivers."
    row = changed[0]
    direction = "improved" if row["places"] > 0 else "fell"
    return f"{row['driver']} {direction} by {abs(row['places'])} positions between laps {row['start_lap']} and {row['end_lap']}."


def _claim_eligible(claim: ReportFinding, results: dict[str, AnalyticalResultRecord]) -> bool:
    if claim.confidence in {"low", "provisional", "unavailable"}:
        return False
    owned = [results[result_id] for result_id in claim.result_ids if result_id in results]
    if any(result.analytical_status in {"unavailable", "unsupported", "source_conflict"} for result in owned):
        return False
    if any(result.measurement_category == "estimated" for result in owned):
        return False
    text = " ".join([*claim.limitations, *(warning for result in owned for warning in result.warnings)]).lower()
    return "confound" not in text


def _publication_section(claim: ReportFinding):
    if claim.finding_type in SESSION_SPINE_TYPES:
        return "how_the_race_developed"
    if claim.finding_kind == "conclusion":
        return "key_comparison"
    return "pace_and_strategy"


def _summary_reference(
    claim: ReportFinding,
    results: dict[str, AnalyticalResultRecord],
) -> str | None:
    result = next((results[item_id] for item_id in claim.result_ids if item_id in results), None)
    if result is None:
        return None
    if claim.finding_type == "race_classification":
        entries = sorted(
            (item for item in result.payload.get("entries", []) if item.get("classification_position") is not None),
            key=lambda item: item["classification_position"],
        )[:3]
        if len(entries) == 3 and all(
            item.get("classification_source") == "official" for item in entries
        ):
            names = [_short_driver_name(item) for item in entries]
            return f"{names[0]} won ahead of {names[1]} and {names[2]}."
        if len(entries) == 3:
            names = [_short_driver_name(item) for item in entries]
            return f"The last recorded running order was {names[0]}, {names[1]} and {names[2]}."
    if claim.finding_type == "grid_to_finish_movement":
        entries = [
            item for item in result.payload.get("entries", []) if item.get("places")
        ]
        if entries:
            return f"{_short_driver_name(entries[0])} made the largest field recovery."
    if claim.finding_type == "neutralisation_periods":
        periods = result.payload.get("periods", [])
        if periods:
            return f"The race included a {' and '.join(periods[0].get('types') or ['neutralisation'])} period."
    return None


def _chart_purpose(claim: ReportFinding) -> str:
    if claim.finding_type in {"representative_pace_advantage", "observed_pace_evolution"}:
        return "Show the selected pace comparison."
    if "pit" in claim.finding_type:
        return "Show the measured pit-cycle comparison."
    return "Show the selected analytical comparison."


def _placement_is_safe(content: ReportContent, placement: PublicationClaimPlacement) -> bool:
    claim = next((item for item in [*content.findings, *content.conclusions] if item.finding_id == placement.finding_id), None)
    if claim is None:
        return False
    return _claim_eligible(claim, {result.result_id: result for result in content.results})


def _publication_default_included(
    claim: ReportFinding,
    results: dict[str, AnalyticalResultRecord],
) -> bool:
    if claim.finding_type in {"pit_stop_sequence", "retirement_status", "position_change_interval"}:
        return False
    if claim.finding_type == "grid_to_finish_movement":
        result = next((results[item_id] for item_id in claim.result_ids if item_id in results), None)
        return bool(
            result
            and any(item.get("places") for item in result.payload.get("entries", []))
        )
    if claim.finding_type == "neutralisation_periods":
        result = next((results[item_id] for item_id in claim.result_ids if item_id in results), None)
        return bool(result and result.payload.get("periods"))
    return True


def _short_driver_name(row: dict[str, Any]) -> str:
    full_name = str(row.get("full_name") or "").strip()
    return full_name.split()[-1] if full_name else str(row.get("driver") or "Driver")


def _minimum_words(value: str, minimum: int) -> bool:
    return len(re.findall(r"\b[\w'-]+\b", value.strip())) >= minimum


def _headline_is_editorial(value: str) -> bool:
    headline = " ".join(value.split())
    if not _minimum_words(headline, 4):
        return False
    return not bool(
        re.search(r"(?:race report|analysis|session report|report)$", headline, re.I)
    )


def _chart_title(content: ReportContent, chart_id: str) -> str:
    for result in content.results:
        for evidence in result.chart_evidence:
            if evidence.chart_instance_id == chart_id:
                return str(evidence.title or "")
    return ""


def _caption_is_informative(
    content: ReportContent,
    chart: PublicationChartPlacement,
) -> bool:
    caption = " ".join(chart.caption.value.split())
    title = " ".join(_chart_title(content, chart.chart_instance_id).split())
    return _minimum_words(caption, 8) and caption.casefold().rstrip(".") != title.casefold().rstrip(".")


def _alt_text_is_visual(
    content: ReportContent,
    chart: PublicationChartPlacement,
) -> bool:
    alt = " ".join(chart.alt_text.value.split())
    if not _minimum_words(alt, 12):
        return False
    normalized = alt.casefold().rstrip(".")
    if normalized == " ".join(chart.caption.value.split()).casefold().rstrip("."):
        return False
    claim_texts = {
        " ".join(item.text.split()).casefold().rstrip(".")
        for item in [*content.findings, *content.conclusions]
    }
    if normalized in claim_texts:
        return False
    return any(
        token in normalized
        for token in ("chart", "line", "lines", "axis", "axes", "points", "markers", "bars", "plot", "panel")
    )

from __future__ import annotations

import unittest

from f1_telemetry_charts.analysis.findings import build_report_content
from f1_telemetry_charts.analysis.practice import (
    is_standard_practice,
    materialize_practice_results,
)
from f1_telemetry_charts.analysis.publication import (
    PRACTICE_PUBLICATION_SECTION_ORDER,
    evaluate_readiness,
    propose_publication_plan,
    validate_publication_plan,
)
from f1_telemetry_charts.analysis.report import render_publication_markdown
from f1_telemetry_charts.analysis.manifest import ArtifactManifest
from f1_telemetry_charts.data import (
    DriverMetadata,
    LapRecord,
    PracticeClassificationEntry,
    SessionDataset,
    SessionMetadata,
    SessionStatusRecord,
    SourceProvenance,
    WeatherSample,
)
from f1_telemetry_charts.recipes.practice import (
    PracticeLongRunPaceRecipe,
    PracticeObservedPaceEvolutionRecipe,
    PracticeRunOverviewRecipe,
)
from f1_telemetry_charts.config.models import ChartRecipeConfig


def practice_dataset(
    *,
    representative_count: int = 8,
    missing_tyre_age: bool = False,
    mixed_compounds: bool = False,
    interrupted: bool = False,
) -> SessionDataset:
    laps: list[LapRecord] = []
    for driver_index, driver in enumerate(("AAA", "BBB")):
        offset = float(driver_index * 5)
        compound = "SOFT" if mixed_compounds and driver == "BBB" else "MEDIUM"
        laps.append(LapRecord(driver=driver, lap_number=1, lap_start_time_seconds=offset, lap_end_time_seconds=10 + offset, is_pit_out_lap=True, compound=compound, tyre_age=0))
        for progress in range(1, representative_count + 1):
            laps.append(
                LapRecord(
                    driver=driver,
                    lap_number=progress + 1,
                    lap_start_time_seconds=20 + progress * 100 + offset,
                    lap_end_time_seconds=100 + progress * 100 + offset,
                    lap_time_seconds=90.0 + driver_index * 0.3 + progress * (0.10 if driver == "AAA" else 0.05),
                    compound=compound,
                    tyre_age=None if missing_tyre_age else float(progress),
                    is_accurate=True,
                    track_status="1",
                )
            )
        laps.append(LapRecord(driver=driver, lap_number=representative_count + 2, lap_start_time_seconds=representative_count * 100 + 110 + offset, lap_end_time_seconds=representative_count * 100 + 150 + offset, is_pit_in_lap=True, compound=compound, tyre_age=float(representative_count + 1)))
    statuses = [SessionStatusRecord(time_seconds=0, status="Started")]
    if interrupted:
        statuses.extend([SessionStatusRecord(time_seconds=350, status="Aborted"), SessionStatusRecord(time_seconds=500, status="Started")])
    statuses.append(SessionStatusRecord(time_seconds=1000, status="Finished"))
    return SessionDataset(
        metadata=SessionMetadata(season=2026, event="Practice Fixture", session="FP2"),
        drivers=[DriverMetadata(abbreviation="AAA", classification_position=1), DriverMetadata(abbreviation="BBB", classification_position=2)],
        laps=laps,
        weather=[WeatherSample(time_seconds=0, rainfall=False), WeatherSample(time_seconds=1000, rainfall=False)],
        session_status=statuses,
        practice_classification=[
            PracticeClassificationEntry(driver="AAA", position=1, fastest_time_seconds=90.1, gap_seconds=0, lap_count=representative_count),
            PracticeClassificationEntry(driver="BBB", position=2, fastest_time_seconds=90.35, gap_seconds=0.25, lap_count=representative_count),
        ],
        provenance=SourceProvenance(provider="fixture", cache_status="fixture"),
    )


class PracticeReportTests(unittest.TestCase):
    def test_scope_accepts_only_standard_practice(self) -> None:
        for name in ("FP1", "fp2", "FP3", "Practice 1", "Practice 3"):
            self.assertTrue(is_standard_practice(name))
        race = practice_dataset().model_copy(update={"metadata": SessionMetadata(season=2026, event="Fixture", session="Race")})
        with self.assertRaisesRegex(ValueError, "FP1, FP2, or FP3"):
            materialize_practice_results("race", race)

    def test_official_classification_is_not_reconstructed_from_laps(self) -> None:
        dataset = practice_dataset().model_copy(update={"practice_classification": []})
        classification = next(item for item in materialize_practice_results("practice", dataset) if item.result_type == "practice_classification")
        self.assertEqual(classification.analytical_status, "unavailable")
        self.assertEqual(classification.payload["entries"], [])

    def test_long_run_summaries_and_evolution_are_auditable(self) -> None:
        results = materialize_practice_results("practice", practice_dataset())
        pace = [item for item in results if item.result_type == "practice_long_run_pace"]
        evolution = [item for item in results if item.result_type == "practice_observed_pace_evolution"]
        self.assertEqual(len(pace), 2)
        self.assertTrue(all(item.payload["run_status"] == "long_run" for item in pace))
        self.assertTrue(all(item.payload["representative_count"] == 8 for item in pace))
        self.assertTrue(all(len(item.payload["representative_laps"]) == 8 for item in pace))
        self.assertEqual({item.payload["basis"] for item in evolution}, {"stint_progress", "tyre_age"})
        self.assertTrue(all("not causal tyre degradation" in " ".join(item.limitations) for item in evolution))

    def test_legitimately_slow_lap_remains_without_explicit_exclusion(self) -> None:
        dataset = practice_dataset()
        laps = [
            lap.model_copy(update={"lap_time_seconds": 180.0})
            if lap.driver == "AAA" and lap.lap_number == 5
            else lap
            for lap in dataset.laps
        ]
        results = materialize_practice_results("practice", dataset.model_copy(update={"laps": laps}))
        pace = next(
            item
            for item in results
            if item.result_type == "practice_long_run_pace" and item.payload["driver"] == "AAA"
        )
        self.assertEqual(pace.payload["representative_count"], 8)
        self.assertEqual(pace.payload["excluded_laps"], [])
        self.assertIn(180.0, [row["lap_time_seconds"] for row in pace.payload["representative_laps"]])

    def test_non_green_track_status_uses_explicit_spec008_reason(self) -> None:
        dataset = practice_dataset()
        laps = [
            lap.model_copy(update={"track_status": "2"})
            if lap.driver == "AAA" and lap.lap_number == 5
            else lap
            for lap in dataset.laps
        ]
        pace = next(
            item
            for item in materialize_practice_results(
                "practice", dataset.model_copy(update={"laps": laps})
            )
            if item.result_type == "practice_long_run_pace" and item.payload["driver"] == "AAA"
        )
        self.assertEqual(pace.payload["representative_count"], 7)
        self.assertEqual(
            pace.payload["excluded_laps"][0]["exclusion_reasons"],
            ["non_green_track_status"],
        )

    def test_five_to_seven_laps_are_sustained_evidence_only(self) -> None:
        content = build_report_content("practice", [], materialize_practice_results("practice", practice_dataset(representative_count=7)))
        pace = [item for item in content.results if item.result_type == "practice_long_run_pace"]
        self.assertTrue(all(item.payload["run_status"] == "sustained_run" for item in pace))
        assessments = [item for item in content.assessments if item.result_type == "practice_long_run_pace"]
        self.assertTrue(all(item.report_disposition == "context_only" for item in assessments))
        self.assertFalse(any(item.result_type == "practice_long_run_comparison" for item in content.results))

    def test_comparison_requires_paired_reliable_tyre_ages(self) -> None:
        comparable = [item for item in materialize_practice_results("practice", practice_dataset()) if item.result_type == "practice_long_run_comparison"]
        self.assertEqual(len(comparable), 1)
        self.assertEqual(comparable[0].payload["comparison_status"], "comparable")
        self.assertEqual(comparable[0].payload["paired_sample_count"], 8)
        self.assertIsNotNone(comparable[0].payload["paired_median_difference_seconds"])
        unknown = next(item for item in materialize_practice_results("practice", practice_dataset(missing_tyre_age=True)) if item.result_type == "practice_long_run_comparison")
        self.assertEqual(unknown.payload["comparison_status"], "unknown")
        self.assertIsNone(unknown.payload["paired_median_difference_seconds"])
        confounded = next(item for item in materialize_practice_results("practice", practice_dataset(mixed_compounds=True)) if item.result_type == "practice_long_run_comparison")
        self.assertEqual(confounded.payload["comparison_status"], "confounded")
        self.assertIsNone(confounded.payload["paired_median_difference_seconds"])

    def test_context_results_have_independent_fingerprints(self) -> None:
        dry = {item.result_type: item for item in materialize_practice_results("same", practice_dataset())}
        stopped = {item.result_type: item for item in materialize_practice_results("same", practice_dataset(interrupted=True))}
        self.assertNotEqual(dry["practice_interruptions"].result_fingerprint, stopped["practice_interruptions"].result_fingerprint)
        self.assertEqual(dry["practice_conditions"].result_fingerprint, stopped["practice_conditions"].result_fingerprint)
        self.assertEqual(dry["practice_traffic_context"].result_fingerprint, stopped["practice_traffic_context"].result_fingerprint)

    def test_existing_authority_uses_deterministic_practice_policy(self) -> None:
        content = build_report_content("practice", [], materialize_practice_results("practice", practice_dataset(interrupted=True)))
        plan = propose_publication_plan(content)
        self.assertEqual(plan.policy_id, "practice-publication-selection")
        self.assertEqual(plan.section_order, PRACTICE_PUBLICATION_SECTION_ORDER)
        validate_publication_plan(content, plan)
        claims = {item.finding_id: item for item in content.findings}
        lead = next(item for item in plan.claims if item.summary_reference)
        self.assertEqual(claims[lead.finding_id].finding_type, "practice_interruptions")
        self.assertTrue(any(claims[item.finding_id].finding_type == "practice_classification" for item in plan.claims))
        self.assertLessEqual(len([item for item in plan.charts if item.selection_mode == "automatic"]), 3)

    def test_practice_reader_structure_does_not_insert_race_or_qualifying_sections(self) -> None:
        content = build_report_content("practice", [], materialize_practice_results("practice", practice_dataset()))
        plan = propose_publication_plan(content)
        editorial = content.publication_editorial.model_copy(deep=True)
        editorial.headline.value = "Observed Practice report"
        content = content.model_copy(update={"publication_plan": plan, "publication_editorial": editorial}, deep=True)
        reviews = [
            {"item_id": claim.finding_id, "reviewed_evidence_fingerprint": claim.evidence_fingerprint, "review_status": "accepted"}
            for claim in content.findings
            if claim.finding_id in {item.finding_id for item in plan.claims}
        ]
        from f1_telemetry_charts.analysis.findings import ReportReviewEntry
        markdown = render_publication_markdown(ArtifactManifest(run_id="practice", status="succeeded", framework_version="test", configuration_hash="fixture", session={"season": 2026, "event": "Fixture", "session": "FP2"}, requested_recipes=[], recipes=[], artifacts=[]), content, [ReportReviewEntry.model_validate(item) for item in reviews])
        self.assertNotIn("## At a Glance", markdown)
        self.assertNotIn("How the Race Developed", markdown)
        self.assertNotIn("How Qualifying Unfolded", markdown)

    def test_readiness_rejects_predictive_or_causal_editorial_language(self) -> None:
        content = build_report_content("practice", [], materialize_practice_results("practice", practice_dataset()))
        plan = propose_publication_plan(content)
        editorial = content.publication_editorial.model_copy(deep=True)
        editorial.headline.value = "Practice evidence says AAA will win"
        editorial.standfirst.value = "This sufficiently long standfirst describes the observed session timing while preserving the source limitations for readers."
        editorial.conclusion.value = "The observed samples remain bounded and programme variables remain unknown."
        for section in {item.section for item in plan.claims}:
            editorial.section_ledes[section] = editorial.headline.model_copy(update={"value": "This section reports recorded evidence with explicit limits and no inferred cause."})
        content = content.model_copy(update={"publication_plan": plan, "publication_editorial": editorial}, deep=True)
        readiness = evaluate_readiness(content, [], evidence_current=True, review_current=True, publication_current=True, export_current=False, package_integrity=True)
        self.assertFalse(readiness.checks["supported_language"])

    def test_three_practice_chart_families_use_typed_results(self) -> None:
        dataset = practice_dataset()
        specs = [
            PracticeRunOverviewRecipe().build_spec(dataset, ChartRecipeConfig(recipe_id="practice_run_overview")),
            PracticeLongRunPaceRecipe().build_spec(dataset, ChartRecipeConfig(recipe_id="practice_long_run_pace_summary")),
            PracticeObservedPaceEvolutionRecipe().build_spec(dataset, ChartRecipeConfig(recipe_id="practice_observed_pace_evolution")),
        ]
        self.assertEqual([spec.metadata["result_kind"] for spec in specs], ["practice_run_chronology", "practice_long_run_pace", "practice_observed_pace_evolution"])
        self.assertTrue(specs[1].x_tick_labels)
        self.assertTrue(all(":" in label for label in specs[1].x_tick_labels.values()))
        self.assertTrue(specs[1].horizontal_bars)
        self.assertTrue(specs[1].y_axis_inverted)
        self.assertNotIn("residual", specs[2].subtitle.lower())


if __name__ == "__main__":
    unittest.main()

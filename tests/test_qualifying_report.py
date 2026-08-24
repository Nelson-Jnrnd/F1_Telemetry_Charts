from __future__ import annotations

import unittest

from f1_telemetry_charts.analysis.findings import ResultSource, build_report_content
from f1_telemetry_charts.analysis.publication import (
    QUALIFYING_PUBLICATION_SECTION_ORDER,
    evaluate_readiness,
    propose_publication_plan,
    validate_publication_plan,
)
from f1_telemetry_charts.analysis.qualifying import (
    QUALIFYING_RESULT_TYPES,
    materialize_qualifying_results,
)
from f1_telemetry_charts.config.models import ChartRecipeConfig
from f1_telemetry_charts.data import (
    DriverMetadata,
    LapRecord,
    QualifyingClassificationEntry,
    QualifyingSegmentClassification,
    SessionDataset,
    SessionMetadata,
    SessionStatusRecord,
    SourceProvenance,
    WeatherSample,
)
from f1_telemetry_charts.recipes.qualifying import (
    QualifyingMarginRecipe,
    QualifyingProgressionRecipe,
    QualifyingSectorContributionRecipe,
)


def qualifying_dataset(*, wet: bool = False, interrupted: bool = False) -> SessionDataset:
    drivers = [
        DriverMetadata(abbreviation=code, classification_position=index, result_status="Finished")
        for index, code in enumerate(("AAA", "BBB", "CCC", "DDD"), start=1)
    ]
    segments = [
        QualifyingSegmentClassification(segment="Q1", entries=[
            QualifyingClassificationEntry(driver="AAA", position=1, time_seconds=90.0, advanced=True),
            QualifyingClassificationEntry(driver="BBB", position=2, time_seconds=90.1, advanced=True),
            QualifyingClassificationEntry(driver="CCC", position=3, time_seconds=90.19, advanced=True),
            QualifyingClassificationEntry(driver="DDD", position=4, time_seconds=90.28, advanced=False),
        ]),
        QualifyingSegmentClassification(segment="Q2", entries=[
            QualifyingClassificationEntry(driver="AAA", position=1, time_seconds=89.5, advanced=True),
            QualifyingClassificationEntry(driver="BBB", position=2, time_seconds=89.55, advanced=True),
            QualifyingClassificationEntry(driver="CCC", position=3, time_seconds=89.64, advanced=False),
        ]),
        QualifyingSegmentClassification(segment="Q3", entries=[
            QualifyingClassificationEntry(driver="AAA", position=1, time_seconds=89.0, advanced=None, advancement_basis="not_applicable"),
            QualifyingClassificationEntry(driver="BBB", position=2, time_seconds=89.08, advanced=None, advancement_basis="not_applicable"),
        ]),
    ]
    compound = "INTERMEDIATE" if wet else "SOFT"
    laps = [
        LapRecord(driver="AAA", lap_number=1, lap_time_seconds=90.2, compound=compound, qualifying_segment="Q1", is_pit_out_lap=True),
        LapRecord(driver="AAA", lap_number=2, lap_time_seconds=90.0, compound=compound, qualifying_segment="Q1", sector_1_time_seconds=30.0, sector_2_time_seconds=30.0, sector_3_time_seconds=30.0),
        LapRecord(driver="BBB", lap_number=2, lap_time_seconds=90.1, compound=compound, qualifying_segment="Q1"),
        LapRecord(driver="CCC", lap_number=2, lap_time_seconds=90.19, compound=compound, qualifying_segment="Q1"),
        LapRecord(driver="DDD", lap_number=2, lap_time_seconds=90.28, compound=compound, qualifying_segment="Q1", is_deleted=True, deletion_reason="track limits"),
        LapRecord(driver="AAA", lap_number=4, lap_time_seconds=89.5, compound=compound, qualifying_segment="Q2"),
        LapRecord(driver="BBB", lap_number=4, lap_time_seconds=89.55, compound=compound, qualifying_segment="Q2"),
        LapRecord(driver="CCC", lap_number=4, lap_time_seconds=89.64, compound=compound, qualifying_segment="Q2"),
        LapRecord(driver="AAA", lap_number=6, lap_time_seconds=89.0, compound=compound, qualifying_segment="Q3", sector_1_time_seconds=29.5, sector_2_time_seconds=29.7, sector_3_time_seconds=29.8, track_status="5" if interrupted else "1"),
        LapRecord(driver="BBB", lap_number=6, lap_time_seconds=89.08, compound=compound, qualifying_segment="Q3", sector_1_time_seconds=29.52, sector_2_time_seconds=29.73, sector_3_time_seconds=29.83),
    ]
    for index, lap in enumerate(laps, start=1):
        lap.lap_end_time_seconds = float(index * 120)
    return SessionDataset(
        metadata=SessionMetadata(season=2024, event="Test Grand Prix", session="Qualifying"),
        drivers=drivers,
        laps=laps,
        weather=[WeatherSample(time_seconds=0, rainfall=wet)],
        session_status=(
            [
                SessionStatusRecord(time_seconds=1080, status="Aborted"),
                SessionStatusRecord(time_seconds=1200, status="Started"),
            ]
            if interrupted
            else []
        ),
        qualifying_segments=segments,
        provenance=SourceProvenance(provider="fixture", cache_status="fixture"),
    )


class QualifyingReportTests(unittest.TestCase):
    def test_scope_and_nine_independent_results(self) -> None:
        dataset = qualifying_dataset()
        first = materialize_qualifying_results("session-q", dataset)
        second = materialize_qualifying_results("session-q", dataset)
        self.assertEqual(tuple(item.result_type for item in first), tuple(sorted(QUALIFYING_RESULT_TYPES)))
        self.assertEqual([item.result_fingerprint for item in first], [item.result_fingerprint for item in second])
        race = dataset.model_copy(update={"metadata": dataset.metadata.model_copy(update={"session": "Race"})})
        with self.assertRaisesRegex(ValueError, "standard Qualifying only"):
            materialize_qualifying_results("race", race)

    def test_official_classification_progression_and_margins(self) -> None:
        results = {item.result_type: item for item in materialize_qualifying_results("session-q", qualifying_dataset())}
        classification = results["qualifying_segment_classification"]
        self.assertEqual(classification.analytical_status, "available")
        self.assertEqual(len(classification.payload["official_session_classification"]), 4)
        self.assertIn("1:29.000", classification.payload["summary"])
        progression = results["qualifying_attempt_progression"]
        self.assertIn("1:29.000", progression.payload["summary"])
        self.assertNotIn("89.000 seconds", progression.payload["summary"])
        deleted = next(row for row in progression.payload["timed_lap_records"] if row["deleted"])
        self.assertFalse(deleted["valid"])
        self.assertEqual(deleted["attempt_role"], "context")
        margins = results["qualifying_margin_comparison"].payload["comparisons"]
        self.assertAlmostEqual(margins[0]["margin_seconds"], 0.08)
        self.assertAlmostEqual(margins[1]["margin_seconds"], 0.09)
        self.assertAlmostEqual(margins[2]["margin_seconds"], 0.09)

    def test_source_conflict_remains_explicit(self) -> None:
        dataset = qualifying_dataset()
        dataset.qualifying_segments[0].status = "source_conflict"
        dataset.qualifying_segments[0].source_conflicts = ["Official Q1 order conflicts with the timing feed."]
        result = next(item for item in materialize_qualifying_results("conflict", dataset) if item.result_type == "qualifying_segment_classification")
        self.assertEqual(result.analytical_status, "source_conflict")
        self.assertIn("conflicts", result.limitations[-1])
        content = build_report_content("conflict", [], materialize_qualifying_results("conflict", dataset))
        plan = propose_publication_plan(content)
        classification_claim_ids = {claim.finding_id for claim in content.findings if claim.finding_type == "qualifying_segment_classification"}
        self.assertFalse(any(item.finding_id in classification_claim_ids for item in plan.claims))

    def test_sector_reconciliation_and_condition_comparability(self) -> None:
        dry = {item.result_type: item for item in materialize_qualifying_results("dry", qualifying_dataset())}
        self.assertEqual(dry["qualifying_sector_contribution"].payload["comparison_status"], "comparable")
        self.assertAlmostEqual(sum(dry["qualifying_sector_contribution"].payload["sector_deltas_seconds"]), 0.08)
        mixed = qualifying_dataset(wet=True)
        mixed.laps[-1].compound = "SOFT"
        mixed_result = {item.result_type: item for item in materialize_qualifying_results("mixed", mixed)}
        self.assertEqual(mixed_result["qualifying_sector_contribution"].payload["comparison_status"], "confounded")

    def test_sector_summary_states_the_motorsport_conclusion(self) -> None:
        dataset = qualifying_dataset()
        dataset.qualifying_segments[-1].entries[1].time_seconds = 89.228
        dataset.laps[-1].lap_time_seconds = 89.228
        dataset.laps[-1].sector_1_time_seconds = 29.727
        dataset.laps[-1].sector_2_time_seconds = 29.700
        dataset.laps[-1].sector_3_time_seconds = 29.801
        result = {item.result_type: item for item in materialize_qualifying_results("sector-story", dataset)}["qualifying_sector_contribution"]
        self.assertIn("AAA secured pole in S1", result.payload["summary"])
        self.assertIn("essentially level across the other two sectors", result.payload["summary"])

    def test_sector_summary_preserves_directional_reversal(self) -> None:
        dataset = qualifying_dataset()
        dataset.qualifying_segments[-1].entries[0].time_seconds = 119.765
        dataset.qualifying_segments[-1].entries[1].time_seconds = 120.086
        dataset.laps[-2].lap_time_seconds = 119.765
        dataset.laps[-2].sector_1_time_seconds = 40.000
        dataset.laps[-2].sector_2_time_seconds = 40.000
        dataset.laps[-2].sector_3_time_seconds = 39.765
        dataset.laps[-1].lap_time_seconds = 120.086
        dataset.laps[-1].sector_1_time_seconds = 39.743
        dataset.laps[-1].sector_2_time_seconds = 40.269
        dataset.laps[-1].sector_3_time_seconds = 40.074
        result = {item.result_type: item for item in materialize_qualifying_results("sector-reversal", dataset)}["qualifying_sector_contribution"]
        self.assertEqual(
            result.payload["summary"],
            "BBB gained 0.257 seconds in S1; AAA recovered 0.269 seconds in S2 and another 0.309 seconds in S3 to take pole by 0.321 seconds.",
        )

    def test_deletion_integrity_conflict_blocks_readiness(self) -> None:
        dataset = qualifying_dataset()
        dataset.qualifying_segments[1].entries[0].time_seconds = 89.6
        results = materialize_qualifying_results("deletion-conflict", dataset)
        deleted = next(item for item in results if item.result_type == "qualifying_deleted_laps")
        self.assertEqual(deleted.analytical_status, "source_conflict")
        self.assertIn("faster than the official segment best", deleted.payload["integrity_conflicts"][0]["reason"])
        content = build_report_content("deletion-conflict", [], results)
        plan = propose_publication_plan(content)
        content = content.model_copy(update={"publication_plan": plan}, deep=True)
        readiness = evaluate_readiness(content, [], evidence_current=True, review_current=False, publication_current=False, export_current=False, package_integrity=True)
        self.assertFalse(readiness.checks["deleted_lap_integrity"])

    def test_material_conditions_and_interruption_define_session_context(self) -> None:
        dataset = qualifying_dataset(wet=True, interrupted=True)
        dataset.laps[0].compound = "WET"
        content = build_report_content("wet-interrupted", [], materialize_qualifying_results("wet-interrupted", dataset))
        conclusions = [item for item in content.conclusions if item.finding_type == "qualifying-session-context"]
        self.assertEqual(len(conclusions), 1)
        self.assertIn("Conditions and stoppages defined", conclusions[0].text)

    def test_context_results_are_independent_and_optional(self) -> None:
        dry = {item.result_type: item for item in materialize_qualifying_results("same", qualifying_dataset())}
        interrupted = {item.result_type: item for item in materialize_qualifying_results("same", qualifying_dataset(interrupted=True))}
        self.assertNotEqual(dry["qualifying_interruptions"].result_fingerprint, interrupted["qualifying_interruptions"].result_fingerprint)
        self.assertEqual(dry["qualifying_deleted_laps"].result_fingerprint, interrupted["qualifying_deleted_laps"].result_fingerprint)

    def test_existing_authority_selects_qualifying_structure(self) -> None:
        content = build_report_content("session-q", [], materialize_qualifying_results("session-q", qualifying_dataset()))
        self.assertEqual(len(content.results), 9)
        self.assertEqual(len(content.assessments), 9)
        self.assertTrue(any(section.section_id == "qualifying_unfolded" and section.items for section in content.plan.sections))
        plan = propose_publication_plan(content)
        self.assertEqual(plan.policy_id, "qualifying-publication-selection")
        self.assertEqual(plan.section_order, QUALIFYING_PUBLICATION_SECTION_ORDER)
        self.assertLessEqual(len(plan.charts), 3)
        claims = {claim.finding_id: claim for claim in [*content.findings, *content.conclusions]}
        summaries = [item.summary_reference for item in plan.claims if item.summary_reference]
        self.assertTrue(summaries)
        self.assertTrue(all(summary == claims[item.finding_id].text for item in plan.claims if (summary := item.summary_reference)))
        self.assertNotIn("Official Q1/Q2/Q3 outcome", summaries)
        self.assertNotIn("Pole and advancement margins", summaries)
        validate_publication_plan(content, plan)
        content = content.model_copy(update={"publication_plan": plan}, deep=True)
        readiness = evaluate_readiness(content, [], evidence_current=True, review_current=False, publication_current=False, export_current=False, package_integrity=True)
        self.assertFalse(readiness.ready)
        self.assertTrue(readiness.checks["official_qualifying_outcome_current"])

    def test_chart_reference_attaches_without_duplicate_result(self) -> None:
        source = ResultSource(target_session_id="session-q", chart_instance_id="chart-margin", image_path="charts/margin.png", metadata_path="charts/margin.json", metadata={"result_kind": "qualifying_margin_comparison", "result_reference_only": True})
        content = build_report_content("session-q", [source], materialize_qualifying_results("session-q", qualifying_dataset()))
        margins = [result for result in content.results if result.result_type == "qualifying_margin_comparison"]
        self.assertEqual(len(margins), 1)
        self.assertEqual(margins[0].chart_evidence[0].chart_instance_id, "chart-margin")
        plan = propose_publication_plan(content)
        self.assertNotIn("chart-margin", [chart.chart_instance_id for chart in plan.charts])

    def test_three_purposeful_chart_contracts(self) -> None:
        dataset = qualifying_dataset(interrupted=True)
        specs = [
            QualifyingProgressionRecipe().build_spec(dataset, ChartRecipeConfig(recipe_id="qualifying_progression")),
            QualifyingMarginRecipe().build_spec(dataset, ChartRecipeConfig(recipe_id="qualifying_margin_comparison")),
            QualifyingSectorContributionRecipe().build_spec(dataset, ChartRecipeConfig(recipe_id="qualifying_sector_contribution")),
        ]
        self.assertEqual([spec.metadata["result_kind"] for spec in specs], ["qualifying_attempt_progression", "qualifying_margin_comparison", "qualifying_sector_contribution"])
        self.assertEqual(len(specs[1].panels), 3)
        self.assertEqual(len(specs[2].horizontal_bars), 3)
        self.assertEqual(specs[0].panels[0].x_label, "Session time (min)")
        self.assertEqual(specs[0].panels[0].y_label, "Running best lap")
        self.assertTrue(specs[0].panels[0].y_tick_labels)
        self.assertTrue(all(":" in label for label in specs[0].panels[0].y_tick_labels.values()))
        self.assertTrue(all(label.count(".") == 1 for label in specs[0].panels[0].y_tick_labels.values()))
        self.assertTrue(specs[0].panels[2].shaded_regions)
        q1_labels = {series.label for series in specs[0].panels[0].series}
        self.assertIn("Deleted lap", q1_labels)
        self.assertNotIn("Deleted / integrity conflict", q1_labels)

    def test_long_red_flag_is_compressed_without_losing_session_time_labels(self) -> None:
        dataset = qualifying_dataset(interrupted=True)
        dataset.session_status = [
            SessionStatusRecord(time_seconds=1080, status="Aborted"),
            SessionStatusRecord(time_seconds=3780, status="Started"),
        ]
        spec = QualifyingProgressionRecipe().build_spec(dataset, ChartRecipeConfig(recipe_id="qualifying_progression"))
        q3 = spec.panels[2]
        red_flag = next(region for region in q3.shaded_regions if region.label == "Red flag")
        self.assertAlmostEqual(red_flag.x_end - red_flag.x_start, 2.0)
        self.assertEqual(red_flag.annotation, "Red flag · 45 min")
        self.assertIn("compressed", q3.x_label)
        self.assertIn("15", q3.x_tick_labels.values())

    def test_integrity_conflict_has_its_own_progression_marker(self) -> None:
        dataset = qualifying_dataset()
        dataset.qualifying_segments[1].entries[0].time_seconds = 89.6
        spec = QualifyingProgressionRecipe().build_spec(dataset, ChartRecipeConfig(recipe_id="qualifying_progression"))
        labels = {series.label for panel in spec.panels for series in panel.series}
        self.assertIn("Integrity conflict", labels)
        self.assertIn("Deleted lap", labels)


if __name__ == "__main__":
    unittest.main()

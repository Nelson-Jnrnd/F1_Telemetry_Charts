from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from pydantic import ValidationError

from f1_telemetry_charts.analysis.findings import (
    AnalyticalResultRecord,
    ReportReviewEntry,
    ResultReportAssessment,
    ResultSource,
    SYNTHESIS_RULE_IDS,
    assess_results,
    build_report_content,
    canonical_fingerprint,
    materialize_results,
    provider_descriptors,
    required_review_item_ids,
    reviews_are_current,
)
from f1_telemetry_charts.analysis.manifest import ArtifactManifest
from f1_telemetry_charts.analysis.report import (
    render_structured_markdown,
    write_structured_report_package,
)


def source(
    *,
    chart: str = "chart-1",
    result_kind: str = "stint_pace",
    results: dict | None = None,
) -> ResultSource:
    return ResultSource(
        target_session_id="2023-bahrain-race",
        chart_instance_id=chart,
        artifact_id=f"artifact-{chart}",
        image_path=f"charts/{chart}.png",
        metadata_path=f"charts/{chart}.json",
        metadata={
            "strategy_analysis_schema_version": 1,
            "result_kind": result_kind,
            "analytical_results": results
            or {
                "value_category": "descriptive",
                "metric": "representative_lap_time",
                "x_axis_basis": "lap_number",
                "comparison_summary": {
                    "stints": [
                        {"label": "VER S1", "sample_count": 8},
                        {"label": "PER S1", "sample_count": 7},
                    ],
                    "median_delta_seconds": -0.32,
                    "median_delta_sign_convention": "VER S1 minus PER S1",
                },
            },
            "analytical_basis": {"representative_sample_count": 15},
            "strategy_warnings": [],
            "strategy_limitations": ["Observed laps only."],
        },
    )


class ReportFindingTests(unittest.TestCase):
    def test_result_fingerprint_deduplicates_chart_presentations(self) -> None:
        results = materialize_results([source(chart="a"), source(chart="b")])

        self.assertEqual(len(results), 1)
        self.assertEqual(
            [evidence.chart_instance_id for evidence in results[0].chart_evidence],
            ["a", "b"],
        )

    def test_driver_battle_and_delta_chart_share_the_nested_gap_result(self) -> None:
        gap_result = {
            "schema_version": 1,
            "result_kind": "measured_gap_change",
            "value_category": "measured",
            "status": "available",
            "focal_driver": "VER",
            "benchmark": "PER",
            "start_lap": 1,
            "end_lap": 20,
            "paired_sample_count": 20,
            "overall_change_seconds": -1.2,
        }
        delta = source(chart="delta", result_kind="measured_gap_change", results=gap_result)
        battle = source(
            chart="battle",
            result_kind="driver_battle",
            results={"gap_result": gap_result, "panel_contract": ["direct_driver_gap"]},
        )

        content = build_report_content("2023-bahrain-race", [delta, battle])

        self.assertEqual(len(content.results), 1)
        self.assertEqual(len(content.findings), 1)
        self.assertEqual(
            [item.chart_instance_id for item in content.findings[0].evidence],
            ["battle", "delta"],
        )

    def test_presentation_only_metadata_does_not_change_fingerprint(self) -> None:
        left = source(chart="a")
        right = source(chart="b")
        left.metadata["effective_configuration"] = {"theme": "light"}
        right.metadata["effective_configuration"] = {"theme": "dark"}

        results = materialize_results([left, right])

        self.assertEqual(len(results), 1)

    def test_semantic_change_changes_result_and_finding_identity(self) -> None:
        left = build_report_content("2023-bahrain-race", [source()])
        changed = source()
        changed.metadata["analytical_results"]["comparison_summary"][
            "median_delta_seconds"
        ] = -0.42
        right = build_report_content("2023-bahrain-race", [changed])

        self.assertNotEqual(left.results[0].result_fingerprint, right.results[0].result_fingerprint)
        self.assertNotEqual(left.findings[0].finding_id, right.findings[0].finding_id)

    def test_stint_pace_provider_produces_qualified_finding(self) -> None:
        content = build_report_content("2023-bahrain-race", [source()])

        self.assertEqual(content.assessments[0].report_disposition, "reportable")
        self.assertEqual(len(content.findings), 1)
        self.assertIn("0.320 s/lap lower", content.findings[0].text)
        self.assertEqual(content.findings[0].metrics["sample_counts"], [8, 7])
        self.assertEqual(len(content.findings[0].evidence), 1)

    def test_below_threshold_is_not_reportable_and_generates_no_prose(self) -> None:
        value = source()
        value.metadata["analytical_results"]["comparison_summary"][
            "median_delta_seconds"
        ] = 0.099

        content = build_report_content("2023-bahrain-race", [value])

        self.assertEqual(content.assessments[0].report_disposition, "not_reportable")
        self.assertEqual(content.findings, [])

    def test_timeline_is_context_only(self) -> None:
        content = build_report_content(
            "2023-bahrain-race",
            [source(result_kind="strategy_timeline", results={"status": "available"})],
        )

        self.assertEqual(content.assessments[0].report_disposition, "context_only")
        self.assertEqual(content.findings, [])

    def test_unknown_result_type_is_explicitly_unsupported(self) -> None:
        content = build_report_content(
            "2023-bahrain-race",
            [source(result_kind="plugin_result", results={"status": "available"})],
        )

        self.assertEqual(content.assessments[0].report_disposition, "unsupported")

    def test_disposition_contract_rejects_findings_on_non_reportable(self) -> None:
        record = materialize_results([source()])[0]
        with self.assertRaises(ValidationError):
            ResultReportAssessment(
                assessment_id="assessment",
                result_id=record.result_id,
                result_fingerprint=record.result_fingerprint,
                result_type=record.result_type,
                provider_id="provider",
                provider_version=1,
                report_disposition="context_only",
                reasons=["context"],
                finding_ids=["finding"],
            )

    def test_provider_criteria_and_rule_catalog_are_fixed_and_inspectable(self) -> None:
        descriptors = {value.provider_id: value for value in provider_descriptors()}

        self.assertEqual(
            descriptors["representative-pace-provider"].criteria[
                "absolute_median_delta_seconds"
            ],
            0.10,
        )
        self.assertEqual(
            SYNTHESIS_RULE_IDS,
            (
                "pace-vs-direct-gap-v1",
                "pace-evolution-comparison-v1",
                "pit-cycle-vs-race-state-v1",
                "pace-vs-position-change-v1",
                "qualifying-session-context-v2",
            ),
        )

    def test_only_included_publishable_claims_require_review(self) -> None:
        content = build_report_content("2023-bahrain-race", [source()])
        claim_id = content.findings[0].finding_id
        self.assertEqual(required_review_item_ids(content), {claim_id})
        self.assertFalse(reviews_are_current(content, []))

        review = ReportReviewEntry(
            item_id=claim_id,
            reviewed_evidence_fingerprint=content.findings[0].evidence_fingerprint,
            review_status="accepted",
        )
        self.assertTrue(reviews_are_current(content, [review]))

        for section in content.plan.sections:
            for item in section.items:
                if item.reference_id == claim_id:
                    item.included = False
        self.assertEqual(required_review_item_ids(content), set())
        self.assertTrue(reviews_are_current(content, []))

    def test_one_session_boundary_is_enforced(self) -> None:
        other = source(chart="other")
        other.target_session_id = "2023-monaco-race"

        with self.assertRaisesRegex(ValueError, "one target session"):
            build_report_content("2023-bahrain-race", [source(), other])

    def test_fingerprint_is_deterministic(self) -> None:
        self.assertEqual(
            canonical_fingerprint({"b": 2, "a": 1}),
            canonical_fingerprint({"a": 1, "b": 2}),
        )

    def test_pace_and_gap_use_named_non_causal_synthesis(self) -> None:
        pace = source()
        pace.metadata["analytical_results"]["comparison_summary"]["stints"] = [
            {"label": "VER S1", "driver": "VER", "representative_lap_count": 8, "start_lap": 3, "end_lap": 20},
            {"label": "PER S1", "driver": "PER", "representative_lap_count": 7, "start_lap": 3, "end_lap": 20},
        ]
        pace.metadata["analytical_results"]["stints"] = pace.metadata[
            "analytical_results"
        ]["comparison_summary"]["stints"]
        gap = source(
            chart="gap",
            result_kind="measured_gap_change",
            results={
                "schema_version": 1,
                "result_kind": "measured_gap_change",
                "value_category": "measured",
                "status": "available",
                "focal_driver": "VER",
                "benchmark": "PER",
                "start_lap": 3,
                "end_lap": 20,
                "paired_sample_count": 18,
                "overall_change_seconds": -1.2,
                "sign_convention": "positive means focal driver lost time; negative means gained",
            },
        )

        content = build_report_content("2023-bahrain-race", [pace, gap])

        self.assertEqual(
            [item.synthesis_rule_id for item in content.conclusions],
            ["pace-vs-direct-gap-v1"],
        )
        self.assertNotIn("caused", content.conclusions[0].text.lower())

    def test_pace_evolution_findings_have_distinct_ids_and_compare(self) -> None:
        evolution = source(
            result_kind="observed_pace_evolution",
            results={
                "value_category": "derived",
                "stints": [
                    {
                        "driver": "VER",
                        "effective_stint": 1,
                        "start_lap": 3,
                        "end_lap": 15,
                        "pace_evolution": {
                            "status": "available",
                            "slope": 0.04,
                            "basis": "tyre_age",
                            "units": "s/tyre-age lap",
                            "sample_count": 10,
                            "quality": "high",
                            "method_id": "theil_sen",
                        },
                    },
                    {
                        "driver": "PER",
                        "effective_stint": 1,
                        "start_lap": 3,
                        "end_lap": 15,
                        "pace_evolution": {
                            "status": "available",
                            "slope": 0.08,
                            "basis": "tyre_age",
                            "units": "s/tyre-age lap",
                            "sample_count": 10,
                            "quality": "medium",
                            "method_id": "theil_sen",
                        },
                    },
                ],
            },
        )

        content = build_report_content("2023-bahrain-race", [evolution])

        self.assertEqual(len(content.findings), 2)
        self.assertEqual(len({item.finding_id for item in content.findings}), 2)
        self.assertEqual(content.conclusions[0].synthesis_rule_id, "pace-evolution-comparison-v1")
        self.assertEqual(content.conclusions[0].confidence, "medium")
        self.assertIn("VER's observed representative lap time increased by 0.040", content.conclusions[0].text)
        self.assertIn("versus 0.080 for PER", content.conclusions[0].text)
        self.assertIn("0.040 s/lap steeper increase for PER", content.conclusions[0].text)
        pace_section = next(
            section for section in content.plan.sections
            if section.section_id == "pace_and_tyre_performance"
        )
        planned_claims = [
            item.reference_id for item in pace_section.items if item.item_type == "claim"
        ]
        self.assertEqual(planned_claims, [content.conclusions[0].finding_id])
        self.assertTrue(
            set(content.conclusions[0].supporting_finding_ids).isdisjoint(planned_claims)
        )

    def test_executive_summary_selects_gap_pace_and_evolution_not_confounded_pit(self) -> None:
        sources = [source()]
        sources.append(
            source(
                chart="evolution",
                result_kind="observed_pace_evolution",
                results={
                    "value_category": "derived",
                    "stints": [
                        {"driver": "VER", "effective_stint": 1, "start_lap": 1, "end_lap": 14,
                         "pace_evolution": {"status": "available", "slope": 0.066, "basis": "tyre_age", "sample_count": 10, "quality": "high"}},
                        {"driver": "PER", "effective_stint": 1, "start_lap": 1, "end_lap": 17,
                         "pace_evolution": {"status": "available", "slope": 0.026, "basis": "tyre_age", "sample_count": 12, "quality": "high"}},
                    ],
                },
            )
        )
        sources.append(
            source(
                chart="gap",
                result_kind="measured_gap_change",
                results={
                    "status": "available",
                    "value_category": "measured",
                    "focal_driver": "VER",
                    "benchmark": "PER",
                    "start_lap": 1,
                    "end_lap": 57,
                    "paired_sample_count": 51,
                    "overall_change_seconds": -9.949,
                },
            )
        )
        sources.append(
            source(
                chart="pit",
                result_kind="measured_pit_cycle_comparison",
                results={
                    "status": "confounded",
                    "focal_driver": "VER",
                    "rival_driver": "PER",
                    "pre_reference_lap": 13,
                    "post_reference_lap": 16,
                    "pit_in_lap": 14,
                    "pit_out_lap": 15,
                    "pit_interval_precision": "exact",
                    "measured_gap_change_seconds": 21.282,
                    "rival_stopped_in_window": True,
                },
            )
        )

        content = build_report_content("2023-bahrain-race", sources)
        executive_ids = [
            item.reference_id for item in content.plan.sections[0].items
        ]
        types = {
            finding.finding_id: finding.finding_type
            for finding in [*content.findings, *content.conclusions]
        }

        self.assertEqual(
            [types[item_id] for item_id in executive_ids],
            [
                "direct_gap_change",
                "representative_pace_advantage",
                "pace-evolution-comparison",
            ],
        )

    def test_confounded_pit_claim_is_precise_and_carries_only_applicable_limits(self) -> None:
        value = source(
            result_kind="measured_pit_cycle_comparison",
            results={
                "status": "confounded",
                "focal_driver": "VER",
                "rival_driver": "PER",
                "pre_reference_lap": 13,
                "post_reference_lap": 16,
                "pit_in_lap": 14,
                "pit_out_lap": 15,
                "pit_interval_precision": "exact",
                "measured_gap_change_seconds": 21.282,
                "rival_stopped_in_window": True,
                "limitations": ["The result is a measured reference-point comparison."],
            },
        )

        content = build_report_content("2023-bahrain-race", [value])
        finding = content.findings[0]

        self.assertEqual(finding.confidence, "low")
        self.assertIn("pre-stop reference at lap 13", finding.text)
        self.assertIn("post-stop reference at lap 16", finding.text)
        self.assertTrue(any("PER also stopped" in item for item in finding.limitations))
        self.assertFalse(any("pace evolution" in item.lower() for item in finding.limitations))
        self.assertFalse(any("representative laps" in item.lower() for item in finding.limitations))

    def test_unsupported_result_schema_version_is_accounted_for(self) -> None:
        value = source()
        value.metadata["strategy_analysis_schema_version"] = 99

        content = build_report_content("2023-bahrain-race", [value])

        self.assertEqual(content.assessments[0].report_disposition, "unsupported")
        self.assertEqual(content.findings, [])

    def test_structured_markdown_embeds_chart_and_metadata(self) -> None:
        content = build_report_content("2023-bahrain-race", [source()])
        review = ReportReviewEntry(
            item_id=content.findings[0].finding_id,
            reviewed_evidence_fingerprint=content.findings[0].evidence_fingerprint,
            review_status="accepted",
        )
        manifest = ArtifactManifest(
            run_id="run",
            status="succeeded",
            framework_version="test",
            configuration_hash="hash",
            session={"season": 2023, "event": "Bahrain", "session": "Race"},
            requested_recipes=[],
        )

        markdown = render_structured_markdown(manifest, content, [review])

        self.assertIn("## Pace and Tyre Performance", markdown)
        self.assertIn("![Supporting analytical chart](charts/chart-1.png)", markdown)
        self.assertIn("[Chart metadata](charts/chart-1.json)", markdown)
        self.assertIn("Confidence: `medium`", markdown)

    def test_context_timeline_is_an_explicit_first_chart_plan_item(self) -> None:
        content = build_report_content(
            "2023-bahrain-race",
            [
                source(chart="timeline", result_kind="strategy_timeline", results={"status": "available"}),
                source(chart="pace"),
            ],
        )
        strategy = next(
            section for section in content.plan.sections
            if section.section_id == "strategy_and_race_evolution"
        )

        self.assertEqual(strategy.items[0].item_type, "chart")
        self.assertEqual(strategy.items[0].reference_id, "timeline")

    def test_publication_basis_humanizes_pace_evolution_intervals(self) -> None:
        evolution = source(
            chart="evolution",
            result_kind="observed_pace_evolution",
            results={
                "value_category": "derived",
                "stints": [
                    {"driver": "VER", "effective_stint": 1, "start_lap": 1, "end_lap": 14,
                     "pace_evolution": {"status": "available", "slope": 0.066, "basis": "tyre_age", "sample_count": 10, "quality": "high"}},
                    {"driver": "PER", "effective_stint": 1, "start_lap": 1, "end_lap": 17,
                     "pace_evolution": {"status": "available", "slope": 0.026, "basis": "tyre_age", "sample_count": 12, "quality": "high"}},
                ],
            },
        )
        content = build_report_content("2023-bahrain-race", [evolution])
        manifest = ArtifactManifest(
            run_id="run", status="succeeded", framework_version="test",
            configuration_hash="hash",
            session={"season": 2023, "event": "Bahrain", "session": "Race"},
            requested_recipes=[],
        )
        markdown = render_structured_markdown(manifest, content, [])

        self.assertIn(
            "Basis: VER stint 1, laps 1-14 vs PER stint 1, laps 1-17; representative laps only.",
            markdown,
        )
        self.assertNotIn("session id=", markdown)
        self.assertNotIn("intervals={", markdown)

    def test_unavailable_compound_assessment_carries_typed_reason_and_next_action(self) -> None:
        compound = source(
            result_kind="descriptive_within_driver_difference",
            results={
                "status": "unavailable",
                "participants": ["VER"],
                "compounds": ["SOFT", "HARD"],
                "sample_counts": {"VER:S1:SOFT": 11, "VER:S2:SOFT": 20, "VER:S3:HARD": 18},
                "control_rule": "race_lap_range",
                "scalar_difference_seconds": None,
            },
        )
        assessment = build_report_content("2023-bahrain-race", [compound]).assessments[0]

        self.assertEqual(assessment.reason_code, "compound_stint_ambiguous")
        self.assertIsNotNone(assessment.next_action)
        self.assertEqual(assessment.technical_details["minimum_samples_per_compound"], 5)

    def test_structured_package_writes_all_versioned_files(self) -> None:
        content = build_report_content("2023-bahrain-race", [source()])
        manifest = ArtifactManifest(
            run_id="run",
            status="succeeded",
            framework_version="test",
            configuration_hash="hash",
            session={"season": 2023, "event": "Bahrain", "session": "Race"},
            requested_recipes=[],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            legacy_observations = Path(temp_dir) / "observations.json"
            legacy_review = Path(temp_dir) / "review.json"
            legacy_observations.write_text("[]", encoding="utf-8")
            legacy_review.write_text("[]", encoding="utf-8")
            paths = write_structured_report_package(
                Path(temp_dir), manifest, content, []
            )

            self.assertTrue(paths.results_path.exists())
            self.assertTrue(paths.assessments_path.exists())
            self.assertTrue(paths.findings_path.exists())
            self.assertTrue(paths.report_path.exists())
            self.assertTrue(paths.review_path.exists())
            self.assertTrue(paths.markdown_path.exists())
            self.assertFalse(legacy_observations.exists())
            self.assertFalse(legacy_review.exists())
            self.assertEqual(len(paths.draft_fingerprint), 64)


if __name__ == "__main__":
    unittest.main()

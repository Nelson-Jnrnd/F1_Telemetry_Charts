from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from f1_telemetry_charts.analysis.findings import (
    EditorialField,
    PublicationEditorial,
    ReportReviewEntry,
    ResultSource,
    assess_results,
    build_report_content,
    provider_descriptors,
)
from f1_telemetry_charts.analysis.manifest import ArtifactManifest
from f1_telemetry_charts.analysis.publication import (
    SESSION_SPINE_TYPES,
    evaluate_readiness,
    materialize_session_spine,
    propose_publication_plan,
    validate_publication_plan,
)
from f1_telemetry_charts.analysis.report import (
    _publication_evidence_payload,
    render_publication_markdown,
)
from f1_telemetry_charts.analysis.workspace import AnalysisService
from f1_telemetry_charts.config.models import DataCacheConfig, SessionConfig
from f1_telemetry_charts.data import SessionDataset
from f1_telemetry_charts.ui.server import create_app


FIXTURE = Path("tests/fixtures/2023_bahrain_race_dataset.json")


class PublicationReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dataset = SessionDataset.model_validate(
            json.loads(FIXTURE.read_text(encoding="utf-8"))
        )
        self.results = materialize_session_spine("race-2023-bahrain", self.dataset)

    def test_session_spine_materializes_six_typed_provenance_qualified_results(self) -> None:
        self.assertEqual({item.result_type for item in self.results}, set(SESSION_SPINE_TYPES))
        categories = {item.result_type: item.measurement_category for item in self.results}
        self.assertEqual(categories["race_classification"], "derived")
        self.assertEqual(categories["grid_to_finish_movement"], "derived")
        self.assertTrue(
            all(
                category == "measured"
                for result_type, category in categories.items()
                if result_type not in {"race_classification", "grid_to_finish_movement"}
            )
        )
        self.assertTrue(all(item.provenance and item.coverage and item.quality for item in self.results))
        self.assertEqual(self.results, materialize_session_spine("race-2023-bahrain", self.dataset))

        assessments, findings = assess_results(self.results)
        self.assertEqual(len(assessments), 6)
        self.assertEqual(len({item.result_id for item in assessments}), 6)
        self.assertTrue(all(item.provider_id == "race-session-spine-provider" for item in assessments))
        self.assertEqual(len(findings), len({item.finding_id for item in findings}))
        descriptor = next(
            item for item in provider_descriptors() if item.provider_id == "race-session-spine-provider"
        )
        self.assertEqual(set(descriptor.result_types), set(SESSION_SPINE_TYPES))

    def test_non_race_scope_is_rejected_explicitly(self) -> None:
        qualifying = self.dataset.model_copy(
            update={"metadata": self.dataset.metadata.model_copy(update={"session": "Qualifying"})},
            deep=True,
        )
        with self.assertRaisesRegex(ValueError, "Race sessions only"):
            materialize_session_spine("qualifying", qualifying)

    def test_recorded_running_order_is_not_official_classification(self) -> None:
        inferred = next(
            item for item in self.results if item.result_type == "race_classification"
        )
        self.assertEqual(inferred.measurement_category, "derived")
        self.assertEqual(inferred.quality["level"], "medium")
        self.assertTrue(
            all(
                entry["classification_source"] == "last_recorded_lap"
                for entry in inferred.payload["entries"]
            )
        )
        self.assertNotIn(" won ", f" {inferred.payload['summary'].lower()} ")
        self.assertIn("last recorded running order", inferred.payload["summary"].lower())
        movement = next(
            item for item in self.results if item.result_type == "grid_to_finish_movement"
        )
        self.assertEqual(movement.measurement_category, "derived")
        self.assertTrue(
            all(entry["finish_source"] == "last_recorded_lap" for entry in movement.payload["entries"])
        )

        official_dataset = self.dataset.model_copy(
            update={
                "drivers": [
                    driver.model_copy(update={"classification_position": index + 1})
                    for index, driver in enumerate(self.dataset.drivers)
                ]
            },
            deep=True,
        )
        official = next(
            item
            for item in materialize_session_spine("official-race", official_dataset)
            if item.result_type == "race_classification"
        )
        self.assertEqual(official.measurement_category, "measured")
        self.assertEqual(official.quality["level"], "high")
        self.assertIn(" won ahead of ", f" {official.payload['summary'].lower()} ")

    def test_pit_lane_grid_zero_is_excluded_from_movement_arithmetic(self) -> None:
        dataset = self.dataset.model_copy(
            update={
                "drivers": [
                    driver.model_copy(
                        update={
                            "classification_position": index + 1,
                            "grid_position": 0 if index == 0 else index + 1,
                            "result_status": "Finished",
                        }
                    )
                    for index, driver in enumerate(self.dataset.drivers)
                ]
            },
            deep=True,
        )
        movement = next(
            item
            for item in materialize_session_spine("pit-lane-race", dataset)
            if item.result_type == "grid_to_finish_movement"
        )
        self.assertNotIn("VER", {entry["driver"] for entry in movement.payload["entries"]})
        self.assertIn("VER", movement.payload["pit_lane_starters"])
        self.assertTrue(any("pit-lane" in item.lower() for item in movement.limitations))

    def test_lapped_result_statuses_are_finishers(self) -> None:
        statuses = ["Lapped", "+1 Lap", "+12 Laps"]
        dataset = self.dataset.model_copy(
            update={
                "drivers": [
                    driver.model_copy(update={"result_status": statuses[index]})
                    for index, driver in enumerate(self.dataset.drivers)
                ]
            },
            deep=True,
        )
        retirement = next(
            item
            for item in materialize_session_spine("lapped-race", dataset)
            if item.result_type == "retirement_status"
        )
        self.assertTrue(all(entry["finish_category"] == "finisher" for entry in retirement.payload["entries"]))
        self.assertIn("all covered drivers as finishers", retirement.payload["summary"])

    def test_chronology_only_readiness_does_not_require_pace_lede(self) -> None:
        content = build_report_content(
            "chronology-only", [], additional_results=self.results
        )
        plan = propose_publication_plan(content)
        self.assertFalse(
            any(
                item.included and item.section == "pace_and_strategy"
                for item in plan.claims
            )
        )
        content = content.model_copy(
            update={
                "publication_plan": plan,
                "publication_editorial": PublicationEditorial(
                    headline=EditorialField(value="Recorded Bahrain order establishes the race chronology"),
                    standfirst=EditorialField(value="The available running order and race chronology provide a bounded account of the recorded session outcome."),
                    section_ledes={
                        "how_the_race_developed": EditorialField(value="The recorded order establishes the available chronology without claiming an official classification."),
                    },
                    conclusion=EditorialField(value="The resulting account remains limited to the available recorded race chronology."),
                ),
            },
            deep=True,
        )
        claims = {item.finding_id: item for item in [*content.findings, *content.conclusions]}
        reviews = [
            ReportReviewEntry(
                item_id=placement.finding_id,
                reviewed_evidence_fingerprint=claims[placement.finding_id].evidence_fingerprint,
                review_status="accepted",
            )
            for placement in plan.claims
            if placement.included
        ]
        readiness = evaluate_readiness(
            content,
            reviews,
            evidence_current=True,
            review_current=True,
            publication_current=True,
            export_current=False,
            package_integrity=True,
        )
        self.assertTrue(readiness.checks["pace_strategy_lede"])
        self.assertTrue(readiness.ready, readiness.blockers)

    def test_selection_and_clean_reader_rendering_are_deterministic(self) -> None:
        content = build_report_content(
            "race-2023-bahrain", [], additional_results=self.results
        )
        first = propose_publication_plan(content)
        second = propose_publication_plan(content)
        self.assertEqual(first, second)
        validate_publication_plan(content, first)
        self.assertEqual(
            first.section_order,
            [
                "headline",
                "standfirst",
                "at_a_glance",
                "how_the_race_developed",
                "pace_and_strategy",
                "key_comparison",
                "conclusion",
                "methods_and_evidence",
            ],
        )
        self.assertEqual(
            len({item.finding_id for item in first.claims if item.included}),
            len([item for item in first.claims if item.included]),
        )
        selected_types = {
            next(
                claim.finding_type
                for claim in [*content.findings, *content.conclusions]
                if claim.finding_id == item.finding_id
            )
            for item in first.claims
            if item.included
        }
        self.assertNotIn("pit_stop_sequence", selected_types)
        self.assertNotIn("position_change_interval", selected_types)
        summaries = [item.summary_reference for item in first.claims if item.summary_reference]
        self.assertTrue(all("reviewed evidence" not in item.lower() for item in summaries))
        self.assertTrue(all("classification established" not in item.lower() for item in summaries))
        editorial = PublicationEditorial(
            headline=EditorialField(value="Verstappen leads Bahrain as the field order changes"),
            standfirst=EditorialField(value="Verstappen led the Bahrain finish while the reviewed chronology and pace evidence defined the main race story."),
            section_ledes={
                "how_the_race_developed": EditorialField(value="The classified order, field recovery and neutralised phase establish the race chronology."),
                "pace_and_strategy": EditorialField(value="The representative-lap comparisons then show how the leading pair differed on pace."),
            },
            conclusion=EditorialField(value="The reviewed evidence defines the final account."),
        )
        content = content.model_copy(
            update={"publication_plan": first, "publication_editorial": editorial},
            deep=True,
        )
        claims = {item.finding_id: item for item in [*content.findings, *content.conclusions]}
        reviews = [
            ReportReviewEntry(
                item_id=placement.finding_id,
                reviewed_evidence_fingerprint=claims[placement.finding_id].evidence_fingerprint,
                review_status="accepted",
            )
            for placement in first.claims
            if placement.included
        ]
        markdown = render_publication_markdown(_manifest(), content, reviews)
        self.assertIn("# Verstappen leads Bahrain as the field order changes", markdown)
        self.assertIn("## How the Race Developed", markdown)
        self.assertNotIn("fingerprint", markdown.lower())
        self.assertNotIn("Confidence:", markdown)
        self.assertNotIn("[object Object]", markdown)
        self.assertNotIn("result-", markdown)

    def test_derived_cumulative_pace_is_not_labelled_as_race_gap(self) -> None:
        source = ResultSource(
            target_session_id="race-2023-bahrain",
            chart_instance_id="delta-chart",
            artifact_id="delta-artifact",
            image_path="charts/delta.png",
            metadata_path="charts/delta.json",
            metadata={
                "result_kind": "derived_cumulative_pace_delta",
                "analytical_results": {
                    "status": "available",
                    "value_category": "derived",
                    "focal_driver": "VER",
                    "benchmark": "PER",
                    "start_lap": 3,
                    "end_lap": 57,
                    "paired_sample_count": 51,
                    "overall_change_seconds": -11.134,
                    "limitations": ["This is not measured race gap."],
                },
                "analytical_basis": {},
                "strategy_warnings": [],
                "strategy_limitations": [],
            },
        )
        content = build_report_content("race-2023-bahrain", [source])
        finding = next(
            item for item in content.findings if item.finding_type == "cumulative_pace_delta"
        )
        self.assertIn("derived pace total, not the elapsed race gap", finding.text)
        plan = propose_publication_plan(content)
        title_only_plan = plan.model_copy(
            update={
                "charts": [
                    item.model_copy(
                        update={
                            "caption": EditorialField(value="Race-Time Delta Evolution."),
                            "alt_text": EditorialField(value=finding.text),
                        },
                        deep=True,
                    )
                    for item in plan.charts
                ]
            },
            deep=True,
        )
        content = content.model_copy(
            update={
                "publication_plan": title_only_plan,
                "publication_editorial": PublicationEditorial(
                    headline=EditorialField(value="Verstappen builds the stronger representative pace profile"),
                    standfirst=EditorialField(value="The reviewed representative laps show a derived pace advantage while remaining separate from the elapsed race gap."),
                ),
            },
            deep=True,
        )
        review = ReportReviewEntry(
            item_id=finding.finding_id,
            reviewed_evidence_fingerprint=finding.evidence_fingerprint,
            review_status="accepted",
        )
        blocked = evaluate_readiness(
            content,
            [review],
            evidence_current=True,
            review_current=True,
            publication_current=True,
            export_current=False,
            package_integrity=True,
        )
        self.assertFalse(blocked.checks["publication_captions"])
        self.assertFalse(blocked.checks["accessible_alt_text"])
        markdown = render_publication_markdown(_manifest(), content, [review])
        self.assertIn(
            "derived cumulative representative-lap pace difference, not elapsed race gap",
            markdown,
        )
        self.assertNotIn("measured direct timing gap", markdown)

        package_payload = _publication_evidence_payload(
            content,
            [review],
            [],
            {"delta-chart": "assets/delta-chart/delta.png"},
        )
        package_references = [
            reference
            for finding_value in package_payload["findings"]
            for reference in finding_value.get("evidence", [])
        ]
        self.assertTrue(package_references)
        self.assertTrue(all(item["reference_scope"] == "package" for item in package_references))
        self.assertEqual(package_references[0]["image_path"], "assets/delta-chart/delta.png")
        self.assertEqual(package_references[0]["metadata_path"], "assets/delta-chart/delta.json")
        self.assertNotIn("source_image_path", package_references[0])

        source_payload = _publication_evidence_payload(content, [review], [], {})
        source_reference = next(
            reference
            for finding_value in source_payload["findings"]
            for reference in finding_value.get("evidence", [])
        )
        self.assertEqual(source_reference["reference_scope"], "source_analysis")
        self.assertNotIn("image_path", source_reference)
        self.assertEqual(source_reference["source_image_path"], "charts/delta.png")

    def test_readiness_requires_editorial_review_preview_and_integrity(self) -> None:
        content = build_report_content(
            "race-2023-bahrain", [], additional_results=self.results
        )
        plan = propose_publication_plan(content)
        content = content.model_copy(update={"publication_plan": plan}, deep=True)
        blocked = evaluate_readiness(
            content,
            [],
            evidence_current=True,
            review_current=False,
            publication_current=False,
            export_current=False,
            package_integrity=False,
        )
        self.assertFalse(blocked.ready)
        self.assertEqual(blocked.state, "editorial_work_required")
        self.assertIn("Editorial headline", blocked.blockers)
        self.assertIn("Package integrity", blocked.blockers)

        content = content.model_copy(
            update={
                "publication_editorial": PublicationEditorial(
                    headline=EditorialField(value="Verstappen leads Bahrain as the field order changes"),
                    standfirst=EditorialField(value="Verstappen led the Bahrain finish while the reviewed chronology and pace evidence defined the main race story."),
                    section_ledes={
                        "how_the_race_developed": EditorialField(value="The classified order, field recovery and neutralised phase establish the race chronology."),
                        "pace_and_strategy": EditorialField(value="The representative-lap comparisons then show how the leading pair differed on pace."),
                    },
                    conclusion=EditorialField(value="The reviewed chronology and representative pace evidence support this final account."),
                )
            },
            deep=True,
        )
        claims = {item.finding_id: item for item in content.findings}
        reviews = [
            ReportReviewEntry(
                item_id=item.finding_id,
                reviewed_evidence_fingerprint=claims[item.finding_id].evidence_fingerprint,
                review_status="accepted",
            )
            for item in plan.claims
            if item.included
        ]
        ready = evaluate_readiness(
            content,
            reviews,
            evidence_current=True,
            review_current=True,
            publication_current=True,
            export_current=False,
            package_integrity=True,
        )
        self.assertTrue(ready.ready)
        self.assertEqual(ready.state, "publication_draft_ready")

    def test_publication_api_is_typed_persisted_and_stale_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "analysis"
            service = AnalysisService(root)
            analysis = service.create("Publication API")
            analysis = service.add_session(
                analysis,
                session=SessionConfig(season=2023, event="Bahrain Grand Prix", session="Race"),
                drivers=["VER", "PER"],
                data_cache=DataCacheConfig(fixture_path=FIXTURE),
            )
            analysis = service.refresh_observations(analysis)
            assert analysis.report_content is not None
            assert analysis.report_content.publication_plan is not None
            client = TestClient(create_app())
            opened = client.post("/api/analysis/open", json={"path": str(root)})
            self.assertEqual(opened.status_code, 200, opened.text)
            editorial = PublicationEditorial(
                headline=EditorialField(value="API headline"),
                standfirst=EditorialField(value="API standfirst"),
            )
            payload = {
                "evidence_fingerprint": analysis.report_content.evidence_fingerprint,
                "plan": analysis.report_content.publication_plan.model_dump(mode="json"),
                "editorial": editorial.model_dump(mode="json"),
            }
            updated = client.put("/api/analysis/publication", json=payload)
            self.assertEqual(updated.status_code, 200, updated.text)
            self.assertEqual(
                updated.json()["analysis"]["report_content"]["publication_editorial"]["headline"]["value"],
                "API headline",
            )
            payload["evidence_fingerprint"] = "stale"
            rejected = client.put("/api/analysis/publication", json=payload)
            self.assertEqual(rejected.status_code, 409, rejected.text)
            reloaded = service.open()
            self.assertEqual(
                reloaded.report_content.publication_editorial.headline.value,
                "API headline",
            )


def _manifest() -> ArtifactManifest:
    return ArtifactManifest(
        run_id="publication-test",
        status="succeeded",
        framework_version="test",
        created_at=datetime(2026, 8, 11, tzinfo=timezone.utc),
        configuration_hash="hash",
        session={"season": 2023, "event": "Bahrain Grand Prix", "session": "Race"},
        requested_recipes=[],
    )


if __name__ == "__main__":
    unittest.main()

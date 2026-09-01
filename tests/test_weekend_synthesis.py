from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from f1_telemetry_charts.analysis.findings import (
    AnalyticalResultRecord,
    ChartEvidence,
    ReportContent,
    ReportFinding,
    ReportPlan,
    ReportPlanSection,
    ReportReviewEntry,
    ResultReportAssessment,
    canonical_fingerprint,
)
from f1_telemetry_charts.analysis.weekend import (
    WeekendClaimCandidate,
    WeekendEditorial,
    WeekendEventIdentity,
    WeekendExpectation,
    WeekendSourceSession,
    bounded_weekend_payload,
    compose_standard_weekend,
    render_weekend_markdown,
    write_weekend_package,
)
from f1_telemetry_charts.ui.server import create_app


class StandardWeekendSynthesisTests(unittest.TestCase):
    def test_dry_weekend_is_deterministic_traceable_and_exportable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources, candidates = _weekend(root, condition="dry")
            editorial = _editorial()
            first = compose_standard_weekend(sources, candidates, editorial=editorial)
            second = compose_standard_weekend(sources, list(reversed(candidates)), editorial=editorial)

            self.assertTrue(first.readiness.ready, first.readiness.blockers)
            self.assertEqual(first.package_hash, second.package_hash)
            self.assertEqual(3, len(first.figures))
            self.assertEqual(
                ["weekend_story", "practice_to_grid", "race_outcome", "expectations_and_outcomes", "evidence_and_limitations"],
                first.section_order,
            )
            self.assertTrue(all(claim.source_result_ids for claim in first.claims))

            output = write_weekend_package(root / "export", first, sources)
            self.assertTrue((output / "article.md").is_file())
            self.assertTrue((output / "evidence.json").is_file())
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(first.package_hash, manifest["package_hash"])
            markdown = (output / "article.md").read_text(encoding="utf-8")
            self.assertEqual(render_weekend_markdown(first, asset_paths=manifest["assets"]), markdown)

    def test_disrupted_and_mixed_conditions_remain_qualified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            disrupted_sources, disrupted_candidates = _weekend(root / "disrupted", condition="safety_car")
            mixed_sources, mixed_candidates = _weekend(root / "mixed", condition="wet_to_dry")
            disrupted = compose_standard_weekend(disrupted_sources, disrupted_candidates, editorial=_editorial())
            mixed = compose_standard_weekend(mixed_sources, mixed_candidates, editorial=_editorial())

            self.assertTrue(disrupted.readiness.ready, disrupted.readiness.blockers)
            self.assertTrue(mixed.readiness.ready, mixed.readiness.blockers)
            self.assertTrue(any("safety car" in value.lower() for value in disrupted.limitations))
            self.assertTrue(any("wet to dry" in value.lower() for value in mixed.limitations))

    def test_sprint_cross_event_and_duplicate_session_scope_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            sources, candidates = _weekend(Path(directory), condition="dry")
            sprint = sources[0].model_copy(update={"event": sources[0].event.model_copy(update={"format": "sprint"})})
            with self.assertRaisesRegex(ValueError, "Sprint"):
                compose_standard_weekend([sprint, *sources[1:]], candidates)
            mismatch = sources[0].model_copy(update={"event": sources[0].event.model_copy(update={"event_id": "other"})})
            with self.assertRaisesRegex(ValueError, "same event"):
                compose_standard_weekend([mismatch, *sources[1:]], candidates)
            duplicate = sources[0].model_copy(update={"session_id": "fp1-copy", "content": sources[0].content.model_copy(update={"target_session_id": "fp1-copy"})})
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                compose_standard_weekend([*sources, duplicate], candidates)

    def test_rejected_stale_unknown_and_causal_claims_cannot_publish(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            sources, candidates = _weekend(Path(directory), condition="dry")
            stale = sources[0].model_copy(update={"evidence_current": False})
            synthesis = compose_standard_weekend([stale, *sources[1:]], candidates, editorial=_editorial())
            self.assertFalse(synthesis.readiness.ready)
            self.assertTrue(any("stale" in value for value in synthesis.readiness.blockers))

            causal_content = sources[0].content.model_copy(deep=True)
            causal_content.findings[0].text = "Practice pace caused the race result."
            causal = sources[0].model_copy(update={"content": causal_content})
            synthesis = compose_standard_weekend([causal, *sources[1:]], candidates, editorial=_editorial())
            self.assertTrue(any("causal" in value for value in synthesis.readiness.blockers))

    def test_explicit_pre_race_expectation_is_compared_descriptively(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            sources, candidates = _weekend(Path(directory), condition="dry")
            expectation = WeekendExpectation(
                expectation_id="expectation-1",
                subject="VER",
                comparison_basis={"basis": "classification"},
                expected_values={"position": 1},
                source_session_id="qualifying",
                source_claim_id="claim-qualifying",
                source_result_ids=["result-qualifying"],
                recorded_at=datetime(2026, 1, 2, 12, tzinfo=timezone.utc),
                author="Editor",
            )
            synthesis = compose_standard_weekend(
                sources, candidates, expectations=[expectation], editorial=_editorial()
            )
            self.assertTrue(synthesis.readiness.ready, synthesis.readiness.blockers)
            self.assertEqual("aligned", synthesis.expectations[0].state)
            markdown = render_weekend_markdown(synthesis)
            self.assertIn("## Expectations and Outcomes", markdown)
            self.assertNotIn("because", markdown.lower())

    def test_bounded_inspection_enforces_payload_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            sources, candidates = _weekend(Path(directory), condition="dry")
            synthesis = compose_standard_weekend(sources, candidates, editorial=_editorial())
            payload = bounded_weekend_payload(synthesis, claim_limit=2)
            self.assertEqual(2, len(payload["claims"]))
            self.assertEqual(3, payload["claim_count"])
            with self.assertRaisesRegex(ValueError, "between 1 and 100"):
                bounded_weekend_payload(synthesis, claim_limit=101)

    def test_workbench_api_persists_composes_inspects_and_exports_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            analysis_root = root / "analysis"
            sources, candidates = _weekend(root / "sources", condition="dry")
            client = TestClient(create_app())
            created = client.post(
                "/api/analysis/create",
                json={"path": str(analysis_root), "name": "Weekend"},
            )
            self.assertEqual(200, created.status_code, created.text)
            composed = client.post(
                "/api/analysis/weekend/compose",
                json={
                    "sources": [item.model_dump(mode="json") for item in sources],
                    "candidates": [item.model_dump(mode="json") for item in candidates],
                    "editorial": _editorial().model_dump(mode="json"),
                },
            )
            self.assertEqual(200, composed.status_code, composed.text)
            synthesis = composed.json()["analysis"]["weekend_synthesis"]
            self.assertTrue(synthesis["readiness"]["ready"])
            inspected = client.get("/api/analysis/weekend", params={"claim_limit": 2})
            self.assertEqual(200, inspected.status_code, inspected.text)
            self.assertEqual(2, len(inspected.json()["claims"]))
            exported = client.post("/api/analysis/weekend/export")
            self.assertEqual(200, exported.status_code, exported.text)
            export_path = Path(exported.json()["analysis"]["weekend_package_path"])
            self.assertTrue((export_path / "manifest.json").is_file())

            stale = client.post(
                "/api/analysis/weekend/compose",
                json={
                    "sources": [item.model_dump(mode="json") for item in sources],
                    "candidates": [item.model_dump(mode="json") for item in candidates],
                    "editorial": _editorial().model_dump(mode="json"),
                    "expected_evidence_fingerprint": "stale-value",
                },
            )
            self.assertEqual(409, stale.status_code)


def _weekend(root: Path, *, condition: str) -> tuple[list[WeekendSourceSession], list[WeekendClaimCandidate]]:
    event = WeekendEventIdentity(season=2026, event_id="bahrain", event_name="Bahrain Grand Prix")
    sessions = [
        ("fp1", "fp1", datetime(2026, 1, 1, 10, tzinfo=timezone.utc)),
        ("qualifying", "qualifying", datetime(2026, 1, 2, 10, tzinfo=timezone.utc)),
        ("race", "race", datetime(2026, 1, 3, 10, tzinfo=timezone.utc)),
    ]
    sources = [
        _source(root, event, session_id, session_kind, session_time, condition)
        for session_id, session_kind, session_time in sessions
    ]
    candidates = [
        WeekendClaimCandidate(
            source_session_id="fp1",
            source_claim_id="claim-fp1",
            subject="VER",
            predicate="recorded representative pace",
            object_value={"rank": 1},
            temporal_scope="FP1",
            comparison_basis={"basis": "representative laps"},
            conditions={"condition": condition},
            section="practice_to_grid",
            summary_eligible=True,
        ),
        WeekendClaimCandidate(
            source_session_id="qualifying",
            source_claim_id="claim-qualifying",
            subject="VER",
            predicate="qualified",
            object_value={"position": 1},
            temporal_scope="Qualifying",
            comparison_basis={"basis": "classification"},
            conditions={"condition": condition},
            section="practice_to_grid",
            summary_eligible=True,
        ),
        WeekendClaimCandidate(
            source_session_id="race",
            source_claim_id="claim-race",
            subject="VER",
            predicate="finished",
            object_value={"position": 1},
            temporal_scope="Race",
            comparison_basis={"basis": "classification"},
            conditions={"condition": condition},
            section="race_outcome",
            summary_eligible=True,
        ),
    ]
    return sources, candidates


def _source(root: Path, event: WeekendEventIdentity, session_id: str, session_kind: str, session_time: datetime, condition: str) -> WeekendSourceSession:
    package_root = root / session_id
    chart_dir = package_root / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)
    (chart_dir / f"{session_id}.png").write_bytes(b"png")
    (chart_dir / f"{session_id}.json").write_text("{}", encoding="utf-8")
    result_id = f"result-{session_id}"
    claim_id = f"claim-{session_id}"
    limitation = {
        "dry": "Dry-session evidence only.",
        "safety_car": "Safety Car context limits direct chronology comparison.",
        "wet_to_dry": "Wet to dry condition change remains material.",
    }[condition]
    evidence_fingerprint = canonical_fingerprint([claim_id, result_id, condition])
    result = AnalyticalResultRecord(
        result_id=result_id,
        result_type=f"{session_kind}_accepted_result",
        result_schema_version=1,
        target_session_id=session_id,
        result_fingerprint=canonical_fingerprint([result_id, condition]),
        analytical_status="available",
        measurement_category="measured",
        quality={"level": "high"},
        payload={"condition": condition},
        limitations=[limitation],
        chart_evidence=[ChartEvidence(
            chart_instance_id=f"chart-{session_id}", artifact_id=f"asset-{session_id}",
            title=f"{session_id.upper()} evidence", image_path=f"charts/{session_id}.png",
            metadata_path=f"charts/{session_id}.json",
        )],
    )
    text = {
        "fp1": "VER recorded the leading representative pace in FP1.",
        "qualifying": "VER qualified first in the official classification.",
        "race": "VER finished first in the official Race classification.",
    }[session_id]
    claim = ReportFinding(
        finding_id=claim_id,
        finding_type=f"{session_kind}_accepted_result",
        evidence_fingerprint=evidence_fingerprint,
        text=text,
        section="session_context" if session_id != "race" else "executive_summary",
        confidence="high",
        result_fingerprints=[result.result_fingerprint],
        result_ids=[result_id],
        provider_id=f"{session_kind}-provider",
        provider_version=1,
        limitations=[limitation],
        evidence=list(result.chart_evidence),
    )
    assessment = ResultReportAssessment(
        assessment_id=f"assessment-{session_id}", result_id=result_id,
        result_fingerprint=result.result_fingerprint, result_type=result.result_type,
        provider_id=f"{session_kind}-provider", provider_version=1,
        report_disposition="reportable", reasons=["Accepted typed evidence."], finding_ids=[claim_id],
    )
    content = ReportContent(
        target_session_id=session_id,
        results=[result], assessments=[assessment], findings=[claim], conclusions=[],
        plan=ReportPlan(target_session_id=session_id, sections=[ReportPlanSection(section_id="session_context", title="Context")]),
        evidence_fingerprint=canonical_fingerprint([session_id, evidence_fingerprint]),
    )
    return WeekendSourceSession(
        package_id=f"package-{session_id}", analysis_id=f"analysis-{session_id}",
        event=event, session_id=session_id, session_kind=session_kind,
        session_time=session_time, content=content,
        reviews=[ReportReviewEntry(item_id=claim_id, reviewed_evidence_fingerprint=evidence_fingerprint, review_status="accepted")],
        source_fingerprint=content.evidence_fingerprint,
        provider_version="1", policy_version="1", package_root=package_root,
    )


def _editorial() -> WeekendEditorial:
    return WeekendEditorial(
        headline="One weekend, three sessions, one supported result",
        standfirst="Accepted Practice, Qualifying, and Race evidence forms one chronological Bahrain weekend account.",
        lede="The accepted record moved from observed Practice pace through the grid outcome to the official Race result.",
        conclusion="The weekend record preserves the limits and provenance of every source session.",
        author="Editor",
        source_result_ids=["result-fp1", "result-qualifying", "result-race"],
        reviewed=True,
    )


if __name__ == "__main__":
    unittest.main()

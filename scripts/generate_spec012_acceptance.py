"""Generate the three real-session SPEC-012 application-workflow packages.

Automated generation records readiness honestly.  Human editorial acceptance
remains a separate closeout gate and is never inferred by this script.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from f1_telemetry_charts.analysis.findings import EditorialField, PublicationEditorial
from f1_telemetry_charts.analysis.workspace import AnalysisService
from f1_telemetry_charts.config.models import DataCacheConfig, SessionConfig


SESSIONS = {
    "dry": (2024, "Bahrain", "FP2", "Dry Practice with multiple eligible long runs and paired same-compound tyre-age evidence."),
    "interrupted": (2023, "Netherlands", "FP2", "Practice with recorded stoppage context and interruption-aware exclusions."),
    "wet": (2022, "Japan", "FP2", "Wet Practice with condition-aware comparison rejection or qualification."),
}
RECIPES = (
    "practice_run_overview",
    "practice_long_run_pace_summary",
    "practice_observed_pace_evolution",
)
EDITORIAL = {
    "dry": {
        "headline": "Bahrain FP2 reveals comparable observed long-run samples",
        "standfirst": "Official order remains unavailable from the configured source, while paired recorded tyre ages support bounded same-compound long-run observations.",
        "conclusion": "The observed long-run samples are comparable on their recorded basis, while fuel load and programme variables remain unknown.",
    },
    "interrupted": {
        "headline": "Recorded stoppages shape the Netherlands FP2 evidence",
        "standfirst": "Session-control timing and excluded laps preserve the interruption boundaries without assigning team intent or reconstructing hidden programme variables.",
        "conclusion": "The interruption-aware samples remain useful evidence, but they do not establish a controlled competitive ranking or predict the weekend outcome.",
    },
    "wet": {
        "headline": "Wet Suzuka running limits direct long-run comparison",
        "standfirst": "Recorded rain and wet-compound evidence keep incompatible Practice samples descriptive and prevent an unsupported scalar competitive ranking.",
        "conclusion": "The wet-session evidence describes only the recorded samples and does not assign a cause to observed pace evolution.",
    },
}
CAPTIONS = {
    "practice_long_run_pace_summary": (
        "Representative-lap medians and interquartile ranges with sample and tyre-age coverage retained in evidence.",
        "Horizontal bars show representative Practice lap-time interquartile ranges with a median marker for each eligible driver run.",
    ),
    "practice_observed_pace_evolution": (
        "Representative laps and fitted observed run-progress trends; hidden programme variables remain unknown.",
        "Scatter points show representative Practice lap times by run progress with dashed non-causal fitted trend lines.",
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", choices=[*SESSIONS, "all"], default="all")
    parser.add_argument("--root", type=Path, default=Path(".cache/spec012-acceptance"))
    parser.add_argument("--cache", type=Path, default=Path(".cache/spec012-fastf1"))
    parser.add_argument("--output", type=Path, default=Path("review-packages"))
    args = parser.parse_args()
    categories = list(SESSIONS) if args.category == "all" else [args.category]
    for category in categories:
        generate(category, args.root, args.cache, args.output)
    return 0


def generate(category: str, root: Path, cache: Path, output: Path) -> Path:
    season, event, session_name, purpose = SESSIONS[category]
    analysis_root = (root / category).resolve()
    expected_root = root.resolve()
    if expected_root not in analysis_root.parents:
        raise RuntimeError("Acceptance workspace escaped its configured root")
    if analysis_root.exists():
        shutil.rmtree(analysis_root)
    service = AnalysisService(analysis_root)
    analysis = service.create(f"SPEC-012 {category.title()} Acceptance")
    analysis = service.add_session(analysis, session=SessionConfig(season=season, event=event, session=session_name), drivers=["*"], data_cache=DataCacheConfig(directory=cache, mode="cache-or-fetch"), load=True)
    session = analysis.sessions[0]
    if session.load_state != "loaded":
        raise RuntimeError("Session load failed: " + "; ".join(session.errors))
    for recipe_id in RECIPES:
        analysis = service.add_chart(analysis, recipe_id=recipe_id, target_session_ids=[session.session_id])
    analysis = service.generate_charts(analysis)
    failed = [chart for chart in analysis.charts if chart.generation_state != "generated"]
    if failed:
        raise RuntimeError("Chart generation failed: " + "; ".join(error for chart in failed for error in chart.errors))
    analysis = service.refresh_observations(analysis)
    if analysis.report_content is None or analysis.report_content.publication_plan is None:
        raise RuntimeError("Practice report authority was not materialized")
    content = analysis.report_content
    _assert_fixture_purpose(category, content.results)
    plan = content.publication_plan
    recipe_by_chart = {chart.chart_instance_id: chart.recipe_id for chart in analysis.charts}
    plan = plan.model_copy(update={"charts": [chart.model_copy(update={"caption": EditorialField(value=CAPTIONS[recipe_by_chart[chart.chart_instance_id]][0]), "alt_text": EditorialField(value=CAPTIONS[recipe_by_chart[chart.chart_instance_id]][1])}, deep=True) for chart in plan.charts]}, deep=True)
    fingerprints = [result.result_fingerprint for result in content.results]
    required_sections = {item.section for item in [*plan.claims, *plan.charts] if item.included and item.section not in {"headline", "standfirst", "conclusion", "methods_and_evidence"}}
    lede_text = {
        "session_context": "Recorded weather and session-control evidence establish the condition and interruption boundaries for this Practice session.",
        "official_classification": "The official Practice classification remains separate from lap timing and is never reconstructed from recorded laps.",
        "relevant_runs": "Pit-bounded runs retain representative and excluded laps, compound evidence, coverage, and unknown programme limitations.",
        "matched_long_run_comparison": "Only overlapping same-compound samples paired at reliable shared tyre ages expose a scalar observed difference.",
        "observed_run_trend": "The fitted line describes observed within-run pace evolution without assigning fuel, tyre, traffic, or programme cause.",
    }
    framing = EDITORIAL[category]
    editorial = PublicationEditorial(headline=EditorialField(value=framing["headline"], dependency_fingerprints=fingerprints), standfirst=EditorialField(value=framing["standfirst"], dependency_fingerprints=fingerprints), section_ledes={section: EditorialField(value=lede_text[section], dependency_fingerprints=fingerprints) for section in required_sections}, conclusion=EditorialField(value=framing["conclusion"], dependency_fingerprints=fingerprints))
    analysis = service.update_publication(analysis, plan=plan, editorial=editorial, evidence_fingerprint=content.evidence_fingerprint)
    content = analysis.report_content
    assert content is not None and content.publication_plan is not None
    claims = {claim.finding_id: claim for claim in [*content.findings, *content.conclusions]}
    for placement in content.publication_plan.claims:
        if not placement.included:
            continue
        claim = claims[placement.finding_id]
        analysis = service.review_report_item(analysis, item_id=claim.finding_id, review_status="accepted", evidence_fingerprint=claim.evidence_fingerprint)
    analysis = service.regenerate_report_draft(analysis)
    content = analysis.report_content
    assert content is not None
    payloads = [result.payload for result in content.results]
    comparison_counts = {
        status: sum(payload.get("comparison_status") == status for payload in payloads)
        for status in ("comparable", "unknown", "confounded")
    }
    conditions = next(
        (payload for payload in payloads if "condition_state" in payload and "weather_samples" in payload),
        {},
    )
    interruptions = next((payload for payload in payloads if "events" in payload and "material" in payload), {})
    ready = content.publication_readiness.ready
    blockers = content.publication_readiness.blockers
    if ready:
        analysis = service.export_package(analysis)
        package_root = Path(analysis.exported_package_path or "")
    else:
        package_root = Path(analysis.report_package_path or "")
    output.mkdir(parents=True, exist_ok=True)
    base = output / f"SPEC-012-{category}-{season}-{event.lower().replace(' ', '-')}-{session_name.lower()}"
    zip_path = base.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    shutil.make_archive(str(base), "zip", package_root)
    evidence = {
        "spec_id": "SPEC-012",
        "category": category,
        "session": {"season": season, "event": event, "session": session_name},
        "purpose": purpose,
        "source": "FastF1 application gateway",
        "source_snapshot_fingerprint": session.snapshot.dataset_hash if session.snapshot else None,
        "package": zip_path.name,
        "package_sha256": hashlib.sha256(zip_path.read_bytes()).hexdigest(),
        "result_count": len(content.results),
        "long_run_count": sum(payload.get("run_status") == "long_run" for payload in payloads),
        "sustained_run_count": sum(payload.get("run_status") == "sustained_run" for payload in payloads),
        "comparison_counts": comparison_counts,
        "condition_state": conditions.get("condition_state", "unknown"),
        "interruption_count": len(interruptions.get("events", [])),
        "policy_versions": {"publication": f"{content.publication_plan.policy_id}:v{content.publication_plan.policy_version}", "practice_results": 1, "run_eligibility": 1, "paired_tyre_age": 1},
        "package_ready": ready,
        "readiness_blockers": blockers,
        "automated_review": "passed" if ready else "intentionally_blocked",
        "human_editorial_acceptance": "pending",
        "rubric": ["correct official order or explicit source-unavailable block", "transparent sample selection", "compatible comparison basis", "non-causal language", "no prediction", "useful charts", "no duplication", "readable mobile output", "claim-to-lap traceability"],
    }
    base.with_suffix(".acceptance.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(zip_path)
    return zip_path


def _assert_fixture_purpose(category: str, results: list[object]) -> None:
    payloads = [getattr(result, "payload") for result in results]
    if category == "dry":
        if sum(payload.get("run_status") == "long_run" for payload in payloads) < 2 or not any(payload.get("comparison_status") == "comparable" for payload in payloads):
            raise RuntimeError("Dry fixture lacks two long runs and a comparable paired sample")
    elif category == "interrupted":
        interruptions = next((payload for payload in payloads if "events" in payload and "material" in payload), None)
        chronology = next((payload for payload in payloads if "runs" in payload), None)
        excluded = sum(len(run.get("excluded_laps", [])) for run in (chronology or {}).get("runs", []))
        if not interruptions or not interruptions.get("material") or excluded == 0:
            raise RuntimeError("Interrupted fixture lacks a material recorded stoppage or exclusions")
    else:
        conditions = next((payload for payload in payloads if "condition_state" in payload and "weather_samples" in payload), None)
        comparisons = [payload for payload in payloads if "comparison_status" in payload]
        if not conditions or conditions.get("condition_state") != "mixed_or_wet" or not any(payload.get("comparison_status") != "comparable" for payload in comparisons):
            raise RuntimeError("Wet fixture lacks condition evidence or comparison rejection")


if __name__ == "__main__":
    raise SystemExit(main())

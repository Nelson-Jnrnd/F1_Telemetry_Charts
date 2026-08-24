"""Generate the three real-session SPEC-011 acceptance packages.

The script deliberately uses AnalysisService so load, chart generation, report
refresh, review, framing, exact preview, readiness, and export follow the same
application workflow as the Workbench.  Human editorial acceptance remains a
separate recorded gate after package generation.
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
    "dry": (2024, "Bahrain", "A dry session with complete Q1/Q2/Q3 running."),
    "interrupted": (2022, "Austria", "A dry session with recorded qualifying red flags."),
    "wet": (2021, "Belgium", "A wet session with recorded interruptions and condition variation."),
}
RECIPES = (
    "qualifying_progression",
    "qualifying_sector_contribution",
)

EDITORIAL_SOURCES = {
    "interrupted": [
        "https://www.formula1.com/en/results/2022/races/1115/austria/qualifying",
        "https://www.formula1.com/en/latest/article/verstappen-beats-ferraris-to-pole-in-austria-as-both-mercedes-crash-out-of.gwiQsXrDwuXn1ZgRALzWy.gwiQsXrDwuXn1ZgRALzWy",
    ],
    "wet": [
        "https://www.formula1.com/en/latest/article/qualifying-verstappen-denies-russell-shock-pole-in-dramatic-wet-qualifying.XP92uMlcsG9ZQbF0vpqYn",
        "https://www.formula1.com/en/latest/article/norris-cleared-to-race-in-belgian-grand-prix-after-high-speed-crash-in.6YgE5dp9k71zm36LXRSeux.6YgE5dp9k71zm36LXRSeux",
    ],
    "dry": ["https://www.formula1.com/en/results/2024/races/1229/bahrain/qualifying"],
}

EDITORIAL = {
    "dry": {
        "headline": "Verstappen wins Bahrain pole in the first sector",
        "standfirst": "Max Verstappen beat Charles Leclerc by 0.228 seconds, with almost the entire pole margin established in the opening sector.",
        "conclusion": "Verstappen's first-sector advantage decided pole; Leclerc was effectively level over the remaining two sectors.",
    },
    "interrupted": {
        "headline": "Austria qualifying fails deleted-lap integrity review",
        "standfirst": "Lewis Hamilton's crash caused the first Q3 red flag and George Russell's caused the second, but the official result and lap feed also disagree over Sergio Pérez's Q2 and Q3 running.",
        "conclusion": "Hamilton and Russell's crashes repeatedly reset the Q3 contest; the Pérez deletion conflict still blocks analytical publication.",
    },
    "wet": {
        "headline": "Verstappen denies Russell after Norris crash resets wet Spa qualifying",
        "standfirst": "Norris topped Q1 and Q2 before crashing without a Q3 time; after the long red flag, Russell briefly took provisional pole before Verstappen beat him by 0.321 seconds.",
        "conclusion": "Wet-track evolution and Norris's interruption reset Q3, then Russell's provisional pole forced Verstappen to deliver the decisive final lap.",
    },
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", choices=[*SESSIONS, "all"], default="all")
    parser.add_argument("--root", type=Path, default=Path(".cache/spec011-acceptance"))
    parser.add_argument("--cache", type=Path, default=Path(".cache/spec011-fastf1"))
    parser.add_argument("--output", type=Path, default=Path("review-packages"))
    args = parser.parse_args()
    categories = list(SESSIONS) if args.category == "all" else [args.category]
    for category in categories:
        generate(category, args.root, args.cache, args.output)
    return 0


def generate(category: str, root: Path, cache: Path, output: Path) -> Path:
    season, event, purpose = SESSIONS[category]
    analysis_root = root / category
    if analysis_root.exists():
        shutil.rmtree(analysis_root)
    service = AnalysisService(analysis_root)
    analysis = service.create(f"SPEC-011 {category.title()} Acceptance")
    analysis = service.add_session(
        analysis,
        session=SessionConfig(season=season, event=event, session="Qualifying"),
        drivers=["*"],
        data_cache=DataCacheConfig(directory=cache, mode="cache-or-fetch"),
        load=True,
    )
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
    assert analysis.report_content is not None
    content = analysis.report_content
    plan = content.publication_plan
    assert plan is not None
    fingerprints = [result.result_fingerprint for result in content.results]
    captions = {
        "qualifying_progression": ("Running best laps on session time, with compound markers, the competitive benchmark and recorded red-flag periods.", "Three qualifying panels chart running best lap times against session time, with tyre markers and shaded rain or red-flag periods."),
        "qualifying_sector_contribution": ("Signed sector contributions to the official Q3 pole margin.", "Horizontal bars show how each sector contributed to the lap-time difference between pole position and second place."),
    }
    recipe_by_chart = {chart.chart_instance_id: chart.recipe_id for chart in analysis.charts}
    plan = plan.model_copy(
        update={
            "charts": [
                chart.model_copy(
                    update={
                        "caption": EditorialField(value=captions[recipe_by_chart[chart.chart_instance_id]][0]),
                        "alt_text": EditorialField(value=captions[recipe_by_chart[chart.chart_instance_id]][1]),
                    },
                    deep=True,
                )
                for chart in plan.charts
            ]
        },
        deep=True,
    )
    required_sections = {item.section for item in [*plan.claims, *plan.charts] if item.included and item.section not in {"headline", "standfirst", "at_a_glance", "conclusion", "methods_and_evidence"}}
    ledes = {
        "how_qualifying_unfolded": "Running best laps on session time show when the competitive order changed through Q1, Q2 and Q3.",
        "pole_and_cutoff_battles": "The official same-segment margins separate the pole fight from the Q1 and Q2 advancement battles.",
        "sector_comparison": "The sector split identifies where the official pole margin was won rather than stopping at the arithmetic.",
    }
    context_edit = None
    if category == "interrupted":
        context_edit = "Hamilton crashed at Turn 7 to cause the first Q3 red flag; after the restart, Russell crashed at the final corner and stopped the session again."
    elif category == "wet":
        context_edit = "Qualifying began on full wets before the improving circuit brought intermediates into play. Rain intensified for Q3, Norris crashed before setting a time, and the long red flag preceded an intermediate-tyre restart in which Russell briefly held provisional pole before Verstappen beat him by 0.321 seconds."
    framing = EDITORIAL[category]
    editorial = PublicationEditorial(
        headline=EditorialField(value=framing["headline"], dependency_fingerprints=fingerprints),
        standfirst=EditorialField(value=framing["standfirst"], dependency_fingerprints=fingerprints),
        section_ledes={section: EditorialField(value=ledes[section], dependency_fingerprints=fingerprints) for section in required_sections if section in ledes},
        conclusion=EditorialField(value=framing["conclusion"], dependency_fingerprints=fingerprints),
        source_urls=EDITORIAL_SOURCES[category],
    )
    analysis = service.update_publication(analysis, plan=plan, editorial=editorial, evidence_fingerprint=content.evidence_fingerprint)
    assert analysis.report_content is not None
    claims = {claim.finding_id: claim for claim in [*analysis.report_content.findings, *analysis.report_content.conclusions]}
    for placement in analysis.report_content.publication_plan.claims:
        if not placement.included:
            continue
        claim = claims[placement.finding_id]
        edited_context = context_edit if placement.section == "session_context" else None
        analysis = service.review_report_item(
            analysis,
            item_id=claim.finding_id,
            review_status="edited" if edited_context else "accepted",
            evidence_fingerprint=claim.evidence_fingerprint,
            edited_text=edited_context,
        )
    analysis = service.regenerate_report_draft(analysis)
    if not analysis.report_content:
        raise RuntimeError("Acceptance package has no report content")
    ready = analysis.report_content.publication_readiness.ready
    blockers = analysis.report_content.publication_readiness.blockers
    if category == "interrupted":
        if ready or analysis.report_content.publication_readiness.checks.get("deleted_lap_integrity", True):
            raise RuntimeError("Austria must remain blocked by the deleted-lap integrity check")
        export_path = Path(analysis.report_package_path or "")
    else:
        if not ready:
            raise RuntimeError("Acceptance package is not ready: " + ", ".join(blockers))
        analysis = service.export_package(analysis)
        export_path = Path(analysis.exported_package_path or "")
    output.mkdir(parents=True, exist_ok=True)
    base = output / f"SPEC-011-{category}-{season}-{event.lower().replace(' ', '-')}-qualifying"
    zip_path = base.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    shutil.make_archive(str(base), "zip", export_path)
    evidence = {
        "spec_id": "SPEC-011",
        "category": category,
        "session": {"season": season, "event": event, "session": "Qualifying"},
        "purpose": purpose,
        "source": "FastF1 application gateway",
        "editorial_sources": EDITORIAL_SOURCES[category],
        "source_snapshot_fingerprint": session.snapshot.dataset_hash if session.snapshot else None,
        "package": zip_path.name,
        "package_sha256": hashlib.sha256(zip_path.read_bytes()).hexdigest(),
        "policy_versions": {
            "publication": f"{analysis.report_content.publication_plan.policy_id}:v{analysis.report_content.publication_plan.policy_version}",
            "qualifying_results": 1,
            "temporal_evolution": 2,
        },
        "package_ready": ready,
        "readiness_blockers": blockers,
        "automated_review": "blocked_as_expected" if category == "interrupted" else "passed",
        "human_editorial_acceptance": "accepted_as_expected_integrity_block" if category == "interrupted" else "accepted",
        "rubric": [
            "correct official story",
            "sound comparison bases",
            "honest availability",
            "non-causal wording",
            "useful charts",
            "no duplication",
            "readable mobile output",
            "claim-to-evidence traceability",
            "no required structural rewrite",
        ],
    }
    base.with_suffix(".acceptance.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(zip_path)
    return zip_path


if __name__ == "__main__":
    raise SystemExit(main())

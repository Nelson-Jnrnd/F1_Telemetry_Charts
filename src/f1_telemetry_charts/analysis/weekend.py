"""Deterministic standard-weekend synthesis over persisted session reports.

The composer deliberately imports no data gateway, session dataset, recipe, or
analytical provider.  Its inputs are immutable report records produced by the
existing Practice, Qualifying, and Race authorities.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from f1_telemetry_charts.analysis.findings import (
    MeasurementCategory,
    ReportContent,
    ReportFinding,
    ReportReviewEntry,
    canonical_fingerprint,
    stable_id,
)


WEEKEND_SYNTHESIS_SCHEMA_VERSION = 1
WEEKEND_POLICY_ID = "standard-weekend-synthesis"
WEEKEND_POLICY_VERSION = 1
WEEKEND_SECTION_ORDER = [
    "weekend_story",
    "practice_to_grid",
    "race_outcome",
    "expectations_and_outcomes",
    "evidence_and_limitations",
]

SessionKind = Literal["fp1", "fp2", "fp3", "qualifying", "race"]
InventoryStatus = Literal["included", "unavailable", "cancelled", "omitted"]
ExpectationState = Literal[
    "aligned", "partially_aligned", "not_aligned", "not_comparable"
]
WeekendSection = Literal[
    "weekend_story",
    "practice_to_grid",
    "race_outcome",
    "expectations_and_outcomes",
    "evidence_and_limitations",
]


class WeekendEventIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    season: int = Field(ge=1950)
    event_id: str = Field(min_length=1)
    event_name: str = Field(min_length=1)
    format: Literal["standard", "sprint", "ambiguous"] = "standard"


class WeekendSourceSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_id: str = Field(min_length=1)
    analysis_id: str = Field(min_length=1)
    event: WeekendEventIdentity
    session_id: str = Field(min_length=1)
    session_kind: SessionKind
    session_time: datetime
    content: ReportContent
    reviews: list[ReportReviewEntry] = Field(default_factory=list)
    source_status: InventoryStatus = "included"
    inclusion_reason: str = "accepted current session evidence"
    evidence_current: bool = True
    review_current: bool = True
    report_disposition: Literal[
        "reportable", "context_only", "not_reportable", "unsupported", "unavailable"
    ] = "reportable"
    source_fingerprint: str = Field(min_length=1)
    provider_version: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    package_root: Path | None = None

    @model_validator(mode="after")
    def content_matches_session(self) -> "WeekendSourceSession":
        if self.content.target_session_id != self.session_id:
            raise ValueError("Source report target does not match its session identity.")
        return self


class WeekendSessionInventoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: WeekendEventIdentity
    session_id: str
    session_kind: SessionKind
    session_time: datetime
    package_id: str
    analysis_id: str
    source_status: InventoryStatus
    inclusion_reason: str
    source_fingerprint: str
    provider_version: str
    policy_version: str


class WeekendClaimCandidate(BaseModel):
    """Editorial semantic mapping for one already accepted session claim."""

    model_config = ConfigDict(extra="forbid")

    source_session_id: str
    source_claim_id: str
    subject: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    object_value: Any
    temporal_scope: str = Field(min_length=1)
    comparison_basis: dict[str, Any] = Field(default_factory=dict)
    conditions: dict[str, Any] = Field(default_factory=dict)
    section: Literal["practice_to_grid", "race_outcome"]
    summary_eligible: bool = False
    supported_cross_session_relationship: bool = False


class WeekendClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    text: str
    subject: str
    predicate: str
    object_value: Any
    temporal_scope: str
    comparison_basis: dict[str, Any] = Field(default_factory=dict)
    conditions: dict[str, Any] = Field(default_factory=dict)
    measurement_category: MeasurementCategory
    quality: str
    limitations: list[str] = Field(default_factory=list)
    source_claim_ids: list[str]
    source_session_ids: list[str]
    source_result_ids: list[str]
    source_chart_asset_ids: list[str] = Field(default_factory=list)
    section: Literal["practice_to_grid", "race_outcome"]
    summary_eligible: bool = False


class WeekendExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expectation_id: str
    subject: str = Field(min_length=1)
    comparison_basis: dict[str, Any]
    expected_values: dict[str, Any] = Field(min_length=1)
    source_session_id: str
    source_claim_id: str
    source_result_ids: list[str] = Field(min_length=1)
    recorded_at: datetime
    author: str = Field(min_length=1)
    reviewed: bool = True


class WeekendExpectationComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comparison_id: str
    expectation_id: str
    outcome_claim_id: str
    state: ExpectationState
    source_session_ids: list[str]
    source_result_ids: list[str]


class WeekendFigure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    figure_id: str
    source_session_id: str
    source_claim_ids: list[str]
    source_result_ids: list[str]
    source_chart_asset_id: str
    source_image_path: str
    source_metadata_path: str
    section: Literal["practice_to_grid", "race_outcome"]
    caption: str
    alt_text: str


class WeekendEditorial(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headline: str = ""
    standfirst: str = ""
    lede: str = ""
    conclusion: str = ""
    author: str = ""
    source_result_ids: list[str] = Field(default_factory=list)
    reviewed: bool = False


class WeekendReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ready: bool = False
    blockers: list[str] = Field(default_factory=list)
    checks: dict[str, bool] = Field(default_factory=dict)
    next_action: str = "Resolve source evidence blockers"


class WeekendSynthesis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = WEEKEND_SYNTHESIS_SCHEMA_VERSION
    policy_id: str = WEEKEND_POLICY_ID
    policy_version: int = WEEKEND_POLICY_VERSION
    weekend_id: str
    event: WeekendEventIdentity
    inventory: list[WeekendSessionInventoryItem]
    claims: list[WeekendClaim]
    summary_claim_ids: list[str]
    expectations: list[WeekendExpectationComparison]
    figures: list[WeekendFigure]
    editorial: WeekendEditorial
    section_order: list[WeekendSection]
    limitations: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    evidence_fingerprint: str
    package_hash: str
    readiness: WeekendReadiness


_SESSION_ORDER = {"fp1": 0, "fp2": 1, "fp3": 2, "qualifying": 3, "race": 4}
_QUALITY_ORDER = {"unavailable": 0, "low": 1, "medium": 2, "high": 3}
_UNSUPPORTED_CAUSALITY = re.compile(
    r"\b(because|caused|led to|resulted in|proved|confirmed|underperformed|overperformed)\b",
    re.I,
)


def compose_standard_weekend(
    sources: list[WeekendSourceSession],
    candidates: list[WeekendClaimCandidate],
    *,
    expectations: list[WeekendExpectation] | None = None,
    editorial: WeekendEditorial | None = None,
) -> WeekendSynthesis:
    """Compose one deterministic standard-weekend record without analytics."""

    source_by_session = _validate_scope(sources)
    event = sources[0].event
    inventory = [
        WeekendSessionInventoryItem(
            event=item.event,
            session_id=item.session_id,
            session_kind=item.session_kind,
            session_time=item.session_time,
            package_id=item.package_id,
            analysis_id=item.analysis_id,
            source_status=item.source_status,
            inclusion_reason=item.inclusion_reason,
            source_fingerprint=item.source_fingerprint,
            provider_version=item.provider_version,
            policy_version=item.policy_version,
        )
        for item in sorted(sources, key=lambda value: (_SESSION_ORDER[value.session_kind], value.session_time, value.session_id))
    ]
    claims, candidate_blockers = _materialize_claims(source_by_session, candidates)
    claims, conflicts = _merge_and_check_claims(claims)
    expectation_pairs, expectation_blockers = _pair_expectations(
        source_by_session, claims, expectations or []
    )
    figures = _select_figures(source_by_session, claims)
    editorial_value = editorial or WeekendEditorial()
    summary_ids = [item.claim_id for item in claims if item.summary_eligible][:3]
    checks = {
        "standard_weekend_scope": True,
        "accepted_current_sources": not candidate_blockers,
        "minimum_session_coverage": _minimum_coverage(sources),
        "claim_traceability": all(item.source_result_ids and item.source_session_ids for item in claims),
        "canonical_claim_placement": len({item.claim_id for item in claims}) == len(claims),
        "conflict_free_synthesis": not conflicts,
        "purposeful_figure_count": 3 <= len(figures) <= 5,
        "editorial_reviewed": editorial_value.reviewed,
        "editorial_provenance": bool(editorial_value.source_result_ids)
        and set(editorial_value.source_result_ids)
        <= {result_id for claim in claims for result_id in claim.source_result_ids},
        "editorial_complete": all(
            value.strip()
            for value in (
                editorial_value.headline,
                editorial_value.standfirst,
                editorial_value.lede,
                editorial_value.conclusion,
                editorial_value.author,
            )
        ),
        "expectations_valid": not expectation_blockers,
    }
    blockers = [
        *candidate_blockers,
        *expectation_blockers,
        *conflicts,
        *[name.replace("_", " ").capitalize() for name, passed in checks.items() if not passed],
    ]
    blockers = list(dict.fromkeys(blockers))
    readiness = WeekendReadiness(
        ready=not blockers,
        blockers=blockers,
        checks=checks,
        next_action=("Export weekend package" if not blockers else blockers[0]),
    )
    semantic = {
        "policy": [WEEKEND_POLICY_ID, WEEKEND_POLICY_VERSION],
        "event": event.model_dump(mode="json"),
        "inventory": [item.model_dump(mode="json") for item in inventory],
        "claims": [item.model_dump(mode="json") for item in claims],
        "expectations": [item.model_dump(mode="json") for item in expectation_pairs],
        "figures": [item.model_dump(mode="json") for item in figures],
        "editorial": editorial_value.model_dump(mode="json"),
    }
    evidence_fingerprint = canonical_fingerprint(semantic)
    return WeekendSynthesis(
        weekend_id=stable_id("weekend", str(event.season), event.event_id),
        event=event,
        inventory=inventory,
        claims=claims,
        summary_claim_ids=summary_ids,
        expectations=expectation_pairs,
        figures=figures,
        editorial=editorial_value,
        section_order=list(WEEKEND_SECTION_ORDER),
        limitations=sorted(
            set(value for claim in claims for value in claim.limitations)
        ),
        conflicts=conflicts,
        evidence_fingerprint=evidence_fingerprint,
        package_hash=canonical_fingerprint({**semantic, "evidence_fingerprint": evidence_fingerprint}),
        readiness=readiness,
    )


def render_weekend_markdown(synthesis: WeekendSynthesis, *, asset_paths: dict[str, str] | None = None) -> str:
    """Render the canonical reader article directly from the synthesis record."""

    assets = asset_paths or {}
    claims = {item.claim_id: item for item in synthesis.claims}
    lines = [f"# {synthesis.editorial.headline}", "", synthesis.editorial.standfirst, "", "## Weekend Story", "", synthesis.editorial.lede, ""]
    for claim_id in synthesis.summary_claim_ids:
        if claim_id in claims:
            lines.append(f"- {claims[claim_id].text} `[{claim_id}]`")
    lines.append("")
    for section, title in (("practice_to_grid", "From Practice to the Grid"), ("race_outcome", "Race Outcome")):
        lines.extend([f"## {title}", ""])
        for claim in synthesis.claims:
            if claim.section == section:
                lines.append(f"{claim.text} `[{claim.claim_id}]`")
                lines.append("")
        for figure in synthesis.figures:
            if figure.section != section:
                continue
            path = assets.get(figure.figure_id, figure.source_image_path).replace("\\", "/")
            lines.extend([f"![{_safe_text(figure.alt_text)}]({path})", "", figure.caption, ""])
    if synthesis.expectations:
        lines.extend(["## Expectations and Outcomes", ""])
        for item in synthesis.expectations:
            lines.append(
                f"- `{item.state.replace('_', ' ')}` — expectation `{item.expectation_id}` compared with outcome `[{item.outcome_claim_id}]`."
            )
        lines.append("")
    lines.extend(["## Evidence and Limitations", ""])
    for item in synthesis.inventory:
        lines.append(f"- {item.session_kind.upper()}: `{item.source_status}` — {item.inclusion_reason}")
    for limitation in synthesis.limitations:
        lines.append(f"- {limitation}")
    lines.extend(["", synthesis.editorial.conclusion, "", "[Machine-readable evidence](evidence.json)", ""])
    return "\n".join(lines)


def write_weekend_package(
    output_dir: Path,
    synthesis: WeekendSynthesis,
    sources: list[WeekendSourceSession],
) -> Path:
    """Write one contained, relocatable weekend publication package."""

    if not synthesis.readiness.ready:
        raise ValueError("Weekend synthesis is not ready: " + ", ".join(synthesis.readiness.blockers))
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "assets").mkdir()
    source_by_session = {item.session_id: item for item in sources}
    asset_paths: dict[str, str] = {}
    for figure in synthesis.figures:
        source = source_by_session[figure.source_session_id]
        if source.package_root is None:
            raise ValueError(f"Source package root is missing for {figure.source_session_id}.")
        source_root = source.package_root.resolve()
        image = _contained_source(source_root, figure.source_image_path)
        metadata = _contained_source(source_root, figure.source_metadata_path)
        target_dir = output_dir / "assets" / figure.figure_id
        target_dir.mkdir()
        image_target = target_dir / image.name
        metadata_target = target_dir / metadata.name
        shutil.copy2(image, image_target)
        shutil.copy2(metadata, metadata_target)
        asset_paths[figure.figure_id] = image_target.relative_to(output_dir).as_posix()
    article = render_weekend_markdown(synthesis, asset_paths=asset_paths)
    (output_dir / "article.md").write_text(article, encoding="utf-8")
    article_payload = {
        "schema_version": synthesis.schema_version,
        "weekend_id": synthesis.weekend_id,
        "event": synthesis.event.model_dump(mode="json"),
        "section_order": synthesis.section_order,
        "summary_claim_ids": synthesis.summary_claim_ids,
        "claim_ids": [item.claim_id for item in synthesis.claims],
        "figure_paths": asset_paths,
        "package_hash": synthesis.package_hash,
    }
    (output_dir / "article.json").write_text(json.dumps(article_payload, indent=2, sort_keys=True), encoding="utf-8")
    (output_dir / "evidence.json").write_text(synthesis.model_dump_json(indent=2), encoding="utf-8")
    (output_dir / "weekend-plan.json").write_text(synthesis.model_dump_json(indent=2), encoding="utf-8")
    manifest = {
        "schema_version": synthesis.schema_version,
        "policy_id": synthesis.policy_id,
        "policy_version": synthesis.policy_version,
        "weekend_id": synthesis.weekend_id,
        "package_hash": synthesis.package_hash,
        "article_markdown_path": "article.md",
        "article_json_path": "article.json",
        "evidence_path": "evidence.json",
        "plan_path": "weekend-plan.json",
        "assets": asset_paths,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return output_dir


def bounded_weekend_payload(synthesis: WeekendSynthesis, *, claim_limit: int = 20) -> dict[str, Any]:
    """Return the bounded, read-only inspection contract used by the UI/API."""

    if not 1 <= claim_limit <= 100:
        raise ValueError("claim_limit must be between 1 and 100.")
    return {
        "schema_version": synthesis.schema_version,
        "weekend_id": synthesis.weekend_id,
        "event": synthesis.event.model_dump(mode="json"),
        "inventory": [item.model_dump(mode="json") for item in synthesis.inventory],
        "claims": [item.model_dump(mode="json") for item in synthesis.claims[:claim_limit]],
        "claim_count": len(synthesis.claims),
        "expectations": [item.model_dump(mode="json") for item in synthesis.expectations],
        "figures": [item.model_dump(mode="json") for item in synthesis.figures],
        "readiness": synthesis.readiness.model_dump(mode="json"),
        "evidence_fingerprint": synthesis.evidence_fingerprint,
    }


def _validate_scope(sources: list[WeekendSourceSession]) -> dict[str, WeekendSourceSession]:
    if not sources:
        raise ValueError("Standard weekend synthesis requires persisted session reports.")
    event_key = (sources[0].event.season, sources[0].event.event_id)
    if sources[0].event.format != "standard":
        raise ValueError("Sprint or ambiguous weekend formats are unsupported.")
    seen: set[SessionKind] = set()
    for source in sources:
        if (source.event.season, source.event.event_id) != event_key:
            raise ValueError("All source reports must resolve to the same event identity.")
        if source.event.format != "standard":
            raise ValueError("Sprint or ambiguous weekend formats are unsupported.")
        if source.session_kind in seen:
            raise ValueError(f"Duplicate weekend session type: {source.session_kind}")
        seen.add(source.session_kind)
    if "qualifying" not in seen or "race" not in seen or not seen.intersection({"fp1", "fp2", "fp3"}):
        raise ValueError("At least one Practice, one Qualifying, and one Race report are required.")
    return {item.session_id: item for item in sources}


def _minimum_coverage(sources: list[WeekendSourceSession]) -> bool:
    included = {item.session_kind for item in sources if item.source_status == "included"}
    return "qualifying" in included and "race" in included and bool(included & {"fp1", "fp2", "fp3"})


def _materialize_claims(
    sources: dict[str, WeekendSourceSession], candidates: list[WeekendClaimCandidate]
) -> tuple[list[WeekendClaim], list[str]]:
    claims: list[WeekendClaim] = []
    blockers: list[str] = []
    for candidate in candidates:
        source = sources.get(candidate.source_session_id)
        if source is None:
            blockers.append(f"Unknown source session: {candidate.source_session_id}")
            continue
        claim = next((item for item in [*source.content.findings, *source.content.conclusions] if item.finding_id == candidate.source_claim_id), None)
        review = next((item for item in source.reviews if item.item_id == candidate.source_claim_id), None)
        assessment_by_result = {item.result_id: item for item in source.content.assessments}
        results = {item.result_id: item for item in source.content.results}
        reason = _ineligible_reason(source, claim, review, assessment_by_result, results)
        if reason:
            blockers.append(f"{candidate.source_claim_id}: {reason}")
            continue
        assert claim is not None and review is not None
        text = review.edited_text if review.review_status == "edited" else claim.text
        if _UNSUPPORTED_CAUSALITY.search(text) and not candidate.supported_cross_session_relationship:
            blockers.append(f"{candidate.source_claim_id}: unsupported causal or evaluative wording")
            continue
        owned = [results[item] for item in claim.result_ids]
        category = min(owned, key=lambda item: _measurement_rank(item.measurement_category)).measurement_category
        quality = min((_quality_label(item) for item in owned), key=lambda item: _QUALITY_ORDER.get(item, 0))
        asset_ids = sorted({evidence.artifact_id or evidence.chart_instance_id for result in owned for evidence in result.chart_evidence if evidence.image_path})
        semantic = {
            "subject": _normalized(candidate.subject),
            "predicate": _normalized(candidate.predicate),
            "object": candidate.object_value,
            "temporal_scope": _normalized(candidate.temporal_scope),
            "comparison_basis": candidate.comparison_basis,
            "conditions": candidate.conditions,
            "result_ids": sorted(claim.result_ids),
        }
        claims.append(WeekendClaim(
            claim_id=stable_id("weekend-claim", canonical_fingerprint(semantic)),
            text=text,
            subject=candidate.subject,
            predicate=candidate.predicate,
            object_value=candidate.object_value,
            temporal_scope=candidate.temporal_scope,
            comparison_basis=candidate.comparison_basis,
            conditions=candidate.conditions,
            measurement_category=category,
            quality=quality,
            limitations=sorted(set([*claim.limitations, *(value for item in owned for value in item.limitations)])),
            source_claim_ids=[claim.finding_id],
            source_session_ids=[source.session_id],
            source_result_ids=sorted(claim.result_ids),
            source_chart_asset_ids=asset_ids,
            section=candidate.section,
            summary_eligible=candidate.summary_eligible,
        ))
    return sorted(claims, key=lambda item: (_SESSION_ORDER[sources[item.source_session_ids[0]].session_kind], item.claim_id)), blockers


def _ineligible_reason(source: WeekendSourceSession, claim: ReportFinding | None, review: ReportReviewEntry | None, assessments: dict[str, Any], results: dict[str, Any]) -> str | None:
    if source.source_status != "included" or source.report_disposition != "reportable":
        return "source session is not publishable"
    if not source.evidence_current or not source.review_current:
        return "source evidence or review is stale"
    if claim is None:
        return "source claim does not exist"
    if review is None or review.review_status not in {"accepted", "edited"} or review.reviewed_evidence_fingerprint != claim.evidence_fingerprint:
        return "source claim is not accepted against current evidence"
    if claim.confidence in {"low", "provisional", "unavailable"}:
        return "source claim quality is not publishable"
    if not claim.result_ids or any(item not in results for item in claim.result_ids):
        return "source result reference is broken"
    for result_id in claim.result_ids:
        result = results[result_id]
        assessment = assessments.get(result_id)
        if result.analytical_status in {"unavailable", "unknown", "confounded", "unsupported", "source_conflict"}:
            return f"source result is {result.analytical_status}"
        if assessment is None or assessment.report_disposition != "reportable":
            return "source result disposition is not reportable"
    return None


def _merge_and_check_claims(claims: list[WeekendClaim]) -> tuple[list[WeekendClaim], list[str]]:
    merged: dict[str, WeekendClaim] = {}
    subject_scope: dict[str, WeekendClaim] = {}
    conflicts: list[str] = []
    for claim in claims:
        duplicate_key = canonical_fingerprint({
            "subject": _normalized(claim.subject), "predicate": _normalized(claim.predicate),
            "object": claim.object_value, "scope": _normalized(claim.temporal_scope),
            "basis": claim.comparison_basis, "conditions": claim.conditions,
            "result_ids": claim.source_result_ids,
        })
        if duplicate_key in merged:
            current = merged[duplicate_key]
            merged[duplicate_key] = current.model_copy(update={
                "source_claim_ids": sorted(set(current.source_claim_ids + claim.source_claim_ids)),
                "source_session_ids": sorted(set(current.source_session_ids + claim.source_session_ids)),
                "source_result_ids": sorted(set(current.source_result_ids + claim.source_result_ids)),
                "source_chart_asset_ids": sorted(set(current.source_chart_asset_ids + claim.source_chart_asset_ids)),
                "limitations": sorted(set(current.limitations + claim.limitations)),
                "summary_eligible": current.summary_eligible or claim.summary_eligible,
            }, deep=True)
            continue
        conflict_key = canonical_fingerprint({
            "subject": _normalized(claim.subject), "predicate": _normalized(claim.predicate),
            "scope": _normalized(claim.temporal_scope), "basis": claim.comparison_basis,
            "conditions": claim.conditions,
        })
        prior = subject_scope.get(conflict_key)
        if prior is not None and prior.object_value != claim.object_value:
            conflicts.append(f"Conflicting accepted claims {prior.claim_id} and {claim.claim_id} require editorial resolution.")
        else:
            subject_scope[conflict_key] = claim
        merged[duplicate_key] = claim
    return list(merged.values()), conflicts


def _pair_expectations(sources: dict[str, WeekendSourceSession], claims: list[WeekendClaim], expectations: list[WeekendExpectation]) -> tuple[list[WeekendExpectationComparison], list[str]]:
    race = next(value for value in sources.values() if value.session_kind == "race")
    pairs: list[WeekendExpectationComparison] = []
    blockers: list[str] = []
    for expectation in expectations:
        source = sources.get(expectation.source_session_id)
        if source is None or source.session_kind not in {"fp1", "fp2", "fp3", "qualifying"} or expectation.recorded_at >= race.session_time or not expectation.reviewed:
            blockers.append(f"Expectation {expectation.expectation_id} is not eligible pre-Race reviewed framing.")
            continue
        source_claim = next((item for item in [*source.content.findings, *source.content.conclusions] if item.finding_id == expectation.source_claim_id), None)
        if source_claim is None or not set(expectation.source_result_ids) <= set(source_claim.result_ids):
            blockers.append(f"Expectation {expectation.expectation_id} has broken source provenance.")
            continue
        outcome = next((item for item in claims if item.section == "race_outcome" and _normalized(item.subject) == _normalized(expectation.subject) and item.comparison_basis == expectation.comparison_basis), None)
        if outcome is None or not isinstance(outcome.object_value, dict):
            continue
        actual = outcome.object_value
        comparable = [key for key in expectation.expected_values if key in actual]
        if not comparable:
            state: ExpectationState = "not_comparable"
        else:
            matches = sum(actual[key] == expectation.expected_values[key] for key in comparable)
            state = "aligned" if matches == len(expectation.expected_values) and len(comparable) == len(expectation.expected_values) else "partially_aligned" if matches else "not_aligned"
        pairs.append(WeekendExpectationComparison(
            comparison_id=stable_id("expectation-comparison", expectation.expectation_id, outcome.claim_id),
            expectation_id=expectation.expectation_id,
            outcome_claim_id=outcome.claim_id,
            state=state,
            source_session_ids=sorted({expectation.source_session_id, *outcome.source_session_ids}),
            source_result_ids=sorted(set(expectation.source_result_ids + outcome.source_result_ids)),
        ))
    return pairs, blockers


def _select_figures(sources: dict[str, WeekendSourceSession], claims: list[WeekendClaim]) -> list[WeekendFigure]:
    figures: list[WeekendFigure] = []
    used_results: set[str] = set()
    used_assets: set[str] = set()
    for claim in claims:
        source = sources[claim.source_session_ids[0]]
        results = {item.result_id: item for item in source.content.results}
        for result_id in claim.source_result_ids:
            result = results.get(result_id)
            if result is None or result_id in used_results:
                continue
            evidence = next((item for item in sorted(result.chart_evidence, key=lambda value: value.chart_instance_id) if item.image_path and item.metadata_path and (item.artifact_id or item.chart_instance_id) not in used_assets), None)
            if evidence is None:
                continue
            asset_id = evidence.artifact_id or evidence.chart_instance_id
            figure_id = stable_id("weekend-figure", source.session_id, asset_id)
            session_label = source.session_kind.upper()
            figures.append(WeekendFigure(
                figure_id=figure_id,
                source_session_id=source.session_id,
                source_claim_ids=claim.source_claim_ids,
                source_result_ids=[result_id],
                source_chart_asset_id=asset_id,
                source_image_path=str(evidence.image_path),
                source_metadata_path=str(evidence.metadata_path),
                section=claim.section,
                caption=f"{session_label} visual evidence for claim [{claim.claim_id}].",
                alt_text=f"{session_label} chart supporting claim [{claim.claim_id}], with plotted marks and labelled axes.",
            ))
            used_results.add(result_id)
            used_assets.add(asset_id)
            break
        if len(figures) == 5:
            break
    return figures


def _measurement_rank(value: MeasurementCategory) -> int:
    return {"estimated": 0, "descriptive": 1, "derived": 2, "measured": 3}[value]


def _quality_label(result: Any) -> str:
    value = str(result.quality.get("level") or "medium").lower()
    return value if value in _QUALITY_ORDER else "medium"


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def _safe_text(value: str) -> str:
    return value.replace("[", "(").replace("]", ")").replace("\n", " ").strip()


def _contained_source(root: Path, relative: str) -> Path:
    value = Path(relative)
    if value.is_absolute():
        raise ValueError(f"Expected a package-relative source asset: {relative}")
    resolved = (root / value).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Source asset escapes its package: {relative}") from exc
    if not resolved.is_file():
        raise ValueError(f"Source asset is missing: {relative}")
    return resolved

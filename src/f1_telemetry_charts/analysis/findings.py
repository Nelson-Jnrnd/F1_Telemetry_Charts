"""Deterministic, analytical-result-owned report content.

This module deliberately has no renderer or workspace dependencies.  Charts are
optional evidence references; the serialized analytical result is the semantic
input to finding providers and synthesis rules.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


REPORT_CONTENT_SCHEMA_VERSION = 1
REPORT_TEMPLATE_VERSION = 1
PUBLICATION_PLAN_SCHEMA_VERSION = 1
PUBLICATION_SELECTION_POLICY_ID = "race-publication-selection"
PUBLICATION_SELECTION_POLICY_VERSION = 2

ReportDisposition = Literal[
    "reportable", "context_only", "not_reportable", "unsupported", "unavailable"
]
Confidence = Literal["high", "medium", "low", "provisional", "unavailable"]
FindingKind = Literal["finding", "conclusion"]
ReportSectionKind = Literal[
    "executive_summary",
    "strategy_and_race_evolution",
    "pace_and_tyre_performance",
    "pit_cycles_and_key_comparisons",
    "limitations_and_evidence",
]
ReportReviewStatus = Literal["pending", "accepted", "edited", "rejected"]
FreshnessStatus = Literal["current", "stale", "missing"]
OperationalReportStatus = Literal[
    "report_current", "review_required", "evidence_changed", "regenerate_draft"
]
MeasurementCategory = Literal["measured", "derived", "descriptive", "estimated"]
PublicationSectionKind = Literal[
    "headline",
    "standfirst",
    "at_a_glance",
    "how_the_race_developed",
    "pace_and_strategy",
    "key_comparison",
    "conclusion",
    "methods_and_evidence",
]
PublicationWorkflowState = Literal[
    "evidence_ready",
    "editorial_work_required",
    "review_required",
    "publication_draft_ready",
    "export_current",
]


def canonical_fingerprint(value: Any) -> str:
    """Hash JSON-compatible semantic content with stable key and number output."""

    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def stable_id(prefix: str, *parts: str) -> str:
    return f"{prefix}-{canonical_fingerprint(list(parts))[:20]}"


class ChartEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chart_instance_id: str
    artifact_id: str | None = None
    title: str | None = None
    image_path: str | None = None
    metadata_path: str | None = None


class AnalyticalResultRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = REPORT_CONTENT_SCHEMA_VERSION
    result_id: str
    result_type: str
    result_schema_version: int
    target_session_id: str
    result_fingerprint: str
    analytical_status: str
    value_category: str | None = None
    measurement_category: MeasurementCategory = "derived"
    subjects: list[str] = Field(default_factory=list)
    boundaries: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    coverage: dict[str, Any] = Field(default_factory=dict)
    quality: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any]
    analytical_basis: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    chart_evidence: list[ChartEvidence] = Field(default_factory=list)


class ReportFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = REPORT_CONTENT_SCHEMA_VERSION
    finding_id: str
    finding_kind: FindingKind = "finding"
    finding_type: str
    evidence_fingerprint: str
    text: str
    section: ReportSectionKind
    priority: int = Field(default=50, ge=0, le=100)
    confidence: Confidence
    result_fingerprints: list[str]
    result_ids: list[str]
    provider_id: str | None = None
    provider_version: int | None = None
    synthesis_rule_id: str | None = None
    comparison_basis: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    evidence: list[ChartEvidence] = Field(default_factory=list)
    supporting_finding_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_owner(self) -> "ReportFinding":
        if self.finding_kind == "finding" and not self.provider_id:
            raise ValueError("A result finding requires a provider ID")
        if self.finding_kind == "conclusion" and not self.synthesis_rule_id:
            raise ValueError("A conclusion requires a synthesis rule ID")
        return self


class ResultReportAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = REPORT_CONTENT_SCHEMA_VERSION
    assessment_id: str
    result_id: str
    result_fingerprint: str
    result_type: str
    provider_id: str
    provider_version: int
    report_disposition: ReportDisposition
    reason_code: str = "unspecified"
    reasons: list[str]
    next_action: str | None = None
    technical_details: dict[str, Any] = Field(default_factory=dict)
    finding_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_finding_accounting(self) -> "ResultReportAssessment":
        if self.report_disposition == "reportable" and not self.finding_ids:
            raise ValueError("A reportable assessment requires at least one finding")
        if self.report_disposition != "reportable" and self.finding_ids:
            raise ValueError("Only a reportable assessment may reference findings")
        return self


class FindingProviderDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str
    provider_version: int
    result_types: list[str]
    criteria: dict[str, Any]


class ReportPlanItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    item_type: Literal["claim", "chart", "assessment"]
    reference_id: str
    included: bool = True


class ReportPlanSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: ReportSectionKind
    title: str
    included: bool = True
    items: list[ReportPlanItem] = Field(default_factory=list)


class ReportPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = REPORT_CONTENT_SCHEMA_VERSION
    template_version: int = REPORT_TEMPLATE_VERSION
    target_session_id: str
    sections: list[ReportPlanSection]


class EditorialField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str = ""
    provenance: Literal["human"] = "human"
    dependency_fingerprints: list[str] = Field(default_factory=list)
    review_required: bool = False


class PublicationClaimPlacement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: str
    section: PublicationSectionKind
    included: bool = True
    selection_mode: Literal["automatic", "explicit"] = "automatic"
    summary_reference: str | None = None


class PublicationChartPlacement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chart_instance_id: str
    section: PublicationSectionKind
    purpose: str
    finding_ids: list[str] = Field(default_factory=list)
    result_ids: list[str] = Field(default_factory=list)
    caption: EditorialField = Field(default_factory=EditorialField)
    alt_text: EditorialField = Field(default_factory=EditorialField)
    included: bool = True
    selection_mode: Literal["automatic", "explicit"] = "automatic"


class PublicationEditorial(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headline: EditorialField = Field(default_factory=EditorialField)
    standfirst: EditorialField = Field(default_factory=EditorialField)
    section_ledes: dict[str, EditorialField] = Field(default_factory=dict)
    conclusion: EditorialField = Field(default_factory=EditorialField)


class PublicationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = PUBLICATION_PLAN_SCHEMA_VERSION
    policy_id: str = PUBLICATION_SELECTION_POLICY_ID
    policy_version: int = PUBLICATION_SELECTION_POLICY_VERSION
    target_session_id: str
    section_order: list[PublicationSectionKind]
    claims: list[PublicationClaimPlacement] = Field(default_factory=list)
    charts: list[PublicationChartPlacement] = Field(default_factory=list)


class PublicationReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ready: bool = False
    state: PublicationWorkflowState = "evidence_ready"
    next_action: str = "Add headline and standfirst"
    blockers: list[str] = Field(default_factory=list)
    checks: dict[str, bool] = Field(default_factory=dict)
    package_integrity: Literal["valid", "invalid", "unchecked"] = "unchecked"


class ReportReviewEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    reviewed_evidence_fingerprint: str
    review_status: ReportReviewStatus = "pending"
    edited_text: str | None = None

    @model_validator(mode="after")
    def edited_requires_text(self) -> "ReportReviewEntry":
        if self.review_status == "edited" and not (self.edited_text or "").strip():
            raise ValueError("Edited review entries require edited text")
        if self.review_status != "edited" and self.edited_text is not None:
            raise ValueError("Only edited review entries may carry edited text")
        return self


class FreshnessLayer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: FreshnessStatus = "missing"
    input_fingerprint: str | None = None


class ReportFreshness(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence: FreshnessLayer = Field(default_factory=FreshnessLayer)
    review: FreshnessLayer = Field(default_factory=FreshnessLayer)
    selection: FreshnessLayer = Field(default_factory=FreshnessLayer)
    editorial: FreshnessLayer = Field(default_factory=FreshnessLayer)
    publication: FreshnessLayer = Field(default_factory=FreshnessLayer)
    draft: FreshnessLayer = Field(default_factory=FreshnessLayer)
    export: FreshnessLayer = Field(default_factory=FreshnessLayer)

    @property
    def operational_status(self) -> OperationalReportStatus:
        if self.evidence.status != "current":
            return "evidence_changed"
        if self.review.status != "current":
            return "review_required"
        if self.draft.status != "current":
            return "regenerate_draft"
        return "report_current"

    @property
    def next_action(self) -> str:
        return {
            "evidence_changed": "Refresh report evidence",
            "review_required": "Review included claims",
            "regenerate_draft": "Regenerate report draft",
            "report_current": "Export current report",
        }[self.operational_status]


class ReportContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = REPORT_CONTENT_SCHEMA_VERSION
    target_session_id: str
    results: list[AnalyticalResultRecord]
    assessments: list[ResultReportAssessment]
    findings: list[ReportFinding]
    conclusions: list[ReportFinding]
    plan: ReportPlan
    evidence_fingerprint: str
    publication_plan: PublicationPlan | None = None
    publication_editorial: PublicationEditorial = Field(default_factory=PublicationEditorial)
    publication_readiness: PublicationReadiness = Field(default_factory=PublicationReadiness)


class ResultSource(BaseModel):
    """Transport record used to materialize one semantic result from metadata."""

    model_config = ConfigDict(extra="forbid")

    target_session_id: str
    chart_instance_id: str
    artifact_id: str | None = None
    title: str | None = None
    image_path: str | None = None
    metadata_path: str | None = None
    metadata: dict[str, Any]


def materialize_results(sources: Iterable[ResultSource]) -> list[AnalyticalResultRecord]:
    """Materialize and deduplicate semantic results, aggregating chart evidence."""

    records: dict[str, AnalyticalResultRecord] = {}
    for source in sources:
        metadata = source.metadata
        result_type = str(metadata.get("result_kind") or "")
        raw_result = metadata.get("analytical_results")
        if not result_type or not isinstance(raw_result, dict):
            continue
        # Driver Battle is a composite presentation. Its reportable semantic
        # result is the same typed direct-gap result that may also be rendered
        # by Race-Time Delta; materialize that nested result so both charts
        # deduplicate and become evidence for one finding.
        if result_type == "driver_battle" and isinstance(
            raw_result.get("gap_result"), dict
        ):
            raw_result = raw_result["gap_result"]
            result_type = str(raw_result.get("result_kind") or "measured_gap_change")
        result_schema_version = int(metadata.get("strategy_analysis_schema_version", 1))
        semantic_payload = _semantic_payload(result_type, raw_result)
        semantic = {
            "result_type": result_type,
            "result_schema_version": result_schema_version,
            "target_session_id": source.target_session_id,
            "payload": semantic_payload,
            "analytical_basis": metadata.get("analytical_basis") or {},
            "warnings": metadata.get("strategy_warnings") or [],
            "limitations": metadata.get("strategy_limitations") or [],
        }
        fingerprint = canonical_fingerprint(semantic)
        evidence = ChartEvidence(
            chart_instance_id=source.chart_instance_id,
            artifact_id=source.artifact_id,
            title=source.title,
            image_path=source.image_path,
            metadata_path=source.metadata_path,
        )
        if fingerprint in records:
            current = records[fingerprint]
            if evidence not in current.chart_evidence:
                current.chart_evidence.append(evidence)
                current.chart_evidence.sort(key=lambda item: item.chart_instance_id)
            continue
        status = str(raw_result.get("status") or _nested_status(raw_result) or "available")
        value_category = raw_result.get("value_category")
        records[fingerprint] = AnalyticalResultRecord(
            result_id=stable_id("result", fingerprint),
            result_type=result_type,
            result_schema_version=result_schema_version,
            target_session_id=source.target_session_id,
            result_fingerprint=fingerprint,
            analytical_status=status,
            value_category=str(value_category) if value_category else None,
            payload=semantic_payload,
            analytical_basis=dict(semantic["analytical_basis"]),
            warnings=[str(value) for value in semantic["warnings"]],
            limitations=[str(value) for value in semantic["limitations"]],
            chart_evidence=[evidence],
        )
    return sorted(records.values(), key=lambda item: item.result_fingerprint)


def _nested_status(payload: Mapping[str, Any]) -> str | None:
    for key in ("gap_result", "pace_evolution"):
        nested = payload.get(key)
        if isinstance(nested, Mapping) and nested.get("status"):
            return str(nested["status"])
    return None


def _semantic_payload(result_type: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Remove known renderer/template transport fields from analytical identity."""

    presentation_only = {
        "stable_recipe_id",
        "template_version",
        "presentation_mode",
        "panel_contract",
        "compound_styles",
    }
    return {
        str(key): value
        for key, value in payload.items()
        if key not in presentation_only
    }


Provider = Callable[[AnalyticalResultRecord], tuple[ResultReportAssessment, list[ReportFinding]]]
_PROVIDERS: dict[str, Provider] = {}
_DESCRIPTORS: dict[str, FindingProviderDescriptor] = {}


def _register(descriptor: FindingProviderDescriptor, provider: Provider) -> None:
    for result_type in descriptor.result_types:
        _PROVIDERS[result_type] = provider
    _DESCRIPTORS[descriptor.provider_id] = descriptor


def register_finding_provider(
    descriptor: FindingProviderDescriptor,
    provider: Provider,
    *,
    replace: bool = False,
) -> None:
    """Register an opt-in result provider without coupling it to a chart recipe."""

    collisions = sorted(set(descriptor.result_types) & set(_PROVIDERS))
    if collisions and not replace:
        raise ValueError(
            "Finding providers are already registered for: " + ", ".join(collisions)
        )
    _register(descriptor, provider)


def provider_descriptors() -> list[FindingProviderDescriptor]:
    return [value.model_copy(deep=True) for _, value in sorted(_DESCRIPTORS.items())]


def assess_results(
    results: Iterable[AnalyticalResultRecord],
) -> tuple[list[ResultReportAssessment], list[ReportFinding]]:
    assessments: list[ResultReportAssessment] = []
    findings: list[ReportFinding] = []
    for result in sorted(results, key=lambda item: item.result_fingerprint):
        if result.result_schema_version != 1:
            assessments.append(
                _assessment(
                    result,
                    provider_id="unsupported-result-version",
                    provider_version=1,
                    disposition="unsupported",
                    reasons=[
                        f"Analytical result schema version {result.result_schema_version} is unsupported."
                    ],
                )
            )
            continue
        provider = _PROVIDERS.get(result.result_type)
        if provider is None:
            assessment = _assessment(
                result,
                provider_id="unsupported-result-provider",
                provider_version=1,
                disposition="unsupported",
                reasons=[f"No finding provider is registered for {result.result_type}."],
            )
            produced: list[ReportFinding] = []
        else:
            try:
                assessment, produced = provider(result)
            except (KeyError, TypeError, ValueError) as error:
                assessment = _assessment(
                    result,
                    provider_id=getattr(provider, "__name__", "result-provider"),
                    provider_version=1,
                    disposition="unsupported",
                    reasons=[f"The typed result could not be interpreted: {error}"],
                )
                produced = []
        assessments.append(assessment)
        findings.extend(produced)
    return assessments, findings


def _assessment(
    result: AnalyticalResultRecord,
    *,
    provider_id: str,
    provider_version: int,
    disposition: ReportDisposition,
    reasons: list[str],
    reason_code: str | None = None,
    next_action: str | None = None,
    technical_details: dict[str, Any] | None = None,
    findings: Iterable[ReportFinding] = (),
) -> ResultReportAssessment:
    finding_ids = [finding.finding_id for finding in findings]
    return ResultReportAssessment(
        assessment_id=stable_id(
            "assessment", result.result_fingerprint, provider_id, str(provider_version)
        ),
        result_id=result.result_id,
        result_fingerprint=result.result_fingerprint,
        result_type=result.result_type,
        provider_id=provider_id,
        provider_version=provider_version,
        report_disposition=disposition,
        reason_code=reason_code or disposition,
        reasons=reasons,
        next_action=next_action,
        technical_details=technical_details or {},
        finding_ids=finding_ids,
    )


def _finding(
    result: AnalyticalResultRecord,
    *,
    provider_id: str,
    provider_version: int,
    finding_type: str,
    text: str,
    section: ReportSectionKind,
    confidence: Confidence,
    comparison_basis: dict[str, Any],
    metrics: dict[str, Any],
    limitations: Iterable[str] = (),
    priority: int = 50,
    identity_scope: str = "",
) -> ReportFinding:
    finding_id = stable_id(
        "finding",
        result.result_fingerprint,
        finding_type,
        identity_scope,
        str(provider_version),
    )
    support = {
        "result_fingerprint": result.result_fingerprint,
        "finding_type": finding_type,
        "provider_id": provider_id,
        "provider_version": provider_version,
        "comparison_basis": comparison_basis,
        "metrics": metrics,
        "limitations": list(limitations),
    }
    return ReportFinding(
        finding_id=finding_id,
        finding_type=finding_type,
        evidence_fingerprint=canonical_fingerprint(support),
        text=text,
        section=section,
        priority=priority,
        confidence=confidence,
        result_fingerprints=[result.result_fingerprint],
        result_ids=[result.result_id],
        provider_id=provider_id,
        provider_version=provider_version,
        comparison_basis=comparison_basis,
        metrics=metrics,
        limitations=list(dict.fromkeys(limitations)),
        evidence=result.chart_evidence,
    )


def _unavailable(result: AnalyticalResultRecord, provider_id: str, version: int):
    return _assessment(
        result,
        provider_id=provider_id,
        provider_version=version,
        disposition="unavailable",
        reasons=["The analytical result is unavailable; no claim was generated."],
    ), []


def _timeline_provider(result: AnalyticalResultRecord):
    provider_id, version = "strategy-timeline-provider", 1
    if result.payload.get("status") == "unavailable":
        return _unavailable(result, provider_id, version)
    return _assessment(
        result,
        provider_id=provider_id,
        provider_version=version,
        disposition="context_only",
        reasons=["The timeline supplies strategy context but does not by itself support a material claim."],
    ), []


def _stint_pace_provider(result: AnalyticalResultRecord):
    provider_id, version = "representative-pace-provider", 1
    summary = result.payload.get("comparison_summary") or {}
    stints = summary.get("stints") or []
    delta = summary.get("median_delta_seconds")
    if len(stints) != 2 or delta is None:
        disposition: ReportDisposition = "context_only" if stints else "unavailable"
        return _assessment(
            result,
            provider_id=provider_id,
            provider_version=version,
            disposition=disposition,
            reasons=["A reportable representative-pace claim requires exactly two comparable stints."],
        ), []
    sample_counts = [
        int(
            item.get("representative_lap_count")
            or item.get("sample_count")
            or item.get("n")
            or 0
        )
        for item in stints
    ]
    if min(sample_counts) < 3:
        return _assessment(
            result,
            provider_id=provider_id,
            provider_version=version,
            disposition="not_reportable",
            reasons=["At least three representative laps are required for each compared stint."],
        ), []
    delta = float(delta)
    if abs(delta) < 0.10:
        return _assessment(
            result,
            provider_id=provider_id,
            provider_version=version,
            disposition="not_reportable",
            reasons=["The absolute representative median difference is below the 0.10 s/lap reportability threshold."],
        ), []
    first = str(stints[0].get("label") or stints[0].get("driver") or "First stint")
    second = str(stints[1].get("label") or stints[1].get("driver") or "Second stint")
    faster, slower = (first, second) if delta < 0 else (second, first)
    faster_index, slower_index = (0, 1) if delta < 0 else (1, 0)
    same_stint_number = stints[0].get("stint") == stints[1].get("stint")
    if (
        stints[0].get("driver")
        and stints[1].get("driver")
        and same_stint_number
        and stints[0].get("stint") is not None
    ):
        pace_text = (
            f"{stints[faster_index]['driver']}'s stint {stints[faster_index]['stint']} "
            f"representative median was {abs(delta):.3f} s/lap lower than "
            f"{stints[slower_index]['driver']}'s ({sample_counts[faster_index]} versus "
            f"{sample_counts[slower_index]} representative laps)."
        )
    else:
        pace_text = (
            f"{faster} recorded a {abs(delta):.3f} s/lap lower representative "
            f"median than {slower} on the compared basis."
        )
    intervals = [
        {
            "driver": item.get("driver"),
            "stint": item.get("stint") or item.get("effective_stint"),
            "start_lap": item.get("start_lap"),
            "end_lap": item.get("end_lap"),
        }
        for item in (result.payload.get("stints") or stints)
    ]
    shared_start = {item["start_lap"] for item in intervals}
    shared_end = {item["end_lap"] for item in intervals}
    finding = _finding(
        result,
        provider_id=provider_id,
        provider_version=version,
        finding_type="representative_pace_advantage",
        text=pace_text,
        section="pace_and_tyre_performance",
        confidence="medium",
        comparison_basis={
            "session_id": result.target_session_id,
            "subjects": list(
                dict.fromkeys(
                    str(item.get("driver") or item.get("label")) for item in stints
                )
            ),
            "metric": result.payload.get("metric"),
            "x_axis_basis": result.payload.get("x_axis_basis"),
            "sign_convention": summary.get("median_delta_sign_convention"),
            "intervals": intervals,
            "start_lap": next(iter(shared_start)) if len(shared_start) == 1 else None,
            "end_lap": next(iter(shared_end)) if len(shared_end) == 1 else None,
        },
        metrics={"median_delta_seconds": delta, "sample_counts": sample_counts},
        limitations=["This is a descriptive comparison of representative observed laps."],
        priority=80,
    )
    return _assessment(
        result,
        provider_id=provider_id,
        provider_version=version,
        disposition="reportable",
        reasons=["The comparison meets availability, sample, and 0.10 s/lap materiality criteria."],
        findings=[finding],
    ), [finding]


def _pace_evolution_provider(result: AnalyticalResultRecord):
    provider_id, version = "observed-pace-evolution-provider", 1
    findings: list[ReportFinding] = []
    for stint in result.payload.get("stints") or []:
        fit = stint.get("pace_evolution") or {}
        if fit.get("status") != "available" or fit.get("slope") is None:
            continue
        slope = float(fit["slope"])
        if fit.get("quality") not in {"high", "medium"} or int(fit.get("sample_count") or 0) < 5:
            continue
        if abs(slope) < 0.01:
            continue
        driver = str(stint.get("driver") or "Driver")
        stint_number = int(stint.get("effective_stint") or 0)
        direction = "increased" if slope > 0 else "decreased"
        findings.append(
            _finding(
                result,
                provider_id=provider_id,
                provider_version=version,
                finding_type="observed_pace_evolution",
                text=f"{driver}'s observed representative lap time {direction} by {abs(slope):.3f} seconds per {str(fit.get('basis', 'stint-progress')).replace('_', '-')} lap during stint {stint_number}.",
                section="pace_and_tyre_performance",
                confidence="high" if fit.get("quality") == "high" else "medium",
                comparison_basis={
                    "session_id": result.target_session_id,
                    "driver": driver,
                    "stint": stint_number,
                    "start_lap": stint.get("start_lap"),
                    "end_lap": stint.get("end_lap"),
                    "basis": fit.get("basis"),
                    "method_id": fit.get("method_id"),
                },
                metrics={"slope": slope, "units": fit.get("units"), "sample_count": fit.get("sample_count")},
                limitations=fit.get("limitations") or [],
                priority=65,
                identity_scope=f"{driver}:S{stint_number}",
            )
        )
    if findings:
        return _assessment(
            result,
            provider_id=provider_id,
            provider_version=version,
            disposition="reportable",
            reasons=["At least one stint meets the quality, five-sample, and 0.01 s/lap slope criteria."],
            findings=findings,
        ), findings
    available = any(
        (stint.get("pace_evolution") or {}).get("status") == "available"
        for stint in result.payload.get("stints") or []
    )
    return _assessment(
        result,
        provider_id=provider_id,
        provider_version=version,
        disposition="not_reportable" if available else "unavailable",
        reasons=["No stint met the explicit quality, sample, and slope reportability criteria."],
    ), []


def _compound_provider(result: AnalyticalResultRecord):
    provider_id, version = "compound-comparison-provider", 1
    payload = result.payload
    if payload.get("status") == "unavailable":
        compounds = [str(value) for value in payload.get("compounds") or []]
        samples = payload.get("sample_counts") or {}
        represented = {
            compound: [key for key, count in samples.items() if key.endswith(f":{compound}") and count]
            for compound in compounds
        }
        reason_code = (
            "compound_stint_ambiguous"
            if any(len(values) > 1 for values in represented.values())
            else "compound_samples_not_comparable"
        )
        return _assessment(
            result,
            provider_id=provider_id,
            provider_version=version,
            disposition="unavailable",
            reason_code=reason_code,
            reasons=[
                "The selected compounds did not produce one eligible, adequately sampled stint per compound on the configured comparison basis."
            ],
            next_action=(
                "Select two compounds with one adequately sampled stint each for the driver, "
                "or narrow the lap or tyre-age interval to remove ambiguous samples."
            ),
            technical_details={
                "compounds": compounds,
                "sample_counts": samples,
                "control_rule": payload.get("control_rule"),
                "minimum_samples_per_compound": 5,
            },
        ), []
    if result.result_type == "unrestricted_descriptive_distribution":
        return _assessment(
            result,
            provider_id=provider_id,
            provider_version=version,
            disposition="context_only",
            reasons=["An unrestricted compound distribution supplies context but does not support a scalar comparison."],
        ), []
    delta = payload.get("scalar_difference_seconds")
    if delta is None or len(payload.get("compounds") or []) != 2:
        return _assessment(
            result,
            provider_id=provider_id,
            provider_version=version,
            disposition="not_reportable",
            reasons=["A controlled two-compound scalar difference is required."],
        ), []
    delta = float(delta)
    if abs(delta) < 0.10:
        return _assessment(
            result,
            provider_id=provider_id,
            provider_version=version,
            disposition="not_reportable",
            reasons=["The controlled compound difference is below the 0.10 s/lap reportability threshold."],
        ), []
    compounds = [str(value) for value in payload["compounds"]]
    finding = _finding(
        result,
        provider_id=provider_id,
        provider_version=version,
        finding_type="compound_comparison",
        text=f"The controlled observed comparison measured a {abs(delta):.3f} s/lap difference between {compounds[0]} and {compounds[1]} samples.",
        section="pace_and_tyre_performance",
        confidence="medium" if payload.get("status") == "available" else "low",
        comparison_basis={
            "session_id": result.target_session_id,
            "participants": payload.get("participants"),
            "compounds": compounds,
            "interval": payload.get("interval"),
            "control_rule": payload.get("control_rule"),
            "weighting": payload.get("weighting"),
        },
        metrics={"scalar_difference_seconds": delta, "sample_counts": payload.get("sample_counts")},
        limitations=payload.get("limitations") or [],
        priority=60,
    )
    return _assessment(
        result,
        provider_id=provider_id,
        provider_version=version,
        disposition="reportable",
        reasons=["A controlled two-compound result exceeds the explicit materiality threshold."],
        findings=[finding],
    ), [finding]


def _gap_provider(result: AnalyticalResultRecord):
    provider_id, version = "race-time-delta-provider", 1
    payload = result.payload
    if payload.get("status") == "unavailable":
        return _unavailable(result, provider_id, version)
    change = payload.get("overall_change_seconds")
    if change is None or int(payload.get("paired_sample_count") or 0) < 2:
        return _assessment(
            result,
            provider_id=provider_id,
            provider_version=version,
            disposition="not_reportable",
            reasons=["At least two paired samples and a measured overall change are required."],
        ), []
    change = float(change)
    focal = str(payload.get("focal_driver") or "Focal driver")
    benchmark = str(payload.get("benchmark") or "benchmark")
    direction = "lost" if change > 0 else "gained"
    start_lap = payload.get("start_lap")
    end_lap = payload.get("end_lap")
    interval_text = (
        f"between laps {start_lap} and {end_lap}"
        if start_lap is not None and end_lap is not None
        else "across the observed interval"
    )
    if result.result_type == "derived_cumulative_pace_delta":
        finding_text = (
            f"Across the representative-lap comparison, {focal} accumulated an "
            f"{abs(change):.3f}-second pace advantage over {benchmark} {interval_text}; "
            "this is a derived pace total, not the elapsed race gap."
        )
    else:
        finding_text = (
            f"{focal} {direction} {abs(change):.3f} seconds relative to "
            f"{benchmark} {interval_text}."
        )
    finding = _finding(
        result,
        provider_id=provider_id,
        provider_version=version,
        finding_type="direct_gap_change" if result.result_type == "measured_gap_change" else "cumulative_pace_delta",
        text=finding_text,
        section="strategy_and_race_evolution",
        confidence="high" if payload.get("status") == "available" else "low",
        comparison_basis={
            "session_id": result.target_session_id,
            "focal_driver": focal,
            "benchmark": benchmark,
            "start_lap": payload.get("start_lap"),
            "end_lap": payload.get("end_lap"),
            "value_category": payload.get("value_category"),
            "sign_convention": payload.get("sign_convention"),
        },
        metrics={"overall_change_seconds": change, "paired_sample_count": payload.get("paired_sample_count")},
        limitations=payload.get("limitations") or [],
        priority=75,
    )
    return _assessment(
        result,
        provider_id=provider_id,
        provider_version=version,
        disposition="reportable",
        reasons=["The result contains a supported interval change with at least two paired samples."],
        findings=[finding],
    ), [finding]


def _pit_cycle_provider(result: AnalyticalResultRecord):
    provider_id, version = "pit-cycle-provider", 1
    payload = result.payload
    if payload.get("status") == "unavailable":
        return _unavailable(result, provider_id, version)
    change = payload.get("measured_gap_change_seconds")
    if change is None:
        return _assessment(
            result,
            provider_id=provider_id,
            provider_version=version,
            disposition="not_reportable",
            reasons=["A measured pre-to-post direct-gap change is required."],
        ), []
    change = float(change)
    focal = str(payload.get("focal_driver") or "Focal driver")
    rival = str(payload.get("rival_driver") or "rival")
    direction = "lost" if change > 0 else "gained"
    pre_lap = payload.get("pre_reference_lap")
    post_lap = payload.get("post_reference_lap")
    qualifications = [str(value) for value in payload.get("limitations") or []]
    qualifications.extend(
        str(value)
        for value in payload.get("warnings") or []
        if not (
            payload.get("rival_stopped_in_window")
            and "rival stopped" in str(value).lower()
        )
    )
    if payload.get("rival_stopped_in_window"):
        qualifications.append(
            f"{rival} also stopped within the comparison window, so the measured change is confounded by both pit cycles."
        )
    if payload.get("neutralized_in_window"):
        qualifications.append(
            "The comparison window included a neutralized race period."
        )
    finding = _finding(
        result,
        provider_id=provider_id,
        provider_version=version,
        finding_type="measured_pit_cycle_change",
        text=(
            f"Between the pre-stop reference at lap {pre_lap} and the post-stop "
            f"reference at lap {post_lap}, {focal} {direction} {abs(change):.3f} "
            f"seconds relative to {rival}."
        ),
        section="pit_cycles_and_key_comparisons",
        confidence=(
            "medium"
            if payload.get("pit_interval_precision") == "exact"
            and payload.get("status") == "available"
            and not payload.get("rival_stopped_in_window")
            and not payload.get("neutralized_in_window")
            else "low"
        ),
        comparison_basis={
            "session_id": result.target_session_id,
            "focal_driver": focal,
            "benchmark": rival,
            "start_lap": payload.get("pre_reference_lap"),
            "end_lap": payload.get("post_reference_lap"),
            "pit_in_lap": payload.get("pit_in_lap"),
            "pit_out_lap": payload.get("pit_out_lap"),
        },
        metrics={"measured_gap_change_seconds": change, "pit_lane_duration_seconds": payload.get("pit_lane_duration_seconds")},
        limitations=[
            *qualifications,
            "The measured change does not establish strategic intent or undercut/overcut causality.",
        ],
        priority=85,
    )
    return _assessment(
        result,
        provider_id=provider_id,
        provider_version=version,
        disposition="reportable",
        reasons=["The result includes an observed pre-to-post pit-cycle gap change."],
        findings=[finding],
    ), [finding]


def _driver_battle_provider(result: AnalyticalResultRecord):
    provider_id, version = "driver-battle-provider", 1
    gap = result.payload.get("gap_result") or {}
    proxy = result.model_copy(
        update={
            "result_type": "measured_gap_change",
            "analytical_status": str(gap.get("status") or "unavailable"),
            "payload": gap,
        },
        deep=True,
    )
    assessment, findings = _gap_provider(proxy)
    converted: list[ReportFinding] = []
    for finding in findings:
        converted.append(
            finding.model_copy(
                update={
                    "finding_id": stable_id("finding", result.result_fingerprint, "driver_battle_outcome", str(version)),
                    "finding_type": "driver_battle_outcome",
                    "result_fingerprints": [result.result_fingerprint],
                    "result_ids": [result.result_id],
                    "provider_id": provider_id,
                    "evidence": result.chart_evidence,
                },
                deep=True,
            )
        )
    if converted:
        converted[0].evidence_fingerprint = canonical_fingerprint(
            {"result": result.result_fingerprint, "provider": provider_id, "version": version, "metrics": converted[0].metrics}
        )
        return _assessment(
            result,
            provider_id=provider_id,
            provider_version=version,
            disposition="reportable",
            reasons=["The battle contains a supported direct-gap interval result."],
            findings=converted,
        ), converted
    return _assessment(
        result,
        provider_id=provider_id,
        provider_version=version,
        disposition=assessment.report_disposition,
        reasons=assessment.reasons,
    ), []


def _session_spine_provider(result: AnalyticalResultRecord):
    """Turn typed race chronology into governed, non-causal findings."""

    provider_id, version = "race-session-spine-provider", 1
    if result.analytical_status == "unavailable":
        return _unavailable(result, provider_id, version)
    summaries = {
        "race_classification": result.payload.get("summary"),
        "grid_to_finish_movement": result.payload.get("summary"),
        "pit_stop_sequence": result.payload.get("summary"),
        "neutralisation_periods": result.payload.get("summary"),
        "retirement_status": result.payload.get("summary"),
        "position_change_interval": result.payload.get("summary"),
    }
    text = summaries.get(result.result_type)
    if not isinstance(text, str) or not text.strip():
        return _assessment(
            result,
            provider_id=provider_id,
            provider_version=version,
            disposition="context_only",
            reasons=["The typed chronology is retained as context without a prose claim."],
        ), []
    confidence: Confidence = "high" if result.quality.get("level") == "high" else "medium"
    finding = _finding(
        result,
        provider_id=provider_id,
        provider_version=version,
        finding_type=result.result_type,
        text=text.strip(),
        section="strategy_and_race_evolution",
        confidence=confidence,
        comparison_basis={
            "session_id": result.target_session_id,
            "subjects": result.subjects,
            **result.boundaries,
        },
        metrics={},
        limitations=result.limitations,
        priority={
            "race_classification": 100,
            "grid_to_finish_movement": 88,
            "pit_stop_sequence": 82,
            "neutralisation_periods": 76,
            "retirement_status": 72,
            "position_change_interval": 68,
        }.get(result.result_type, 60),
    )
    return _assessment(
        result,
        provider_id=provider_id,
        provider_version=version,
        disposition="reportable",
        reasons=["The typed result supports a provenance-qualified race-chronology claim."],
        findings=[finding],
    ), [finding]


_register(
    FindingProviderDescriptor(
        provider_id="strategy-timeline-provider",
        provider_version=1,
        result_types=["strategy_timeline"],
        criteria={"available": "context_only", "unavailable": "unavailable"},
    ),
    _timeline_provider,
)
_register(
    FindingProviderDescriptor(
        provider_id="representative-pace-provider",
        provider_version=1,
        result_types=["stint_pace"],
        criteria={"comparison_stints": 2, "minimum_samples_per_stint": 3, "absolute_median_delta_seconds": 0.10},
    ),
    _stint_pace_provider,
)
_register(
    FindingProviderDescriptor(
        provider_id="observed-pace-evolution-provider",
        provider_version=1,
        result_types=["observed_pace_evolution"],
        criteria={"accepted_quality": ["high", "medium"], "minimum_samples": 5, "absolute_slope_seconds_per_lap": 0.01},
    ),
    _pace_evolution_provider,
)
_register(
    FindingProviderDescriptor(
        provider_id="sector-evolution-provider",
        provider_version=1,
        result_types=["observed_sector_time_evolution"],
        criteria={"disposition": "context_only", "reason": "sector panels qualify whole-lap evolution but do not independently generate claims"},
    ),
    lambda result: (
        _assessment(
            result,
            provider_id="sector-evolution-provider",
            provider_version=1,
            disposition="context_only",
            reasons=["Sector evolution is retained as qualifying context without manufacturing additional prose."],
        ),
        [],
    ),
)
_register(
    FindingProviderDescriptor(
        provider_id="compound-comparison-provider",
        provider_version=1,
        result_types=[
            "descriptive_within_driver_difference",
            "matched_driver_descriptive_difference",
            "unrestricted_descriptive_distribution",
        ],
        criteria={"controlled_scalar_required": True, "absolute_difference_seconds": 0.10},
    ),
    _compound_provider,
)
_register(
    FindingProviderDescriptor(
        provider_id="race-time-delta-provider",
        provider_version=1,
        result_types=["measured_gap_change", "derived_cumulative_pace_delta"],
        criteria={"minimum_paired_samples": 2, "overall_change_required": True},
    ),
    _gap_provider,
)
_register(
    FindingProviderDescriptor(
        provider_id="pit-cycle-provider",
        provider_version=1,
        result_types=["measured_pit_cycle_comparison"],
        criteria={"measured_gap_change_required": True, "causal_claims": False},
    ),
    _pit_cycle_provider,
)
_register(
    FindingProviderDescriptor(
        provider_id="driver-battle-provider",
        provider_version=1,
        result_types=["driver_battle"],
        criteria={"supported_nested_direct_gap_required": True},
    ),
    _driver_battle_provider,
)
_register(
    FindingProviderDescriptor(
        provider_id="race-session-spine-provider",
        provider_version=1,
        result_types=[
            "race_classification",
            "grid_to_finish_movement",
            "pit_stop_sequence",
            "neutralisation_periods",
            "retirement_status",
            "position_change_interval",
        ],
        criteria={
            "measurement_category": "measured",
            "causal_or_intent_language": False,
            "partial_states_supported": True,
        },
    ),
    _session_spine_provider,
)


SYNTHESIS_RULE_IDS = (
    "pace-vs-direct-gap-v1",
    "pace-evolution-comparison-v1",
    "pit-cycle-vs-race-state-v1",
    "pace-vs-position-change-v1",
)
_CONFIDENCE_ORDER = {"unavailable": 0, "provisional": 1, "low": 2, "medium": 3, "high": 4}


def synthesize_findings(findings: Iterable[ReportFinding]) -> list[ReportFinding]:
    """Run the fixed SPEC-009 catalog. Rules emit nothing when incompatible."""

    values = list({item.finding_id: item for item in findings}.values())
    conclusions = [
        *_pace_vs_direct_gap(values),
        *_pace_evolution_comparison(values),
        *_pit_cycle_vs_race_state(values),
        *_pace_vs_position_change(values),
    ]
    return sorted(conclusions, key=lambda item: item.finding_id)


def _compatible_pair(left: ReportFinding, right: ReportFinding) -> bool:
    if left.comparison_basis.get("session_id") != right.comparison_basis.get("session_id"):
        return False
    left_subjects = set(left.comparison_basis.get("subjects") or [])
    left_subjects.update(
        value for value in (left.comparison_basis.get("focal_driver"), left.comparison_basis.get("benchmark")) if value
    )
    right_subjects = set(right.comparison_basis.get("subjects") or [])
    right_subjects.update(
        value for value in (right.comparison_basis.get("focal_driver"), right.comparison_basis.get("benchmark")) if value
    )
    return bool(left_subjects & right_subjects) or not left_subjects or not right_subjects


def _same_interval(left: ReportFinding, right: ReportFinding) -> bool:
    keys = ("start_lap", "end_lap")
    left_interval = tuple(left.comparison_basis.get(key) for key in keys)
    right_interval = tuple(right.comparison_basis.get(key) for key in keys)
    return None not in left_interval and left_interval == right_interval


def _conclusion(rule_id: str, supports: list[ReportFinding], text: str, section: ReportSectionKind) -> ReportFinding:
    support_fingerprints = sorted(item.evidence_fingerprint for item in supports)
    evidence = {item.chart_instance_id: item for finding in supports for item in finding.evidence}
    confidence = min(supports, key=lambda item: _CONFIDENCE_ORDER[item.confidence]).confidence
    conclusion_id = stable_id("conclusion", rule_id, *support_fingerprints)
    return ReportFinding(
        finding_id=conclusion_id,
        finding_kind="conclusion",
        finding_type=rule_id.removesuffix("-v1"),
        evidence_fingerprint=canonical_fingerprint({"rule_id": rule_id, "supports": support_fingerprints}),
        text=text,
        section=section,
        priority=90,
        confidence=confidence,
        result_fingerprints=sorted({value for item in supports for value in item.result_fingerprints}),
        result_ids=sorted({value for item in supports for value in item.result_ids}),
        synthesis_rule_id=rule_id,
        comparison_basis={"session_id": supports[0].comparison_basis.get("session_id")},
        limitations=list(dict.fromkeys(value for item in supports for value in item.limitations)),
        evidence=sorted(evidence.values(), key=lambda item: item.chart_instance_id),
        supporting_finding_ids=sorted(item.finding_id for item in supports),
    )


def _pace_vs_direct_gap(findings: list[ReportFinding]) -> list[ReportFinding]:
    pace = [item for item in findings if item.finding_type == "representative_pace_advantage"]
    gaps = [item for item in findings if item.finding_type in {"direct_gap_change", "driver_battle_outcome"}]
    output: list[ReportFinding] = []
    for left in pace:
        for right in gaps:
            if _compatible_pair(left, right) and _same_interval(left, right):
                output.append(_conclusion(
                    "pace-vs-direct-gap-v1",
                    [left, right],
                    f"The supported representative-pace difference coincided with the observed direct-gap change: {right.text}",
                    "executive_summary",
                ))
    return output[:1]


def _pace_evolution_comparison(findings: list[ReportFinding]) -> list[ReportFinding]:
    values = [item for item in findings if item.finding_type == "observed_pace_evolution"]
    for index, left in enumerate(values):
        for right in values[index + 1 :]:
            if not _compatible_pair(left, right):
                continue
            if left.comparison_basis.get("basis") != right.comparison_basis.get("basis"):
                continue
            if left.comparison_basis.get("driver") == right.comparison_basis.get("driver"):
                continue
            left_slope, right_slope = float(left.metrics["slope"]), float(right.metrics["slope"])
            left_direction = "increased" if left_slope >= 0 else "decreased"
            right_direction = "increased" if right_slope >= 0 else "decreased"
            difference = abs(left_slope - right_slope)
            if left_slope >= right_slope:
                directional_summary = (
                    f"a {difference:.3f} s/lap steeper increase for "
                    f"{left.comparison_basis['driver']}"
                    if left_slope >= 0 and right_slope >= 0
                    else f"a {difference:.3f} s/lap greater slope for {left.comparison_basis['driver']}"
                )
            else:
                directional_summary = (
                    f"a {difference:.3f} s/lap steeper increase for "
                    f"{right.comparison_basis['driver']}"
                    if left_slope >= 0 and right_slope >= 0
                    else f"a {difference:.3f} s/lap greater slope for {right.comparison_basis['driver']}"
                )
            conclusion = _conclusion(
                "pace-evolution-comparison-v1",
                [left, right],
                (
                    f"{left.comparison_basis['driver']}'s observed representative lap time "
                    f"{left_direction} by {abs(left_slope):.3f} seconds per "
                    f"{str(left.comparison_basis.get('basis', 'stint-progress')).replace('_', '-')} lap, "
                    f"versus {abs(right_slope):.3f} for {right.comparison_basis['driver']}; "
                    f"{directional_summary}."
                ),
                "pace_and_tyre_performance",
            )
            conclusion = conclusion.model_copy(
                update={
                    "comparison_basis": {
                        "session_id": left.comparison_basis.get("session_id"),
                        "basis": left.comparison_basis.get("basis"),
                        "intervals": [
                            {
                                "driver": item.comparison_basis.get("driver"),
                                "stint": item.comparison_basis.get("stint"),
                                "start_lap": item.comparison_basis.get("start_lap"),
                                "end_lap": item.comparison_basis.get("end_lap"),
                            }
                            for item in (left, right)
                        ],
                        "representative_laps_only": True,
                    }
                },
                deep=True,
            )
            return [conclusion]
    return []


def _pit_cycle_vs_race_state(findings: list[ReportFinding]) -> list[ReportFinding]:
    cycles = [item for item in findings if item.finding_type == "measured_pit_cycle_change"]
    gaps = [item for item in findings if item.finding_type in {"direct_gap_change", "driver_battle_outcome"}]
    for cycle in cycles:
        for gap in gaps:
            if _compatible_pair(cycle, gap) and _same_interval(cycle, gap):
                return [_conclusion(
                    "pit-cycle-vs-race-state-v1",
                    [cycle, gap],
                    f"The measured pit-cycle change occurred within the same observed race-state comparison. {cycle.text}",
                    "pit_cycles_and_key_comparisons",
                )]
    return []


def _pace_vs_position_change(findings: list[ReportFinding]) -> list[ReportFinding]:
    pace = [item for item in findings if item.finding_type == "representative_pace_advantage"]
    positions = [item for item in findings if item.finding_type == "race_position_change"]
    for left in pace:
        for right in positions:
            if _compatible_pair(left, right):
                return [_conclusion(
                    "pace-vs-position-change-v1",
                    [left, right],
                    "The supported representative-pace evidence and observed race-position change describe the same compatible interval without establishing causality.",
                    "strategy_and_race_evolution",
                )]
    return []


_SECTION_TITLES: tuple[tuple[ReportSectionKind, str], ...] = (
    ("executive_summary", "Executive Summary"),
    ("strategy_and_race_evolution", "Strategy and Race Evolution"),
    ("pace_and_tyre_performance", "Pace and Tyre Performance"),
    ("pit_cycles_and_key_comparisons", "Pit Cycles and Key Comparisons"),
    ("limitations_and_evidence", "Limitations and Evidence"),
)


def default_report_plan(
    target_session_id: str,
    results: Iterable[AnalyticalResultRecord],
    findings: Iterable[ReportFinding],
    conclusions: Iterable[ReportFinding],
) -> ReportPlan:
    finding_values = list(findings)
    conclusion_values = list(conclusions)
    result_values = list(results)
    claims = sorted(
        [*finding_values, *conclusion_values],
        key=lambda item: (-item.priority, item.finding_id),
    )
    evidence_only_finding_ids = {
        finding_id
        for conclusion in conclusion_values
        if conclusion.synthesis_rule_id == "pace-evolution-comparison-v1"
        for finding_id in conclusion.supporting_finding_ids
    }
    chart_section_by_id: dict[str, ReportSectionKind] = {}
    chart_by_id: dict[str, ChartEvidence] = {}
    context_chart_ids: set[str] = set()
    for result in result_values:
        for evidence in result.chart_evidence:
            chart_by_id[evidence.chart_instance_id] = evidence
            if result.result_type == "strategy_timeline":
                chart_section_by_id[evidence.chart_instance_id] = "strategy_and_race_evolution"
                context_chart_ids.add(evidence.chart_instance_id)
    for claim in claims:
        for evidence in claim.evidence:
            chart_by_id[evidence.chart_instance_id] = evidence
            chart_section_by_id.setdefault(evidence.chart_instance_id, claim.section)
    executive_claims = _select_executive_claims(claims)
    sections: list[ReportPlanSection] = []
    for section_id, title in _SECTION_TITLES:
        section_claims = executive_claims if section_id == "executive_summary" else [
            claim
            for claim in claims
            if claim.section == section_id and claim.finding_id not in evidence_only_finding_ids
        ]
        claim_items = [
            ReportPlanItem(
                item_id=stable_id("plan-item", section_id, claim.finding_id),
                item_type="claim",
                reference_id=claim.finding_id,
            )
            for claim in section_claims
        ]
        chart_items = [
            ReportPlanItem(
                item_id=stable_id("plan-item", section_id, "chart", chart_id),
                item_type="chart",
                reference_id=chart_id,
            )
            for chart_id in sorted(chart_by_id)
            if section_id != "executive_summary" and chart_section_by_id.get(chart_id) == section_id
        ]
        if section_id == "strategy_and_race_evolution":
            context_items = [item for item in chart_items if item.reference_id in context_chart_ids]
            supporting_items = [item for item in chart_items if item.reference_id not in context_chart_ids]
            items = context_items + claim_items + supporting_items
        else:
            items = claim_items + chart_items
        sections.append(ReportPlanSection(section_id=section_id, title=title, items=items))
    return ReportPlan(target_session_id=target_session_id, sections=sections)


def _select_executive_claims(claims: list[ReportFinding]) -> list[ReportFinding]:
    """Select the main race story deterministically, independent of synthesis order."""

    preferred_types = (
        "direct_gap_change",
        "representative_pace_advantage",
        "pace-evolution-comparison",
    )
    selected: list[ReportFinding] = []
    for finding_type in preferred_types:
        candidates = [claim for claim in claims if claim.finding_type == finding_type]
        if candidates:
            selected.append(sorted(candidates, key=lambda item: (-item.priority, item.finding_id))[0])
    if len(selected) < 3:
        remaining = [claim for claim in claims if claim.finding_id not in {item.finding_id for item in selected}]
        selected.extend(remaining[: 3 - len(selected)])
    return selected[:3]


def build_report_content(
    target_session_id: str,
    sources: Iterable[ResultSource],
    additional_results: Iterable[AnalyticalResultRecord] = (),
) -> ReportContent:
    source_values = list(sources)
    if any(source.target_session_id != target_session_id for source in source_values):
        raise ValueError("A report may contain analytical results from one target session only")
    results_by_fingerprint = {
        result.result_fingerprint: result
        for result in [*materialize_results(source_values), *additional_results]
    }
    results = sorted(results_by_fingerprint.values(), key=lambda item: item.result_fingerprint)
    assessments, findings = assess_results(results)
    conclusions = synthesize_findings(findings)
    plan = default_report_plan(target_session_id, results, findings, conclusions)
    evidence_fingerprint = canonical_fingerprint(
        {
            "target_session_id": target_session_id,
            "results": [result.result_fingerprint for result in results],
            "assessments": [assessment.model_dump(mode="json") for assessment in assessments],
            "findings": [finding.evidence_fingerprint for finding in findings],
            "conclusions": [conclusion.evidence_fingerprint for conclusion in conclusions],
        }
    )
    return ReportContent(
        target_session_id=target_session_id,
        results=results,
        assessments=assessments,
        findings=findings,
        conclusions=conclusions,
        plan=plan,
        evidence_fingerprint=evidence_fingerprint,
    )


def required_review_item_ids(content: ReportContent) -> set[str]:
    claims = {item.finding_id for item in [*content.findings, *content.conclusions]}
    if content.publication_plan is not None:
        return {
            item.finding_id
            for item in content.publication_plan.claims
            if item.included and item.finding_id in claims
        }
    return {
        item.reference_id
        for section in content.plan.sections
        if section.included
        for item in section.items
        if item.included and item.item_type == "claim" and item.reference_id in claims
    }


def reviews_are_current(content: ReportContent, reviews: Iterable[ReportReviewEntry]) -> bool:
    by_id = {review.item_id: review for review in reviews}
    claims = {item.finding_id: item for item in [*content.findings, *content.conclusions]}
    for item_id in required_review_item_ids(content):
        review = by_id.get(item_id)
        claim = claims[item_id]
        if review is None or review.review_status == "pending":
            return False
        if review.reviewed_evidence_fingerprint != claim.evidence_fingerprint:
            return False
    return True

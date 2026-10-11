from decimal import Decimal
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class Materiality(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class ClaimStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    MISSING = "MISSING"
    UNVERIFIABLE = "UNVERIFIABLE"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    # Backwards compatibility aliases
    NOT_FOUND = "MISSING"
    AMBIGUOUS = "UNVERIFIABLE"

class ReasonCode(str, Enum):
    EXACT_MATCH = "EXACT_MATCH"
    NUMERIC_CONTRADICTION = "NUMERIC_CONTRADICTION"
    POLARITY_CONTRADICTION = "POLARITY_CONTRADICTION"
    QUALIFIER_MISMATCH = "QUALIFIER_MISMATCH"
    TIMELINE_MISMATCH = "TIMELINE_MISMATCH"
    BURIED_DISCLAIMER = "BURIED_DISCLAIMER"
    CLAIM_NOT_FOUND = "CLAIM_NOT_FOUND"
    CONFLICTING_PAGE_EVIDENCE = "CONFLICTING_PAGE_EVIDENCE"
    FABRICATED_QUOTE_REJECTED = "FABRICATED_QUOTE_REJECTED"
    SEMANTIC_EQUIVALENT = "SEMANTIC_EQUIVALENT"
    UNVERIFIABLE_EVIDENCE = "UNVERIFIABLE_EVIDENCE"
    UNKNOWN = "UNKNOWN"

class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class DOMZone(str, Enum):
    HERO_CANDIDATE = "HERO_CANDIDATE"
    MAIN_BODY = "MAIN_BODY"
    FOOTER_DISCLAIMER = "FOOTER_DISCLAIMER"
    HIDDEN_OR_UNKNOWN = "HIDDEN_OR_UNKNOWN"
    UNKNOWN = "UNKNOWN"

class ClaimType(str, Enum):
    TRIAL_DURATION = "TRIAL_DURATION"
    PRICING_DISCOUNT = "PRICING_DISCOUNT"
    PRICE_POINT = "PRICE_POINT"
    APPROVAL_TIMELINE = "APPROVAL_TIMELINE"
    REQUIREMENT_FRICTION = "REQUIREMENT_FRICTION"
    GUARANTEE = "GUARANTEE"
    PRODUCT_CAPABILITY = "PRODUCT_CAPABILITY"
    AVAILABILITY_CONDITION = "AVAILABILITY_CONDITION"
    SUBJECTIVE_MARKETING = "SUBJECTIVE_MARKETING"
    CALL_TO_ACTION = "CALL_TO_ACTION"
    VALUE_PROPOSITION = "VALUE_PROPOSITION"
    OTHER = "OTHER"

class Comparator(str, Enum):
    EXACT = "EXACT"
    UP_TO = "UP_TO"
    AT_LEAST = "AT_LEAST"
    FROM = "FROM"
    RANGE = "RANGE"

class Polarity(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    CONDITIONAL = "CONDITIONAL"

class NumericSpec(BaseModel):
    value: Optional[Decimal] = None
    value_min: Optional[Decimal] = None
    value_max: Optional[Decimal] = None
    unit: str # e.g. "day", "percent", "dollar", "hour"
    comparator: Comparator = Comparator.EXACT
    time_basis: Optional[str] = None # e.g. "month", "year", "business_day"
    raw_str: str

    model_config = {
        "arbitrary_types_allowed": True
    }

class AtomicClaim(BaseModel):
    claim_id: str
    canonical_id: str # Grouping ID to deduplicate claims (subject + predicate + value)
    text: str
    claim_type: ClaimType
    subject: str
    predicate: str
    numeric: Optional[NumericSpec] = None
    qualifiers: List[str] = Field(default_factory=list)
    polarity: Polarity = Polarity.POSITIVE
    materiality: Materiality = Materiality.HIGH
    source: str # "ad_headline", "ad_description", or "ad_call_to_action"
    is_factual: bool = True # False for subjective marketing puffery or pure call to action
    source_span: Optional[str] = None # Verbatim substring or clause from ad source

class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    INVALID = "INVALID"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"

class RelevanceStatus(str, Enum):
    RELEVANT = "RELEVANT"
    IRRELEVANT = "IRRELEVANT"
    UNCERTAIN = "UNCERTAIN"

class DOMBlock(BaseModel):
    block_id: str
    tag_name: str
    dom_zone: DOMZone
    order_index: int
    raw_text: str
    normalized_text: str
    is_hidden: bool = False
    selector_path: Optional[str] = None # e.g. "div.hero > h1" or "footer > div.fine"
    prominence_weight: float = 1.0 # 1.0 for Hero, 0.75 for Main, 0.25 for Footer, 0.0 for Hidden
    has_conditions: bool = False # Flag if block contains caveats, asterisks, or disclaimers
    snapshot_id: Optional[str] = None # Source snapshot or content hash

class EvidencePassage(BaseModel):
    quote: str
    normalized_quote: str
    block_id: str
    dom_zone: DOMZone
    tag_name: str
    is_verified: bool = False
    verification_method: str = "unverified" # "exact", "normalized_whitespace", "unverified"
    selector_path: Optional[str] = None
    prominence_weight: float = 1.0
    snapshot_id: Optional[str] = None
    source_start_offset: Optional[int] = None
    source_end_offset: Optional[int] = None
    verification_status: VerificationStatus = VerificationStatus.VERIFIED
    relevance_status: RelevanceStatus = RelevanceStatus.RELEVANT
    rejection_reason: Optional[str] = None

class CitationVerificationRecord(BaseModel):
    citation_id: str
    claim_id: str
    block_id: str
    snapshot_id: str
    quoted_text: str
    verification_status: VerificationStatus
    match_method: str
    source_start_offset: Optional[int] = None
    source_end_offset: Optional[int] = None
    dom_zone: DOMZone
    relevance_status: RelevanceStatus
    rejection_reason: Optional[str] = None

class ComparisonRecord(BaseModel):
    claim_id: str
    subject_match: bool = False
    predicate_match: bool = False
    numeric_match: Optional[bool] = None
    polarity_match: Optional[bool] = None
    qualifiers_conflict: bool = False
    evidence_passages: List[EvidencePassage] = Field(default_factory=list)

class MismatchExplanation(BaseModel):
    """
    Phase 5: Structured Mismatch Explanation conforming to the 7-part evaluation criteria:
    1. original_ad_claim: verbatim advertised promise
    2. landing_page_finding: what inspected landing page establishes
    3. discrepancy_description: precise discrepancy
    4. practical_significance: impact on customer expectation and friction
    5. conditions_and_visibility: qualifications, fine print, or prominence issues
    6. recommended_ad_fix & recommended_page_fix: actionable, non-vague corrections
    7. certainty_level: distinction between factual findings and uncertain interpretations
    """
    original_ad_claim: str
    landing_page_finding: str
    discrepancy_description: str
    practical_significance: str
    conditions_and_visibility: str
    recommended_ad_fix: str
    recommended_page_fix: str
    is_factual: bool = True
    certainty_level: str = "FACTUAL_EVIDENCE" # "FACTUAL_EVIDENCE" or "UNCERTAIN_INTERPRETATION"

class SeverityAssessment(BaseModel):
    """
    Phase 6: Multi-Factor Severity Assessment & Prioritization.
    Prioritizes findings based on promise materiality, discrepancy magnitude,
    and customer impact, while flagging potential regulatory concerns with factual basis.
    """
    level: Severity # CRITICAL, HIGH, MEDIUM, LOW, INFO
    priority_rank: int # 1 (Critical) to 5 (Info)
    rationale: str
    is_potentially_misleading: bool = False
    regulatory_flag: bool = False
    regulatory_review_note: Optional[str] = None

class AuditFinding(BaseModel):
    claim_id: str
    canonical_id: str
    ad_claim_text: str
    claim_materiality: Materiality
    status: ClaimStatus
    reason_code: ReasonCode
    severity: Severity
    confidence: Confidence
    comparison: ComparisonRecord
    primary_evidence: Optional[EvidencePassage] = None
    conflicting_evidence: Optional[EvidencePassage] = None
    explanation: str
    recommended_ad_fix: str
    recommended_page_fix: str
    mismatch_details: Optional[MismatchExplanation] = None
    severity_assessment: Optional[SeverityAssessment] = None
    regulatory_flag: bool = False
    regulatory_review_note: Optional[str] = None

class AuditState(str, Enum):
    COMPLETED = "COMPLETED"
    PARTIAL_CONTENT_WARNING = "PARTIAL_CONTENT_WARNING"
    FAILED_UNREADABLE_INPUT = "FAILED_UNREADABLE_INPUT"

class AuditResult(BaseModel):
    audit_state: AuditState = AuditState.COMPLETED
    match_score: Optional[int] = None # 0-100 evidence-weighted, or None if failed
    scoring_unavailability_reason: Optional[str] = None # Set when match_score is None
    scoring_methodology_version: str = "1.0.0-evidence-weighted"
    evidence_coverage_index: Optional[int] = None # 0-100, or None
    evidence_prominence_index: Optional[int] = None # 0-100, or None if no evidence found
    grade: str # "Strong Match", "Partial Match", "Poor Match", "Unable to Assess"
    total_claims: int = 0
    unique_canonical_claims: int = 0
    findings: List[AuditFinding] = Field(default_factory=list)
    citation_records: List[CitationVerificationRecord] = Field(default_factory=list)
    critical_issues_count: int = 0
    has_critical_marketing_liability: bool = False
    regulatory_issues_count: int = 0
    reported_quotes_count: int = 0
    verified_quotes_count: int = 0
    rejected_quotes_count: int = 0
    evidence_validity_rate: Optional[float] = None # None when reported_quotes_count == 0
    audit_warnings: List[str] = Field(default_factory=list)
    retrieval_limitations: List[str] = Field(default_factory=list)
    audit_metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Returns valid dictionary representation conforming to Pydantic schema."""
        return self.model_dump(mode="json")

    def to_json(self, indent: int = 2) -> str:
        """Phase 7: Return valid formatted JSON string conforming to the application schema."""
        return self.model_dump_json(indent=indent)

    def to_structured_report(self) -> Dict[str, Any]:
        """
        Phase 7: Returns clean, standardized structured JSON report
        guaranteeing exact fields requested in the audit engine specification:
        - Audit status
        - Overall score or reason scoring is not possible
        - Scoring methodology version
        - Evidence coverage & prominence
        - Individual claims, statuses, quotations, source locations, explanations, severity, corrections
        - Uncertainties and retrieval limitations
        """
        claims_report = []
        for f in self.findings:
            item = {
                "claim_id": f.claim_id,
                "ad_claim_text": f.ad_claim_text,
                "claim_materiality": f.claim_materiality.value,
                "status": f.status.value,
                "reason_code": f.reason_code.value,
                "severity": f.severity.value,
                "priority_rank": f.severity_assessment.priority_rank if f.severity_assessment else 3,
                "regulatory_flag": f.regulatory_flag,
                "regulatory_review_note": f.regulatory_review_note,
                "quotation": f.primary_evidence.quote if f.primary_evidence else None,
                "source_location": {
                    "block_id": f.primary_evidence.block_id if f.primary_evidence else None,
                    "dom_zone": f.primary_evidence.dom_zone.value if f.primary_evidence else None,
                    "selector_path": f.primary_evidence.selector_path if f.primary_evidence else None,
                    "start_offset": f.primary_evidence.source_start_offset if f.primary_evidence else None,
                    "end_offset": f.primary_evidence.source_end_offset if f.primary_evidence else None
                } if f.primary_evidence else None,
                "explanation": f.explanation,
                "mismatch_details": f.mismatch_details.model_dump() if f.mismatch_details else None,
                "recommended_ad_fix": f.recommended_ad_fix,
                "recommended_page_fix": f.recommended_page_fix
            }
            claims_report.append(item)

        return {
            "audit_status": self.audit_state.value,
            "overall_score": self.match_score,
            "scoring_unavailability_reason": self.scoring_unavailability_reason,
            "scoring_methodology_version": self.scoring_methodology_version,
            "grade": self.grade,
            "evidence_coverage_index": self.evidence_coverage_index,
            "evidence_prominence_index": self.evidence_prominence_index,
            "total_claims": self.total_claims,
            "critical_issues_count": self.critical_issues_count,
            "regulatory_issues_count": self.regulatory_issues_count,
            "evidence_validity_rate": self.evidence_validity_rate,
            "individual_claims": claims_report,
            "retrieval_limitations_and_uncertainties": self.retrieval_limitations or self.audit_warnings,
            "audit_metadata": self.audit_metadata
        }

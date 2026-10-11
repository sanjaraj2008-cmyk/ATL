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
    NOT_FOUND = "NOT_FOUND"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    AMBIGUOUS = "AMBIGUOUS"

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
    APPROVAL_TIMELINE = "APPROVAL_TIMELINE"
    REQUIREMENT_FRICTION = "REQUIREMENT_FRICTION"
    VALUE_PROPOSITION = "VALUE_PROPOSITION"
    CALL_TO_ACTION = "CALL_TO_ACTION"
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
    source: str # "ad_headline" or "ad_description"

class DOMBlock(BaseModel):
    block_id: str
    tag_name: str
    dom_zone: DOMZone
    order_index: int
    raw_text: str
    normalized_text: str
    is_hidden: bool = False

class EvidencePassage(BaseModel):
    quote: str
    normalized_quote: str
    block_id: str
    dom_zone: DOMZone
    tag_name: str
    is_verified: bool = False
    verification_method: str = "unverified" # "exact", "normalized_whitespace", "unverified"

class ComparisonRecord(BaseModel):
    claim_id: str
    subject_match: bool = False
    predicate_match: bool = False
    numeric_match: Optional[bool] = None
    polarity_match: Optional[bool] = None
    qualifiers_conflict: bool = False
    evidence_passages: List[EvidencePassage] = Field(default_factory=list)

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

class AuditState(str, Enum):
    COMPLETED = "COMPLETED"
    PARTIAL_CONTENT_WARNING = "PARTIAL_CONTENT_WARNING"
    FAILED_UNREADABLE_INPUT = "FAILED_UNREADABLE_INPUT"

class AuditResult(BaseModel):
    audit_state: AuditState = AuditState.COMPLETED
    match_score: Optional[int] = None # 0-100 evidence-weighted, or None if failed
    evidence_coverage_index: Optional[int] = None # 0-100, or None
    evidence_prominence_index: Optional[int] = None # 0-100, or None if no evidence found
    grade: str # "Strong Match", "Partial Match", "Poor Match", "Unable to Assess"
    total_claims: int = 0
    unique_canonical_claims: int = 0
    findings: List[AuditFinding] = Field(default_factory=list)
    critical_issues_count: int = 0
    has_critical_marketing_liability: bool = False
    reported_quotes_count: int = 0
    verified_quotes_count: int = 0
    evidence_validity_rate: Optional[float] = None # None when reported_quotes_count == 0
    audit_warnings: List[str] = Field(default_factory=list)
    audit_metadata: Dict[str, Any] = Field(default_factory=dict)

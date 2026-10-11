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
    citation_records: List[CitationVerificationRecord] = Field(default_factory=list)
    critical_issues_count: int = 0
    has_critical_marketing_liability: bool = False
    reported_quotes_count: int = 0
    verified_quotes_count: int = 0
    rejected_quotes_count: int = 0
    evidence_validity_rate: Optional[float] = None # None when reported_quotes_count == 0
    audit_warnings: List[str] = Field(default_factory=list)
    audit_metadata: Dict[str, Any] = Field(default_factory=dict)

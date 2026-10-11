import hashlib
from typing import List, Dict, Any, Optional
from core.schemas import (
    AuditResult, AuditState, AuditFinding, Severity, ClaimStatus,
    VerificationStatus, CitationVerificationRecord
)
from core.extractor import ContentExtractor
from core.claims import ClaimsDecomposer
from core.matcher import ClaimMatcher
from core.verifier import EvidenceVerifier
from core.explainer import MismatchExplainer
from core.scorer import Scorer

class AuditEngine:
    """
    Main Orchestrator for the Ad-to-Landing-Page Message Match Auditor.
    Connects Extractor, Decomposer, Matcher, Verifier, Explainer, and Scorer into an atomic pipeline.
    """

    VERSION = "1.0.0"

    def __init__(self):
        self.extractor = ContentExtractor()
        self.decomposer = ClaimsDecomposer()
        self.matcher = ClaimMatcher()
        self.verifier = EvidenceVerifier()
        self.explainer = MismatchExplainer()
        self.scorer = Scorer()

    def audit(
        self,
        ad_headline: str,
        ad_description: str,
        landing_page_html: str,
        ad_call_to_action: Optional[str] = None,
        snapshot_id: Optional[str] = None
    ) -> AuditResult:
        warnings: List[str] = []

        # 1. Validation checks
        if not (ad_headline or ad_description or ad_call_to_action):
            return AuditResult(
                audit_state=AuditState.FAILED_UNREADABLE_INPUT,
                grade="Unable to Assess",
                audit_warnings=["Ad headline, description, and call to action are all empty."]
            )

        if not landing_page_html or not landing_page_html.strip():
            return AuditResult(
                audit_state=AuditState.FAILED_UNREADABLE_INPUT,
                grade="Unable to Assess",
                audit_warnings=["Landing page HTML snapshot is empty."]
            )

        snap_id = snapshot_id or hashlib.sha256(landing_page_html.encode('utf-8')).hexdigest()[:16]

        # 2. Extract DOM blocks (Phase 2)
        blocks, extract_warnings = self.extractor.extract_blocks(landing_page_html, snapshot_id=snap_id)
        warnings.extend(extract_warnings)

        if not blocks:
            return AuditResult(
                audit_state=AuditState.FAILED_UNREADABLE_INPUT,
                grade="Unable to Assess",
                audit_warnings=warnings or ["No text content could be extracted from the landing page."]
            )

        # 3. Decompose ad copy into claims (Phase 1)
        atomic_claims = self.decomposer.decompose(ad_headline, ad_description, ad_call_to_action)
        if not atomic_claims:
            return AuditResult(
                audit_state=AuditState.FAILED_UNREADABLE_INPUT,
                grade="Unable to Assess",
                audit_warnings=["Could not decompose any recognizable claims from the provided ad text."]
            )

        # 4. Compare claims against extracted blocks (Phase 3)
        findings: List[AuditFinding] = []
        for claim in atomic_claims:
            finding = self.matcher.evaluate_claim(claim, blocks)
            findings.append(finding)

        # 5. Phase 4: Deterministic Quotation Verification & Provenance Hardening
        all_citation_records: List[CitationVerificationRecord] = []
        for finding in findings:
            records = self.verifier.audit_and_harden_finding(finding, blocks, snapshot_id=snap_id)
            all_citation_records.extend(records)

        # 6. Phase 5: Explain the Mismatch & Synthesize Concrete Recommendations
        for finding, claim in zip(findings, atomic_claims):
            self.explainer.explain_finding(finding, claim, blocks, retrieval_warnings=warnings)

        # 7. Calculate scores, coverage, prominence, and critical flags
        match_score, coverage_idx, prominence_idx, has_crit_liability, grade = self.scorer.calculate_scores(findings)

        # 7. Compute quote verification rates from hardened records
        reported_quotes = len(all_citation_records)
        verified_quotes = sum(1 for r in all_citation_records if r.verification_status == VerificationStatus.VERIFIED)
        rejected_quotes = sum(1 for r in all_citation_records if r.verification_status == VerificationStatus.INVALID)

        evidence_validity_rate = (
            round((verified_quotes / reported_quotes) * 100.0, 1)
            if reported_quotes > 0 else None
        )

        critical_count = sum(
            1 for f in findings
            if f.severity == Severity.CRITICAL or (f.status == ClaimStatus.CONTRADICTED and f.severity == Severity.HIGH)
        )

        audit_state = AuditState.PARTIAL_CONTENT_WARNING if warnings else AuditState.COMPLETED

        return AuditResult(
            audit_state=audit_state,
            match_score=match_score,
            evidence_coverage_index=coverage_idx,
            evidence_prominence_index=prominence_idx,
            grade=grade,
            total_claims=len(atomic_claims),
            unique_canonical_claims=len(set(c.canonical_id for c in atomic_claims)),
            findings=findings,
            citation_records=all_citation_records,
            critical_issues_count=critical_count,
            has_critical_marketing_liability=has_crit_liability,
            reported_quotes_count=reported_quotes,
            verified_quotes_count=verified_quotes,
            rejected_quotes_count=rejected_quotes,
            evidence_validity_rate=evidence_validity_rate,
            audit_warnings=warnings,
            audit_metadata={
                "engine_version": self.VERSION,
                "blocks_analyzed": len(blocks),
                "claims_extracted": len(atomic_claims),
                "snapshot_id": snap_id,
                "citations_verified": verified_quotes,
                "citations_rejected": rejected_quotes,
                "mode": "deterministic_offline"
            }
        )

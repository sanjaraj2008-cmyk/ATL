from typing import List, Dict, Any, Optional
from core.schemas import (
    AuditResult, AuditState, AuditFinding, Severity, ClaimStatus
)
from core.extractor import ContentExtractor
from core.claims import ClaimsDecomposer
from core.matcher import ClaimMatcher
from core.scorer import Scorer

class AuditEngine:
    """
    Main Orchestrator for the Ad-to-Landing-Page Message Match Auditor.
    Connects Extractor, Decomposer, Matcher, Verifier, and Scorer into an atomic pipeline.
    """

    VERSION = "1.0.0"

    def __init__(self):
        self.extractor = ContentExtractor()
        self.decomposer = ClaimsDecomposer()
        self.matcher = ClaimMatcher()
        self.scorer = Scorer()

    def audit(
        self,
        ad_headline: str,
        ad_description: str,
        landing_page_html: str,
        ad_call_to_action: Optional[str] = None
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

        # 2. Extract DOM blocks
        blocks, extract_warnings = self.extractor.extract_blocks(landing_page_html)
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

        # 4. Compare claims against extracted blocks
        findings: List[AuditFinding] = []
        for claim in atomic_claims:
            finding = self.matcher.evaluate_claim(claim, blocks)
            findings.append(finding)

        # 5. Calculate scores, coverage, prominence, and critical flags
        match_score, coverage_idx, prominence_idx, has_crit_liability, grade = self.scorer.calculate_scores(findings)

        # 6. Compute quote verification rates
        reported_quotes = 0
        verified_quotes = 0
        for f in findings:
            if f.primary_evidence:
                reported_quotes += 1
                if f.primary_evidence.is_verified:
                    verified_quotes += 1

        evidence_validity_rate = (
            round((verified_quotes / reported_quotes) * 100.0, 1)
            if reported_quotes > 0 else None
        )

        critical_count = sum(1 for f in findings if f.severity == Severity.CRITICAL or (f.status == ClaimStatus.CONTRADICTED and f.severity == Severity.HIGH))

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
            critical_issues_count=critical_count,
            has_critical_marketing_liability=has_crit_liability,
            reported_quotes_count=reported_quotes,
            verified_quotes_count=verified_quotes,
            evidence_validity_rate=evidence_validity_rate,
            audit_warnings=warnings,
            audit_metadata={
                "engine_version": self.VERSION,
                "blocks_analyzed": len(blocks),
                "claims_extracted": len(atomic_claims),
                "mode": "deterministic_offline"
            }
        )

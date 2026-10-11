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
from core.severity import SeverityAssessor
from core.scorer import Scorer
from core.fetcher import URLFetcher

class AuditEngine:
    """
    Main Orchestrator for the Ad-to-Landing-Page Message Match Auditor.
    Connects URLFetcher, Extractor, Decomposer, Matcher, Verifier, Explainer, SeverityAssessor, and Scorer.
    """

    VERSION = "1.0.0"

    def __init__(self, allow_local_fetch: bool = False):
        self.fetcher = URLFetcher(allow_local=allow_local_fetch)
        self.extractor = ContentExtractor()
        self.decomposer = ClaimsDecomposer()
        self.matcher = ClaimMatcher()
        self.verifier = EvidenceVerifier()
        self.explainer = MismatchExplainer()
        self.severity_assessor = SeverityAssessor()
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
            msg = "Ad headline, description, and call to action are all empty."
            return AuditResult(
                audit_state=AuditState.FAILED_UNREADABLE_INPUT,
                grade="Unable to Assess",
                scoring_unavailability_reason=msg,
                audit_warnings=[msg],
                retrieval_limitations=[msg]
            )

        if not landing_page_html or not landing_page_html.strip():
            msg = "Landing page HTML snapshot is empty."
            return AuditResult(
                audit_state=AuditState.FAILED_UNREADABLE_INPUT,
                grade="Unable to Assess",
                scoring_unavailability_reason=msg,
                audit_warnings=[msg],
                retrieval_limitations=[msg]
            )

        snap_id = snapshot_id or hashlib.sha256(landing_page_html.encode('utf-8')).hexdigest()[:16]

        # 2. Extract DOM blocks (Phase 2)
        blocks, extract_warnings = self.extractor.extract_blocks(landing_page_html, snapshot_id=snap_id)
        warnings.extend(extract_warnings)

        if not blocks:
            msg = "No text content could be extracted from the landing page snapshot."
            return AuditResult(
                audit_state=AuditState.FAILED_UNREADABLE_INPUT,
                grade="Unable to Assess",
                scoring_unavailability_reason=msg,
                audit_warnings=warnings or [msg],
                retrieval_limitations=warnings or [msg]
            )

        # 3. Decompose ad copy into claims (Phase 1)
        atomic_claims = self.decomposer.decompose(ad_headline, ad_description, ad_call_to_action)
        if not atomic_claims:
            msg = "Could not decompose any recognizable claims from the provided ad copy."
            return AuditResult(
                audit_state=AuditState.FAILED_UNREADABLE_INPUT,
                grade="Unable to Assess",
                scoring_unavailability_reason=msg,
                audit_warnings=[msg],
                retrieval_limitations=[msg]
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

        # 7. Phase 6: Assess Severity & Regulatory Compliance Risks
        for finding, claim in zip(findings, atomic_claims):
            self.severity_assessor.assess_finding(finding, claim)

        # Sort findings by priority (Critical/High first)
        findings = self.severity_assessor.sort_findings_by_priority(findings)

        # 8. Calculate scores, coverage, prominence, and critical flags
        match_score, coverage_idx, prominence_idx, has_crit_liability, grade = self.scorer.calculate_scores(findings)

        # 9. Compute quote verification rates from hardened records
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
        regulatory_count = sum(1 for f in findings if f.regulatory_flag)

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
            regulatory_issues_count=regulatory_count,
            reported_quotes_count=reported_quotes,
            verified_quotes_count=verified_quotes,
            rejected_quotes_count=rejected_quotes,
            evidence_validity_rate=evidence_validity_rate,
            audit_warnings=warnings,
            retrieval_limitations=warnings,
            audit_metadata={
                "engine_version": self.VERSION,
                "blocks_analyzed": len(blocks),
                "claims_extracted": len(atomic_claims),
                "snapshot_id": snap_id,
                "citations_verified": verified_quotes,
                "citations_rejected": rejected_quotes,
                "regulatory_concerns_flagged": regulatory_count,
                "mode": "deterministic_offline"
            }
        )

    def audit_url(
        self,
        ad_headline: str,
        ad_description: str,
        landing_page_url: str,
        ad_call_to_action: Optional[str] = None
    ) -> AuditResult:
        """
        Fetches the live destination landing page HTML via URLFetcher
        and executes the full 7-phase audit engine.
        """
        html_content, fetch_err, metadata = self.fetcher.fetch_html(landing_page_url)
        if fetch_err or not html_content:
            err_msg = f"Failed to fetch landing page URL '{landing_page_url}': {fetch_err or 'Empty response'}"
            return AuditResult(
                audit_state=AuditState.FAILED_UNREADABLE_INPUT,
                grade="Unable to Assess",
                scoring_unavailability_reason=err_msg,
                audit_warnings=[err_msg],
                retrieval_limitations=[err_msg],
                audit_metadata={"url_metadata": metadata}
            )

        result = self.audit(
            ad_headline=ad_headline,
            ad_description=ad_description,
            landing_page_html=html_content,
            ad_call_to_action=ad_call_to_action,
            snapshot_id=metadata.get("content_hash")
        )

        # Bind URL metadata to audit result
        result.audit_metadata["source_url"] = landing_page_url
        result.audit_metadata["final_url"] = metadata.get("final_url")
        result.audit_metadata["http_status"] = metadata.get("status_code")
        result.audit_metadata["load_time_ms"] = metadata.get("load_time_ms")
        if metadata.get("warnings"):
            result.audit_warnings.extend(metadata["warnings"])
            result.retrieval_limitations.extend(metadata["warnings"])
            result.audit_state = AuditState.PARTIAL_CONTENT_WARNING

        return result

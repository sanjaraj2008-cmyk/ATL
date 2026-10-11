import unittest
from core.schemas import (
    AtomicClaim, ClaimType, Materiality, DOMBlock, DOMZone,
    AuditFinding, ClaimStatus, ReasonCode, Severity, Confidence, ComparisonRecord,
    EvidencePassage
)
from core.severity import SeverityAssessor

class TestPhase6SeverityAssessor(unittest.TestCase):
    def setUp(self):
        self.assessor = SeverityAssessor()

    def test_critical_price_contradiction(self):
        """Phase 6: High materiality pricing contradiction must be CRITICAL and flag regulatory review."""
        claim = AtomicClaim(
            claim_id="c_price",
            canonical_id="canon_price",
            text="Starts at $49/mo",
            claim_type=ClaimType.PRICE_POINT,
            materiality=Materiality.HIGH,
            subject="pricing",
            predicate="starts",
            source="ad_headline",
            is_factual=True
        )
        finding = AuditFinding(
            claim_id=claim.claim_id,
            canonical_id=claim.canonical_id,
            ad_claim_text=claim.text,
            claim_materiality=claim.materiality,
            status=ClaimStatus.CONTRADICTED,
            reason_code=ReasonCode.NUMERIC_CONTRADICTION,
            severity=Severity.HIGH,
            confidence=Confidence.HIGH,
            comparison=ComparisonRecord(claim_id=claim.claim_id),
            primary_evidence=EvidencePassage(
                quote="Enterprise Cloud Accounting starts at $79/mo.",
                normalized_quote="enterprise cloud accounting starts at $79/mo.",
                block_id="B001",
                dom_zone=DOMZone.HERO_CANDIDATE,
                tag_name="h1",
                is_verified=True
            ),
            explanation="",
            recommended_ad_fix="",
            recommended_page_fix=""
        )

        sev = self.assessor.assess_finding(finding, claim)

        self.assertEqual(sev.level, Severity.CRITICAL)
        self.assertEqual(sev.priority_rank, 1)
        self.assertTrue(sev.regulatory_flag)
        self.assertIsNotNone(sev.regulatory_review_note)
        # Check factual wording without definitive judicial ruling
        self.assertIn("Factual compliance review recommended", sev.regulatory_review_note)
        self.assertNotIn("guilty", sev.regulatory_review_note.lower())

    def test_missing_phrase_non_equivalence(self):
        """Phase 6: Do not treat every missing phrase as equally serious."""
        # 1. High materiality missing promise ($500 funding limit)
        claim_funding = AtomicClaim(
            claim_id="c_fund",
            canonical_id="canon_fund",
            text="Funding up to $500,000",
            claim_type=ClaimType.PRICE_POINT,
            materiality=Materiality.HIGH,
            subject="funding",
            predicate="up to",
            source="ad_headline",
            is_factual=True
        )
        finding_funding = AuditFinding(
            claim_id=claim_funding.claim_id,
            canonical_id=claim_funding.canonical_id,
            ad_claim_text=claim_funding.text,
            claim_materiality=claim_funding.materiality,
            status=ClaimStatus.MISSING,
            reason_code=ReasonCode.CLAIM_NOT_FOUND,
            severity=Severity.MEDIUM,
            confidence=Confidence.HIGH,
            comparison=ComparisonRecord(claim_id=claim_funding.claim_id),
            explanation="",
            recommended_ad_fix="",
            recommended_page_fix=""
        )

        # 2. Low materiality missing subjective puffery ("Top-rated experience")
        claim_puffery = AtomicClaim(
            claim_id="c_puff",
            canonical_id="canon_puff",
            text="Top-rated customer experience",
            claim_type=ClaimType.SUBJECTIVE_MARKETING,
            materiality=Materiality.LOW,
            subject="experience",
            predicate="top-rated",
            source="ad_description",
            is_factual=False
        )
        finding_puffery = AuditFinding(
            claim_id=claim_puffery.claim_id,
            canonical_id=claim_puffery.canonical_id,
            ad_claim_text=claim_puffery.text,
            claim_materiality=claim_puffery.materiality,
            status=ClaimStatus.MISSING,
            reason_code=ReasonCode.CLAIM_NOT_FOUND,
            severity=Severity.LOW,
            confidence=Confidence.HIGH,
            comparison=ComparisonRecord(claim_id=claim_puffery.claim_id),
            explanation="",
            recommended_ad_fix="",
            recommended_page_fix=""
        )

        sev_funding = self.assessor.assess_finding(finding_funding, claim_funding)
        sev_puffery = self.assessor.assess_finding(finding_puffery, claim_puffery)

        # The commercial promise must be HIGH severity; the puffery must be LOW severity
        self.assertEqual(sev_funding.level, Severity.HIGH)
        self.assertEqual(sev_puffery.level, Severity.LOW)
        self.assertLess(sev_funding.priority_rank, sev_puffery.priority_rank)

    def test_buried_disclaimer_regulatory_review(self):
        """Phase 6: High materiality terms hidden in footer must be flagged for disclosure prominence."""
        claim = AtomicClaim(
            claim_id="c_credit",
            canonical_id="canon_credit",
            text="All credit scores accepted",
            claim_type=ClaimType.REQUIREMENT_FRICTION,
            materiality=Materiality.HIGH,
            subject="credit",
            predicate="accepted",
            source="ad_headline",
            is_factual=True
        )
        finding = AuditFinding(
            claim_id=claim.claim_id,
            canonical_id=claim.canonical_id,
            ad_claim_text=claim.text,
            claim_materiality=claim.materiality,
            status=ClaimStatus.PARTIALLY_SUPPORTED,
            reason_code=ReasonCode.BURIED_DISCLAIMER,
            severity=Severity.MEDIUM,
            confidence=Confidence.HIGH,
            comparison=ComparisonRecord(claim_id=claim.claim_id),
            primary_evidence=EvidencePassage(
                quote="*Requires minimum credit score of 720. Rates vary.",
                normalized_quote="*requires minimum credit score of 720. rates vary.",
                block_id="B099",
                dom_zone=DOMZone.FOOTER_DISCLAIMER,
                tag_name="p",
                is_verified=True
            ),
            explanation="",
            recommended_ad_fix="",
            recommended_page_fix=""
        )

        sev = self.assessor.assess_finding(finding, claim)

        self.assertEqual(sev.level, Severity.HIGH)
        self.assertTrue(sev.regulatory_flag)
        self.assertIn("clear and conspicuous disclosure", sev.regulatory_review_note.lower())

    def test_priority_sorting(self):
        """Findings should sort from highest priority (CRITICAL/HIGH) to lowest (INFO)."""
        findings = [
            AuditFinding(
                claim_id="c1", canonical_id="c1", ad_claim_text="Supported",
                claim_materiality=Materiality.LOW, status=ClaimStatus.SUPPORTED,
                reason_code=ReasonCode.EXACT_MATCH, severity=Severity.INFO,
                confidence=Confidence.HIGH, comparison=ComparisonRecord(claim_id="c1"),
                explanation="", recommended_ad_fix="", recommended_page_fix=""
            ),
            AuditFinding(
                claim_id="c2", canonical_id="c2", ad_claim_text="Contradicted",
                claim_materiality=Materiality.HIGH, status=ClaimStatus.CONTRADICTED,
                reason_code=ReasonCode.NUMERIC_CONTRADICTION, severity=Severity.CRITICAL,
                confidence=Confidence.HIGH, comparison=ComparisonRecord(claim_id="c2"),
                explanation="", recommended_ad_fix="", recommended_page_fix=""
            ),
            AuditFinding(
                claim_id="c3", canonical_id="c3", ad_claim_text="Missing Feature",
                claim_materiality=Materiality.MEDIUM, status=ClaimStatus.MISSING,
                reason_code=ReasonCode.CLAIM_NOT_FOUND, severity=Severity.MEDIUM,
                confidence=Confidence.HIGH, comparison=ComparisonRecord(claim_id="c3"),
                explanation="", recommended_ad_fix="", recommended_page_fix=""
            )
        ]
        sorted_findings = self.assessor.sort_findings_by_priority(findings)
        self.assertEqual(sorted_findings[0].claim_id, "c2") # CRITICAL first
        self.assertEqual(sorted_findings[1].claim_id, "c3") # MEDIUM second
        self.assertEqual(sorted_findings[2].claim_id, "c1") # INFO last

if __name__ == "__main__":
    unittest.main()

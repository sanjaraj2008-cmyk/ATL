import unittest
from core.schemas import (
    AtomicClaim, ClaimType, DOMBlock, DOMZone,
    AuditFinding, ClaimStatus, ReasonCode, Severity, Confidence, ComparisonRecord,
    EvidencePassage, VerificationStatus, RelevanceStatus
)
from core.explainer import MismatchExplainer

class TestPhase5MismatchExplainer(unittest.TestCase):
    def setUp(self):
        self.explainer = MismatchExplainer()
        self.sample_blocks = [
            DOMBlock(
                block_id="B001",
                tag_name="h1",
                dom_zone=DOMZone.HERO_CANDIDATE,
                order_index=0,
                raw_text="Enterprise Cloud Accounting starts at $79/mo.",
                normalized_text="enterprise cloud accounting starts at $79/mo.",
                selector_path="body > div.hero > h1",
                prominence_weight=1.0,
                has_conditions=False
            ),
            DOMBlock(
                block_id="B015",
                tag_name="p",
                dom_zone=DOMZone.FOOTER_DISCLAIMER,
                order_index=15,
                raw_text="*Rates from 4.9% APR available only for qualified corporate applicants with credit scores above 750.",
                normalized_text="*rates from 4.9% apr available only for qualified corporate applicants with credit scores above 750.",
                selector_path="body > footer > p",
                prominence_weight=0.25,
                has_conditions=True
            )
        ]

    def test_contradicted_finding_explanation(self):
        """Phase 5: Contradicted claim must clearly state ad promise, page reality, discrepancy, and significance."""
        claim = AtomicClaim(
            claim_id="c_price",
            canonical_id="canon_price",
            text="Starts at $49/mo",
            claim_type=ClaimType.PRICE_POINT,
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
                is_verified=True,
                source_start_offset=0,
                source_end_offset=46
            ),
            explanation="",
            recommended_ad_fix="",
            recommended_page_fix=""
        )

        mismatch = self.explainer.explain_finding(finding, claim, self.sample_blocks)

        self.assertIsNotNone(finding.mismatch_details)
        self.assertIn("Starts at $49/mo", mismatch.original_ad_claim)
        self.assertIn("$79/mo", mismatch.landing_page_finding)
        self.assertIn("contradiction", mismatch.discrepancy_description.lower())
        self.assertIn("bounce rate", mismatch.practical_significance.lower())
        self.assertIn("Starts at $49/mo", mismatch.recommended_ad_fix)
        self.assertIn("honor the advertised promise", mismatch.recommended_page_fix)
        self.assertTrue(mismatch.is_factual)
        self.assertIn("FACTUAL_EVIDENCE", mismatch.certainty_level)

    def test_buried_disclaimer_visibility_issues(self):
        """Phase 5: Buried disclaimers must flag footer placement and low prominence."""
        claim = AtomicClaim(
            claim_id="c_apr",
            canonical_id="canon_apr",
            text="4.9% APR for all applicants",
            claim_type=ClaimType.PRICE_POINT,
            subject="apr",
            predicate="rate",
            source="ad_description",
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
                quote="*Rates from 4.9% APR available only for qualified corporate applicants with credit scores above 750.",
                normalized_quote="*rates from 4.9% apr available only for qualified corporate applicants with credit scores above 750.",
                block_id="B015",
                dom_zone=DOMZone.FOOTER_DISCLAIMER,
                tag_name="p",
                is_verified=True,
                source_start_offset=0,
                source_end_offset=105
            ),
            explanation="",
            recommended_ad_fix="",
            recommended_page_fix=""
        )

        mismatch = self.explainer.explain_finding(finding, claim, self.sample_blocks)

        self.assertIn("footer disclaimer", mismatch.conditions_and_visibility.lower())
        self.assertIn("asterisks", mismatch.conditions_and_visibility.lower())
        self.assertIn("terms apply", mismatch.recommended_ad_fix.lower())
        self.assertIn("elevate", mismatch.recommended_page_fix.lower())

    def test_missing_claim_explanation(self):
        """Phase 5: Missing claims must explicitly declare total absence without hallucinated quotes."""
        claim = AtomicClaim(
            claim_id="c_free_shipping",
            canonical_id="canon_shipping",
            text="Same-Day Free Shipping",
            claim_type=ClaimType.PRODUCT_CAPABILITY,
            subject="shipping",
            predicate="same-day",
            source="ad_call_to_action",
            is_factual=True
        )
        finding = AuditFinding(
            claim_id=claim.claim_id,
            canonical_id=claim.canonical_id,
            ad_claim_text=claim.text,
            claim_materiality=claim.materiality,
            status=ClaimStatus.MISSING,
            reason_code=ReasonCode.CLAIM_NOT_FOUND,
            severity=Severity.HIGH,
            confidence=Confidence.HIGH,
            comparison=ComparisonRecord(claim_id=claim.claim_id),
            primary_evidence=None,
            explanation="",
            recommended_ad_fix="",
            recommended_page_fix=""
        )

        mismatch = self.explainer.explain_finding(finding, claim, self.sample_blocks)

        self.assertIn("No mention", mismatch.landing_page_finding)
        self.assertIn("Total absence mismatch", mismatch.discrepancy_description)
        self.assertIn("abandonment risk", mismatch.practical_significance.lower())
        self.assertIn("Remove \"Same-Day Free Shipping\"", mismatch.recommended_ad_fix)
        self.assertIn("Add dedicated content", mismatch.recommended_page_fix)

    def test_unverifiable_due_to_partial_retrieval(self):
        """Phase 5: Partial retrieval limitations must be identified as UNCERTAIN_INTERPRETATION."""
        claim = AtomicClaim(
            claim_id="c_ai",
            canonical_id="canon_ai",
            text="Voted #1 AI tool in 2026",
            claim_type=ClaimType.SUBJECTIVE_MARKETING,
            subject="ai tool",
            predicate="voted #1",
            source="ad_description",
            is_factual=False
        )
        finding = AuditFinding(
            claim_id=claim.claim_id,
            canonical_id=claim.canonical_id,
            ad_claim_text=claim.text,
            claim_materiality=claim.materiality,
            status=ClaimStatus.UNVERIFIABLE,
            reason_code=ReasonCode.UNVERIFIABLE_EVIDENCE,
            severity=Severity.LOW,
            confidence=Confidence.LOW,
            comparison=ComparisonRecord(claim_id=claim.claim_id),
            primary_evidence=None,
            explanation="",
            recommended_ad_fix="",
            recommended_page_fix=""
        )

        mismatch = self.explainer.explain_finding(
            finding, claim, self.sample_blocks,
            retrieval_warnings=["SPA client-side hydration container detected"]
        )

        self.assertFalse(mismatch.is_factual)
        self.assertIn("UNCERTAIN_INTERPRETATION", mismatch.certainty_level)
        self.assertIn("SPA client-side hydration", mismatch.landing_page_finding)

if __name__ == "__main__":
    unittest.main()

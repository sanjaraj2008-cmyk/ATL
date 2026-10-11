import unittest
from core.schemas import (
    AtomicClaim, ClaimType, DOMBlock, DOMZone, 
    AuditFinding, ClaimStatus, ReasonCode, Severity, Confidence, ComparisonRecord,
    VerificationStatus, RelevanceStatus, EvidencePassage
)
from core.verifier import EvidenceVerifier

class TestPhase4QuotationVerification(unittest.TestCase):
    def setUp(self):
        self.verifier = EvidenceVerifier()
        self.sample_blocks = [
            DOMBlock(
                block_id="hero-1",
                tag_name="h1",
                dom_zone=DOMZone.HERO_CANDIDATE,
                order_index=0,
                raw_text="Transform your marketing with zero upfront fees today.",
                normalized_text="transform your marketing with zero upfront fees today.",
                selector_path="body > div.hero > h1",
                prominence_weight=1.0,
                snapshot_id="snap_12345"
            ),
            DOMBlock(
                block_id="pricing-2",
                tag_name="p",
                dom_zone=DOMZone.MAIN_BODY,
                order_index=1,
                raw_text="Monthly pricing starts at $49/mo with no credit card required.",
                normalized_text="monthly pricing starts at $49/mo with no credit card required.",
                selector_path="body > div.pricing > p",
                prominence_weight=0.75,
                snapshot_id="snap_12345"
            ),
            DOMBlock(
                block_id="footer-1",
                tag_name="footer",
                dom_zone=DOMZone.FOOTER_DISCLAIMER,
                order_index=2,
                raw_text="Privacy Policy and Terms of Service. All rights reserved.",
                normalized_text="privacy policy and terms of service. all rights reserved.",
                selector_path="body > footer",
                prominence_weight=0.25,
                snapshot_id="snap_12345"
            )
        ]
        self.claim_pricing = AtomicClaim(
            claim_id="c_price",
            canonical_id="canon_price",
            text="No credit card required",
            claim_type=ClaimType.PRICE_POINT,
            subject="credit card",
            predicate="required",
            source="ad_description",
            is_factual=True
        )

    def test_exact_match_with_offsets(self):
        """Phase 4 requires calculating exact source start and end character offsets."""
        quote = "no credit card required"
        is_valid, passage, reason = self.verifier.verify_quote_detailed(
            candidate_quote=quote,
            blocks=self.sample_blocks,
            expected_block_id="pricing-2",
            expected_snapshot_id="snap_12345"
        )
        self.assertTrue(is_valid)
        self.assertIsNotNone(passage)
        self.assertEqual(passage.block_id, "pricing-2")
        self.assertEqual(passage.source_start_offset, 38)
        self.assertEqual(passage.source_end_offset, 61)
        # Verify slice matches
        block_text = self.sample_blocks[1].raw_text
        self.assertEqual(block_text[passage.source_start_offset:passage.source_end_offset], "no credit card required")

    def test_reject_fabricated_quote(self):
        """Phase 4 must reject quotes not found in the block's source text."""
        quote = "Completely free forever with instant AI approval"
        is_valid, passage, reason = self.verifier.verify_quote_detailed(
            candidate_quote=quote,
            blocks=self.sample_blocks,
            expected_block_id="pricing-2",
            expected_snapshot_id="snap_12345"
        )
        self.assertFalse(is_valid)
        self.assertIsNone(passage)
        self.assertIn("not found within referenced block", reason)

    def test_reject_wrong_block_provenance(self):
        """Quote must be present in the SPECIFIC cited block, not just somewhere on the page."""
        quote = "no credit card required"
        # The quote is in pricing-2, but we cite hero-1
        is_valid, passage, reason = self.verifier.verify_quote_detailed(
            candidate_quote=quote,
            blocks=self.sample_blocks,
            expected_block_id="hero-1",
            expected_snapshot_id="snap_12345"
        )
        self.assertFalse(is_valid)
        self.assertIsNone(passage)
        self.assertIn("not found within referenced block", reason)

    def test_reject_nonexistent_block(self):
        """Reject citation referring to a non-existent block_id."""
        is_valid, passage, reason = self.verifier.verify_quote_detailed(
            candidate_quote="zero upfront fees",
            blocks=self.sample_blocks,
            expected_block_id="nonexistent-block-99"
        )
        self.assertFalse(is_valid)
        self.assertIsNone(passage)
        self.assertIn("does not exist in extracted page blocks", reason)

    def test_reject_wrong_snapshot_id(self):
        """Reject quote citation if the block belongs to a mismatched snapshot ID."""
        is_valid, passage, reason = self.verifier.verify_quote_detailed(
            candidate_quote="zero upfront fees",
            blocks=self.sample_blocks,
            expected_block_id="hero-1",
            expected_snapshot_id="snap_mismatch_999"
        )
        self.assertFalse(is_valid)
        self.assertIsNone(passage)
        self.assertIn("Snapshot mismatch", reason)

    def test_relevance_verification_supported(self):
        """Relevance check should verify that the quote semantically addresses the claim."""
        passage = EvidencePassage(
            quote="no credit card required",
            normalized_quote="no credit card required",
            block_id="pricing-2",
            dom_zone=DOMZone.MAIN_BODY,
            tag_name="p"
        )
        rel_status, msg = self.verifier.verify_relevance(
            claim_text=self.claim_pricing.text,
            finding_status=ClaimStatus.SUPPORTED,
            passage=passage
        )
        self.assertEqual(rel_status, RelevanceStatus.RELEVANT)

    def test_relevance_verification_irrelevant_quote(self):
        """If a quote exists in the DOM but is completely unrelated to the claim, flag it."""
        passage = EvidencePassage(
            quote="Privacy Policy and Terms of Service. All rights reserved.",
            normalized_quote="privacy policy and terms of service. all rights reserved.",
            block_id="footer-1",
            dom_zone=DOMZone.FOOTER_DISCLAIMER,
            tag_name="footer"
        )
        rel_status, msg = self.verifier.verify_relevance(
            claim_text=self.claim_pricing.text,
            finding_status=ClaimStatus.SUPPORTED,
            passage=passage
        )
        self.assertEqual(rel_status, RelevanceStatus.IRRELEVANT)

    def test_missing_claim_cannot_retain_quote(self):
        """Missing or Unverifiable findings must strictly have zero attached quote."""
        assessment = AuditFinding(
            claim_id=self.claim_pricing.claim_id,
            canonical_id=self.claim_pricing.canonical_id,
            ad_claim_text=self.claim_pricing.text,
            claim_materiality=self.claim_pricing.materiality,
            status=ClaimStatus.MISSING,
            reason_code=ReasonCode.CLAIM_NOT_FOUND,
            severity=Severity.HIGH,
            confidence=Confidence.HIGH,
            comparison=ComparisonRecord(claim_id=self.claim_pricing.claim_id),
            primary_evidence=EvidencePassage(
                quote="some accidental quote",
                normalized_quote="some accidental quote",
                block_id="hero-1",
                dom_zone=DOMZone.HERO_CANDIDATE,
                tag_name="h1"
            ),
            explanation="Missing from landing page.",
            recommended_ad_fix="",
            recommended_page_fix=""
        )
        records = self.verifier.audit_and_harden_finding(
            finding=assessment,
            blocks=self.sample_blocks,
            snapshot_id="snap_12345"
        )
        self.assertIsNone(assessment.primary_evidence)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].verification_status, VerificationStatus.INVALID)
        self.assertIn("cannot be attached to a MISSING claim", records[0].rejection_reason)

    def test_recovery_on_misattributed_quote(self):
        """If a valid quote has the wrong block_id, verifier attempts to recover correct block."""
        quote = "zero upfront fees"
        claim_zero = AtomicClaim(
            claim_id="c_zero",
            canonical_id="canon_zero",
            text="Zero upfront fees",
            claim_type=ClaimType.PRICE_POINT,
            subject="fees",
            predicate="upfront",
            source="ad_headline",
            is_factual=True
        )
        assessment = AuditFinding(
            claim_id=claim_zero.claim_id,
            canonical_id=claim_zero.canonical_id,
            ad_claim_text=claim_zero.text,
            claim_materiality=claim_zero.materiality,
            status=ClaimStatus.SUPPORTED,
            reason_code=ReasonCode.EXACT_MATCH,
            severity=Severity.INFO,
            confidence=Confidence.HIGH,
            comparison=ComparisonRecord(claim_id=claim_zero.claim_id),
            primary_evidence=EvidencePassage(
                quote=quote,
                normalized_quote=quote,
                block_id="wrong_block_id",
                dom_zone=DOMZone.MAIN_BODY,
                tag_name="p"
            ),
            explanation="Claim supported.",
            recommended_ad_fix="",
            recommended_page_fix=""
        )
        records = self.verifier.audit_and_harden_finding(
            finding=assessment,
            blocks=self.sample_blocks,
            snapshot_id="snap_12345"
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].verification_status, VerificationStatus.VERIFIED)
        self.assertEqual(assessment.primary_evidence.block_id, "hero-1")
        self.assertEqual(assessment.primary_evidence.dom_zone, DOMZone.HERO_CANDIDATE)

if __name__ == "__main__":
    unittest.main()

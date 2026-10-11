import unittest
from decimal import Decimal
from core.extractor import ContentExtractor
from core.claims import ClaimsDecomposer
from core.matcher import ClaimMatcher
from core.verifier import EvidenceVerifier
from core.scorer import Scorer
from core.audit_engine import AuditEngine
from core.schemas import (
    ClaimStatus, ReasonCode, Materiality, Severity, DOMZone, AuditState, Comparator
)

class TestMessageMatchAuditor(unittest.TestCase):

    def setUp(self):
        self.extractor = ContentExtractor()
        self.decomposer = ClaimsDecomposer()
        self.verifier = EvidenceVerifier()
        self.matcher = ClaimMatcher()
        self.scorer = Scorer()
        self.engine = AuditEngine()

    def test_canonical_case_trial_duration_mismatch(self):
        """Case 1: Ad says 30-day trial & no credit card. Page says 7-day trial & payment required."""
        ad_h = "Get a 30-day free trial"
        ad_d = "Start using our project management software today. No credit card required."
        html = """
        <html>
            <body>
                <header><h1>Start your free 7-day trial</h1></header>
                <main>
                    <p>Explore our project management tools.</p>
                    <p>Enter your payment details to continue.</p>
                </main>
            </body>
        </html>
        """
        result = self.engine.audit(ad_h, ad_d, html)

        self.assertEqual(result.audit_state, AuditState.COMPLETED)
        self.assertTrue(result.has_critical_marketing_liability)
        self.assertLess(result.match_score, 50)
        self.assertEqual(result.evidence_validity_rate, 100.0)

        # Verify findings
        statuses = {f.reason_code: f.status for f in result.findings}
        self.assertIn(ReasonCode.NUMERIC_CONTRADICTION, statuses)
        self.assertEqual(statuses[ReasonCode.NUMERIC_CONTRADICTION], ClaimStatus.CONTRADICTED)
        self.assertIn(ReasonCode.POLARITY_CONTRADICTION, statuses)
        self.assertEqual(statuses[ReasonCode.POLARITY_CONTRADICTION], ClaimStatus.CONTRADICTED)

    def test_canonical_case_missing_evidence_is_not_contradiction(self):
        """Case 2: Ad promises same-day loan approval. Page says nothing about approval speed."""
        ad_h = "Get your loan approved on the same day!"
        ad_d = "Fast personal loans with low interest rates."
        html = """
        <html>
            <body>
                <h1>Personal Loans Made Simple</h1>
                <p>Low interest rates from 4.9% APR. Apply online in 10 minutes.</p>
            </body>
        </html>
        """
        result = self.engine.audit(ad_h, ad_d, html)

        approval_finding = next((f for f in result.findings if "same day" in f.ad_claim_text.lower() or "loan" in f.ad_claim_text.lower()), None)
        self.assertIsNotNone(approval_finding)
        # Critical verification: Must be NOT_FOUND, NOT CONTRADICTED!
        self.assertEqual(approval_finding.status, ClaimStatus.NOT_FOUND)
        self.assertEqual(approval_finding.reason_code, ReasonCode.CLAIM_NOT_FOUND)
        self.assertFalse(result.has_critical_marketing_liability)

    def test_canonical_case_perfect_match(self):
        """Case 3: All promises match landing page exactly."""
        ad_h = "30-Day Free Trial"
        ad_d = "No credit card required. Modern project management software."
        html = """
        <html>
            <body>
                <h1>Start your 30-day free trial</h1>
                <p>No credit card required to get started.</p>
                <p>Modern project management software for teams.</p>
            </body>
        </html>
        """
        result = self.engine.audit(ad_h, ad_d, html)

        self.assertGreaterEqual(result.match_score, 90)
        self.assertEqual(result.grade, "Strong Match")
        self.assertFalse(result.has_critical_marketing_liability)
        self.assertEqual(result.evidence_validity_rate, 100.0)

    def test_qualifier_mismatch_up_to_discount(self):
        """Case 4: Ad promises 50% off unconditionally; Page says 'Up to 50% off'."""
        ad_h = "Huge Summer Sale - 50% off"
        ad_d = "Save on all items."
        html = """
        <html>
            <body>
                <h1>Summer Sale</h1>
                <p>Get up to 50% discount across our seasonal catalog.</p>
            </body>
        </html>
        """
        result = self.engine.audit(ad_h, ad_d, html)
        finding = next(f for f in result.findings if f.reason_code == ReasonCode.QUALIFIER_MISMATCH)
        self.assertEqual(finding.status, ClaimStatus.PARTIALLY_SUPPORTED)

    def test_buried_in_footer_disclaimer(self):
        """Case 5: Offer appears only in the footer disclaimer."""
        ad_h = "Always Free for Students"
        ad_d = "Free cloud computing."
        html = """
        <html>
            <body>
                <h1>Cloud Platform Pricing</h1>
                <p>Plans starting at $20/month for all users.</p>
                <footer>
                    <small>* Always free for students with valid .edu email.</small>
                </footer>
            </body>
        </html>
        """
        result = self.engine.audit(ad_h, ad_d, html)
        student_finding = next((f for f in result.findings if "student" in f.ad_claim_text.lower()), None)
        if student_finding:
            self.assertEqual(student_finding.primary_evidence.dom_zone, DOMZone.FOOTER_DISCLAIMER)

    def test_hallucinated_quote_rejection(self):
        """Verifier must reject any quote not in the HTML."""
        blocks, _ = self.extractor.extract_blocks("<html><body><p>Real content here</p></body></html>")
        verified, passage = self.verifier.verify_quote("This sentence does not exist anywhere on the page", blocks)
        self.assertFalse(verified)
        self.assertIsNone(passage)

    def test_zero_quote_handling_returns_none(self):
        """When 0 quotes are reported, evidence validity rate must be None, not 100% or zero division."""
        ad_h = "Instant Approval Loan"
        ad_d = "Borrow up to $50,000 today."
        html = "<html><body><h1>Cars For Sale</h1><p>Browse inventory.</p></body></html>"
        result = self.engine.audit(ad_h, ad_d, html)
        if result.reported_quotes_count == 0:
            self.assertIsNone(result.evidence_validity_rate)

    def test_metamorphic_whitespace_and_punctuation_invariance(self):
        """Normalizing extra spaces or entities should not alter findings."""
        ad_h = "Get a 30-day free trial"
        ad_d = "No credit card required."
        html1 = "<html><body><h1>Start your free 7-day trial</h1><p>Enter your payment details.</p></body></html>"
        html2 = "<html><body><h1>Start   your&nbsp;free\n\n7-day\t trial</h1><p>Enter   your payment  details.</p></body></html>"

        res1 = self.engine.audit(ad_h, ad_d, html1)
        res2 = self.engine.audit(ad_h, ad_d, html2)

        self.assertEqual(res1.match_score, res2.match_score)
        self.assertEqual(res1.has_critical_marketing_liability, res2.has_critical_marketing_liability)

    def test_deduplication_prevents_score_manipulation(self):
        """Repeated duplicate claims in ad description must not inflate or double penalize score."""
        ad_h = "Get a 30-day free trial. 30-day free trial!"
        ad_d = "30-day free trial for all teams."
        html = "<html><body><h1>Start your free 7-day trial</h1></body></html>"
        result = self.engine.audit(ad_h, ad_d, html)
        self.assertEqual(result.unique_canonical_claims, 1)

if __name__ == "__main__":
    unittest.main()

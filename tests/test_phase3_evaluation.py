import unittest
from decimal import Decimal
from core.audit_engine import AuditEngine
from core.schemas import ClaimStatus, ReasonCode, Severity, Materiality

class TestPhase3ClaimEvaluation(unittest.TestCase):

    def setUp(self):
        self.engine = AuditEngine()

    def test_supported_status_when_evidence_matches(self):
        """Supported only when evidence establishes the claim."""
        ad_h = "Simple Accounting for Small Teams"
        ad_d = "Plans starting at $15/month. Work with confidence."
        html = """
        <html><body>
            <h1>Simple Accounting Software</h1>
            <p>Our standard plan starts at $15/month for all teams.</p>
        </body></html>
        """
        result = self.engine.audit(ad_h, ad_d, html)
        price_finding = next((f for f in result.findings if "$15" in f.ad_claim_text), None)
        self.assertIsNotNone(price_finding)
        self.assertEqual(price_finding.status, ClaimStatus.SUPPORTED)

    def test_contradicted_status_on_explicit_conflict(self):
        """Contradicted only when retrieved evidence explicitly conflicts."""
        ad_h = "Same-Day Loan Approval"
        ad_d = "Get approved today."
        html = """
        <html><body>
            <h1>Business Loans</h1>
            <p>Applications take 5 to 7 business days for approval.</p>
        </body></html>
        """
        result = self.engine.audit(ad_h, ad_d, html)
        timeline_finding = next((f for f in result.findings if "same-day" in f.ad_claim_text.lower()), None)
        self.assertIsNotNone(timeline_finding)
        self.assertEqual(timeline_finding.status, ClaimStatus.CONTRADICTED)
        self.assertEqual(timeline_finding.reason_code, ReasonCode.TIMELINE_MISMATCH)

    def test_missing_status_when_absent(self):
        """Missing when adequate supporting evidence was not found in inspected content."""
        ad_h = "24/7 Live Customer Support"
        ad_d = "Cloud database hosting."
        html = """
        <html><body>
            <h1>Cloud Database Hosting</h1>
            <p>Fast and reliable managed MySQL and Postgres databases.</p>
        </body></html>
        """
        result = self.engine.audit(ad_h, ad_d, html)
        support_finding = next((f for f in result.findings if "support" in f.ad_claim_text.lower()), None)
        self.assertIsNotNone(support_finding)
        self.assertEqual(support_finding.status, ClaimStatus.MISSING)
        self.assertEqual(support_finding.reason_code, ReasonCode.CLAIM_NOT_FOUND)

    def test_partially_supported_explains_both_halves(self):
        """Partial support identifies supported portion and unsupported condition."""
        ad_h = "50% Off Everything"
        ad_d = "Summer clearance."
        html = """
        <html><body>
            <h1>Summer Sale</h1>
            <p>Get up to 50% discount on select seasonal items.</p>
        </body></html>
        """
        result = self.engine.audit(ad_h, ad_d, html)
        discount_finding = next((f for f in result.findings if "50%" in f.ad_claim_text), None)
        self.assertIsNotNone(discount_finding)
        self.assertEqual(discount_finding.status, ClaimStatus.PARTIALLY_SUPPORTED)
        self.assertIn("up to", discount_finding.explanation.lower())

    def test_guarantee_contradiction_flags_critical_liability(self):
        """Guarantee contradiction triggers critical marketing liability."""
        ad_h = "30-Day Money-Back Guarantee"
        ad_d = "Risk-free trial."
        html = """
        <html><body>
            <h1>Software License</h1>
            <p>All sales are final. We maintain a strict non-refundable policy.</p>
        </body></html>
        """
        result = self.engine.audit(ad_h, ad_d, html)
        guarantee_finding = next((f for f in result.findings if "guarantee" in f.ad_claim_text.lower()), None)
        self.assertIsNotNone(guarantee_finding)
        self.assertEqual(guarantee_finding.status, ClaimStatus.CONTRADICTED)
        self.assertEqual(guarantee_finding.severity, Severity.CRITICAL)
        self.assertTrue(result.has_critical_marketing_liability)

if __name__ == "__main__":
    unittest.main()

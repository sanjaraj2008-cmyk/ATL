import json
import unittest
from core.audit_engine import AuditEngine
from core.schemas import AuditState, ClaimStatus

class TestPhase7StructuredOutput(unittest.TestCase):
    def setUp(self):
        self.engine = AuditEngine()
        self.sample_html = """
        <!DOCTYPE html>
        <html>
        <head><title>CloudPayroll Pro</title></head>
        <body>
            <div class="hero">
                <h1>Automated Payroll Starting at $29/mo</h1>
                <p>Run payroll in 5 minutes with zero upfront fees.</p>
            </div>
            <div class="pricing">
                <p>No credit card required for our 14-day free trial.</p>
            </div>
            <footer>
                <p>*Prices exclude state tax filing fees.</p>
            </footer>
        </body>
        </html>
        """

    def test_valid_json_serialization(self):
        """Phase 7: Return valid JSON conforming to the application's schema."""
        result = self.engine.audit(
            ad_headline="Automated Payroll | $29/mo",
            ad_description="Run payroll in 5 minutes. No credit card required.",
            landing_page_html=self.sample_html
        )
        json_str = result.to_json()
        self.assertIsInstance(json_str, str)
        parsed = json.loads(json_str)
        self.assertEqual(parsed["audit_state"], AuditState.COMPLETED.value)
        self.assertIn("match_score", parsed)
        self.assertIn("findings", parsed)
        self.assertIn("citation_records", parsed)

    def test_structured_report_fields_completeness(self):
        """Phase 7: Verify all required fields in the standardized audit report."""
        result = self.engine.audit(
            ad_headline="Automated Payroll | $29/mo",
            ad_description="Run payroll in 5 minutes. 24/7 dedicated telephone support.",
            landing_page_html=self.sample_html
        )
        report = result.to_structured_report()

        # 1. Audit status
        self.assertIn("audit_status", report)
        self.assertEqual(report["audit_status"], "COMPLETED")

        # 2. Overall score or reason scoring is not possible
        self.assertIn("overall_score", report)
        self.assertIsInstance(report["overall_score"], int)
        self.assertIn("scoring_unavailability_reason", report)

        # 3. Scoring methodology version
        self.assertIn("scoring_methodology_version", report)
        self.assertEqual(report["scoring_methodology_version"], "1.0.0-evidence-weighted")

        # 4. Evidence coverage & prominence
        self.assertIn("evidence_coverage_index", report)
        self.assertIn("evidence_prominence_index", report)

        # 5. Individual claims & detailed verification
        self.assertIn("individual_claims", report)
        self.assertGreater(len(report["individual_claims"]), 0)

        for claim_item in report["individual_claims"]:
            self.assertIn("claim_id", claim_item)
            self.assertIn("ad_claim_text", claim_item)
            self.assertIn("status", claim_item)
            self.assertIn("severity", claim_item)
            self.assertIn("priority_rank", claim_item)
            self.assertIn("explanation", claim_item)
            self.assertIn("recommended_ad_fix", claim_item)
            self.assertIn("recommended_page_fix", claim_item)

            # Absence guarantee
            if claim_item["status"] in (ClaimStatus.MISSING.value, ClaimStatus.UNVERIFIABLE.value):
                self.assertIsNone(claim_item["quotation"])
                self.assertIsNone(claim_item["source_location"])
            elif claim_item["status"] == ClaimStatus.SUPPORTED.value:
                self.assertIsNotNone(claim_item["quotation"])
                self.assertIsNotNone(claim_item["source_location"])
                loc = claim_item["source_location"]
                self.assertIn("block_id", loc)
                self.assertIn("dom_zone", loc)
                self.assertIn("start_offset", loc)
                self.assertIn("end_offset", loc)

        # 6. Uncertainties and retrieval limitations
        self.assertIn("retrieval_limitations_and_uncertainties", report)

    def test_failed_audit_unavailability_reason(self):
        """Phase 7: If evidence is unreadable, report limitation instead of inventing score."""
        result = self.engine.audit(
            ad_headline="",
            ad_description="",
            landing_page_html=""
        )
        report = result.to_structured_report()

        self.assertEqual(report["audit_status"], "FAILED_UNREADABLE_INPUT")
        self.assertIsNone(report["overall_score"])
        self.assertIsNotNone(report["scoring_unavailability_reason"])
        self.assertIn("empty", report["scoring_unavailability_reason"].lower())

    def test_json_dumps_cleanly(self):
        """Ensure report can be cleanly serialized to JSON with standard json.dumps."""
        result = self.engine.audit(
            ad_headline="Payroll Software",
            ad_description="Fast payroll",
            landing_page_html=self.sample_html
        )
        report = result.to_structured_report()
        dumped = json.dumps(report, indent=2)
        reloaded = json.loads(dumped)
        self.assertEqual(reloaded["overall_score"], report["overall_score"])

if __name__ == "__main__":
    unittest.main()

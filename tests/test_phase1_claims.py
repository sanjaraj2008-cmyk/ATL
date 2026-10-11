import unittest
from decimal import Decimal
from core.claims import ClaimsDecomposer
from core.schemas import ClaimType, Materiality, Polarity, Comparator

class TestPhase1ClaimsDecomposer(unittest.TestCase):

    def setUp(self):
        self.decomposer = ClaimsDecomposer()

    def test_headline_body_and_cta_ingestion(self):
        """Verifies ingestion of headline, body copy, and call to action."""
        headline = "Get 50% Off Your First Year"
        description = "Modern cloud analytics. No credit card required."
        cta = "Start your 14-day free trial now"

        claims = self.decomposer.decompose(headline, description, cta)
        self.assertGreaterEqual(len(claims), 3)

        sources = {c.source for c in claims}
        self.assertIn("ad_headline", sources)
        self.assertIn("ad_description", sources)
        self.assertIn("ad_call_to_action", sources)

    def test_exact_source_span_preserved(self):
        """Verifies original wording and exact source span are preserved."""
        headline = "30-Day Money-Back Guarantee | Billed Annually"
        claims = self.decomposer.decompose(headline, "")

        guarantee_claim = next(c for c in claims if c.claim_type == ClaimType.GUARANTEE)
        self.assertIn("30-day money-back guarantee", guarantee_claim.text.lower())
        self.assertIn("billed annually", guarantee_claim.qualifiers)
        self.assertEqual(guarantee_claim.source_span, guarantee_claim.text)
        self.assertTrue(guarantee_claim.is_factual)

    def test_guarantee_extraction(self):
        """Identifies money-back and satisfaction guarantees with numeric timeframes."""
        claims = self.decomposer.decompose("60-Day Money-Back Guarantee", "100% satisfaction guaranteed.")
        guarantee_claims = [c for c in claims if c.claim_type == ClaimType.GUARANTEE]
        self.assertGreaterEqual(len(guarantee_claims), 1)

        first_g = guarantee_claims[0]
        self.assertIsNotNone(first_g.numeric)
        self.assertEqual(first_g.numeric.value, Decimal("60"))
        self.assertEqual(first_g.numeric.unit, "day")

    def test_price_point_and_apr_extraction(self):
        """Identifies base prices, monthly/annual tiers, and 0% APR financing."""
        claims = self.decomposer.decompose("Starting at $9/month", "0% APR for 12 months with approved credit.")
        price_claims = [c for c in claims if c.claim_type == ClaimType.PRICE_POINT]
        self.assertEqual(len(price_claims), 2)

        monthly = next(c for c in price_claims if c.subject == "pricing_tier")
        self.assertEqual(monthly.numeric.value, Decimal("9"))
        self.assertEqual(monthly.numeric.unit, "dollar")
        self.assertEqual(monthly.numeric.time_basis, "month")

        apr = next(c for c in price_claims if c.subject == "financing_terms")
        self.assertEqual(apr.numeric.value, Decimal("0"))
        self.assertEqual(apr.numeric.unit, "percent")

    def test_product_capabilities_and_specs(self):
        """Identifies uptime SLAs, 24/7 support, and unlimited resource claims."""
        headline = "99.9% Uptime SLA Guaranteed"
        body = "24/7 live customer support with unlimited cloud storage."
        claims = self.decomposer.decompose(headline, body)

        capability_claims = [c for c in claims if c.claim_type == ClaimType.PRODUCT_CAPABILITY]
        self.assertGreaterEqual(len(capability_claims), 2)
        self.assertTrue(all(c.is_factual for c in capability_claims))
        self.assertTrue(all(c.materiality == Materiality.HIGH for c in capability_claims))

    def test_material_qualifiers_preserved(self):
        """Material qualifiers (billed annually, for new customers only, contract) must be captured."""
        headline = "Save 40% on Enterprise - Billed Annually"
        body = "Offer valid for new customers only. Subject to credit approval."
        claims = self.decomposer.decompose(headline, body)

        discount_claim = next(c for c in claims if c.claim_type == ClaimType.PRICING_DISCOUNT)
        self.assertIn("billed annually", discount_claim.qualifiers)

        condition_claims = [c for c in claims if "new customers only" in c.qualifiers or "subject to credit approval" in c.qualifiers]
        self.assertGreaterEqual(len(condition_claims), 1)

    def test_separation_of_subjective_marketing_and_cta(self):
        """Subjective puffery and pure CTAs must be distinguished from factual claims."""
        headline = "The World's Best CRM Software"
        body = "Award-winning customer management platform. Get started today!"
        claims = self.decomposer.decompose(headline, body)

        non_factual = [c for c in claims if not c.is_factual]
        self.assertGreaterEqual(len(non_factual), 2)

        types = {c.claim_type for c in non_factual}
        self.assertTrue(ClaimType.SUBJECTIVE_MARKETING in types or ClaimType.CALL_TO_ACTION in types)
        self.assertTrue(all(c.materiality == Materiality.LOW for c in non_factual))

    def test_no_invented_claims_for_empty_ad(self):
        """Does not invent claims when input is empty."""
        claims = self.decomposer.decompose("", "", "")
        self.assertEqual(claims, [])

if __name__ == "__main__":
    unittest.main()

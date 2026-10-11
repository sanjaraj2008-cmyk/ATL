import re
from decimal import Decimal
from typing import List, Optional, Tuple
from core.schemas import (
    AtomicClaim, DOMBlock, ComparisonRecord, AuditFinding, ClaimStatus,
    ReasonCode, Severity, Confidence, DOMZone, ClaimType, Comparator, Polarity,
    EvidencePassage, RelevanceStatus
)
from core.verifier import EvidenceVerifier

class ClaimMatcher:
    """
    Compares atomic claims against verified DOMBlocks.
    Performs deterministic evaluation of numbers, units, negation/polarity, and timeline promises.
    """

    def __init__(self):
        self.verifier = EvidenceVerifier()

    def evaluate_claim(self, claim: AtomicClaim, blocks: List[DOMBlock]) -> AuditFinding:
        # Phase 3: Route by claim type for specialized evidence evaluation
        if claim.claim_type == ClaimType.TRIAL_DURATION:
            return self._match_trial_duration(claim, blocks)
        elif claim.claim_type == ClaimType.REQUIREMENT_FRICTION:
            return self._match_friction(claim, blocks)
        elif claim.claim_type == ClaimType.APPROVAL_TIMELINE:
            return self._match_approval_timeline(claim, blocks)
        elif claim.claim_type == ClaimType.PRICING_DISCOUNT:
            return self._match_discount(claim, blocks)
        elif claim.claim_type == ClaimType.PRICE_POINT:
            return self._match_price_point(claim, blocks)
        elif claim.claim_type == ClaimType.GUARANTEE:
            return self._match_guarantee(claim, blocks)
        elif claim.claim_type == ClaimType.PRODUCT_CAPABILITY:
            return self._match_capability(claim, blocks)
        elif claim.claim_type == ClaimType.AVAILABILITY_CONDITION:
            return self._match_condition(claim, blocks)
        else:
            return self._match_general_claim(claim, blocks)

    def _match_trial_duration(self, claim: AtomicClaim, blocks: List[DOMBlock]) -> AuditFinding:
        expected_days = claim.numeric.value if claim.numeric else None
        
        # Scan blocks for trial mentions
        candidate_blocks = []
        for block in blocks:
            b_text = block.normalized_text.lower()
            if 'trial' in b_text or 'free' in b_text:
                candidate_blocks.append(block)

        found_contradiction = None
        found_support = None

        for b in candidate_blocks:
            match = re.search(r'(\d+)[-\s]*(day|week|month)s?\s*(?:free\s*)?trial|free\s*trial(?:\s*for)?\s*(\d+)[-\s]*(day|week|month)s?', b.normalized_text.lower())
            if match:
                days_found = Decimal(match.group(1) or match.group(3))
                unit = match.group(2) or match.group(4)
                if 'week' in unit:
                    days_found *= Decimal(7)
                elif 'month' in unit:
                    days_found *= Decimal(30)

                verified, passage = self.verifier.verify_quote(b.raw_text, blocks)
                if not verified:
                    continue

                if expected_days and days_found != expected_days:
                    found_contradiction = (passage, days_found)
                    break
                elif expected_days and days_found == expected_days:
                    found_support = passage

        # Contradiction detected
        if found_contradiction:
            passage, days_found = found_contradiction
            return AuditFinding(
                claim_id=claim.claim_id,
                canonical_id=claim.canonical_id,
                ad_claim_text=claim.text,
                claim_materiality=claim.materiality,
                status=ClaimStatus.CONTRADICTED,
                reason_code=ReasonCode.NUMERIC_CONTRADICTION,
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                comparison=ComparisonRecord(
                    claim_id=claim.claim_id,
                    subject_match=True,
                    predicate_match=True,
                    numeric_match=False,
                    polarity_match=True,
                    evidence_passages=[passage]
                ),
                primary_evidence=passage,
                explanation=f"Advertisement promises a {expected_days}-day free trial, but landing page explicitly states a {days_found}-day trial.",
                recommended_ad_fix=f"Update ad headline to advertise a {days_found}-day free trial to match landing page.",
                recommended_page_fix=f"Extend landing page trial duration to {expected_days} days to honor advertised promise."
            )

        # Supported
        if found_support:
            return AuditFinding(
                claim_id=claim.claim_id,
                canonical_id=claim.canonical_id,
                ad_claim_text=claim.text,
                claim_materiality=claim.materiality,
                status=ClaimStatus.SUPPORTED,
                reason_code=ReasonCode.EXACT_MATCH,
                severity=Severity.INFO,
                confidence=Confidence.HIGH,
                comparison=ComparisonRecord(
                    claim_id=claim.claim_id,
                    subject_match=True,
                    predicate_match=True,
                    numeric_match=True,
                    polarity_match=True,
                    evidence_passages=[found_support]
                ),
                primary_evidence=found_support,
                explanation=f"Landing page prominently offers the advertised {expected_days}-day trial period.",
                recommended_ad_fix="No change required.",
                recommended_page_fix="No change required."
            )

        # Not Found
        return AuditFinding(
            claim_id=claim.claim_id,
            canonical_id=claim.canonical_id,
            ad_claim_text=claim.text,
            claim_materiality=claim.materiality,
            status=ClaimStatus.NOT_FOUND,
            reason_code=ReasonCode.CLAIM_NOT_FOUND,
            severity=Severity.MEDIUM,
            confidence=Confidence.HIGH,
            comparison=ComparisonRecord(
                claim_id=claim.claim_id,
                subject_match=False,
                predicate_match=False
            ),
            explanation="The landing page does not mention trial duration anywhere on the page.",
            recommended_ad_fix="Remove specific trial duration from ad unless clarified on page.",
            recommended_page_fix=f"Add clear mention of the {expected_days}-day free trial offer in the hero section."
        )

    def _match_friction(self, claim: AtomicClaim, blocks: List[DOMBlock]) -> AuditFinding:
        # e.g., Ad says "No credit card required" (Polarity.NEGATIVE)
        payment_required_blocks = []
        payment_not_required_blocks = []

        for b in blocks:
            text_lower = b.normalized_text.lower()
            
            # Check support FIRST (no credit card needed/required)
            if re.search(r'no\s+(?:credit\s*)?card\s*(?:required|needed)?|no\s*payment\s*(?:required|details|needed)', text_lower):
                verified, passage = self.verifier.verify_quote(b.raw_text, blocks)
                if verified:
                    payment_not_required_blocks.append(passage)
                    continue

            # Signs of contradiction (explicitly asking for payment/card to continue or signup)
            if re.search(r'enter\s*(?:your\s*)?(?:payment|card|billing|credit\s*card)\s*(?:details|info|information)?|credit\s*card\s*required|payment\s*required', text_lower):
                verified, passage = self.verifier.verify_quote(b.raw_text, blocks)
                if verified:
                    payment_required_blocks.append(passage)

        if payment_not_required_blocks:
            passage = payment_not_required_blocks[0]
            return AuditFinding(
                claim_id=claim.claim_id,
                canonical_id=claim.canonical_id,
                ad_claim_text=claim.text,
                claim_materiality=claim.materiality,
                status=ClaimStatus.SUPPORTED,
                reason_code=ReasonCode.EXACT_MATCH,
                severity=Severity.INFO,
                confidence=Confidence.HIGH,
                comparison=ComparisonRecord(
                    claim_id=claim.claim_id,
                    subject_match=True,
                    predicate_match=True,
                    polarity_match=True,
                    evidence_passages=[passage]
                ),
                primary_evidence=passage,
                explanation="Landing page verifies that no credit card is needed to get started.",
                recommended_ad_fix="No change required.",
                recommended_page_fix="No change required."
            )

        if payment_required_blocks:
            passage = payment_required_blocks[0]
            return AuditFinding(
                claim_id=claim.claim_id,
                canonical_id=claim.canonical_id,
                ad_claim_text=claim.text,
                claim_materiality=claim.materiality,
                status=ClaimStatus.CONTRADICTED,
                reason_code=ReasonCode.POLARITY_CONTRADICTION,
                severity=Severity.CRITICAL,
                confidence=Confidence.HIGH,
                comparison=ComparisonRecord(
                    claim_id=claim.claim_id,
                    subject_match=True,
                    predicate_match=True,
                    polarity_match=False,
                    evidence_passages=[passage]
                ),
                primary_evidence=passage,
                explanation="Ad promises 'No credit card required', but the landing page demands payment/billing details to proceed.",
                recommended_ad_fix="Remove 'No credit card required' from ad copy.",
                recommended_page_fix="Remove mandatory payment details field from the trial signup form."
            )

        return AuditFinding(
            claim_id=claim.claim_id,
            canonical_id=claim.canonical_id,
            ad_claim_text=claim.text,
            claim_materiality=claim.materiality,
            status=ClaimStatus.NOT_FOUND,
            reason_code=ReasonCode.CLAIM_NOT_FOUND,
            severity=Severity.MEDIUM,
            confidence=Confidence.HIGH,
            comparison=ComparisonRecord(
                claim_id=claim.claim_id,
                subject_match=False,
                predicate_match=False
            ),
            explanation="The landing page does not mention credit card or payment requirements.",
            recommended_ad_fix="Ensure ad aligns with signup steps stated on page.",
            recommended_page_fix="Explicitly state 'No credit card required' near the call-to-action button to boost conversions."
        )

    def _match_approval_timeline(self, claim: AtomicClaim, blocks: List[DOMBlock]) -> AuditFinding:
        # e.g., Ad says "Same-day approval"
        speed_mentions = []
        contradictions = []

        for b in blocks:
            text_lower = b.normalized_text.lower()
            if 'same-day' in text_lower or 'same day' in text_lower or 'instant approval' in text_lower:
                verified, passage = self.verifier.verify_quote(b.raw_text, blocks)
                if verified:
                    speed_mentions.append(passage)
            # Check for multi-day statements e.g. "takes 3 to 5 business days", "within 7 days"
            multi_day = re.search(r'(\d+)\s*(?:to\s*\d+\s*)?(?:business\s*)?days?\s*(?:for\s*approval|to\s*approve|decision)', text_lower)
            if multi_day and Decimal(multi_day.group(1)) > Decimal(1):
                verified, passage = self.verifier.verify_quote(b.raw_text, blocks)
                if verified:
                    contradictions.append((passage, multi_day.group(1)))

        if contradictions:
            passage, days = contradictions[0]
            return AuditFinding(
                claim_id=claim.claim_id,
                canonical_id=claim.canonical_id,
                ad_claim_text=claim.text,
                claim_materiality=claim.materiality,
                status=ClaimStatus.CONTRADICTED,
                reason_code=ReasonCode.TIMELINE_MISMATCH,
                severity=Severity.CRITICAL,
                confidence=Confidence.HIGH,
                comparison=ComparisonRecord(
                    claim_id=claim.claim_id,
                    subject_match=True,
                    predicate_match=True,
                    numeric_match=False,
                    evidence_passages=[passage]
                ),
                primary_evidence=passage,
                explanation=f"Ad promises same-day approval, but landing page explicitly states approval takes up to {days} days.",
                recommended_ad_fix=f"Disclose realistic turnaround of {days} days in ad.",
                recommended_page_fix="Align landing page with expedited approval process if offered."
            )

        if speed_mentions:
            passage = speed_mentions[0]
            return AuditFinding(
                claim_id=claim.claim_id,
                canonical_id=claim.canonical_id,
                ad_claim_text=claim.text,
                claim_materiality=claim.materiality,
                status=ClaimStatus.SUPPORTED,
                reason_code=ReasonCode.EXACT_MATCH,
                severity=Severity.INFO,
                confidence=Confidence.HIGH,
                comparison=ComparisonRecord(
                    claim_id=claim.claim_id,
                    subject_match=True,
                    predicate_match=True,
                    evidence_passages=[passage]
                ),
                primary_evidence=passage,
                explanation="Landing page confirms same-day approval timeline.",
                recommended_ad_fix="No change required.",
                recommended_page_fix="No change required."
            )

        # Absence: Note this is an evidence gap (NOT_FOUND), NOT a contradiction!
        return AuditFinding(
            claim_id=claim.claim_id,
            canonical_id=claim.canonical_id,
            ad_claim_text=claim.text,
            claim_materiality=claim.materiality,
            status=ClaimStatus.NOT_FOUND,
            reason_code=ReasonCode.CLAIM_NOT_FOUND,
            severity=Severity.MEDIUM,
            confidence=Confidence.HIGH,
            comparison=ComparisonRecord(
                claim_id=claim.claim_id,
                subject_match=False,
                predicate_match=False
            ),
            explanation="The landing page does not mention approval speed or timeline anywhere on the page.",
            recommended_ad_fix="Do not promise same-day approval if the landing page does not corroborate it.",
            recommended_page_fix="Add clear turnaround time ('Approved same day') to the landing page hero copy."
        )

    def _match_discount(self, claim: AtomicClaim, blocks: List[DOMBlock]) -> AuditFinding:
        expected_pct = claim.numeric.value if claim.numeric else None
        
        found_matches = []
        found_contradictions = []

        for b in blocks:
            text_lower = b.normalized_text.lower()
            match = re.search(r'(up\s*to\s*)?(\d+)\s*(?:%|percent)\s*(?:off|discount)', text_lower)
            if match:
                is_up_to = bool(match.group(1))
                page_val = Decimal(match.group(2))
                verified, passage = self.verifier.verify_quote(b.raw_text, blocks)
                if not verified:
                    continue

                if expected_pct and page_val == expected_pct:
                    # Check comparator conflict e.g. ad says "50% off", page says "up to 50% off"
                    if not (claim.numeric.comparator == Comparator.UP_TO) and is_up_to:
                        found_contradictions.append((passage, page_val, ReasonCode.QUALIFIER_MISMATCH))
                    else:
                        found_matches.append(passage)
                elif expected_pct and page_val != expected_pct:
                    found_contradictions.append((passage, page_val, ReasonCode.NUMERIC_CONTRADICTION))

        if found_contradictions:
            passage, val, rcode = found_contradictions[0]
            if rcode == ReasonCode.QUALIFIER_MISMATCH:
                return AuditFinding(
                    claim_id=claim.claim_id,
                    canonical_id=claim.canonical_id,
                    ad_claim_text=claim.text,
                    claim_materiality=claim.materiality,
                    status=ClaimStatus.PARTIALLY_SUPPORTED,
                    reason_code=ReasonCode.QUALIFIER_MISMATCH,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.HIGH,
                    comparison=ComparisonRecord(
                        claim_id=claim.claim_id,
                        subject_match=True,
                        predicate_match=True,
                        qualifiers_conflict=True,
                        evidence_passages=[passage]
                    ),
                    primary_evidence=passage,
                    explanation=f"Ad promises an unconditional {expected_pct}% discount, but landing page qualifies it as 'up to {val}% off'.",
                    recommended_ad_fix=f"Include 'Up to' qualifier in ad copy: 'Save up to {val}%'.",
                    recommended_page_fix="Clarify site-wide vs category-specific discount eligibility."
                )
            else:
                return AuditFinding(
                    claim_id=claim.claim_id,
                    canonical_id=claim.canonical_id,
                    ad_claim_text=claim.text,
                    claim_materiality=claim.materiality,
                    status=ClaimStatus.CONTRADICTED,
                    reason_code=ReasonCode.NUMERIC_CONTRADICTION,
                    severity=Severity.HIGH,
                    confidence=Confidence.HIGH,
                    comparison=ComparisonRecord(
                        claim_id=claim.claim_id,
                        subject_match=True,
                        predicate_match=True,
                        numeric_match=False,
                        evidence_passages=[passage]
                    ),
                    primary_evidence=passage,
                    explanation=f"Ad promises {expected_pct}% discount, but landing page only offers {val}% off.",
                    recommended_ad_fix=f"Update ad discount percentage to {val}%.",
                    recommended_page_fix=f"Match the advertised {expected_pct}% discount on page."
                )

        if found_matches:
            passage = found_matches[0]
            return AuditFinding(
                claim_id=claim.claim_id,
                canonical_id=claim.canonical_id,
                ad_claim_text=claim.text,
                claim_materiality=claim.materiality,
                status=ClaimStatus.SUPPORTED,
                reason_code=ReasonCode.EXACT_MATCH,
                severity=Severity.INFO,
                confidence=Confidence.HIGH,
                comparison=ComparisonRecord(
                    claim_id=claim.claim_id,
                    subject_match=True,
                    predicate_match=True,
                    evidence_passages=[passage]
                ),
                primary_evidence=passage,
                explanation=f"Landing page corroborates the advertised {expected_pct}% discount.",
                recommended_ad_fix="No change required.",
                recommended_page_fix="No change required."
            )

        return AuditFinding(
            claim_id=claim.claim_id,
            canonical_id=claim.canonical_id,
            ad_claim_text=claim.text,
            claim_materiality=claim.materiality,
            status=ClaimStatus.NOT_FOUND,
            reason_code=ReasonCode.CLAIM_NOT_FOUND,
            severity=Severity.HIGH,
            confidence=Confidence.HIGH,
            comparison=ComparisonRecord(
                claim_id=claim.claim_id,
                subject_match=False,
                predicate_match=False
            ),
            explanation=f"No mention of the advertised {expected_pct}% discount found on landing page.",
            recommended_ad_fix="Remove discount from ad if no longer running.",
            recommended_page_fix="Add promotional banner highlighting the discount."
        )

    def _match_general_claim(self, claim: AtomicClaim, blocks: List[DOMBlock]) -> AuditFinding:
        # Keyword token overlap matching with substantive candidate filtering
        tokens = [t.lower() for t in re.findall(r'\b[a-zA-Z]{3,}\b', claim.text)]
        candidates = self.verifier.find_best_candidate_passages(tokens, blocks)

        for best_block in candidates:
            verified, passage = self.verifier.verify_quote(best_block.raw_text, blocks)
            if verified and passage:
                rel_status, _ = self.verifier.verify_relevance(claim.text, ClaimStatus.SUPPORTED, passage)
                if rel_status != RelevanceStatus.RELEVANT:
                    continue

                # Check if buried in footer
                if passage.dom_zone == DOMZone.FOOTER_DISCLAIMER:
                    return AuditFinding(
                        claim_id=claim.claim_id,
                        canonical_id=claim.canonical_id,
                        ad_claim_text=claim.text,
                        claim_materiality=claim.materiality,
                        status=ClaimStatus.SUPPORTED,
                        reason_code=ReasonCode.BURIED_DISCLAIMER,
                        severity=Severity.LOW,
                        confidence=Confidence.MEDIUM,
                        comparison=ComparisonRecord(
                            claim_id=claim.claim_id,
                            subject_match=True,
                            predicate_match=True,
                            evidence_passages=[passage]
                        ),
                        primary_evidence=passage,
                        explanation="Claim is mentioned, but only appears buried in footer fine print / disclaimer.",
                        recommended_ad_fix="No change necessary.",
                        recommended_page_fix="Elevate this offer into the main hero or body section."
                    )

                return AuditFinding(
                    claim_id=claim.claim_id,
                    canonical_id=claim.canonical_id,
                    ad_claim_text=claim.text,
                    claim_materiality=claim.materiality,
                    status=ClaimStatus.SUPPORTED,
                    reason_code=ReasonCode.SEMANTIC_EQUIVALENT,
                    severity=Severity.INFO,
                    confidence=Confidence.MEDIUM,
                    comparison=ComparisonRecord(
                        claim_id=claim.claim_id,
                        subject_match=True,
                        predicate_match=True,
                        evidence_passages=[passage]
                    ),
                    primary_evidence=passage,
                    explanation="Landing page content supports this advertised feature.",
                    recommended_ad_fix="No change required.",
                    recommended_page_fix="No change required."
                )

        return AuditFinding(
            claim_id=claim.claim_id,
            canonical_id=claim.canonical_id,
            ad_claim_text=claim.text,
            claim_materiality=claim.materiality,
            status=ClaimStatus.NOT_FOUND,
            reason_code=ReasonCode.CLAIM_NOT_FOUND,
            severity=Severity.LOW,
            confidence=Confidence.HIGH,
            comparison=ComparisonRecord(
                claim_id=claim.claim_id,
                subject_match=False,
                predicate_match=False
            ),
            explanation="This general feature or statement was not explicitly found in page content.",
            recommended_ad_fix="Align ad description with features actually highlighted on page.",
            recommended_page_fix="Add descriptive copy supporting this product capability."
        )

    def _match_price_point(self, claim: AtomicClaim, blocks: List[DOMBlock]) -> AuditFinding:
        expected_num = claim.numeric.value if claim.numeric else None
        is_apr = claim.numeric and claim.numeric.unit == "percent"

        found_support = None
        found_contradiction = None
        found_partial = None

        for b in blocks:
            text_lower = b.normalized_text.lower()
            if is_apr:
                match = re.search(r'(\d+(?:\.\d+)?)\s*%\s*apr', text_lower)
                if match:
                    val = Decimal(match.group(1))
                    verified, passage = self.verifier.verify_quote(b.raw_text, blocks)
                    if not verified:
                        continue
                    if expected_num and val == expected_num:
                        if b.has_conditions or "qualified" in text_lower or b.dom_zone == DOMZone.FOOTER_DISCLAIMER:
                            found_partial = (passage, val, "requires qualification or terms")
                        else:
                            found_support = passage
                    elif expected_num and val != expected_num:
                        found_contradiction = (passage, val)
            else:
                match = re.search(r'\$(\d+(?:\.\d+)?)', text_lower)
                if match:
                    val = Decimal(match.group(1))
                    verified, passage = self.verifier.verify_quote(b.raw_text, blocks)
                    if not verified:
                        continue
                    if expected_num and val == expected_num:
                        if b.has_conditions or b.dom_zone == DOMZone.FOOTER_DISCLAIMER:
                            found_partial = (passage, val, "conditions or billing caveats apply")
                        else:
                            found_support = passage
                    elif expected_num and val != expected_num and val > expected_num:
                        found_contradiction = (passage, val)

        if found_contradiction:
            passage, val = found_contradiction
            unit_str = "% APR" if is_apr else "$"
            return AuditFinding(
                claim_id=claim.claim_id,
                canonical_id=claim.canonical_id,
                ad_claim_text=claim.text,
                claim_materiality=claim.materiality,
                status=ClaimStatus.CONTRADICTED,
                reason_code=ReasonCode.NUMERIC_CONTRADICTION,
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                comparison=ComparisonRecord(
                    claim_id=claim.claim_id,
                    subject_match=True,
                    predicate_match=True,
                    numeric_match=False,
                    evidence_passages=[passage]
                ),
                primary_evidence=passage,
                explanation=f"Ad promises {unit_str}{expected_num}, but landing page explicitly states {unit_str}{val}.",
                recommended_ad_fix=f"Update advertised price or rate to match landing page ({unit_str}{val}).",
                recommended_page_fix=f"Honor the advertised price or rate of {unit_str}{expected_num} on the page."
            )

        if found_partial:
            passage, val, caveat = found_partial
            return AuditFinding(
                claim_id=claim.claim_id,
                canonical_id=claim.canonical_id,
                ad_claim_text=claim.text,
                claim_materiality=claim.materiality,
                status=ClaimStatus.PARTIALLY_SUPPORTED,
                reason_code=ReasonCode.QUALIFIER_MISMATCH,
                severity=Severity.MEDIUM,
                confidence=Confidence.HIGH,
                comparison=ComparisonRecord(
                    claim_id=claim.claim_id,
                    subject_match=True,
                    predicate_match=True,
                    qualifiers_conflict=True,
                    evidence_passages=[passage]
                ),
                primary_evidence=passage,
                explanation=f"Partially supported: advertised rate/price is corroborated, but landing page imposes material caveats: {caveat}.",
                recommended_ad_fix="Disclose qualifications or billing conditions in ad copy.",
                recommended_page_fix="Elevate qualification criteria to reduce customer drop-off."
            )

        if found_support:
            return AuditFinding(
                claim_id=claim.claim_id,
                canonical_id=claim.canonical_id,
                ad_claim_text=claim.text,
                claim_materiality=claim.materiality,
                status=ClaimStatus.SUPPORTED,
                reason_code=ReasonCode.EXACT_MATCH,
                severity=Severity.INFO,
                confidence=Confidence.HIGH,
                comparison=ComparisonRecord(
                    claim_id=claim.claim_id,
                    subject_match=True,
                    predicate_match=True,
                    numeric_match=True,
                    evidence_passages=[found_support]
                ),
                primary_evidence=found_support,
                explanation="Landing page fully corroborates the advertised pricing structure.",
                recommended_ad_fix="No change required.",
                recommended_page_fix="No change required."
            )

        return AuditFinding(
            claim_id=claim.claim_id,
            canonical_id=claim.canonical_id,
            ad_claim_text=claim.text,
            claim_materiality=claim.materiality,
            status=ClaimStatus.MISSING,
            reason_code=ReasonCode.CLAIM_NOT_FOUND,
            severity=Severity.MEDIUM,
            confidence=Confidence.HIGH,
            comparison=ComparisonRecord(
                claim_id=claim.claim_id,
                subject_match=False,
                predicate_match=False
            ),
            explanation="The advertised price point or financing term was not found on the landing page.",
            recommended_ad_fix="Ensure price mentioned in ad is prominently displayed on the page.",
            recommended_page_fix="Add clear pricing or financing terms to the landing page."
        )

    def _match_guarantee(self, claim: AtomicClaim, blocks: List[DOMBlock]) -> AuditFinding:
        expected_days = claim.numeric.value if claim.numeric else None
        
        found_support = None
        found_contradiction = None

        for b in blocks:
            text_lower = b.normalized_text.lower()
            if "no refunds" in text_lower or "all sales final" in text_lower or "non-refundable" in text_lower:
                verified, passage = self.verifier.verify_quote(b.raw_text, blocks)
                if verified:
                    found_contradiction = passage
                    break
            if "guarantee" in text_lower or "money-back" in text_lower or "risk-free" in text_lower:
                verified, passage = self.verifier.verify_quote(b.raw_text, blocks)
                if verified:
                    found_support = passage

        if found_contradiction:
            return AuditFinding(
                claim_id=claim.claim_id,
                canonical_id=claim.canonical_id,
                ad_claim_text=claim.text,
                claim_materiality=claim.materiality,
                status=ClaimStatus.CONTRADICTED,
                reason_code=ReasonCode.POLARITY_CONTRADICTION,
                severity=Severity.CRITICAL,
                confidence=Confidence.HIGH,
                comparison=ComparisonRecord(
                    claim_id=claim.claim_id,
                    subject_match=True,
                    predicate_match=True,
                    polarity_match=False,
                    evidence_passages=[found_contradiction]
                ),
                primary_evidence=found_contradiction,
                explanation="Ad promises a money-back or satisfaction guarantee, but landing page explicitly disclaims refunds ('All sales final' / 'Non-refundable').",
                recommended_ad_fix="Remove guarantee claim from advertising copy immediately.",
                recommended_page_fix="Align return policy with advertised satisfaction guarantee."
            )

        if found_support:
            return AuditFinding(
                claim_id=claim.claim_id,
                canonical_id=claim.canonical_id,
                ad_claim_text=claim.text,
                claim_materiality=claim.materiality,
                status=ClaimStatus.SUPPORTED,
                reason_code=ReasonCode.EXACT_MATCH,
                severity=Severity.INFO,
                confidence=Confidence.HIGH,
                comparison=ComparisonRecord(
                    claim_id=claim.claim_id,
                    subject_match=True,
                    predicate_match=True,
                    evidence_passages=[found_support]
                ),
                primary_evidence=found_support,
                explanation="Landing page corroborates the advertised guarantee policy.",
                recommended_ad_fix="No change required.",
                recommended_page_fix="No change required."
            )

        return AuditFinding(
            claim_id=claim.claim_id,
            canonical_id=claim.canonical_id,
            ad_claim_text=claim.text,
            claim_materiality=claim.materiality,
            status=ClaimStatus.MISSING,
            reason_code=ReasonCode.CLAIM_NOT_FOUND,
            severity=Severity.HIGH,
            confidence=Confidence.HIGH,
            comparison=ComparisonRecord(
                claim_id=claim.claim_id,
                subject_match=False,
                predicate_match=False
            ),
            explanation="The advertised satisfaction guarantee was not mentioned on the landing page.",
            recommended_ad_fix="Add guarantee terms to landing page or remove guarantee promise from ad.",
            recommended_page_fix="Add prominent guarantee badge on the landing page."
        )

    def _match_capability(self, claim: AtomicClaim, blocks: List[DOMBlock]) -> AuditFinding:
        tokens = [t.lower() for t in re.findall(r'\b[a-zA-Z]{3,}\b', claim.text)]
        candidates = self.verifier.find_best_candidate_passages(tokens, blocks)

        for best_b in candidates:
            verified, passage = self.verifier.verify_quote(best_b.raw_text, blocks)
            if verified and passage:
                rel_status, _ = self.verifier.verify_relevance(claim.text, ClaimStatus.SUPPORTED, passage)
                if rel_status != RelevanceStatus.RELEVANT:
                    continue

                return AuditFinding(
                    claim_id=claim.claim_id,
                    canonical_id=claim.canonical_id,
                    ad_claim_text=claim.text,
                    claim_materiality=claim.materiality,
                    status=ClaimStatus.SUPPORTED,
                    reason_code=ReasonCode.SEMANTIC_EQUIVALENT,
                    severity=Severity.INFO,
                    confidence=Confidence.HIGH,
                    comparison=ComparisonRecord(
                        claim_id=claim.claim_id,
                        subject_match=True,
                        predicate_match=True,
                        evidence_passages=[passage]
                    ),
                    primary_evidence=passage,
                    explanation="Landing page corroborates the advertised capability.",
                    recommended_ad_fix="No change required.",
                    recommended_page_fix="No change required."
                )

        return AuditFinding(
            claim_id=claim.claim_id,
            canonical_id=claim.canonical_id,
            ad_claim_text=claim.text,
            claim_materiality=claim.materiality,
            status=ClaimStatus.MISSING,
            reason_code=ReasonCode.CLAIM_NOT_FOUND,
            severity=Severity.MEDIUM,
            confidence=Confidence.HIGH,
            comparison=ComparisonRecord(
                claim_id=claim.claim_id,
                subject_match=False,
                predicate_match=False
            ),
            explanation="The advertised product capability was not found in page content.",
            recommended_ad_fix="Align ad copy with features actually highlighted on the page.",
            recommended_page_fix="Add supporting technical specifications to the landing page."
        )

    def _match_condition(self, claim: AtomicClaim, blocks: List[DOMBlock]) -> AuditFinding:
        tokens = [t.lower() for t in re.findall(r'\b[a-zA-Z]{3,}\b', claim.text)]
        candidates = self.verifier.find_best_candidate_passages(tokens, blocks)

        for best_b in candidates:
            verified, passage = self.verifier.verify_quote(best_b.raw_text, blocks)
            if verified and passage:
                rel_status, _ = self.verifier.verify_relevance(claim.text, ClaimStatus.SUPPORTED, passage)
                if rel_status != RelevanceStatus.RELEVANT:
                    continue

                status = ClaimStatus.SUPPORTED
                explanation = "Landing page mentions this qualification or eligibility statement."
                if passage.dom_zone == DOMZone.FOOTER_DISCLAIMER:
                    status = ClaimStatus.PARTIALLY_SUPPORTED
                    explanation = "Partially supported: eligibility condition is mentioned, but only in the footer fine print."
                return AuditFinding(
                    claim_id=claim.claim_id,
                    canonical_id=claim.canonical_id,
                    ad_claim_text=claim.text,
                    claim_materiality=claim.materiality,
                    status=status,
                    reason_code=ReasonCode.EXACT_MATCH if status == ClaimStatus.SUPPORTED else ReasonCode.BURIED_DISCLAIMER,
                    severity=Severity.INFO if status == ClaimStatus.SUPPORTED else Severity.LOW,
                    confidence=Confidence.HIGH,
                    comparison=ComparisonRecord(
                        claim_id=claim.claim_id,
                        subject_match=True,
                        predicate_match=True,
                        evidence_passages=[passage]
                    ),
                    primary_evidence=passage,
                    explanation=explanation,
                    recommended_ad_fix="No change required.",
                    recommended_page_fix="No change required."
                )

        return AuditFinding(
            claim_id=claim.claim_id,
            canonical_id=claim.canonical_id,
            ad_claim_text=claim.text,
            claim_materiality=claim.materiality,
            status=ClaimStatus.MISSING,
            reason_code=ReasonCode.CLAIM_NOT_FOUND,
            severity=Severity.LOW,
            confidence=Confidence.HIGH,
            comparison=ComparisonRecord(
                claim_id=claim.claim_id,
                subject_match=False,
                predicate_match=False
            ),
            explanation="Eligibility condition was not explicitly corroborated on the landing page.",
            recommended_ad_fix="Clarify eligibility requirements in ad copy if relevant.",
            recommended_page_fix="Explicitly document eligibility requirements on landing page."
        )

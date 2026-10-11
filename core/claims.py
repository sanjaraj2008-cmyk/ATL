import re
from decimal import Decimal
from typing import List, Optional, Tuple
from core.schemas import (
    AtomicClaim, ClaimType, Materiality, NumericSpec, Comparator, Polarity
)

class ClaimsDecomposer:
    """
    Decomposes advertising copy into atomic claims with canonical deduplication.
    Identifies trial periods, discounts, approval speed, requirements, and propositions.
    """

    def decompose(self, headline: str, description: str) -> List[AtomicClaim]:
        claims: List[AtomicClaim] = []
        claim_counter = 1

        combined_entries = [
            ("ad_headline", headline.strip()),
            ("ad_description", description.strip())
        ]

        seen_canonical_keys = set()

        for source_name, text in combined_entries:
            if not text:
                continue

            # Split on pipes '|' or newlines or sentence terminators, but NOT on periods inside decimal numbers (like 6.9%)
            # Protect decimals by splitting on sentence punctuation followed by space/end, or pipes
            clauses = re.split(r'\|+|\n+|(?<!\d)[.!?]+(?!\d)|(?<=\d)[.!?]+(?=[^\d]|$)', text)
            for clause in clauses:
                clause = clause.strip()
                if not clause or len(clause) < 3:
                    continue

                extracted_for_clause = self._parse_clause(clause, source_name, claim_counter)
                for cl in extracted_for_clause:
                    # Deduplicate claims using canonical key: (subject, predicate, numeric_raw, polarity)
                    num_key = cl.numeric.raw_str if cl.numeric else "none"
                    canonical_key = f"{cl.subject}:{cl.predicate}:{num_key}:{cl.polarity}"
                    cl.canonical_id = canonical_key

                    if canonical_key in seen_canonical_keys:
                        continue
                    seen_canonical_keys.add(canonical_key)

                    cl.claim_id = f"C{claim_counter:03d}"
                    claims.append(cl)
                    claim_counter += 1

        # Fallback if no specific atomic claim was caught
        if not claims and (headline or description):
            fallback_text = (headline + " " + description).strip()
            claims.append(AtomicClaim(
                claim_id="C001",
                canonical_id="general:value_proposition:none:POSITIVE",
                text=fallback_text,
                claim_type=ClaimType.VALUE_PROPOSITION,
                subject="product_or_service",
                predicate="offer",
                materiality=Materiality.MEDIUM,
                polarity=Polarity.POSITIVE,
                source="ad_headline" if headline else "ad_description"
            ))

        return claims

    def _parse_clause(self, clause: str, source: str, counter: int) -> List[AtomicClaim]:
        results: List[AtomicClaim] = []
        clause_lower = clause.lower()

        # 1. Trial duration check (e.g., "30-day free trial", "free trial for 7 days", "14 day trial")
        trial_match = re.search(r'(\d+)[-\s]*(day|week|month)s?\s*(?:free\s*)?trial|free\s*trial(?:\s*for)?\s*(\d+)[-\s]*(day|week|month)s?', clause_lower)
        if trial_match:
            days = trial_match.group(1) or trial_match.group(3)
            unit = trial_match.group(2) or trial_match.group(4)
            unit_norm = "day" if "day" in unit else ("week" if "week" in unit else "month")
            results.append(AtomicClaim(
                claim_id="",
                canonical_id="",
                text=clause,
                claim_type=ClaimType.TRIAL_DURATION,
                subject="trial_period",
                predicate="duration",
                numeric=NumericSpec(
                    value=Decimal(days),
                    unit=unit_norm,
                    comparator=Comparator.EXACT,
                    raw_str=f"{days} {unit_norm}"
                ),
                materiality=Materiality.HIGH,
                polarity=Polarity.POSITIVE,
                source=source
            ))

        # 2. Friction / Requirement check (e.g., "No credit card required", "No card needed", "No payment details")
        no_cc_match = re.search(r'no\s+(?:credit\s*card|payment(?:\s*details)?|card)\s*(?:required|needed)?', clause_lower)
        if no_cc_match:
            results.append(AtomicClaim(
                claim_id="",
                canonical_id="",
                text=clause,
                claim_type=ClaimType.REQUIREMENT_FRICTION,
                subject="payment_method",
                predicate="required_at_signup",
                qualifiers=[],
                polarity=Polarity.NEGATIVE, # Negative polarity: explicitly NOT required
                materiality=Materiality.HIGH,
                source=source
            ))

        # 3. Timeline / Speed promise (e.g., "same-day approval", "approved on the same day", "instant approval")
        timeline_match = re.search(r'(same[-\s]*day|instant|instantaneous|within\s*(\d+)\s*(?:hours|days))\s*(?:loan\s*)?(?:approval|decision|approved)|(?:loan\s*)?approved\s*(?:on\s*)?(?:the\s*)?(same[-\s]*day)', clause_lower)
        if timeline_match:
            speed_val = "same_day"
            results.append(AtomicClaim(
                claim_id="",
                canonical_id="",
                text=clause,
                claim_type=ClaimType.APPROVAL_TIMELINE,
                subject="loan_application",
                predicate="approval_speed",
                qualifiers=[],
                numeric=NumericSpec(value=Decimal(1), unit="day", comparator=Comparator.EXACT, raw_str=speed_val),
                materiality=Materiality.HIGH,
                polarity=Polarity.POSITIVE,
                source=source
            ))

        # 4. Pricing / Discounts (e.g., "50% off", "up to 50% discount", "$100 off", "save $50")
        discount_match = re.search(r'(up\s*to\s*)?(\$?\d+(?:\.\d+)?)\s*(%|percent|\$|dollars)?\s*(?:off|discount|savings)', clause_lower)
        if discount_match:
            comp = Comparator.UP_TO if discount_match.group(1) else Comparator.EXACT
            raw_val = discount_match.group(2).replace('$', '')
            unit = "percent" if ("%" in clause_lower or "percent" in clause_lower) else "dollar"
            results.append(AtomicClaim(
                claim_id="",
                canonical_id="",
                text=clause,
                claim_type=ClaimType.PRICING_DISCOUNT,
                subject="discount_offer",
                predicate="savings_amount",
                numeric=NumericSpec(
                    value=Decimal(raw_val),
                    unit=unit,
                    comparator=comp,
                    raw_str=f"{comp.value} {raw_val} {unit}"
                ),
                materiality=Materiality.HIGH,
                polarity=Polarity.POSITIVE,
                source=source
            ))

        # 5. Core Value Proposition / Service features
        if not results:
            results.append(AtomicClaim(
                claim_id="",
                canonical_id="",
                text=clause,
                claim_type=ClaimType.VALUE_PROPOSITION,
                subject="product_offer",
                predicate="delivers",
                materiality=Materiality.MEDIUM,
                polarity=Polarity.POSITIVE,
                source=source
            ))

        return results

import re
from decimal import Decimal
from typing import List, Optional, Tuple
from core.schemas import (
    AtomicClaim, ClaimType, Materiality, NumericSpec, Comparator, Polarity
)

class ClaimsDecomposer:
    """
    Phase 1: Understand the Advertisement.
    Decomposes advertising copy into atomic claims with canonical deduplication.
    - Preserves verbatim source spans and original wording.
    - Identifies prices, percentages, guarantees, product capabilities, availability statements, and conditions.
    - Separates factual claims from subjective marketing puffery and calls to action.
    - Preserves material qualifications (e.g., 'billed annually', 'new customers only').
    - Never invents claims not present in the advertisement.
    """

    def decompose(
        self,
        headline: str,
        description: str,
        call_to_action: Optional[str] = None
    ) -> List[AtomicClaim]:
        claims: List[AtomicClaim] = []
        claim_counter = 1

        combined_entries = [
            ("ad_headline", (headline or "").strip()),
            ("ad_description", (description or "").strip()),
            ("ad_call_to_action", (call_to_action or "").strip())
        ]

        seen_canonical_keys = set()

        for source_name, text in combined_entries:
            if not text:
                continue

            entry_qualifiers = self._extract_qualifiers(text.lower())

            # Split on pipes '|', newlines, or sentence terminators (. ! ? ;),
            # but protect decimal numbers (e.g. 6.9% or $9.99)
            clauses = re.split(r'\|+|\n+|(?<!\d)[.!?;]+(?!\d)|(?<=\d)[.!?;]+(?=[^\d]|$)', text)
            for clause in clauses:
                clause = clause.strip()
                if not clause or len(clause) < 3:
                    continue

                extracted_for_clause = self._parse_clause(clause, source_name, claim_counter, entry_qualifiers)
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

        # Fallback if no specific atomic claim was decomposed
        if not claims and (headline or description or call_to_action):
            fallback_text = " ".join(filter(None, [headline, description, call_to_action])).strip()
            claims.append(AtomicClaim(
                claim_id="C001",
                canonical_id="general:value_proposition:none:POSITIVE",
                text=fallback_text,
                source_span=fallback_text,
                claim_type=ClaimType.VALUE_PROPOSITION,
                subject="product_or_service",
                predicate="offer",
                materiality=Materiality.MEDIUM,
                polarity=Polarity.POSITIVE,
                is_factual=True,
                source="ad_headline" if headline else "ad_description"
            ))

        return claims

    def _extract_qualifiers(self, clause_lower: str) -> List[str]:
        """Extracts material conditions, qualifiers, and exclusions attached to a claim."""
        qualifiers = []
        if re.search(r'\b(?:billed\s*annually|annual\s*billing|paid\s*yearly|with\s*annual\s*plan)\b', clause_lower):
            qualifiers.append("billed annually")
        if re.search(r'\b(?:for\s*new\s*customers\s*only|new\s*(?:users|customers)\s*only|first[-\s]*time\s*users)\b', clause_lower):
            qualifiers.append("new customers only")
        if re.search(r'\b(?:with\s*(?:a\s*)?(?:\d+)[-\s]*year\s*(?:contract|agreement)|contract\s*required)\b', clause_lower):
            qualifiers.append("annual contract required")
        if re.search(r'\b(?:select\s*(?:plans|items|products|locations|models)\s*only)\b', clause_lower):
            qualifiers.append("select items only")
        if re.search(r'\b(?:subject\s*to\s*(?:credit\s*)?approval|credit\s*check\s*required)\b', clause_lower):
            qualifiers.append("subject to credit approval")
        if re.search(r'\b(?:terms\s*(?:and|&)\s*conditions\s*apply|terms\s*apply)\b', clause_lower):
            qualifiers.append("terms apply")
        if re.search(r'\bwith\s*(?:valid\s*)?\.edu\s*email\b', clause_lower):
            qualifiers.append("requires .edu email")
        return qualifiers

    def _parse_clause(
        self,
        clause: str,
        source: str,
        counter: int,
        entry_qualifiers: Optional[List[str]] = None
    ) -> List[AtomicClaim]:
        results: List[AtomicClaim] = []
        clause_lower = clause.lower()
        clause_qualifiers = self._extract_qualifiers(clause_lower)
        extracted_qualifiers = list(dict.fromkeys(clause_qualifiers + (entry_qualifiers or [])))

        # 1. Trial duration check (e.g., "30-day free trial", "free trial for 7 days", "14 day trial")
        trial_match = re.search(
            r'(\d+)[-\s]*(day|week|month)s?\s*(?:free\s*)?trial|free\s*trial(?:\s*for)?\s*(\d+)[-\s]*(day|week|month)s?',
            clause_lower
        )
        if trial_match:
            days = trial_match.group(1) or trial_match.group(3)
            unit = trial_match.group(2) or trial_match.group(4)
            unit_norm = "day" if "day" in unit else ("week" if "week" in unit else "month")
            results.append(AtomicClaim(
                claim_id="",
                canonical_id="",
                text=clause,
                source_span=clause,
                claim_type=ClaimType.TRIAL_DURATION,
                subject="trial_period",
                predicate="duration",
                numeric=NumericSpec(
                    value=Decimal(days),
                    unit=unit_norm,
                    comparator=Comparator.EXACT,
                    raw_str=f"{days} {unit_norm}"
                ),
                qualifiers=extracted_qualifiers,
                materiality=Materiality.HIGH,
                polarity=Polarity.POSITIVE,
                is_factual=True,
                source=source
            ))

        # 2. Friction / Requirement check (e.g., "No credit card required", "No card needed", "No setup fees")
        no_friction_match = re.search(
            r'no\s+(?:credit\s*card|payment(?:\s*details)?|card|setup\s*fees?|hidden\s*fees?)\s*(?:required|needed)?',
            clause_lower
        )
        if no_friction_match:
            predicate_kind = "setup_fees" if "fee" in no_friction_match.group(0) else "required_at_signup"
            results.append(AtomicClaim(
                claim_id="",
                canonical_id="",
                text=clause,
                source_span=clause,
                claim_type=ClaimType.REQUIREMENT_FRICTION,
                subject="payment_method" if "fee" not in no_friction_match.group(0) else "setup_cost",
                predicate=predicate_kind,
                qualifiers=extracted_qualifiers,
                polarity=Polarity.NEGATIVE, # Explicitly NOT required
                materiality=Materiality.HIGH,
                is_factual=True,
                source=source
            ))

        # 3. Timeline / Speed promise (e.g., "same-day approval", "approved on the same day", "instant approval")
        timeline_match = re.search(
            r'(same[-\s]*day|instant|instantaneous|within\s*(\d+)\s*(?:hours|days))\s*(?:loan\s*)?(?:approval|decision|approved)|(?:loan\s*)?approved\s*(?:on\s*)?(?:the\s*)?(same[-\s]*day)',
            clause_lower
        )
        if timeline_match:
            speed_val = "same_day"
            results.append(AtomicClaim(
                claim_id="",
                canonical_id="",
                text=clause,
                source_span=clause,
                claim_type=ClaimType.APPROVAL_TIMELINE,
                subject="loan_application",
                predicate="approval_speed",
                qualifiers=extracted_qualifiers,
                numeric=NumericSpec(value=Decimal(1), unit="day", comparator=Comparator.EXACT, raw_str=speed_val),
                materiality=Materiality.HIGH,
                polarity=Polarity.POSITIVE,
                is_factual=True,
                source=source
            ))

        # 4. Pricing / Discounts (e.g., "50% off", "up to 50% discount", "$100 off", "save $50", "save 40%")
        save_m = re.search(r'save\s+(up\s*to\s*)?(\$?\d+(?:\.\d+)?)\s*(%|percent|\$|dollars)?', clause_lower)
        discount_m = re.search(
            r'(up\s*to\s*)?(\$?\d+(?:\.\d+)?)\s*(%|percent|\$|dollars)?\s*(?:off|discount|savings)',
            clause_lower
        )
        if save_m or discount_m:
            m = save_m if save_m else discount_m
            comp = Comparator.UP_TO if m.group(1) else Comparator.EXACT
            raw_val = m.group(2).replace('$', '')
            unit = "percent" if ("%" in clause_lower or "percent" in clause_lower) else "dollar"
            results.append(AtomicClaim(
                claim_id="",
                canonical_id="",
                text=clause,
                source_span=clause,
                claim_type=ClaimType.PRICING_DISCOUNT,
                subject="discount_offer",
                predicate="savings_amount",
                numeric=NumericSpec(
                    value=Decimal(raw_val),
                    unit=unit,
                    comparator=comp,
                    raw_str=f"{comp.value} {raw_val} {unit}"
                ),
                qualifiers=extracted_qualifiers,
                materiality=Materiality.HIGH,
                polarity=Polarity.POSITIVE,
                is_factual=True,
                source=source
            ))

        # 5. Guarantees (e.g., "30-day money-back guarantee", "100% satisfaction guaranteed", "risk-free guarantee")
        guarantee_match = re.search(
            r'(?:(\d+)[-\s]*(day|month|year)s?\s*)?(?:money[-\s]*back|satisfaction|risk[-\s]*free)\s*guarantee[d]?|guarantee[d]?\s*(?:for\s*)?(\d+)[-\s]*(day|month|year)s?',
            clause_lower
        )
        if guarantee_match:
            g_val = guarantee_match.group(1) or guarantee_match.group(3)
            g_unit = guarantee_match.group(2) or guarantee_match.group(4)
            num_spec = None
            if g_val:
                g_unit_norm = "day" if "day" in g_unit else ("month" if "month" in g_unit else "year")
                num_spec = NumericSpec(
                    value=Decimal(g_val),
                    unit=g_unit_norm,
                    comparator=Comparator.EXACT,
                    raw_str=f"{g_val} {g_unit_norm}"
                )
            results.append(AtomicClaim(
                claim_id="",
                canonical_id="",
                text=clause,
                source_span=clause,
                claim_type=ClaimType.GUARANTEE,
                subject="satisfaction_guarantee",
                predicate="money_back" if "money" in clause_lower else "satisfaction",
                numeric=num_spec,
                qualifiers=extracted_qualifiers,
                materiality=Materiality.HIGH,
                polarity=Polarity.POSITIVE,
                is_factual=True,
                source=source
            ))

        # 6. Specific Price Point / APR (e.g. "$9/month", "Plans from $29", "0% APR")
        apr_match = re.search(r'(\d+(?:\.\d+)?)\s*%\s*apr(?:\s*(?:for|up\s*to)\s*(\d+)\s*(month|year)s?)?', clause_lower)
        if apr_match:
            apr_val = apr_match.group(1)
            results.append(AtomicClaim(
                claim_id="",
                canonical_id="",
                text=clause,
                source_span=clause,
                claim_type=ClaimType.PRICE_POINT,
                subject="financing_terms",
                predicate="apr_rate",
                numeric=NumericSpec(
                    value=Decimal(apr_val),
                    unit="percent",
                    comparator=Comparator.EXACT,
                    raw_str=f"{apr_val}% APR"
                ),
                qualifiers=extracted_qualifiers,
                materiality=Materiality.HIGH,
                polarity=Polarity.POSITIVE,
                is_factual=True,
                source=source
            ))
        else:
            price_match = re.search(
                r'(?:starting\s*(?:at|from)|from|only|as\s*low\s*as)?\s*\$(\d+(?:\.\d+)?)\s*(?:\/|\s*per\s*|\s*a\s*)?\s*(month|mo|year|yr|user|seat|day|week)?',
                clause_lower
            )
            # Only treat as price point if it wasn't a discount statement (e.g. not "$50 off" and not "save $50")
            if price_match and not (save_m or discount_m):
                amount = price_match.group(1)
                time_unit = price_match.group(2) or "unit"
                results.append(AtomicClaim(
                    claim_id="",
                    canonical_id="",
                    text=clause,
                    source_span=clause,
                    claim_type=ClaimType.PRICE_POINT,
                    subject="pricing_tier",
                    predicate="base_price",
                    numeric=NumericSpec(
                        value=Decimal(amount),
                        unit="dollar",
                        time_basis=time_unit,
                        comparator=Comparator.FROM if "from" in clause_lower or "starting" in clause_lower else Comparator.EXACT,
                        raw_str=f"${amount}/{time_unit}"
                    ),
                    qualifiers=extracted_qualifiers,
                    materiality=Materiality.HIGH,
                    polarity=Polarity.POSITIVE,
                    is_factual=True,
                    source=source
                ))

        # 7. Product Capabilities & Specifications (e.g., "99.9% uptime", "24/7 support", "unlimited cloud storage")
        uptime_m = re.search(r'(\d+(?:\.\d+)?)\s*%\s*(?:uptime|sla|availability)', clause_lower)
        if uptime_m:
            results.append(AtomicClaim(
                claim_id="",
                canonical_id="",
                text=clause,
                source_span=uptime_m.group(0),
                claim_type=ClaimType.PRODUCT_CAPABILITY,
                subject="uptime_sla",
                predicate="guaranteed_uptime",
                numeric=NumericSpec(
                    value=Decimal(uptime_m.group(1)),
                    unit="percent",
                    comparator=Comparator.EXACT,
                    raw_str=f"{uptime_m.group(1)}% uptime"
                ),
                qualifiers=extracted_qualifiers,
                materiality=Materiality.HIGH,
                polarity=Polarity.POSITIVE,
                is_factual=True,
                source=source
            ))

        support_m = re.search(r'24\s*\/\s*7\s*(?:live\s*)?(?:customer\s*)?(?:support|service|assistance|help)', clause_lower)
        if support_m:
            results.append(AtomicClaim(
                claim_id="",
                canonical_id="",
                text=clause,
                source_span=support_m.group(0),
                claim_type=ClaimType.PRODUCT_CAPABILITY,
                subject="customer_support",
                predicate="availability_24_7",
                qualifiers=extracted_qualifiers,
                materiality=Materiality.HIGH,
                polarity=Polarity.POSITIVE,
                is_factual=True,
                source=source
            ))

        unlimited_m = re.search(r'unlimited\s+([a-zA-Z\s]+?)(?=[.,;!?]|$|\s+with|\s+and)', clause_lower)
        if unlimited_m:
            resource = unlimited_m.group(1).strip()
            results.append(AtomicClaim(
                claim_id="",
                canonical_id="",
                text=clause,
                source_span=unlimited_m.group(0),
                claim_type=ClaimType.PRODUCT_CAPABILITY,
                subject=f"resource_{resource.replace(' ', '_')}",
                predicate="unlimited_capacity",
                qualifiers=extracted_qualifiers,
                materiality=Materiality.HIGH,
                polarity=Polarity.POSITIVE,
                is_factual=True,
                source=source
            ))


        # 8. Availability & Eligibility Statements (e.g., "new customers only", "students only")
        if extracted_qualifiers and not results:
            results.append(AtomicClaim(
                claim_id="",
                canonical_id="",
                text=clause,
                source_span=clause,
                claim_type=ClaimType.AVAILABILITY_CONDITION,
                subject="eligibility_requirement",
                predicate="restriction",
                qualifiers=extracted_qualifiers,
                materiality=Materiality.HIGH,
                polarity=Polarity.CONDITIONAL,
                is_factual=True,
                source=source
            ))

        # 9. Pure Call to Action (e.g., "Get started today", "Sign up now", "Claim offer")
        cta_match = re.search(
            r'^(?:get\s*started|sign\s*up|try\s*(?:now|it\s*free)|start\s*(?:now|today|your)|claim\s*(?:your\s*)?(?:offer|deal|discount)|join\s*today|download\s*now|subscribe\s*today)\b',
            clause_lower
        )
        if cta_match and not results:
            results.append(AtomicClaim(
                claim_id="",
                canonical_id="",
                text=clause,
                source_span=clause,
                claim_type=ClaimType.CALL_TO_ACTION,
                subject="user_action",
                predicate="call_to_action",
                qualifiers=extracted_qualifiers,
                materiality=Materiality.LOW,
                polarity=Polarity.POSITIVE,
                is_factual=False, # Separated from factual claims
                source=source
            ))

        # 10. Subjective Marketing Language / Puffery (e.g., "#1 tool", "world's best", "award-winning")
        puffery_match = re.search(
            r'\b(?:#1|world\'?s?\s*best|industry[-\s]*leading|top[-\s]*rated|award[-\s]*winning|most\s*popular|fastest\s*growing|loved\s*by\s*(?:millions|thousands|\d+))\b',
            clause_lower
        )
        if puffery_match and not results:
            results.append(AtomicClaim(
                claim_id="",
                canonical_id="",
                text=clause,
                source_span=clause,
                claim_type=ClaimType.SUBJECTIVE_MARKETING,
                subject="marketing_assertion",
                predicate="puffery",
                qualifiers=extracted_qualifiers,
                materiality=Materiality.LOW,
                polarity=Polarity.POSITIVE,
                is_factual=False, # Separated from factual claims
                source=source
            ))

        # 11. General Value Proposition / Core Offer fallback
        if not results:
            results.append(AtomicClaim(
                claim_id="",
                canonical_id="",
                text=clause,
                source_span=clause,
                claim_type=ClaimType.VALUE_PROPOSITION,
                subject="product_offer",
                predicate="delivers",
                qualifiers=extracted_qualifiers,
                materiality=Materiality.MEDIUM,
                polarity=Polarity.POSITIVE,
                is_factual=True,
                source=source
            ))

        return results

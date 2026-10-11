import re
from typing import List, Optional, Dict
from core.schemas import (
    AtomicClaim, AuditFinding, ClaimStatus, ReasonCode, Severity,
    DOMZone, DOMBlock, MismatchExplanation
)

class MismatchExplainer:
    """
    Phase 5: Structured Mismatch Explanation Engine.
    Conforms strictly to the 7-part evaluation criteria:
    1. State the original advertising claim with source context.
    2. Explain what the landing page establishes (verified quotes & provenance).
    3. Describe the discrepancy precisely.
    4. Explain practical significance on customer expectations and business impact.
    5. Identify relevant conditions, exclusions, caveats, or visibility/prominence issues.
    6. Recommend specific, non-vague corrections for both ad copy and landing page.
    7. Distinguish factual findings from uncertain interpretations.
    """

    def explain_finding(
        self,
        finding: AuditFinding,
        claim: AtomicClaim,
        blocks: List[DOMBlock],
        retrieval_warnings: Optional[List[str]] = None
    ) -> MismatchExplanation:
        retrieval_warnings = retrieval_warnings or []
        is_partial_retrieval = len(retrieval_warnings) > 0

        # 1. Original Advertising Claim
        source_label = claim.source.replace("ad_", "").replace("_", " ").title()
        original_ad_claim = f"{source_label} promise: \"{claim.text}\""

        # 2. What Landing Page Establishes
        ev = finding.primary_evidence
        if ev and ev.is_verified:
            zone_desc = self._format_zone(ev.dom_zone)
            lp_finding = (
                f"Inspected landing page confirms in {zone_desc} (Block {ev.block_id}): "
                f"\"{ev.quote.strip()}\""
            )
        elif finding.status == ClaimStatus.MISSING:
            lp_finding = (
                f"No mention, pricing, or qualification matching \"{claim.text}\" "
                f"was detected across {len(blocks)} inspected DOM elements on the landing page."
            )
        elif finding.status == ClaimStatus.UNVERIFIABLE:
            if is_partial_retrieval:
                lp_finding = (
                    f"Landing page retrieval was incomplete or restricted ({'; '.join(retrieval_warnings)}), "
                    f"preventing exhaustive verification of \"{claim.text}\"."
                )
            else:
                lp_finding = (
                    f"Landing page references related concepts but lacks sufficient unambiguous data "
                    f"to establish or refute \"{claim.text}\"."
                )
        else:
            lp_finding = f"Inspected landing page does not validate the claim \"{claim.text}\"."

        # 3. Discrepancy Description
        discrepancy = self._describe_discrepancy(finding, claim)

        # 4. Practical Significance
        significance = self._assess_practical_significance(finding, claim)

        # 5. Conditions, Exclusions, and Visibility Issues
        conditions_visibility = self._assess_conditions_and_visibility(finding, blocks)

        # 6. Specific, Actionable Corrections
        ad_fix, page_fix = self._generate_specific_corrections(finding, claim)

        # 7. Certainty Level
        if is_partial_retrieval or finding.status == ClaimStatus.UNVERIFIABLE or not claim.is_factual:
            certainty = "UNCERTAIN_INTERPRETATION: Conclusion subject to retrieval limitations or subjective phrasing."
            is_factual = False
        else:
            certainty = "FACTUAL_EVIDENCE: Grounded in deterministic DOM extraction and exact source citations."
            is_factual = True

        mismatch = MismatchExplanation(
            original_ad_claim=original_ad_claim,
            landing_page_finding=lp_finding,
            discrepancy_description=discrepancy,
            practical_significance=significance,
            conditions_and_visibility=conditions_visibility,
            recommended_ad_fix=ad_fix,
            recommended_page_fix=page_fix,
            is_factual=is_factual,
            certainty_level=certainty
        )

        plain_summary = self._generate_plain_english_summary(finding, claim)
        finding.plain_summary = plain_summary
        finding.explanation = plain_summary
        finding.recommended_ad_fix = ad_fix
        finding.recommended_page_fix = page_fix
        finding.mismatch_details = mismatch

        return mismatch

    def _generate_plain_english_summary(self, finding: AuditFinding, claim: AtomicClaim) -> str:
        """
        Creates a friendly, simple 1-2 sentence explanation that anyone (including a 5th grader)
        can immediately understand without reading confusing technical jargon.
        """
        status = finding.status
        reason = finding.reason_code
        ev = finding.primary_evidence

        if status == ClaimStatus.SUPPORTED:
            if ev and ev.dom_zone == DOMZone.FOOTER_DISCLAIMER:
                return (
                    f"The website mentions \"{claim.text}\", but it hides it in tiny print at the bottom "
                    f"of the page instead of showing it clearly upfront."
                )
            return (
                f"Great match! The website clearly delivers on the promise (\"{claim.text}\") "
                f"that was made in the ad."
            )

        if status == ClaimStatus.CONTRADICTED:
            if ev:
                clean_quote = ev.quote.strip()
                if len(clean_quote) > 90:
                    clean_quote = clean_quote[:87] + "..."
                return (
                    f"The ad says \"{claim.text}\", but the website actually says: \"{clean_quote}\". "
                    f"Visitors will be upset because they won't get what the ad promised."
                )
            return (
                f"The ad promises \"{claim.text}\", but the website directly contradicts it. "
                f"Visitors will be confused and lose trust."
            )

        if status == ClaimStatus.PARTIALLY_SUPPORTED:
            if ev and "up to" in ev.quote.lower():
                return (
                    f"The ad promises an unconditional \"{claim.text}\", but the website actually says "
                    f"\"up to\", meaning not everyone gets the full amount."
                )
            if reason == ReasonCode.BURIED_DISCLAIMER:
                return (
                    f"The ad promises \"{claim.text}\", but the website buries important rules or fine print "
                    f"in the footer at the bottom of the page."
                )
            return (
                f"The website offers something similar to \"{claim.text}\", but adds extra restrictions "
                f"or hidden conditions that were not mentioned in the ad."
            )

        if status in (ClaimStatus.MISSING, ClaimStatus.NOT_FOUND):
            return (
                f"The ad promises \"{claim.text}\", but we searched the entire website and could not find "
                f"any mention of it. Visitors looking for this will be confused or leave."
            )

        if status == ClaimStatus.UNVERIFIABLE:
            return (
                f"We could not confirm \"{claim.text}\" because the website content was incomplete "
                f"or could not be clearly verified."
            )

        return f"The ad and the website do not match on \"{claim.text}\"."

    def _format_zone(self, zone: DOMZone) -> str:
        if zone == DOMZone.HERO_CANDIDATE:
            return "the hero section (primary viewport)"
        elif zone == DOMZone.FOOTER_DISCLAIMER:
            return "the footer disclaimer (fine print)"
        elif zone == DOMZone.MAIN_BODY:
            return "the main body content"
        return "the page content"

    def _describe_discrepancy(self, finding: AuditFinding, claim: AtomicClaim) -> str:
        status = finding.status
        reason = finding.reason_code
        ev = finding.primary_evidence

        if status == ClaimStatus.SUPPORTED:
            return "No discrepancy detected. The landing page prominently and directly substantiates the advertised promise."

        if status == ClaimStatus.CONTRADICTED:
            if reason == ReasonCode.NUMERIC_CONTRADICTION:
                if claim.numeric and ev:
                    return (
                        f"Direct numerical contradiction: The ad advertises {claim.numeric.raw_str}, "
                        f"whereas the landing page specifies contradictory terms (\"{ev.quote.strip()}\")."
                    )
                return "Direct contradiction between advertised numerical specifications and landing page terms."
            elif reason == ReasonCode.POLARITY_CONTRADICTION:
                return (
                    f"Direct polarity contradiction: The ad promises an unconditional benefit ('{claim.text}'), "
                    f"but the landing page explicitly imposes contrary requirements (\"{ev.quote.strip() if ev else ''}\")."
                )
            return f"The landing page explicitly contradicts the advertised promise of '{claim.text}'."

        if status == ClaimStatus.PARTIALLY_SUPPORTED:
            if reason == ReasonCode.BURIED_DISCLAIMER:
                return (
                    f"Visibility mismatch: The ad makes a prominent upfront claim ('{claim.text}'), "
                    f"but the landing page relegates essential terms or caveats to buried footer disclaimers."
                )
            elif reason == ReasonCode.QUALIFIER_MISMATCH:
                return (
                    f"Qualification mismatch: The ad promises '{claim.text}' broadly, "
                    f"but the landing page restricts eligibility to specific subsets or conditions."
                )
            return (
                f"Partial support: Core elements of '{claim.text}' are referenced, "
                f"but key terms, qualifiers, or guarantees are omitted or restricted."
            )

        if status == ClaimStatus.MISSING:
            return (
                f"Total absence mismatch: The advertised promise '{claim.text}' is completely missing "
                f"from the destination landing page, offering zero confirmation to visitors."
            )

        if status == ClaimStatus.UNVERIFIABLE:
            return (
                f"Verifiability limitation: Cannot confirm '{claim.text}' due to ambiguous terminology, "
                f"subjective marketing puffery, or incomplete page assets."
            )

        return f"Discrepancy identified between ad claim '{claim.text}' and destination landing page."

    def _assess_practical_significance(self, finding: AuditFinding, claim: AtomicClaim) -> str:
        status = finding.status

        if status == ClaimStatus.SUPPORTED:
            return "Positive customer impact: Reinforces customer confidence and frictionless message match from ad impression to conversion."

        if status == ClaimStatus.CONTRADICTED:
            return (
                "Severe customer expectation mismatch: Visitors attracted by the advertised promise face immediate disappointment "
                "or unexpected friction upon landing, creating high bounce rates and potential regulatory exposure under deceptive advertising standards."
            )

        if status == ClaimStatus.PARTIALLY_SUPPORTED:
            return (
                "Material expectation friction: Qualified consumers may feel misled when discovering fine-print exclusions "
                "or restrictive eligibility criteria not disclosed in the advertising copy."
            )

        if status == ClaimStatus.MISSING:
            return (
                "High abandonment risk: Visitors clicking specifically for this feature or offer fail to locate it immediately, "
                "eroding conversion rates and wasting paid ad spend."
            )

        return "Uncertain impact: May create mild friction or confusion depending on user familiarity with the brand."

    def _assess_conditions_and_visibility(self, finding: AuditFinding, blocks: List[DOMBlock]) -> str:
        ev = finding.primary_evidence
        if not ev:
            if finding.status in (ClaimStatus.MISSING, ClaimStatus.UNVERIFIABLE):
                return "Visibility assessment: N/A (no relevant content detected in inspected DOM elements)."
            return "No specific visibility constraints detected."

        details = []
        if ev.dom_zone == DOMZone.FOOTER_DISCLAIMER:
            details.append("Buried in footer disclaimer / small print with low visual prominence (weight 0.25)")
        elif ev.dom_zone == DOMZone.HERO_CANDIDATE:
            details.append("Prominently displayed in hero / primary viewport (weight 1.0)")
        elif ev.dom_zone == DOMZone.MAIN_BODY:
            details.append("Displayed within body content (weight 0.75)")

        # Check if block has caveat indicators
        matching_block = next((b for b in blocks if b.block_id == ev.block_id), None)
        if matching_block and matching_block.has_conditions:
            details.append("Accompanied by asterisks, qualifying clauses, or conditional terms")
        
        caveat_keywords = ["qualified", "terms apply", "subject to", "starting from", "up to", "select"]
        if any(kw in ev.quote.lower() for kw in caveat_keywords):
            details.append("Contains explicit restrictive language or eligibility qualifications")

        return "; ".join(details) if details else "Standard visibility without explicit caveat terms."

    def _generate_specific_corrections(self, finding: AuditFinding, claim: AtomicClaim) -> tuple:
        status = finding.status
        ev = finding.primary_evidence

        if status == ClaimStatus.SUPPORTED:
            ad_fix = f"Maintain current ad phrasing (\"{claim.text}\"); it aligns accurately with verified page content."
            page_fix = "Maintain current landing page copy and prominence; message match is verified."
            return ad_fix, page_fix

        if status == ClaimStatus.CONTRADICTED:
            if ev and ev.quote:
                clean_quote = ev.quote.strip()
                if len(clean_quote) > 60:
                    clean_quote = clean_quote[:57] + "..."
                ad_fix = f"Revise ad text from \"{claim.text}\" to reflect actual page terms: \"{clean_quote}\"."
                page_fix = f"Update landing page to honor the advertised promise \"{claim.text}\" if this offer is intended for customers."
            else:
                ad_fix = f"Remove or reword \"{claim.text}\" in ad copy to eliminate the direct conflict with landing page terms."
                page_fix = f"Revise landing page terms to match advertised promise \"{claim.text}\"."
            return ad_fix, page_fix

        if status == ClaimStatus.PARTIALLY_SUPPORTED:
            if ev and ev.dom_zone == DOMZone.FOOTER_DISCLAIMER:
                ad_fix = f"Add qualification to ad copy (e.g., \"{claim.text}* (terms apply)\") to disclose restrictions upfront."
                page_fix = f"Elevate qualifying disclosures for \"{claim.text}\" from the footer into the hero/pricing section."
            else:
                ad_fix = f"Add explicit qualifying terms to \"{claim.text}\" in ad copy (e.g., specifying eligibility criteria)."
                page_fix = f"Clarify full terms and scope of \"{claim.text}\" in the primary body content of the landing page."
            return ad_fix, page_fix

        if status == ClaimStatus.MISSING:
            ad_fix = f"Remove \"{claim.text}\" from ad creative or replace with a feature verified on the landing page."
            page_fix = f"Add dedicated content or an explanatory section highlighting \"{claim.text}\" above the fold on the landing page."
            return ad_fix, page_fix

        # UNVERIFIABLE
        ad_fix = f"Clarify \"{claim.text}\" with factual, verifiable terminology rather than ambiguous marketing phrasing."
        page_fix = f"Add concrete, verifiable specifications regarding \"{claim.text}\" to the landing page copy."
        return ad_fix, page_fix

from typing import List, Optional, Tuple
from core.schemas import (
    AtomicClaim, AuditFinding, ClaimStatus, ReasonCode, Severity,
    Materiality, DOMZone, SeverityAssessment
)

class SeverityAssessor:
    """
    Phase 6: Multi-Factor Severity Assessor & Regulatory Risk Auditor.
    Prioritizes findings based on promise materiality, discrepancy magnitude,
    and customer impact, avoiding false equivalence between missing phrases.
    Flags potential deceptive/regulatory issues with factual basis,
    without making definitive legal determinations.
    """

    PRIORITY_MAP = {
        Severity.CRITICAL: 1,
        Severity.HIGH: 2,
        Severity.MEDIUM: 3,
        Severity.LOW: 4,
        Severity.INFO: 5
    }

    def assess_finding(
        self,
        finding: AuditFinding,
        claim: AtomicClaim
    ) -> SeverityAssessment:
        status = finding.status
        reason = finding.reason_code
        mat = claim.materiality
        ev = finding.primary_evidence

        level = Severity.INFO
        rationale = ""
        is_misleading = False
        regulatory_flag = False
        regulatory_note: Optional[str] = None

        # 1. SUPPORTED
        if status == ClaimStatus.SUPPORTED:
            level = Severity.INFO
            rationale = "Claim substantiated: Verifiable landing page evidence directly supports the advertised promise."

        # 2. CONTRADICTED
        elif status == ClaimStatus.CONTRADICTED:
            is_misleading = True
            quote_snippet = f" (page states: \"{ev.quote[:60]}...\")" if ev and ev.quote else ""

            if mat == Materiality.HIGH:
                level = Severity.CRITICAL
                regulatory_flag = True
                rationale = (
                    f"Critical material contradiction: High-impact promise ('{claim.text}') is directly "
                    f"contradicted on destination page{quote_snippet}. Directly impacts purchasing decisions."
                )
                regulatory_note = (
                    f"Factual compliance review recommended: Ad prominently promotes '{claim.text}', "
                    f"but inspected landing page explicitly states conflicting terms{quote_snippet}. "
                    "This finding documents a factual claim discrepancy for review against applicable advertising standards."
                )
            else:
                level = Severity.HIGH
                rationale = (
                    f"Significant term contradiction: Advertised feature or specification '{claim.text}' "
                    f"is contradicted by landing page evidence{quote_snippet}."
                )
                regulatory_note = (
                    f"Factual inconsistency flagged: Advertised claim '{claim.text}' conflicts with landing page "
                    f"content. Recommended for marketing alignment review."
                )

        # 3. PARTIALLY_SUPPORTED
        elif status == ClaimStatus.PARTIALLY_SUPPORTED:
            if reason == ReasonCode.BURIED_DISCLAIMER:
                if mat == Materiality.HIGH:
                    level = Severity.HIGH
                    is_misleading = True
                    regulatory_flag = True
                    rationale = (
                        f"High-risk prominence disparity: High-materiality claim '{claim.text}' is qualified "
                        "only in low-prominence footer disclaimers, masking essential restrictions from primary view."
                    )
                    regulatory_note = (
                        f"Disclosure prominence review recommended: Advertised promise '{claim.text}' appears "
                        "without upfront qualifications in ad copy, while landing page restricts eligibility via fine print. "
                        "Flagged for clear and conspicuous disclosure evaluation."
                    )
                else:
                    level = Severity.MEDIUM
                    rationale = (
                        f"Moderate visibility disparity: Terms qualifying '{claim.text}' appear in fine print or disclaimers."
                    )
            elif reason == ReasonCode.QUALIFIER_MISMATCH:
                level = Severity.HIGH if mat == Materiality.HIGH else Severity.MEDIUM
                rationale = (
                    f"Eligibility condition restriction: The ad states '{claim.text}' unconditionally, "
                    "but landing page imposes specific eligibility criteria."
                )
                if mat == Materiality.HIGH:
                    is_misleading = True
                    regulatory_flag = True
                    regulatory_note = (
                        f"Unqualified claim flagged: The ad asserts '{claim.text}', but page evidence limits availability "
                        "to qualified sub-segments. Review for necessary qualifying disclosures."
                    )
            else:
                level = Severity.MEDIUM
                rationale = f"Partial support: Some aspects of '{claim.text}' are verified, but key terms remain unverified."

        # 4. MISSING (Crucial Phase 6 rule: Do not treat every missing phrase as equally serious)
        elif status == ClaimStatus.MISSING:
            if not claim.is_factual or mat == Materiality.LOW:
                # Subjective puffery / low materiality missing phrase
                level = Severity.LOW
                rationale = (
                    f"Minor omission: Subjective marketing slogan or low-materiality phrase ('{claim.text}') "
                    "is absent from landing page without distorting core consumer expectations or pricing."
                )
            elif mat == Materiality.MEDIUM:
                # Secondary feature / capability missing
                level = Severity.MEDIUM
                rationale = (
                    f"Moderate omission: Advertised feature or timeline ('{claim.text}') is not found on destination page, "
                    "introducing information search friction for interested consumers."
                )
            else:
                # High-materiality promise missing (e.g. price point, money-back guarantee, approval terms)
                level = Severity.HIGH
                is_misleading = True
                rationale = (
                    f"Material omission: Core commercial promise ('{claim.text}') is completely missing from destination page, "
                    "setting customer expectations that are unaddressed upon arrival."
                )
                regulatory_note = (
                    f"Unsubstantiated ad promise: Core advertised claim '{claim.text}' could not be verified on the landing page. "
                    "Review to ensure destination page substantiates advertising copy."
                )

        # 5. UNVERIFIABLE
        elif status == ClaimStatus.UNVERIFIABLE:
            level = Severity.LOW
            rationale = (
                f"Informational / Low severity: Claim '{claim.text}' cannot be definitively verified due to "
                "subjective phrasing or incomplete page extraction; does not indicate bad-faith misrepresentation."
            )

        priority = self.PRIORITY_MAP.get(level, 3)

        assessment = SeverityAssessment(
            level=level,
            priority_rank=priority,
            rationale=rationale,
            is_potentially_misleading=is_misleading,
            regulatory_flag=regulatory_flag,
            regulatory_review_note=regulatory_note
        )

        # Enrich finding
        finding.severity = level
        finding.severity_assessment = assessment
        finding.regulatory_flag = regulatory_flag
        finding.regulatory_review_note = regulatory_note

        return assessment

    def sort_findings_by_priority(self, findings: List[AuditFinding]) -> List[AuditFinding]:
        """Sorts findings with highest priority (CRITICAL/HIGH) first."""
        def sort_key(f: AuditFinding) -> Tuple[int, int]:
            rank = f.severity_assessment.priority_rank if f.severity_assessment else self.PRIORITY_MAP.get(f.severity, 3)
            # Secondary sort: Materiality (High=0, Med=1, Low=2)
            mat_order = {Materiality.HIGH: 0, Materiality.MEDIUM: 1, Materiality.LOW: 2}.get(f.claim_materiality, 1)
            return (rank, mat_order)

        return sorted(findings, key=sort_key)

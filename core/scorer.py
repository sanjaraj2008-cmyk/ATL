from typing import List, Tuple, Optional
from core.schemas import (
    AuditFinding, ClaimStatus, Materiality, DOMZone, ReasonCode, Severity
)

class Scorer:
    """
    Computes mathematically sound, evidence-weighted scores and metrics:
    1. Match Score (S): Normalized weighted average across deduplicated claims.
    2. Coverage Index (C): Percentage of claims with assessable page evidence.
    3. Prominence Index (P): Evaluated strictly over claims with identified evidence.
    4. Anti-Masking Critical Banner flag.
    """

    SUPPORT_VALUES = {
        ClaimStatus.SUPPORTED: 1.0,
        ClaimStatus.PARTIALLY_SUPPORTED: 0.50,
        ClaimStatus.NOT_FOUND: 0.25,
        ClaimStatus.AMBIGUOUS: 0.20,
        ClaimStatus.CONTRADICTED: 0.0
    }

    MATERIALITY_WEIGHTS = {
        Materiality.HIGH: 3.0,
        Materiality.MEDIUM: 2.0,
        Materiality.LOW: 1.0
    }

    def calculate_scores(self, findings: List[AuditFinding]) -> Tuple[int, int, Optional[int], bool, str]:
        """
        Returns:
            match_score (0-100)
            coverage_index (0-100)
            prominence_index (0-100 or None if no evidence)
            has_critical_liability (bool)
            grade (str)
        """
        if not findings:
            return 100, 100, None, False, "Strong Match"

        # Deduplicate findings by canonical_id
        unique_findings = {}
        for f in findings:
            if f.canonical_id not in unique_findings:
                unique_findings[f.canonical_id] = f
            else:
                # Keep the more severe finding if duplicates exist
                if f.severity in (Severity.CRITICAL, Severity.HIGH):
                    unique_findings[f.canonical_id] = f

        assessed = list(unique_findings.values())

        # 1. Match Score Calculation
        total_weighted_support = 0.0
        total_weight = 0.0
        has_critical_liability = False

        for f in assessed:
            w = self.MATERIALITY_WEIGHTS.get(f.claim_materiality, 1.0)
            s = self.SUPPORT_VALUES.get(f.status, 0.25)

            # Heuristic location discount if supported only in footer
            if f.status == ClaimStatus.SUPPORTED and f.reason_code == ReasonCode.BURIED_DISCLAIMER:
                s = 0.70

            total_weighted_support += w * s
            total_weight += w

            # Anti-Masking Rule: Material contradiction flags liability
            if f.claim_materiality == Materiality.HIGH and f.status == ClaimStatus.CONTRADICTED:
                has_critical_liability = True

        match_score = int(round(100.0 * (total_weighted_support / total_weight))) if total_weight > 0 else 0
        match_score = max(0, min(100, match_score))

        # 2. Coverage Index (What % of claims have evidence on page)
        covered_weight = sum(
            self.MATERIALITY_WEIGHTS.get(f.claim_materiality, 1.0)
            for f in assessed
            if f.status != ClaimStatus.NOT_FOUND
        )
        coverage_index = int(round(100.0 * (covered_weight / total_weight))) if total_weight > 0 else 0

        # 3. Prominence Index (Where does evidence appear for claims that HAVE evidence)
        evidence_findings = [f for f in assessed if f.primary_evidence is not None]
        if evidence_findings:
            p_weight_sum = 0.0
            p_score_sum = 0.0
            for f in evidence_findings:
                w = self.MATERIALITY_WEIGHTS.get(f.claim_materiality, 1.0)
                # Zone prominence factor
                zone_factor = 0.4 if f.primary_evidence.dom_zone == DOMZone.FOOTER_DISCLAIMER else 1.0
                p_score_sum += w * zone_factor
                p_weight_sum += w
            prominence_index = int(round(100.0 * (p_score_sum / p_weight_sum))) if p_weight_sum > 0 else None
        else:
            prominence_index = None

        # 4. Grade Assignment
        if has_critical_liability:
            grade = "Poor Match (Critical Liability)"
        elif match_score >= 85:
            grade = "Strong Match"
        elif match_score >= 60:
            grade = "Partial Match"
        else:
            grade = "Poor Match"

        return match_score, coverage_index, prominence_index, has_critical_liability, grade

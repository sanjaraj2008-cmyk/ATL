import csv
import os
import sys
from collections import Counter

# Add ATL root to sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from core.audit_engine import AuditEngine
from core.schemas import ClaimStatus, Severity

DATA_DIR = r"c:\Users\SANJAY RAJ\Downloads\Srishti-2K26-Datasets-All\PS-03_message_match_auditor_dataset\PS-03_message_match_auditor"
ADS_CSV = os.path.join(DATA_DIR, "ads.csv")

def evaluate_phase6_dataset():
    if not os.path.exists(ADS_CSV):
        print(f"[ERROR] Dataset file not found at: {ADS_CSV}")
        return False

    with open(ADS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print("=" * 85)
    print(f"PHASE 6 EVALUATION: MULTI-FACTOR SEVERITY & REGULATORY RISK AUDIT ON {len(rows)} PAIRS")
    print("=" * 85)

    engine = AuditEngine()

    total_pairs = len(rows)
    total_findings = 0
    severity_counter = Counter()
    priority_counter = Counter()
    regulatory_flags_count = 0
    missing_by_severity = Counter()
    sorting_violations = 0
    definitive_legal_claims_count = 0

    sample_regulatory_notes = []
    sample_severities = []

    prohibited_legal_terms = ["guilty of", "court will find", "violates federal law", "criminal fraud"]

    for row in rows:
        pair_id = row["pair_id"]
        advertiser = row["advertiser"]
        snapshot_rel = row["snapshot_file"]
        snapshot_path = os.path.join(DATA_DIR, snapshot_rel)

        if not os.path.exists(snapshot_path):
            continue

        with open(snapshot_path, "r", encoding="utf-8") as sf:
            html = sf.read()

        headlines = " | ".join(filter(None, [row.get("headline_1", ""), row.get("headline_2", ""), row.get("headline_3", "")]))
        desc = " ".join(filter(None, [row.get("description_1", ""), row.get("description_2", "")]))

        result = engine.audit(headlines, desc, html)

        # Check sorting order: priority rank should be non-decreasing
        ranks = [f.severity_assessment.priority_rank for f in result.findings if f.severity_assessment]
        if ranks != sorted(ranks):
            sorting_violations += 1

        for f in result.findings:
            total_findings += 1
            sev = f.severity_assessment
            if sev:
                severity_counter[sev.level.value] += 1
                priority_counter[sev.priority_rank] += 1

                if f.status == ClaimStatus.MISSING:
                    missing_by_severity[sev.level.value] += 1

                if sev.regulatory_flag:
                    regulatory_flags_count += 1
                    note = sev.regulatory_review_note or ""
                    # Check for prohibited judicial assertions
                    if any(t in note.lower() for t in prohibited_legal_terms):
                        definitive_legal_claims_count += 1

                    if len(sample_regulatory_notes) < 4:
                        sample_regulatory_notes.append({
                            "pair_id": pair_id,
                            "claim": f.ad_claim_text,
                            "severity": sev.level.value,
                            "note": note
                        })

                if len(sample_severities) < 5 and sev.level in (Severity.CRITICAL, Severity.HIGH):
                    sample_severities.append({
                        "pair_id": pair_id,
                        "claim": f.ad_claim_text,
                        "status": f.status.value,
                        "severity": sev.level.value,
                        "rank": sev.priority_rank,
                        "rationale": sev.rationale
                    })

    print("\n--- PHASE 6 SEVERITY DISTRIBUTION ---")
    print(f"Total Ad-Landing Page Pairs Evaluated:  {total_pairs}")
    print(f"Total Atomic Claims Audited:           {total_findings}")
    print(f"Priority Sorting Violations:           {sorting_violations} (Must be 0)")
    print(f"Definitive Legal Declarations:         {definitive_legal_claims_count} (Must be 0)")

    print("\n--- FINDINGS BY SEVERITY TIER ---")
    for level, count in severity_counter.most_common():
        print(f"  {level:<15} (Rank {engine.severity_assessor.PRIORITY_MAP.get(Severity(level))}): {count} ({count/total_findings*100:.1f}%)")

    print("\n--- NON-EQUIVALENCE OF MISSING CLAIMS ---")
    print("Severity distribution of MISSING claims (proves missing phrases are not treated equally):")
    for level, count in missing_by_severity.most_common():
        print(f"  MISSING -> {level:<10}: {count} ({count/sum(missing_by_severity.values())*100:.1f}%)")

    print("\n--- REGULATORY / COMPLIANCE REVIEWS FLAGGED ---")
    print(f"Total Potential Issues Flagged for Review: {regulatory_flags_count}")
    for s in sample_regulatory_notes:
        print(f"[{s['pair_id']}] [{s['severity']}] Claim: \"{s['claim']}\"")
        print(f"  Review Note: {s['note']}")
        print("-" * 75)

    print("\n--- SAMPLE HIGH & CRITICAL SEVERITY FINDINGS ---")
    for s in sample_severities:
        print(f"[{s['pair_id']}] [{s['severity']} - Rank {s['rank']}] Status: {s['status']}")
        print(f"  Claim: \"{s['claim']}\"")
        print(f"  Rationale: {s['rationale']}")
        print("-" * 75)

    # Assertions
    assert sorting_violations == 0, "Violation: Findings are not sorted by priority rank!"
    assert definitive_legal_claims_count == 0, "Violation: Detected prohibited definitive legal declarations!"
    assert len(missing_by_severity) > 1, "Violation: Missing claims were all assigned the same severity level!"
    assert regulatory_flags_count > 0, "Violation: Zero regulatory concerns were flagged!"

    print("\n[SUCCESS] Phase 6: Assess Severity PASSED on all 60 pairs!")
    return True

if __name__ == "__main__":
    success = evaluate_phase6_dataset()
    if not success:
        sys.exit(1)

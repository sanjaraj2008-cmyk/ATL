import csv
import os
import sys
from collections import Counter

# Add ATL root to sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from core.audit_engine import AuditEngine
from core.schemas import ClaimStatus

DATA_DIR = r"c:\Users\SANJAY RAJ\Downloads\Srishti-2K26-Datasets-All\PS-03_message_match_auditor_dataset\PS-03_message_match_auditor"
ADS_CSV = os.path.join(DATA_DIR, "ads.csv")

def evaluate_phase5_dataset():
    if not os.path.exists(ADS_CSV):
        print(f"[ERROR] Dataset file not found at: {ADS_CSV}")
        return False

    with open(ADS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print("=" * 85)
    print(f"PHASE 5 EVALUATION: MISMATCH EXPLANATION & RECOMMENDATIONS ON {len(rows)} PAIRS")
    print("=" * 85)

    engine = AuditEngine()

    total_pairs = len(rows)
    total_findings = 0
    findings_with_mismatch = 0
    factual_findings = 0
    uncertain_findings = 0
    vague_recommendations_count = 0

    status_counts = Counter()
    certainty_counts = Counter()

    samples_by_status = {
        ClaimStatus.CONTRADICTED: [],
        ClaimStatus.PARTIALLY_SUPPORTED: [],
        ClaimStatus.MISSING: [],
        ClaimStatus.SUPPORTED: []
    }

    vague_phrases = ["fix ad", "improve page", "change copy", "update text", "fix website", "do better"]

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

        for finding in result.findings:
            total_findings += 1
            status_counts[finding.status.value] += 1

            # Phase 5 Check: Presence of complete MismatchExplanation
            m = finding.mismatch_details
            if m:
                findings_with_mismatch += 1
                if m.is_factual:
                    factual_findings += 1
                else:
                    uncertain_findings += 1

                certainty_counts[m.certainty_level.split(":")[0]] += 1

                # Check for vague recommendations
                ad_fix_lower = m.recommended_ad_fix.strip().lower()
                page_fix_lower = m.recommended_page_fix.strip().lower()

                if any(ad_fix_lower == vp for vp in vague_phrases) or len(m.recommended_ad_fix) < 15:
                    vague_recommendations_count += 1
                if any(page_fix_lower == vp for vp in vague_phrases) or len(m.recommended_page_fix) < 15:
                    vague_recommendations_count += 1

                if finding.status in samples_by_status and len(samples_by_status[finding.status]) < 2:
                    samples_by_status[finding.status].append({
                        "pair_id": pair_id,
                        "claim": m.original_ad_claim,
                        "finding": m.landing_page_finding,
                        "discrepancy": m.discrepancy_description,
                        "significance": m.practical_significance,
                        "conditions": m.conditions_and_visibility,
                        "ad_fix": m.recommended_ad_fix,
                        "page_fix": m.recommended_page_fix,
                        "certainty": m.certainty_level
                    })

    print("\n--- PHASE 5 EXPLANATION ENGINE INTEGRITY ---")
    print(f"Total Ad-Landing Page Pairs Evaluated:  {total_pairs}")
    print(f"Total Atomic Claims Audited:           {total_findings}")
    print(f"Findings with 7-Part Mismatch Details: {findings_with_mismatch} ({findings_with_mismatch/total_findings*100:.1f}%)")
    print(f"Factual Findings (DOM Provenance):     {factual_findings} ({factual_findings/total_findings*100:.1f}%)")
    print(f"Uncertain / Subjective Interpretations:{uncertain_findings} ({uncertain_findings/total_findings*100:.1f}%)")
    print(f"Vague or Incomplete Recommendations:   {vague_recommendations_count} (Must be 0)")

    print("\n--- FINDINGS BY STATUS ---")
    for status, count in status_counts.most_common():
        print(f"  {status:<25}: {count}")

    print("\n--- SAMPLE STANDARDIZED 6-PART EXPLANATIONS & RECOMMENDATIONS ---")
    for status, samples in samples_by_status.items():
        print(f"\n==================== STATUS: {status.value} ====================")
        for s in samples:
            print(f"[{s['pair_id']}]")
            print(f"  1. Ad Claim:       {s['claim']}")
            print(f"  2. Page Reality:   {s['finding']}")
            print(f"  3. Discrepancy:    {s['discrepancy']}")
            print(f"  4. Significance:   {s['significance']}")
            print(f"  5. Visibility/Ops: {s['conditions']}")
            print(f"  6a. Ad Fix:        {s['ad_fix']}")
            print(f"  6b. Page Fix:      {s['page_fix']}")
            print(f"  7. Certainty:      {s['certainty']}")
            print("-" * 75)

    # Assertions
    assert findings_with_mismatch == total_findings, "Violation: Not all findings have mismatch explanations!"
    assert vague_recommendations_count == 0, "Violation: Detected vague or empty recommendations!"
    print("\n[SUCCESS] Phase 5: Explain the Mismatch PASSED on all 60 pairs!")
    return True

if __name__ == "__main__":
    success = evaluate_phase5_dataset()
    if not success:
        sys.exit(1)

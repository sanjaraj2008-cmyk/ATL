import csv
import os
import sys
import json
from collections import Counter

# Ensure ATL path is in sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from core.audit_engine import AuditEngine
from core.schemas import ClaimStatus, Severity

DATA_DIR = r"c:\Users\SANJAY RAJ\Downloads\Srishti-2K26-Datasets-All\PS-03_message_match_auditor_dataset\PS-03_message_match_auditor"
ADS_CSV = os.path.join(DATA_DIR, "ads.csv")
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "audit_dataset_results.csv")
OUTPUT_JSON = os.path.join(SCRIPT_DIR, "audit_dataset_results.json")

def run_dataset_audit():
    if not os.path.exists(ADS_CSV):
        print(f"Dataset CSV not found at: {ADS_CSV}")
        return

    engine = AuditEngine()
    results_summary = []
    detailed_findings = []

    with open(ADS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"================================================================")
    print(f"Running Audit on {len(rows)} Ad-to-Landing-Page Pairs")
    print(f"================================================================")

    scores = []
    grades_counter = Counter()
    liabilities_count = 0
    total_claims_assessed = 0
    total_verified_quotes = 0
    total_reported_quotes = 0

    for idx, row in enumerate(rows, 1):
        pair_id = row["pair_id"]
        advertiser = row["advertiser"]
        vertical = row["vertical"]
        headlines = " | ".join(filter(None, [row.get("headline_1", ""), row.get("headline_2", ""), row.get("headline_3", "")]))
        descriptions = " ".join(filter(None, [row.get("description_1", ""), row.get("description_2", "")]))
        
        snapshot_rel = row["snapshot_file"]
        snapshot_path = os.path.join(DATA_DIR, snapshot_rel)

        if not os.path.exists(snapshot_path):
            print(f"[{pair_id}] Missing snapshot: {snapshot_path}")
            continue

        with open(snapshot_path, "r", encoding="utf-8") as sf:
            html = sf.read()

        res = engine.audit(headlines, descriptions, html)

        scores.append(res.match_score)
        grades_counter[res.grade] += 1
        if res.has_critical_marketing_liability:
            liabilities_count += 1

        total_claims_assessed += res.total_claims
        total_reported_quotes += res.reported_quotes_count
        total_verified_quotes += res.verified_quotes_count

        summary_item = {
            "pair_id": pair_id,
            "advertiser": advertiser,
            "vertical": vertical,
            "match_score": res.match_score,
            "grade": res.grade,
            "has_critical_liability": res.has_critical_marketing_liability,
            "coverage_index": res.evidence_coverage_index,
            "prominence_index": res.evidence_prominence_index,
            "evidence_validity_rate": res.evidence_validity_rate,
            "claims_count": res.total_claims,
            "critical_issues": res.critical_issues_count
        }
        results_summary.append(summary_item)

        # Collect detailed findings for CSV export
        for finding in res.findings:
            detailed_findings.append({
                "pair_id": pair_id,
                "advertiser": advertiser,
                "vertical": vertical,
                "overall_score": res.match_score,
                "claim_id": finding.claim_id,
                "ad_claim_text": finding.ad_claim_text,
                "status": finding.status.value,
                "reason_code": finding.reason_code.value,
                "materiality": finding.claim_materiality.value,
                "severity": finding.severity.value,
                "evidence_quote": finding.primary_evidence.quote if finding.primary_evidence else "",
                "evidence_zone": finding.primary_evidence.dom_zone.value if finding.primary_evidence else "",
                "quote_verified": finding.primary_evidence.is_verified if finding.primary_evidence else False,
                "explanation": finding.explanation,
                "recommended_ad_fix": finding.recommended_ad_fix,
                "recommended_page_fix": finding.recommended_page_fix
            })

        print(f"[{idx:02d}/60] {pair_id} ({advertiser:26}) | Score: {res.match_score:3d}/100 | Grade: {res.grade:25} | Claims: {res.total_claims} | Liability: {'YES' if res.has_critical_marketing_liability else 'NO'}")

    # Export to CSV
    keys = detailed_findings[0].keys()
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(detailed_findings)

    # Export to JSON
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "dataset_summary": {
                "total_pairs_audited": len(results_summary),
                "average_score": round(sum(scores) / len(scores), 1) if scores else 0,
                "critical_liabilities_detected": liabilities_count,
                "grade_breakdown": dict(grades_counter),
                "total_claims_assessed": total_claims_assessed,
                "overall_evidence_validity_rate": round(total_verified_quotes / total_reported_quotes * 100.0, 1) if total_reported_quotes > 0 else None
            },
            "pair_summaries": results_summary
        }, f, indent=2)

    print(f"\n================================================================")
    print(f"DATASET AUDIT EXECUTION COMPLETED")
    print(f"================================================================")
    print(f"Total Ad-Page Pairs Audited: {len(results_summary)}")
    print(f"Average Match Score:         {round(sum(scores)/len(scores), 1)}/100")
    print(f"Critical Liabilities:        {liabilities_count} pairs")
    print(f"Grade Breakdown:             {dict(grades_counter)}")
    print(f"Evidence Validity Rate:      {round(total_verified_quotes / total_reported_quotes * 100.0, 1) if total_reported_quotes > 0 else 'N/A'}%")
    print(f"Detailed CSV Report Saved:   {OUTPUT_CSV}")
    print(f"Summary JSON Report Saved:   {OUTPUT_JSON}")
    print(f"================================================================")

if __name__ == "__main__":
    run_dataset_audit()

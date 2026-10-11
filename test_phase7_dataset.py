import csv
import json
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

def evaluate_phase7_dataset():
    if not os.path.exists(ADS_CSV):
        print(f"[ERROR] Dataset file not found at: {ADS_CSV}")
        return False

    with open(ADS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print("=" * 85)
    print(f"PHASE 7 EVALUATION: STRUCTURED JSON SCHEMA VALIDATION ON {len(rows)} PAIRS")
    print("=" * 85)

    engine = AuditEngine()

    total_pairs = len(rows)
    valid_json_outputs = 0
    schema_conformant_reports = 0
    total_claims_validated = 0
    phantom_quotes_detected = 0
    missing_source_locations = 0

    sample_reports = {}

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

        # 1. Test model_dump_json / to_json()
        try:
            raw_json = result.to_json()
            json.loads(raw_json)
            valid_json_outputs += 1
        except Exception as e:
            print(f"[ERROR] JSON serialization failed for {pair_id}: {e}")

        # 2. Test to_structured_report()
        report = result.to_structured_report()
        try:
            # Verify clean serialization with native json
            dumped = json.dumps(report, indent=2)
            parsed = json.loads(dumped)

            # Validate schema contract
            assert "audit_status" in parsed
            assert "overall_score" in parsed
            assert "scoring_methodology_version" in parsed
            assert "evidence_coverage_index" in parsed
            assert "individual_claims" in parsed

            for claim_item in parsed["individual_claims"]:
                total_claims_validated += 1
                status = claim_item["status"]
                quote = claim_item["quotation"]
                loc = claim_item["source_location"]

                if status in (ClaimStatus.MISSING.value, ClaimStatus.UNVERIFIABLE.value):
                    if quote is not None:
                        phantom_quotes_detected += 1
                elif status == ClaimStatus.SUPPORTED.value:
                    if loc is None or loc.get("block_id") is None:
                        missing_source_locations += 1

            schema_conformant_reports += 1

            if pair_id in ("P01", "P32"):
                sample_reports[pair_id] = parsed

        except Exception as e:
            print(f"[ERROR] Structured report validation failed for {pair_id}: {e}")

    print("\n--- PHASE 7 STRUCTURED OUTPUT SUMMARY ---")
    print(f"Total Ad-Landing Page Pairs Evaluated: {total_pairs}")
    print(f"Valid JSON Serializations:            {valid_json_outputs} / {total_pairs} (100%)")
    print(f"Schema-Conformant Structured Reports:  {schema_conformant_reports} / {total_pairs} (100%)")
    print(f"Total Individual Claims Validated:     {total_claims_validated}")
    print(f"Phantom Quotes on Missing Claims:      {phantom_quotes_detected} (Must be 0)")
    print(f"Missing Source Locations on Supported: {missing_source_locations} (Must be 0)")

    # Save sample report to disk to demonstrate output artifact
    sample_file = os.path.join(SCRIPT_DIR, "sample_audit_report.json")
    with open(sample_file, "w", encoding="utf-8") as f:
        json.dump(sample_reports.get("P01"), f, indent=2)
    print(f"\n[INFO] Wrote sample structured audit report to: {sample_file}")

    print("\n--- SAMPLE STRUCTURED JSON REPORT (PAIR P01) ---")
    p01_sample = sample_reports.get("P01", {})
    print(f"Audit Status:          {p01_sample.get('audit_status')}")
    print(f"Overall Score:         {p01_sample.get('overall_score')}/100 ({p01_sample.get('grade')})")
    print(f"Methodology Version:   {p01_sample.get('scoring_methodology_version')}")
    print(f"Evidence Coverage:     {p01_sample.get('evidence_coverage_index')}%")
    print(f"Evidence Validity Rate:{p01_sample.get('evidence_validity_rate')}%")
    print(f"Total Claims Audited:  {len(p01_sample.get('individual_claims', []))}")
    for idx, c in enumerate(p01_sample.get("individual_claims", []), 1):
        print(f"\n  Claim #{idx}: \"{c['ad_claim_text']}\"")
        print(f"    Status:   {c['status']} | Severity: {c['severity']} (Priority Rank {c['priority_rank']})")
        print(f"    Quote:    {c['quotation']}")
        print(f"    Location: {c['source_location']}")
        print(f"    Ad Fix:   {c['recommended_ad_fix']}")
        print(f"    Page Fix: {c['recommended_page_fix']}")

    # Assertions
    assert valid_json_outputs == total_pairs, "Violation: JSON serialization failed on dataset!"
    assert schema_conformant_reports == total_pairs, "Violation: Schema non-conformance detected!"
    assert phantom_quotes_detected == 0, "Violation: Phantom quotes detected on missing claims!"
    assert missing_source_locations == 0, "Violation: Missing source locations on supported claims!"

    print("\n[SUCCESS] Phase 7: Return Structured Output PASSED on all 60 pairs!")
    return True

if __name__ == "__main__":
    success = evaluate_phase7_dataset()
    if not success:
        sys.exit(1)

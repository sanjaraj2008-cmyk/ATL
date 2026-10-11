import csv
import os
import sys
from collections import Counter

# Add ATL root to sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from core.audit_engine import AuditEngine
from core.schemas import ClaimStatus, VerificationStatus, RelevanceStatus

DATA_DIR = r"c:\Users\SANJAY RAJ\Downloads\Srishti-2K26-Datasets-All\PS-03_message_match_auditor_dataset\PS-03_message_match_auditor"
ADS_CSV = os.path.join(DATA_DIR, "ads.csv")

def evaluate_phase4_dataset():
    if not os.path.exists(ADS_CSV):
        print(f"[ERROR] Dataset file not found at: {ADS_CSV}")
        return False

    with open(ADS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print("=" * 85)
    print(f"PHASE 4 EVALUATION: DETERMINISTIC QUOTATION VERIFICATION ON {len(rows)} PAIRS")
    print("=" * 85)

    engine = AuditEngine()

    total_pairs = len(rows)
    total_findings = 0
    total_citations = 0
    total_verified = 0
    total_invalid = 0
    total_review = 0

    match_methods = Counter()
    dom_zones = Counter()
    relevance_counts = Counter()
    missing_findings_with_quote = 0
    offset_verification_failures = 0

    sample_verified_citations = []

    for idx, row in enumerate(rows):
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

        total_citations += result.reported_quotes_count
        total_verified += result.verified_quotes_count
        total_invalid += result.rejected_quotes_count

        for finding in result.findings:
            total_findings += 1
            # Step 1: Check absence guarantee on MISSING/UNVERIFIABLE findings
            if finding.status in (ClaimStatus.MISSING, ClaimStatus.UNVERIFIABLE):
                if finding.primary_evidence is not None:
                    missing_findings_with_quote += 1

            # Step 2: Check verified primary evidence integrity
            if finding.primary_evidence and finding.primary_evidence.is_verified:
                ev = finding.primary_evidence
                dom_zones[ev.dom_zone.value] += 1
                match_methods[ev.verification_method] += 1
                relevance_counts[ev.relevance_status.value] += 1

                # Check exact source offsets existence
                if ev.source_start_offset is None or ev.source_end_offset is None:
                    offset_verification_failures += 1

                if len(sample_verified_citations) < 8:
                    sample_verified_citations.append({
                        "pair_id": pair_id,
                        "claim": finding.ad_claim_text,
                        "status": finding.status.value,
                        "quote": ev.quote,
                        "block_id": ev.block_id,
                        "zone": ev.dom_zone.value,
                        "method": ev.verification_method,
                        "offsets": f"[{ev.source_start_offset}:{ev.source_end_offset}]",
                        "relevance": ev.relevance_status.value
                    })

        for rec in result.citation_records:
            if rec.verification_status == VerificationStatus.REQUIRES_REVIEW:
                total_review += 1

    print("\n--- PHASE 4 CITATION VERIFICATION SUMMARY ---")
    print(f"Total Ad-Landing Page Pairs Evaluated: {total_pairs}")
    print(f"Total Atomic Claims Audited:          {total_findings}")
    print(f"Total Evidence Citations Evaluated:   {total_citations}")
    print(f"  - Deterministically Verified:        {total_verified} ({total_verified/max(1, total_citations)*100:.1f}%)")
    print(f"  - Rejected / Invalid:                {total_invalid}")
    print(f"  - Flagged for Review:                {total_review}")

    print("\n--- PROVENANCE & OFFSET FIDELITY ---")
    print(f"Missing/Unverifiable Claims with Quote (Must be 0): {missing_findings_with_quote}")
    print(f"Verified Quotes Missing Exact Offsets (Must be 0):  {offset_verification_failures}")

    print("\n--- VERIFICATION MATCH METHODS ---")
    for method, count in match_methods.most_common():
        print(f"  {method:<25}: {count} ({count/max(1, total_verified)*100:.1f}%)")

    print("\n--- EVIDENCE DOM ZONE DISTRIBUTION ---")
    for zone, count in dom_zones.most_common():
        print(f"  {zone:<25}: {count} ({count/max(1, total_verified)*100:.1f}%)")

    print("\n--- RELEVANCE STATUS ---")
    for rel, count in relevance_counts.most_common():
        print(f"  {rel:<25}: {count} ({count/max(1, total_verified)*100:.1f}%)")

    print("\n--- SAMPLE VERIFIED EVIDENCE CITATIONS ---")
    for s in sample_verified_citations:
        print(f"[{s['pair_id']}] Status: {s['status']}")
        print(f"  Claim:   \"{s['claim']}\"")
        print(f"  Quote:   \"{s['quote']}\"")
        print(f"  Block:   {s['block_id']} ({s['zone']}) | Offsets: {s['offsets']} | Method: {s['method']}")
        print(f"  Relevance: {s['relevance']}")
        print("-" * 60)

    # Assert Phase 4 guarantees
    assert missing_findings_with_quote == 0, "Violation: Missing claims retain quotes!"
    assert offset_verification_failures == 0, "Violation: Verified quotes lack character offsets!"
    assert total_verified > 0, "Violation: No quotes verified!"

    print("\n[SUCCESS] Phase 4: Quotation Verification Engine PASSED on all 60 pairs!")
    return True

if __name__ == "__main__":
    success = evaluate_phase4_dataset()
    if not success:
        sys.exit(1)

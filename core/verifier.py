import re
from typing import List, Optional, Tuple
from core.schemas import (
    DOMBlock, EvidencePassage, DOMZone, ClaimStatus,
    VerificationStatus, RelevanceStatus, CitationVerificationRecord,
    AuditFinding, ReasonCode
)

class EvidenceVerifier:
    """
    Phase 4: Quotation Verification Engine.
    Enforces deterministic, backend-verified quotations:
    1. Exact & controlled whitespace text matching against authoritative source blocks.
    2. Exact source start and end offset extraction.
    3. Block ID and Snapshot ID provenance validation.
    4. Independent semantic relevance evaluation.
    5. Automatic rejection and recovery of invalid/fabricated citations.
    6. Citation verification record logging.
    """

    GENERIC_STOP_WORDS = {
        "start", "started", "starting", "using", "uses", "used", "today", "with",
        "your", "yours", "our", "ours", "their", "theirs", "his", "her", "hers", "its",
        "my", "mine", "you", "they", "them", "this", "that", "these", "those", "make",
        "makes", "making", "online", "click", "here", "learn", "more", "best", "great",
        "simple", "easy", "fast", "quick", "need", "needs", "help", "from", "into", "over",
        "such", "free", "trial", "plan", "join", "sign", "signup", "register", "come",
        "look", "about", "have", "more", "most", "take", "takes", "some", "every", "page",
        "menu", "home", "back", "next", "view", "read", "open", "close", "find", "good",
        "well", "just", "also", "very", "then", "what", "when", "where", "which", "will",
        "would", "could", "should", "tell", "give", "gives", "getting", "gets"
    }

    SYNONYM_MAP = {
        "loan": ["loan", "funding", "financing", "credit", "borrow", "capital"],
        "funding": ["funding", "loan", "financing", "credit", "capital"],
        "credit": ["credit", "loan", "funding", "score", "borrow", "card", "payment"],
        "card": ["card", "credit card", "payment", "billing", "pay"],
        "payment": ["payment", "card", "credit card", "billing", "fee", "pay"],
        "trial": ["trial", "free trial", "test drive", "demo", "evaluation"],
        "discount": ["discount", "off", "save", "savings", "deal"],
        "approval": ["approval", "approved", "decision", "decisioned"],
        "instant": ["instant", "instantaneous", "immediate", "same-day", "same day"],
        "rate": ["rate", "apr", "interest", "percentage"],
        "shipping": ["shipping", "delivery", "dispatch", "ship"],
        "guarantee": ["guarantee", "guaranteed", "warranty", "money-back", "satisfaction"],
        "collateral": ["collateral", "security", "secured"],
        "support": ["support", "service", "help", "assistance"],
        "software": ["software", "platform", "app", "application", "tool", "system"],
        "management": ["management", "manage", "organize", "tracker", "tracking", "coordination"],
        "apply": ["apply", "application", "applying", "applied"],
        "minute": ["minute", "minutes", "min", "mins"],
        "profile": ["profile", "profiles", "type", "types", "tier", "tiers"]
    }

    def verify_quote(
        self,
        candidate_quote: str,
        blocks: List[DOMBlock],
        expected_block_id: Optional[str] = None,
        expected_snapshot_id: Optional[str] = None
    ) -> Tuple[bool, Optional[EvidencePassage]]:
        """Backwards-compatible 2-tuple verification."""
        ok, passage, _ = self.verify_quote_detailed(
            candidate_quote, blocks, expected_block_id, expected_snapshot_id
        )
        return ok, passage

    def verify_quote_detailed(
        self,
        candidate_quote: str,
        blocks: List[DOMBlock],
        expected_block_id: Optional[str] = None,
        expected_snapshot_id: Optional[str] = None
    ) -> Tuple[bool, Optional[EvidencePassage], Optional[str]]:
        """
        Step 3 & 4: Deterministic text verification against authoritative source blocks.
        Returns: (is_verified, EvidencePassage, rejection_reason)
        """
        if not candidate_quote or not candidate_quote.strip():
            return False, None, "Quotation text is empty."

        cleaned_target = self._normalize_whitespace(candidate_quote)
        if not cleaned_target:
            return False, None, "Quotation text contains only whitespace."

        # If a specific block_id is expected, prioritize and validate it
        candidate_blocks = blocks
        if expected_block_id:
            matching_blocks = [b for b in blocks if b.block_id == expected_block_id]
            if not matching_blocks:
                return False, None, f"Referenced block_id '{expected_block_id}' does not exist in extracted page blocks."
            target_block = matching_blocks[0]
            if expected_snapshot_id and target_block.snapshot_id and target_block.snapshot_id != expected_snapshot_id:
                return False, None, f"Snapshot mismatch: block belongs to snapshot '{target_block.snapshot_id}', expected '{expected_snapshot_id}'."
            candidate_blocks = matching_blocks

        # 1. Exact raw substring match
        for block in candidate_blocks:
            quote_strip = candidate_quote.strip()
            start_idx = block.raw_text.find(quote_strip)
            if start_idx != -1:
                end_idx = start_idx + len(quote_strip)
                return True, EvidencePassage(
                    quote=quote_strip,
                    normalized_quote=cleaned_target,
                    block_id=block.block_id,
                    dom_zone=block.dom_zone,
                    tag_name=block.tag_name,
                    is_verified=True,
                    verification_method="exact",
                    selector_path=block.selector_path,
                    prominence_weight=block.prominence_weight,
                    snapshot_id=block.snapshot_id,
                    source_start_offset=start_idx,
                    source_end_offset=end_idx,
                    verification_status=VerificationStatus.VERIFIED,
                    relevance_status=RelevanceStatus.RELEVANT
                ), None

        # 2. Controlled whitespace-normalized match (preserves raw text offsets)
        for block in candidate_blocks:
            # Build regex pattern where whitespace sequences match any whitespace
            words = cleaned_target.split()
            if words:
                pattern = r'\s+'.join(re.escape(w) for w in words)
                match = re.search(pattern, block.raw_text)
                if match:
                    start_idx = match.start()
                    end_idx = match.end()
                    raw_slice = block.raw_text[start_idx:end_idx]
                    return True, EvidencePassage(
                        quote=raw_slice,
                        normalized_quote=cleaned_target,
                        block_id=block.block_id,
                        dom_zone=block.dom_zone,
                        tag_name=block.tag_name,
                        is_verified=True,
                        verification_method="normalized_whitespace",
                        selector_path=block.selector_path,
                        prominence_weight=block.prominence_weight,
                        snapshot_id=block.snapshot_id,
                        source_start_offset=start_idx,
                        source_end_offset=end_idx,
                        verification_status=VerificationStatus.VERIFIED,
                        relevance_status=RelevanceStatus.RELEVANT
                    ), None

        # 3. Controlled case-insensitive match (retains raw slice & offsets)
        for block in candidate_blocks:
            words = cleaned_target.split()
            if words:
                pattern = r'\s+'.join(re.escape(w) for w in words)
                match = re.search(pattern, block.raw_text, re.IGNORECASE)
                if match:
                    start_idx = match.start()
                    end_idx = match.end()
                    raw_slice = block.raw_text[start_idx:end_idx]
                    return True, EvidencePassage(
                        quote=raw_slice,
                        normalized_quote=self._normalize_whitespace(raw_slice),
                        block_id=block.block_id,
                        dom_zone=block.dom_zone,
                        tag_name=block.tag_name,
                        is_verified=True,
                        verification_method="case_insensitive",
                        selector_path=block.selector_path,
                        prominence_weight=block.prominence_weight,
                        snapshot_id=block.snapshot_id,
                        source_start_offset=start_idx,
                        source_end_offset=end_idx,
                        verification_status=VerificationStatus.VERIFIED,
                        relevance_status=RelevanceStatus.RELEVANT
                    ), None

        # If not found in expected block or all blocks: reject
        if expected_block_id:
            return False, None, f"Quotation text was not found within referenced block '{expected_block_id}'."
        return False, None, "Quotation text was not found in any extracted page blocks."

    def verify_relevance(
        self,
        claim_text: str,
        finding_status: ClaimStatus,
        passage: EvidencePassage
    ) -> Tuple[RelevanceStatus, Optional[str]]:
        """
        Step 5: Evidentiary relevance evaluation.
        Verifies whether the textually genuine quote supports the finding status.
        """
        quote_lower = passage.quote.lower()
        claim_lower = claim_text.lower()

        # Extract content words (> 3 characters) excluding generic stop words
        claim_words = [w for w in re.findall(r'\b[a-zA-Z]{3,}\b', claim_lower) if w not in self.GENERIC_STOP_WORDS]
        if not claim_words:
            claim_words = [w for w in re.findall(r'\b[a-zA-Z]{4,}\b', claim_lower)]
        numbers_in_claim = re.findall(r'\d+(?:\.\d+)?', claim_lower)

        # Build expansions for each substantive keyword
        kw_expansions = []
        for w in claim_words:
            exp = {w}
            for root, syns in self.SYNONYM_MAP.items():
                if root in w or w in root:
                    exp.update(syns)
            kw_expansions.append(exp)

        # Check how many distinct substantive keywords appear in the quote
        matched_kw_count = sum(1 for exp in kw_expansions if any(re.search(r'\b' + re.escape(syn) + r'\b', quote_lower) for syn in exp))
        min_kws_needed = 1 if len(claim_words) == 1 else min(2, len(claim_words))
        has_keyword_match = matched_kw_count >= min_kws_needed
        has_number_match = any(num in quote_lower for num in numbers_in_claim)

        # Contradiction indicators (e.g. "no refunds", "non-refundable", different numbers, payment required)
        contradiction_cues = [
            "no refunds", "non-refundable", "all sales final", "not eligible", "disclaim",
            "fee required", "payment details", "enter your payment", "payment required",
            "card required", "billing details"
        ]
        has_contradiction_cue = any(cue in quote_lower for cue in contradiction_cues)

        if finding_status == ClaimStatus.CONTRADICTED:
            if has_contradiction_cue or has_keyword_match or (numbers_in_claim and any(c.isdigit() for c in quote_lower)):
                return RelevanceStatus.RELEVANT, None
            return RelevanceStatus.IRRELEVANT, "Quotation does not contain contradictory terms or conflicting specifications."

        if finding_status in (ClaimStatus.SUPPORTED, ClaimStatus.PARTIALLY_SUPPORTED):
            if has_keyword_match or has_number_match:
                return RelevanceStatus.RELEVANT, None
            return RelevanceStatus.IRRELEVANT, "Quotation does not contain sufficient substantive terms or numbers relevant to the advertised claim."

        return RelevanceStatus.RELEVANT, None

    def audit_and_harden_finding(
        self,
        finding: AuditFinding,
        blocks: List[DOMBlock],
        snapshot_id: str
    ) -> List[CitationVerificationRecord]:
        """
        Steps 6 & 7: Verify all citations attached to a finding, reject fabricated quotes,
        attempt automatic recovery from genuine blocks, and generate verification records.
        """
        records: List[CitationVerificationRecord] = []

        # If claim is MISSING or UNVERIFIABLE, ensure NO quotation is attached
        if finding.status in (ClaimStatus.MISSING, ClaimStatus.UNVERIFIABLE):
            if finding.primary_evidence:
                # Fabricated quote attached to missing claim -> reject and remove
                rec = CitationVerificationRecord(
                    citation_id=f"CIT_{finding.claim_id}_01",
                    claim_id=finding.claim_id,
                    block_id=finding.primary_evidence.block_id or "UNKNOWN",
                    snapshot_id=snapshot_id,
                    quoted_text=finding.primary_evidence.quote,
                    verification_status=VerificationStatus.INVALID,
                    match_method="unverified",
                    dom_zone=finding.primary_evidence.dom_zone,
                    relevance_status=RelevanceStatus.IRRELEVANT,
                    rejection_reason="Quotation cannot be attached to a MISSING claim; removed."
                )
                records.append(rec)
                finding.primary_evidence = None
            return records

        # If finding has primary evidence, verify it deterministically
        if finding.primary_evidence:
            ev = finding.primary_evidence
            expected_block = ev.block_id if ev.block_id and ev.block_id.startswith("B") else None
            
            is_valid, verified_ev, rej_reason = self.verify_quote_detailed(
                candidate_quote=ev.quote,
                blocks=blocks,
                expected_block_id=expected_block,
                expected_snapshot_id=snapshot_id
            )

            cit_id = f"CIT_{finding.claim_id}_01"

            if is_valid and verified_ev:
                # Text is verified: check relevance
                rel_status, rel_reason = self.verify_relevance(
                    claim_text=finding.ad_claim_text,
                    finding_status=finding.status,
                    passage=verified_ev
                )

                verified_ev.relevance_status = rel_status
                if rel_status == RelevanceStatus.IRRELEVANT:
                    verified_ev.verification_status = VerificationStatus.REQUIRES_REVIEW
                    verified_ev.rejection_reason = rel_reason

                finding.primary_evidence = verified_ev

                rec = CitationVerificationRecord(
                    citation_id=cit_id,
                    claim_id=finding.claim_id,
                    block_id=verified_ev.block_id,
                    snapshot_id=verified_ev.snapshot_id or snapshot_id,
                    quoted_text=verified_ev.quote,
                    verification_status=verified_ev.verification_status,
                    match_method=verified_ev.verification_method,
                    source_start_offset=verified_ev.source_start_offset,
                    source_end_offset=verified_ev.source_end_offset,
                    dom_zone=verified_ev.dom_zone,
                    relevance_status=rel_status,
                    rejection_reason=rel_reason
                )
                records.append(rec)
            else:
                # Text verification failed: record INVALID citation
                rec = CitationVerificationRecord(
                    citation_id=cit_id,
                    claim_id=finding.claim_id,
                    block_id=ev.block_id or "UNKNOWN",
                    snapshot_id=snapshot_id,
                    quoted_text=ev.quote,
                    verification_status=VerificationStatus.INVALID,
                    match_method="unverified",
                    dom_zone=ev.dom_zone,
                    relevance_status=RelevanceStatus.IRRELEVANT,
                    rejection_reason=rej_reason
                )
                records.append(rec)

                # Step 7 Recovery: Search stored blocks for a legitimate alternative
                tokens = [t.lower() for t in re.findall(r'\b[a-zA-Z]{4,}\b', finding.ad_claim_text)]
                candidate_blocks = self.find_best_candidate_passages(tokens, blocks)
                recovered = False

                for cb in candidate_blocks:
                    val_ok, recov_ev, _ = self.verify_quote(cb.raw_text, blocks, expected_block_id=cb.block_id)
                    if val_ok and recov_ev:
                        finding.primary_evidence = recov_ev
                        finding.reason_code = ReasonCode.SEMANTIC_EQUIVALENT
                        recovered = True
                        break

                if not recovered:
                    finding.primary_evidence = None
                    finding.status = ClaimStatus.MISSING
                    finding.reason_code = ReasonCode.FABRICATED_QUOTE_REJECTED
                    finding.explanation = "Proposed quotation failed verification and was rejected. Supporting evidence was not found."

        return records

    def find_best_candidate_passages(self, claim_keywords: List[str], blocks: List[DOMBlock]) -> List[DOMBlock]:
        """Retrieve candidate blocks that mention keywords or synonyms for a claim with substantive threshold."""
        # 1. Filter out generic stop words
        substantive_kws = [k.lower() for k in claim_keywords if k.lower() not in self.GENERIC_STOP_WORDS and len(k) >= 3]
        if not substantive_kws:
            substantive_kws = [k.lower() for k in claim_keywords if len(k) >= 3]

        if not substantive_kws:
            return []

        # Determine threshold
        if len(substantive_kws) == 1:
            min_hits = 1
        elif len(substantive_kws) == 2:
            min_hits = 2
        else:
            min_hits = max(2, int(len(substantive_kws) * 0.5))

        # Map each substantive keyword to its synonym expansion
        kw_expansions = []
        for kw in substantive_kws:
            exp = {kw}
            for root, syns in self.SYNONYM_MAP.items():
                if root in kw or kw in root:
                    exp.update(syns)
            kw_expansions.append(exp)

        matched = []
        for block in blocks:
            text_lower = block.normalized_text.lower()
            # Count how many distinct substantive keywords matched this block
            hit_count = 0
            for exp in kw_expansions:
                if any(re.search(r'\b' + re.escape(syn) + r'\b', text_lower) for syn in exp):
                    hit_count += 1

            if hit_count >= min_hits:
                score = hit_count * (1.0 + block.prominence_weight * 0.5)
                matched.append((score, block.order_index, block))

        matched.sort(key=lambda x: (-x[0], x[1]))
        return [b for _, _, b in matched[:5]]

    def _normalize_whitespace(self, text: str) -> str:
        return re.sub(r'\s+', ' ', text).strip()

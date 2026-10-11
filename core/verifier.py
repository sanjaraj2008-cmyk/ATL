import re
from typing import List, Optional, Tuple
from core.schemas import DOMBlock, EvidencePassage, DOMZone

class EvidenceVerifier:
    """
    Deterministic Two-Tier Grounding & Verification.
    Strictly verifies evidence quotes against extracted DOMBlocks.
    A quote is NEVER marked verified unless it actually exists in the source text.
    """

    def verify_quote(self, candidate_quote: str, blocks: List[DOMBlock]) -> Tuple[bool, Optional[EvidencePassage]]:
        if not candidate_quote or not candidate_quote.strip():
            return False, None

        cleaned_target = self._normalize_whitespace(candidate_quote)
        if not cleaned_target:
            return False, None

        # 1. Exact or normalized substring match against blocks
        for block in blocks:
            # Check exact raw match
            if candidate_quote.strip() in block.raw_text:
                return True, EvidencePassage(
                    quote=candidate_quote.strip(),
                    normalized_quote=cleaned_target,
                    block_id=block.block_id,
                    dom_zone=block.dom_zone,
                    tag_name=block.tag_name,
                    is_verified=True,
                    verification_method="exact"
                )

            # Check normalized whitespace match
            if cleaned_target in block.normalized_text:
                # Extract the corresponding raw segment if possible, or use candidate
                return True, EvidencePassage(
                    quote=candidate_quote.strip(),
                    normalized_quote=cleaned_target,
                    block_id=block.block_id,
                    dom_zone=block.dom_zone,
                    tag_name=block.tag_name,
                    is_verified=True,
                    verification_method="normalized_whitespace"
                )

        # 2. Check case-insensitive substring match
        target_lower = cleaned_target.lower()
        for block in blocks:
            if target_lower in block.normalized_text.lower():
                return True, EvidencePassage(
                    quote=candidate_quote.strip(),
                    normalized_quote=cleaned_target,
                    block_id=block.block_id,
                    dom_zone=block.dom_zone,
                    tag_name=block.tag_name,
                    is_verified=True,
                    verification_method="case_insensitive"
                )

        # Non-existent quote in source: rejected
        return False, None

    def find_best_candidate_passages(self, claim_keywords: List[str], blocks: List[DOMBlock]) -> List[DOMBlock]:
        """Retrieve candidate blocks that mention keywords for a claim."""
        matched = []
        for block in blocks:
            text_lower = block.normalized_text.lower()
            hit_count = sum(1 for kw in claim_keywords if kw.lower() in text_lower)
            if hit_count > 0:
                matched.append((hit_count, block.order_index, block))

        # Sort by hit count descending, then order index ascending (earlier DOM blocks preferred)
        matched.sort(key=lambda x: (-x[0], x[1]))
        return [b for _, _, b in matched[:5]]

    def _normalize_whitespace(self, text: str) -> str:
        return re.sub(r'\s+', ' ', text).strip()

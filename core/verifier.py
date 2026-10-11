import re
from typing import List, Optional, Tuple
from core.schemas import DOMBlock, EvidencePassage, DOMZone

class EvidenceVerifier:
    """
    Phase 2 & Phase 4: Grounded Passage Identification and Quotation Verification.
    Strictly verifies evidence quotes against extracted DOMBlocks.
    - Preserves source location, block ID, selector path, and prominence weight.
    - Rejects hallucinated quotes.
    - Expands candidate search with domain synonyms while strictly verifying final citations.
    """

    SYNONYM_MAP = {
        "loan": ["loan", "funding", "financing", "credit", "borrow", "capital"],
        "funding": ["funding", "loan", "financing", "credit", "capital"],
        "credit": ["credit", "loan", "funding", "score", "borrow"],
        "trial": ["trial", "free trial", "test drive", "demo", "evaluation"],
        "discount": ["discount", "off", "save", "savings", "deal"],
        "approval": ["approval", "approved", "decision", "decisioned"],
        "instant": ["instant", "instantaneous", "immediate", "same-day", "same day"],
        "rate": ["rate", "apr", "interest", "percentage"],
        "shipping": ["shipping", "delivery", "dispatch", "ship"],
        "guarantee": ["guarantee", "guaranteed", "warranty", "money-back", "satisfaction"],
        "collateral": ["collateral", "security", "secured"],
        "support": ["support", "service", "help", "assistance"]
    }

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
                    verification_method="exact",
                    selector_path=block.selector_path,
                    prominence_weight=block.prominence_weight
                )

            # Check normalized whitespace match
            if cleaned_target in block.normalized_text:
                return True, EvidencePassage(
                    quote=candidate_quote.strip(),
                    normalized_quote=cleaned_target,
                    block_id=block.block_id,
                    dom_zone=block.dom_zone,
                    tag_name=block.tag_name,
                    is_verified=True,
                    verification_method="normalized_whitespace",
                    selector_path=block.selector_path,
                    prominence_weight=block.prominence_weight
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
                    verification_method="case_insensitive",
                    selector_path=block.selector_path,
                    prominence_weight=block.prominence_weight
                )

        # Non-existent quote in source: rejected
        return False, None

    def find_best_candidate_passages(self, claim_keywords: List[str], blocks: List[DOMBlock]) -> List[DOMBlock]:
        """Retrieve candidate blocks that mention keywords or synonyms for a claim."""
        expanded_keywords = set()
        for kw in claim_keywords:
            kw_low = kw.lower()
            expanded_keywords.add(kw_low)
            for root, syns in self.SYNONYM_MAP.items():
                if root in kw_low or kw_low in root:
                    expanded_keywords.update(syns)

        matched = []
        for block in blocks:
            text_lower = block.normalized_text.lower()
            hit_count = sum(1 for kw in expanded_keywords if kw in text_lower)
            if hit_count > 0:
                # Weighted score based on hits and prominence
                score = hit_count * (1.0 + block.prominence_weight * 0.5)
                matched.append((score, block.order_index, block))

        # Sort by score descending, then order index ascending (earlier DOM blocks preferred)
        matched.sort(key=lambda x: (-x[0], x[1]))
        return [b for _, _, b in matched[:5]]

    def _normalize_whitespace(self, text: str) -> str:
        return re.sub(r'\s+', ' ', text).strip()

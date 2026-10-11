import re
import html
from typing import List, Tuple
from bs4 import BeautifulSoup, Comment
from core.schemas import DOMBlock, DOMZone

def normalize_text(text: str) -> str:
    """Normalize whitespace, decode HTML entities, and remove non-printable characters."""
    if not text:
        return ""
    decoded = html.unescape(text)
    # Replace non-breaking spaces and all unicode whitespace with standard space
    cleaned = re.sub(r'[\s\u00a0\u2000-\u200b\u202f\u205f\u3000]+', ' ', decoded)
    return cleaned.strip()

class ContentExtractor:
    """
    Phase 2: Examine the Supplied Landing-Page Evidence.
    - Reads extracted page content and rich source metadata.
    - Assigns DOM zones, selector paths, and prominence weights.
    - Detects conditions, exclusions, and disclaimers within blocks.
    - Evaluates retrieval completeness to prevent false absence conclusions.
    """
    
    HERO_TAGS = {'h1', 'header'}
    BODY_TAGS = {'p', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'button', 'a', 'span', 'div', 'td', 'th'}
    FOOTER_TAGS = {'footer', 'small'}
    
    FOOTER_INDICATORS = {'footer', 'disclaimer', 'legal', 'terms', 'fineprint', 'copyright', 'privacy', 'fine'}
    HERO_INDICATORS = {'hero', 'banner', 'headline', 'main-title', 'top'}

    CONDITION_PATTERNS = [
        r'\*',
        r'†',
        r'\bterms\s*(?:and|&)?\s*conditions\b',
        r'\bsubject\s*to\b',
        r'\bqualified\s*(?:borrowers|buyers|applicants|customers)\b',
        r'\brestrictions\s*apply\b',
        r'\bsee\s*details\b',
        r'\bdisclaimer\b',
        r'\bwhile\s*supplies\s*last\b',
        r'\bfor\s*eligible\s*users\b'
    ]

    def extract_blocks(self, html_content: str) -> Tuple[List[DOMBlock], List[str]]:
        warnings = []
        if not html_content or not html_content.strip():
            warnings.append("Input HTML snapshot is empty.")
            return [], warnings

        # Phase 2 Rule 5: Check for incomplete or truncated retrieval
        self._check_retrieval_completeness(html_content, warnings)

        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove irrelevant tags that pollute content
        for element in soup(['script', 'style', 'noscript', 'iframe']):
            element.decompose()

        # Remove HTML comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        blocks: List[DOMBlock] = []
        block_counter = 1

        # Extract SVG title/aria labels before stripping
        for svg in soup.find_all('svg'):
            label = svg.get('aria-label') or (svg.find('title').get_text() if svg.find('title') else "")
            if label and label.strip():
                norm = normalize_text(label)
                if norm:
                    blocks.append(DOMBlock(
                        block_id=f"B{block_counter:03d}",
                        tag_name="svg_label",
                        dom_zone=DOMZone.MAIN_BODY,
                        order_index=block_counter,
                        raw_text=label.strip(),
                        normalized_text=norm,
                        is_hidden=False,
                        selector_path="svg",
                        prominence_weight=0.5,
                        has_conditions=self._detect_conditions(label)
                    ))
                    block_counter += 1

        # Identify all meaningful content nodes
        candidates = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li', 'button', 'a', 'footer', 'small', 'div'])
        
        seen_texts = set()
        for idx, tag in enumerate(candidates):
            # Only process leaf-ish nodes or nodes without block children
            has_nested_blocks = bool(tag.find(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'footer', 'small']))
            if has_nested_blocks and tag.name in {'div', 'footer'}:
                continue

            raw = tag.get_text()
            norm = normalize_text(raw)
            if not norm or len(norm) < 2:
                continue

            # Skip duplicate identical adjacent text blocks
            if norm in seen_texts:
                continue
            seen_texts.add(norm)

            # Check hidden styles and attributes
            style = tag.get('style', '') or ''
            classes = tag.get('class', [])
            is_hidden = (
                'display:none' in style.lower() or
                'visibility:hidden' in style.lower() or
                'opacity:0' in style.lower() or
                tag.get('aria-hidden') == 'true' or
                'hidden' in classes or
                'sr-only' in classes
            )

            # Determine heuristic DOM Zone & Prominence
            zone = self._determine_zone(tag, block_counter)
            prominence = self._calculate_prominence(tag, zone, is_hidden)
            selector_path = self._build_selector_path(tag)
            has_conds = self._detect_conditions(raw)

            blocks.append(DOMBlock(
                block_id=f"B{block_counter:03d}",
                tag_name=tag.name,
                dom_zone=zone,
                order_index=block_counter,
                raw_text=raw.strip(),
                normalized_text=norm,
                is_hidden=is_hidden,
                selector_path=selector_path,
                prominence_weight=prominence,
                has_conditions=has_conds
            ))
            block_counter += 1

        if not blocks:
            warnings.append("Extracted zero meaningful text blocks from document.")
        elif block_counter < 3:
            warnings.append("Document yielded very sparse content (less than 3 blocks).")

        return blocks, warnings

    def _check_retrieval_completeness(self, html_content: str, warnings: List[str]):
        """Detects if page snapshot was truncated or if single-page dynamic content is missing."""
        content_lower = html_content.lower()
        if '</html>' not in content_lower:
            warnings.append("HTML document appears truncated or unclosed (missing </html>).")
        if '</body>' not in content_lower:
            warnings.append("HTML document body is unclosed.")
        if ('id="root"' in content_lower or 'id="app"' in content_lower) and len(html_content) < 800:
            warnings.append("Possible unhydrated single-page client application root detected.")

    def _build_selector_path(self, tag) -> str:
        """Constructs an interpretable CSS selector path for traceability."""
        parts = []
        curr = tag
        depth = 0
        while curr and curr.name not in {'[document]', 'html', 'body'} and depth < 3:
            tag_str = curr.name
            classes = curr.get('class', [])
            if classes:
                first_class = classes[0]
                tag_str += f".{first_class}"
            elif curr.get('id'):
                tag_str += f"#{curr.get('id')}"
            parts.insert(0, tag_str)
            curr = curr.parent
            depth += 1
        return " > ".join(parts) if parts else tag.name

    def _calculate_prominence(self, tag, zone: DOMZone, is_hidden: bool) -> float:
        """Calculates evidence prominence weight (0.0 to 1.0) based on location and typography."""
        if is_hidden:
            return 0.0
        if zone == DOMZone.HERO_CANDIDATE:
            return 1.0
        elif zone == DOMZone.FOOTER_DISCLAIMER:
            return 0.2 if tag.name == 'small' else 0.3
        elif tag.name in {'h1', 'h2'}:
            return 0.9
        elif tag.name in {'h3', 'h4', 'h5', 'h6'}:
            return 0.8
        return 0.75

    def _detect_conditions(self, text: str) -> bool:
        """Flags whether text contains caveats, exclusions, or disclaimer cues."""
        text_lower = text.lower()
        return any(re.search(pat, text_lower) for pat in self.CONDITION_PATTERNS)

    def _determine_zone(self, tag, order_idx: int) -> DOMZone:
        # Check parents for footer or hero cues
        classes_and_id = ' '.join(filter(None, [
            ' '.join(tag.get('class', [])),
            tag.get('id', '')
        ])).lower()

        # Check if in footer or disclaimer container
        if tag.name in self.FOOTER_TAGS or any(ind in classes_and_id for ind in self.FOOTER_INDICATORS):
            return DOMZone.FOOTER_DISCLAIMER
        for parent in tag.parents:
            if parent and parent.name in self.FOOTER_TAGS:
                return DOMZone.FOOTER_DISCLAIMER
            p_class = ' '.join(parent.get('class', [])).lower() if parent and parent.name else ''
            p_id = (parent.get('id', '') or '').lower() if parent and parent.name else ''
            if any(ind in f"{p_class} {p_id}" for ind in self.FOOTER_INDICATORS):
                return DOMZone.FOOTER_DISCLAIMER

        # Check for Hero Candidates (early order, h1, or hero classes)
        if (tag.name in self.HERO_TAGS or order_idx <= 2 or any(ind in classes_and_id for ind in self.HERO_INDICATORS)) and order_idx <= 5:
            return DOMZone.HERO_CANDIDATE

        return DOMZone.MAIN_BODY

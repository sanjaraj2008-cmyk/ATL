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
    Extracts text and semantic hierarchy from HTML snapshots.
    Maintains raw text immutability and assigns heuristic DOM zones.
    """
    
    HERO_TAGS = {'h1', 'header'}
    BODY_TAGS = {'p', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'button', 'a', 'span', 'div', 'td', 'th'}
    FOOTER_TAGS = {'footer', 'small'}
    
    FOOTER_INDICATORS = {'footer', 'disclaimer', 'legal', 'terms', 'fineprint', 'copyright', 'privacy'}
    HERO_INDICATORS = {'hero', 'banner', 'headline', 'main-title', 'top'}

    def extract_blocks(self, html_content: str) -> Tuple[List[DOMBlock], List[str]]:
        warnings = []
        if not html_content or not html_content.strip():
            warnings.append("Input HTML is empty.")
            return [], warnings

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
                        is_hidden=False
                    ))
                    block_counter += 1

        # Identify all meaningful content nodes
        # Traverse top-level content tags
        candidates = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li', 'button', 'a', 'footer', 'small', 'div'])
        
        seen_texts = set()
        for idx, tag in enumerate(candidates):
            # Only process leaf-ish nodes or nodes without block children to avoid redundant outer wraps
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

            # Check hidden styles
            style = tag.get('style', '') or ''
            is_hidden = 'display:none' in style.lower() or 'visibility:hidden' in style.lower() or tag.get('aria-hidden') == 'true'

            # Determine heuristic DOM Zone
            zone = self._determine_zone(tag, block_counter)

            blocks.append(DOMBlock(
                block_id=f"B{block_counter:03d}",
                tag_name=tag.name,
                dom_zone=zone,
                order_index=block_counter,
                raw_text=raw.strip(),
                normalized_text=norm,
                is_hidden=is_hidden
            ))
            block_counter += 1

        if not blocks:
            warnings.append("Extracted zero meaningful text blocks from document.")
        elif block_counter < 3:
            warnings.append("Document yielded very sparse content (less than 3 blocks).")

        return blocks, warnings

    def _determine_zone(self, tag, order_idx: int) -> DOMZone:
        # Check parents for footer or hero cues
        classes_and_id = ' '.join(filter(None, [
            ' '.join(tag.get('class', [])),
            tag.get('id', '')
        ])).lower()

        # Check if in footer
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

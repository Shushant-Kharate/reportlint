"""Conservative chapter identity from outline structure and explicit banners.

No fuzzy matching: typos and semantic synonyms still need reviewed aliases.
"""
import re

BANNER = re.compile(r"^chapter\s+(?:\d+|[ivxlcdm]+)\b\s*[:.\-–—]?\s*(.*)$", re.I)


def title_key(text):
    value = " ".join(text.casefold().split()).rstrip(" :.;–—-")
    banner = BANNER.fullmatch(value)
    if banner and banner[1]:
        value = banner[1]
    # A deliberately narrow spelling variant, not generic stemming.
    if value in {"acknowledgment", "acknowledgments", "acknowledgements"}:
        value = "acknowledgement"
    return value


def chapter_titles(paragraphs):
    """Map trusted chapter paragraph indexes to titles, including split banners."""
    titles = {}
    headings = [p for p in paragraphs if p.role == "HEADING"]
    for p in headings:
        banner = BANNER.fullmatch(p.text.strip())
        if p.level == 1 or (banner and banner[1]):
            titles[p.index] = p.text
        elif banner:
            # Split CHAPTER 4 / Implementation Details: same-level next heading,
            # with only empty paragraphs between. Never concatenate body prose.
            following = next((q for q in paragraphs if q.index > p.index and q.text.strip()), None)
            if following and following.role == "HEADING" and following.level == p.level and not BANNER.match(following.text):
                titles[p.index] = following.text
    return titles

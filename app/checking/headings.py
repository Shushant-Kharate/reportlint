"""Conservative chapter identity from outline structure and explicit banners.

No free fuzzy matching: a one-character variant needs independent structural
corroboration; semantic synonyms still need reviewed aliases.
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


def single_character_variant(left, right):
    """One edit in one word, never a semantic synonym or free fuzzy match."""
    a, b = title_key(left).split(), title_key(right).split()
    if len(a) != len(b):
        return False
    different = [(x, y) for x, y in zip(a, b) if x != y]
    if len(different) != 1:
        return False
    x, y = different[0]
    if min(len(x), len(y)) < 4 or abs(len(x) - len(y)) > 1:
        return False
    if len(x) == len(y):
        positions = [i for i, (u, v) in enumerate(zip(x, y)) if u != v]
        return len(positions) == 1 or (len(positions) == 2 and positions[1] == positions[0] + 1
            and x[positions[0]] == y[positions[1]] and x[positions[1]] == y[positions[0]])
    short, long = (x, y) if len(x) < len(y) else (y, x)
    return any(long[:i] + long[i + 1:] == short for i in range(len(long)))


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

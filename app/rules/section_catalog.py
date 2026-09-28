import re
import unicodedata
from rapidfuzz import fuzz

_LEADING_NUM_RE = re.compile(
    r"^\s*(chapter\s+\d+\s*[:\-.]?|\d+(\.\d+)*\s*[:\-.]?)\s*", re.IGNORECASE)
_PUNCT_RE = re.compile(r"[^\w\s-]", re.UNICODE)
_WS_RE = re.compile(r"\s+")

DEFAULT_ALIASES: dict[str, list[str]] = {
    "introduction": ["intro"],
    "literature survey": [
        "literature survey and analysis", "literature review",
        "review of literature", "related work",
    ],
    "system design": ["design", "proposed system", "methodology"],
    "conclusion and future scope": [
        "conclusion", "conclusion future scope", "conclusion and future work",
    ],
    "references": ["bibliography", "reference"],
    "appendix": ["appendices"],
    "acknowledgement": ["acknowledgements", "acknowledgment", "acknowledgments"],
    "abstract": [],
    "certificate": [],
    "declaration": [],
}

FUZZY_THRESHOLD = 85


def normalize_heading(text: str) -> str:
    t = unicodedata.normalize("NFKC", text)
    t = t.lower()
    t = _LEADING_NUM_RE.sub("", t)
    t = _PUNCT_RE.sub("", t)
    t = _WS_RE.sub(" ", t).strip()
    return t


class SectionMatch:
    def __init__(self, canonical_name, heading_text, match_type, score=100):
        self.canonical_name = canonical_name
        self.heading_text = heading_text
        self.match_type = match_type  # "EXACT" | "ALIAS" | "FUZZY"
        self.score = score


def match_section(canonical_name: str, aliases: list[str],
                   candidate_sections: dict[str, "DocumentSection"]) -> SectionMatch | None:
    """candidate_sections: normalized_heading_text -> DocumentSection"""
    norm_canonical = normalize_heading(canonical_name)

    if norm_canonical in candidate_sections:
        sec = candidate_sections[norm_canonical]
        return SectionMatch(canonical_name, sec.heading_text, "EXACT", 100)

    for alias in aliases:
        norm_alias = normalize_heading(alias)
        if norm_alias in candidate_sections:
            sec = candidate_sections[norm_alias]
            return SectionMatch(canonical_name, sec.heading_text, "ALIAS", 100)

    best_score = 0
    best_sec = None
    for norm_text, sec in candidate_sections.items():
        score = fuzz.token_sort_ratio(norm_canonical, norm_text)
        if score > best_score:
            best_score = score
            best_sec = sec
    if best_sec is not None and best_score >= FUZZY_THRESHOLD:
        return SectionMatch(canonical_name, best_sec.heading_text, "FUZZY", best_score)

    return None

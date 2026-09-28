from abc import ABC, abstractmethod
from collections import defaultdict, Counter
from app.models.document_model import DocumentModel
from app.models.rule_model import Rule, RuleScope
from app.models.result_model import Violation


class ReportIndex:
    def __init__(self, doc: DocumentModel):
        self.doc = doc
        self.paragraphs_by_style: dict[str, list[int]] = defaultdict(list)
        self.headings_by_level: dict[int, list[int]] = defaultdict(list)
        self.font_histogram: Counter = Counter()
        for p in doc.paragraphs:
            if p.style_name:
                self.paragraphs_by_style[p.style_name].append(p.index)
            if p.is_heading and p.heading_level:
                self.headings_by_level[p.heading_level].append(p.index)
            for r in p.runs:
                if r.font_name:
                    self.font_histogram[r.font_name] += len(r.text)


def paragraphs_in_scope(doc: DocumentModel, scope: RuleScope, section_ref: str | None = None):
    if scope == RuleScope.DOCUMENT:
        return doc.paragraphs
    if scope == RuleScope.BODY:
        return [p for p in doc.paragraphs if not p.is_heading and len(p.text.strip()) > 40]
    if scope in (RuleScope.HEADING_1, RuleScope.HEADING_2, RuleScope.HEADING_3):
        level = int(scope.value[-1])
        return [p for p in doc.paragraphs if p.is_heading and p.heading_level == level]
    if scope == RuleScope.SPECIFIC_SECTION:
        from app.ooxml.structure_extractor import extract_sections
        from app.rules.section_catalog import normalize_heading
        tree = extract_sections(doc)

        def flatten(secs):
            out = []
            for s in secs:
                out.append(s)
                out.extend(flatten(s.subsections))
            return out

        for s in flatten(tree):
            if s.heading_text_normalized == normalize_heading(section_ref or ""):
                idx_set = set(s.paragraph_indices)
                return [p for p in doc.paragraphs if p.index in idx_set]
        return []
    return doc.paragraphs


def within_tolerance(actual: float, expected: float, tol_pt: float = 0.25) -> bool:
    return abs(actual - expected) <= tol_pt


class Validator(ABC):
    @abstractmethod
    def validate(self, doc: DocumentModel, rule: Rule) -> tuple[list[Violation], int]:
        """Returns (violations, checks_performed) — checks_performed is the
        denominator used by scoring (Section 7), NOT just violation count."""
        ...

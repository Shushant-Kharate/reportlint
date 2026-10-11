"""Narrow, evidence-backed proposals for stored document structure."""
import re

from app.models.template_analysis import (
    ChapterBoldValue, SectionSizeValue, PageNumberAlignmentValue,
    BodyNumberFormatValue, FrontNumberFormatValue, IntroductionNumberingValue,
    ContentsStructureValue, ContentsAlignmentValue, IllustrationListsValue, CaptionsValue,
)


def proposals(text):
    values = []
    original = text
    optional = re.search(r"\b(?:may|optional|either)\b", text, re.I)
    if not optional and re.search(r"chapter number.*?\btitle\b.{0,200}?\b(?:shall|must)\s+be\s+printed\b(?:(?!shall not|must not).){0,200}?\bbold face\b", original, re.I):
        values.append(ChapterBoldValue())
    text = " ".join(sentence for sentence in re.split(r"(?<=[.!?])\s+", text)
                    if not re.search(r"\b(?:shall|must|should|will)\s+not\b", sentence, re.I))
    if not optional:
        if not any(isinstance(v, ChapterBoldValue) for v in values) and re.search(r"chapter number.*\btitle\b.*\bbold face\b", text, re.I):
            values.append(ChapterBoldValue())
        sizes = re.search(r"section and sub\s*section titles.*\((\d+(?:\.\d+)?)\s+and\s+(\d+(?:\.\d+)?)\s*pt\).*respectively", text, re.I)
        if sizes and all(float(sizes[i]) > 0 for i in (1, 2)):
            values.extend(SectionSizeValue(depth=d, expected_pt=float(sizes[i])) for d, i in ((2, 1), (3, 2)))
        if re.search(r"page numbering.*(?:shall|must).*hindu[\s-]*arabic", text, re.I):
            values.append(BodyNumberFormatValue())
        if re.search(r"page numbering.*(?:shall|must).*center of (?:the )?footer", text, re.I):
            values.append(PageNumberAlignmentValue())
        if re.search(r"(?:pagination.*before (?:the )?introduction.*(?:shall|must).*lower case roman|auxiliary page.*(?:shall|must).*roman numerals in lower case)", text, re.I):
            values.append(FrontNumberFormatValue())
        if re.search(r"contents.*(?:shall|must).*chapters.*section.*subsection.*decimal notation", text, re.I):
            values.append(ContentsStructureValue())
        if re.search(r"(?:contents|chapters, sections and subsections).*(?:shall|must).*page numbers?.*flushed to the right", text, re.I):
            values.append(ContentsAlignmentValue())
        if re.search(r"two separate lists of figure captions and table titles.*(?:shall|must).*follow (?:the )?contents", text, re.I):
            values.append(IllustrationListsValue())
        if re.search(r"table number and title.*(?:will|shall|must).*above the table.*figure number and caption.*below the figure", text, re.I):
            values.extend((CaptionsValue(kind="table_titles"), CaptionsValue(kind="figure_captions")))
    # This requirement is deliberately negative: the first printed number is suppressed.
    if not optional and re.search(r"page number\W*1\W+for the first page of the introduction chapter (?:shall|must) not appear.*second page.*number\W*2", original, re.I):
        values.append(IntroductionNumberingValue())
    return values

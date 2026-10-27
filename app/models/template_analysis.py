"""Proposed extraction contracts. These are not executable/approved rules."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, model_validator


class AnalysisModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True, str_strip_whitespace=True)


class SourceEvidence(AnalysisModel):
    source_id: str
    part: Literal["word/document.xml", "word/styles.xml", "external-guideline"] = "word/document.xml"
    path: str
    excerpt: str


class FontValue(AnalysisModel):
    kind: Literal["font_family"] = "font_family"
    font: str = Field(min_length=1, max_length=100)


class SizeValue(AnalysisModel):
    kind: Literal["font_size"] = "font_size"
    expected_pt: PositiveFloat


class SpacingValue(AnalysisModel):
    kind: Literal["line_spacing_multiple"] = "line_spacing_multiple"
    multiplier: PositiveFloat


class PageValue(AnalysisModel):
    kind: Literal["page_size"] = "page_size"
    width_pt: PositiveFloat
    height_pt: PositiveFloat


class BodyColumnsValue(AnalysisModel):
    kind: Literal["body_columns"] = "body_columns"
    count: int = Field(ge=1, le=6)


class MarginValue(AnalysisModel):
    kind: Literal["margin"] = "margin"
    side: Literal["top", "bottom", "left", "right"]
    expected_pt: float = Field(ge=0)


class PaperFormatValue(AnalysisModel):
    """Individually reviewable paper requirements; no institution-ID shortcuts."""
    kind: Literal["paper_abstract_size", "paper_heading_size", "paper_title_size", "paper_reference_size",
                  "paper_heading_numbering", "paper_abstract_run_in", "paper_no_page_numbers",
                  "paper_body_alignment", "paper_caption_numbering", "paper_keywords"]
    expected_pt: PositiveFloat | None = None

    @model_validator(mode="after")
    def size_contract(self):
        if self.kind.endswith("_size") != (self.expected_pt is not None):
            raise ValueError("Only paper size rules require expected_pt")
        return self


class MarginRangeValue(AnalysisModel):
    kind: Literal["margin_range"] = "margin_range"
    side: Literal["left", "right"]
    minimum_pt: PositiveFloat
    maximum_pt: PositiveFloat

    @model_validator(mode="after")
    def ordered(self):
        if self.minimum_pt > self.maximum_pt:
            raise ValueError("Margin range must be ordered")
        return self


class ChapterSizeValue(AnalysisModel):
    kind: Literal["chapter_font_size"] = "chapter_font_size"
    expected_pt: PositiveFloat


class ChapterCaseValue(AnalysisModel):
    kind: Literal["chapter_case"] = "chapter_case"
    expected: Literal["mixed"] = "mixed"


class AbstractWordsValue(AnalysisModel):
    kind: Literal["abstract_word_count"] = "abstract_word_count"
    expected_words: int = Field(gt=0, le=100000)


class AbstractKeywordsValue(AnalysisModel):
    kind: Literal["abstract_keywords"] = "abstract_keywords"
    required: Literal[True] = True


class ChapterBoldValue(AnalysisModel):
    kind: Literal["chapter_bold"] = "chapter_bold"
    required: Literal[True] = True


class SectionSizeValue(AnalysisModel):
    kind: Literal["section_font_size"] = "section_font_size"
    depth: Literal[2, 3]
    expected_pt: PositiveFloat


class PageNumberAlignmentValue(AnalysisModel):
    kind: Literal["page_number_alignment"] = "page_number_alignment"
    alignment: Literal["center"] = "center"


class BodyNumberFormatValue(AnalysisModel):
    kind: Literal["body_page_number_format"] = "body_page_number_format"
    format: Literal["decimal"] = "decimal"


class FrontNumberFormatValue(AnalysisModel):
    kind: Literal["front_page_number_format"] = "front_page_number_format"
    format: Literal["lowerRoman"] = "lowerRoman"


class IntroductionNumberingValue(AnalysisModel):
    kind: Literal["introduction_numbering"] = "introduction_numbering"
    start: Literal[1] = 1
    suppress_first: Literal[True] = True


class ContentsStructureValue(AnalysisModel):
    kind: Literal["contents_structure"] = "contents_structure"
    decimal_sections: Literal[True] = True
    individual_page_references: Literal[True] = True


class ContentsAlignmentValue(AnalysisModel):
    kind: Literal["contents_page_alignment"] = "contents_page_alignment"
    alignment: Literal["right"] = "right"


class IllustrationListsValue(AnalysisModel):
    kind: Literal["illustration_lists"] = "illustration_lists"
    separate: Literal[True] = True


class CaptionsValue(AnalysisModel):
    kind: Literal["figure_captions", "table_titles"]
    chapter_numbering: Literal[True] = True


RequirementValue = Annotated[
    FontValue | SizeValue | SpacingValue | PageValue | BodyColumnsValue | MarginValue | ChapterSizeValue | ChapterCaseValue | AbstractWordsValue | AbstractKeywordsValue
    | ChapterBoldValue | SectionSizeValue | PageNumberAlignmentValue | BodyNumberFormatValue
    | FrontNumberFormatValue | IntroductionNumberingValue | ContentsStructureValue
    | ContentsAlignmentValue | IllustrationListsValue | CaptionsValue | PaperFormatValue | MarginRangeValue,
    Field(discriminator="kind"),
]


class RuleCandidate(AnalysisModel):
    candidate_id: str
    scope: Literal["body", "document"]
    value: RequirementValue
    condition: Literal["ALWAYS", "HEADER_ABSENT"] = "ALWAYS"
    origin: Literal["EXPLICIT_PROSE", "OBSERVED_APPEARANCE"]
    evidence_ids: list[str] = Field(min_length=1)
    review_status: Literal["PROPOSED"] = "PROPOSED"
    note: str = ""


class Conflict(AnalysisModel):
    conflict_id: str
    kind: Literal["PROSE_APPEARANCE", "COMPETING_REQUIREMENTS", "CONDITIONAL_OVERRIDE"]
    candidate_ids: list[str] = Field(min_length=2)
    suggested_candidate_id: str | None = None
    explanation: str
    status: Literal["UNRESOLVED"] = "UNRESOLVED"


class ChapterCandidate(AnalysisModel):
    title: str
    number: str | None = None
    suggested_topics: list[str] = Field(default_factory=list)
    evidence_ids: list[str]
    # Deliberately undecided: index rows do not establish mandatory subtopics.
    required: None = None


class ProfileCandidate(AnalysisModel):
    profile_id: str
    label: Literal["report", "synopsis"]
    chapters: list[ChapterCandidate]
    review_status: Literal["PROPOSED"] = "PROPOSED"


class RequirementDisposition(AnalysisModel):
    evidence_id: str
    status: Literal["CANDIDATES_NEED_REVIEW", "UNCLASSIFIED", "MANUAL_REVIEW"]
    candidate_ids: list[str] = Field(default_factory=list)


class TemplateAnalysis(AnalysisModel):
    schema_version: Literal[2] = 2
    extractor_version: Literal["0.1.0", "0.2.0", "0.3.0"] = "0.1.0"
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    candidates: list[RuleCandidate] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    profiles: list[ProfileCandidate] = Field(default_factory=list)
    evidence: list[SourceEvidence] = Field(default_factory=list)
    requirement_ledger: list[RequirementDisposition] = Field(default_factory=list)
    notices: list[str] = Field(default_factory=list)
    publication_ready: Literal[False] = False

    @model_validator(mode="after")
    def validate_references(self):
        for items, key in ((self.candidates, "candidate_id"), (self.conflicts, "conflict_id"),
                           (self.evidence, "source_id"), (self.profiles, "profile_id")):
            ids = [getattr(item, key) for item in items]
            if len(ids) != len(set(ids)):
                raise ValueError(f"Duplicate {key}")
        evidence = {e.source_id for e in self.evidence}
        candidates = {c.candidate_id for c in self.candidates}
        for candidate in self.candidates:
            if not set(candidate.evidence_ids) <= evidence:
                raise ValueError("Candidate references missing evidence")
        for conflict in self.conflicts:
            if len(set(conflict.candidate_ids)) < 2 or not set(conflict.candidate_ids) <= candidates:
                raise ValueError("Conflict references invalid candidates")
            if conflict.suggested_candidate_id and conflict.suggested_candidate_id not in conflict.candidate_ids:
                raise ValueError("Suggested resolution is not a conflict candidate")
        for item in self.requirement_ledger:
            if item.evidence_id not in evidence or not set(item.candidate_ids) <= candidates:
                raise ValueError("Ledger references missing evidence or candidates")
        for profile in self.profiles:
            for chapter in profile.chapters:
                if not chapter.evidence_ids or not set(chapter.evidence_ids) <= evidence:
                    raise ValueError("Chapter references missing evidence")
        return self

from enum import Enum
from pydantic import BaseModel


class Alignment(str, Enum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    JUSTIFY = "justify"
    UNKNOWN = "unknown"


class Confidence(str, Enum):
    EXPLICIT = "EXPLICIT"
    INHERITED = "INHERITED"
    DEFAULT = "DEFAULT"
    UNKNOWN = "UNKNOWN"


class RunModel(BaseModel):
    text: str
    font_name: str | None = None
    font_size_pt: float | None = None
    bold: bool | None = None
    italic: bool | None = None
    underline: bool | None = None
    confidence: Confidence = Confidence.UNKNOWN


class ParagraphModel(BaseModel):
    index: int
    text: str
    style_name: str | None = None
    style_id: str | None = None
    outline_level: int | None = None
    alignment: Alignment = Alignment.UNKNOWN
    line_spacing: float | None = None          # multiplier, e.g. 1.5
    line_spacing_rule: str | None = None        # "auto" | "atLeast" | "exact"
    line_spacing_exact_pt: float | None = None  # populated only when rule != "auto"
    spacing_before_pt: float | None = None
    spacing_after_pt: float | None = None
    left_indent_pt: float | None = None
    right_indent_pt: float | None = None
    first_line_indent_pt: float | None = None
    runs: list[RunModel] = []
    is_heading: bool = False
    heading_level: int | None = None
    heading_source: str | None = None  # "STYLE" | "OUTLINE" | "HEURISTIC"


class TableModel(BaseModel):
    index: int
    preceding_paragraph_index: int | None = None
    row_count: int = 0
    col_count: int = 0
    caption_text: str | None = None


class ImageModel(BaseModel):
    index: int
    preceding_paragraph_index: int | None = None
    width_in: float | None = None
    height_in: float | None = None
    caption_text: str | None = None


class SectionPropertiesModel(BaseModel):
    page_width_pt: float | None = None
    page_height_pt: float | None = None
    orientation: str | None = None
    margin_top_pt: float | None = None
    margin_bottom_pt: float | None = None
    margin_left_pt: float | None = None
    margin_right_pt: float | None = None
    margin_header_pt: float | None = None
    margin_footer_pt: float | None = None
    applies_from_paragraph_index: int = 0


class DocumentModel(BaseModel):
    source_filename: str
    paragraphs: list[ParagraphModel] = []
    tables: list[TableModel] = []
    images: list[ImageModel] = []
    sections: list[SectionPropertiesModel] = []
    doc_default_font_name: str | None = None
    doc_default_font_size_pt: float | None = None

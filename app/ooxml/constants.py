"""OOXML namespace map and unit conversion helpers."""

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}

W = f"{{{NS['w']}}}"


def qn(tag: str) -> str:
    """Qualify a bare 'w:xxx' style tag/attr name with the w: namespace URI."""
    prefix, local = tag.split(":")
    return f"{{{NS[prefix]}}}{local}"


def twips_to_pt(v) -> float:
    return int(v) / 20


def halfpt_to_pt(v) -> float:
    return int(v) / 2


def emu_to_inch(v) -> float:
    return int(v) / 914400

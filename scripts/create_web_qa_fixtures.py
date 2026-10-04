"""Create fictional browser-test inputs in an explicitly selected directory."""
import argparse
from pathlib import Path

from docx.shared import Mm, Pt
from tests.test_report_role_review import manual_report
from tests.test_template_analysis import complex_format, encoded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    folder = parser.parse_args().directory
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "format.docx").write_bytes(encoded(complex_format()))
    report = manual_report()
    report.paragraphs[2].runs[0].font.size = Pt(10)
    (folder / "report.docx").write_bytes(encoded(report))
    partial = manual_report()
    section = partial.sections[0]
    section.page_width, section.page_height = Mm(210), Mm(297)
    for side, mm in {"top": 15, "bottom": 22, "left": 30, "right": 20}.items():
        setattr(section, side + "_margin", Mm(mm))
    (folder / "partial-report.docx").write_bytes(encoded(partial))
    print(f"Browser fixtures written to {folder.resolve()}")


if __name__ == "__main__":
    main()

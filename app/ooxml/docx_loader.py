"""Low-level access to a .docx's constituent XML parts. Pure access only —
no interpretation happens here (see style_resolver.py / structure_extractor.py)."""

import zipfile
import posixpath
import re
from decimal import Decimal
from lxml import etree

MAX_MEMBER_SIZE = 200 * 1024 * 1024  # 200MB guard against zip bombs
MAX_MEMBER_COUNT = 5000
MAX_TOTAL_SIZE = 200 * 1024 * 1024


def _xml(data):
    root = etree.fromstring(data, parser=etree.XMLParser(resolve_entities=False, no_network=True))
    if root.getroottree().docinfo.doctype:
        raise InvalidDocxError("Document type declarations are not allowed")
    # ISO Strict OOXML uses different namespace URIs for the same supported
    # Word properties. Normalize element/attribute names in memory only; keep
    # source bytes, text, semantic measurements and their source hash unchanged.
    namespaces = {
        "http://purl.oclc.org/ooxml/wordprocessingml/main": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
        "http://purl.oclc.org/ooxml/officeDocument/relationships": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        "http://purl.oclc.org/ooxml/drawingml/main": "http://schemas.openxmlformats.org/drawingml/2006/main",
        "http://purl.oclc.org/ooxml/drawingml/wordprocessingDrawing": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    }
    def name(value):
        if not isinstance(value, str) or not value.startswith("{"):
            return value
        uri, local = value[1:].split("}", 1)
        return "{" + namespaces.get(uri, uri) + "}" + local
    if any(uri in namespaces for uri in root.nsmap.values()):
        for element in root.iter():
            if not isinstance(element.tag, str):
                continue
            element.tag = name(element.tag)
            attributes = {name(k): v for k, v in element.attrib.items()}
            local = etree.QName(element).localname if isinstance(element.tag, str) else ""
            measured = {"pgSz", "pgMar", "cols", "col", "ind", "spacing", "tab", "tblW", "tcW", "tblInd", "sz", "szCs", "position", "kern"}
            if local in measured:
                for key, value in attributes.items():
                    match = re.fullmatch(r"(-?[0-9]{1,9}(?:\.[0-9]{1,6})?)(pt|in|cm|mm|pc|pi)", value)
                    if key.startswith("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}") and match:
                        points = Decimal(match[1]) * {"pt": Decimal(1), "in": Decimal(72), "cm": Decimal(7200)/254, "mm": Decimal(720)/254, "pc": Decimal(12), "pi": Decimal(12)}[match[2]]
                        factor = 2 if local in {"sz", "szCs", "position", "kern"} else 20
                        attributes[key] = str(round(points * factor))
            element.attrib.clear()
            element.attrib.update(attributes)
        replacement = etree.Element(root.tag, nsmap={k: namespaces.get(v, v) for k, v in root.nsmap.items()})
        replacement.attrib.update(root.attrib)
        replacement.text, replacement.tail = root.text, root.tail
        replacement.extend(root)
        root = replacement
        etree.cleanup_namespaces(root)
    return root


class InvalidDocxError(Exception):
    pass


class DocxPackage:
    def __init__(self):
        self.document_tree: etree._ElementTree | None = None
        self.styles_tree: etree._ElementTree | None = None
        self.numbering_tree: etree._ElementTree | None = None
        self.settings_tree: etree._ElementTree | None = None
        self.media: dict[str, bytes] = {}
        self.rels: dict[str, str] = {}
        self.rel_types: dict[str, str] = {}
        self.external_rels: set[str] = set()
        self.story_parts: dict[str, object] = {}

    @classmethod
    def load(cls, path: str) -> "DocxPackage":
        if not zipfile.is_zipfile(path):
            raise InvalidDocxError(f"{path} is not a valid ZIP/.docx file")

        pkg = cls()
        try:
            with zipfile.ZipFile(path) as zf:
                infos = zf.infolist()
                if sum(info.file_size for info in infos) > MAX_TOTAL_SIZE:
                    raise InvalidDocxError("Uncompressed document is too large")
                if len({info.filename for info in infos}) != len(infos):
                    raise InvalidDocxError("Duplicate archive entries")
                if len(infos) > MAX_MEMBER_COUNT:
                    raise InvalidDocxError("Too many entries in archive (possible zip bomb)")
                for info in infos:
                    if info.file_size > MAX_MEMBER_SIZE:
                        raise InvalidDocxError(f"Entry {info.filename} exceeds size guard")

                names = set(zf.namelist())
                if "word/document.xml" not in names:
                    raise InvalidDocxError("word/document.xml missing — not a valid .docx")

                pkg.document_tree = _xml(zf.read("word/document.xml")).getroottree()
                from app.ooxml.constants import qn
                if pkg.document_tree.getroot().find(qn("w:body")) is None:
                    raise InvalidDocxError("Document body is missing")

                if "word/styles.xml" in names:
                    pkg.styles_tree = _xml(zf.read("word/styles.xml")).getroottree()
                if "word/numbering.xml" in names:
                    pkg.numbering_tree = _xml(zf.read("word/numbering.xml")).getroottree()
                if "word/settings.xml" in names:
                    pkg.settings_tree = _xml(zf.read("word/settings.xml")).getroottree()

                for name in names:
                    if name.startswith("word/media/"):
                        pkg.media[name] = zf.read(name)

                rels_path = "word/_rels/document.xml.rels"
                if rels_path in names:
                    rels_root = _xml(zf.read(rels_path))
                    rel_ns = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
                    for rel in rels_root.findall("r:Relationship", rel_ns):
                        pkg.rels[rel.get("Id")] = rel.get("Target")
                        pkg.rel_types[rel.get("Id")] = rel.get("Type", "")
                        if rel.get("TargetMode", "Internal") != "Internal":
                            pkg.external_rels.add(rel.get("Id"))
                    for rel_id, target in pkg.rels.items():
                        if rel_id in pkg.external_rels or not pkg.rel_types[rel_id].endswith(("/header", "/footer")):
                            continue
                        if not target:
                            continue
                        part = posixpath.normpath(target.lstrip("/") if target.startswith("/") else "word/" + target)
                        if part.startswith("word/") and part in names:
                            pkg.story_parts[part] = _xml(zf.read(part)).getroottree()
        except zipfile.BadZipFile as e:
            raise InvalidDocxError(f"Corrupted zip: {e}") from e
        except etree.XMLSyntaxError as e:
            raise InvalidDocxError(f"Malformed XML inside docx: {e}") from e
        except (RuntimeError, NotImplementedError) as e:
            raise InvalidDocxError("Encrypted or unsupported archive") from e

        return pkg

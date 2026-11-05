"""File-type detection and text extraction for PDF and DOCX resumes (with hidden-text stripping)."""
from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field

from app.schemas.common import Flag

MAX_PAGES = 10
MAX_CHARS = 60_000
MIN_CHARS = 50
PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class ParseFailure(Exception):
    """A user-presentable reason a resume could not be read."""

    def __init__(self, message: str, code: str = "parse_failed"):
        super().__init__(message)
        self.message = message
        self.code = code


@dataclass
class Extracted:
    text: str
    page_count: int | None = None
    kind: str = "pdf"
    warnings: list[str] = field(default_factory=list)
    flags: list[Flag] = field(default_factory=list)
    hidden_chars: int = 0


def detect_kind(data: bytes) -> str | None:
    """'pdf' | 'docx' | None, decided by magic bytes (never by file name or client MIME)."""
    if data[:5] == b"%PDF-":
        return "pdf"
    if data[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                names = set(z.namelist())
                if "word/document.xml" in names and "[Content_Types].xml" in names:
                    return "docx"
        except zipfile.BadZipFile:
            return None
    return None


def content_type_for(kind: str) -> str:
    return PDF_MIME if kind == "pdf" else DOCX_MIME


def validate_upload(data: bytes, max_bytes: int) -> str:
    """Return the detected kind or raise ParseFailure with a friendly message."""
    if not data:
        raise ParseFailure("The uploaded file is empty.", "empty_file")
    if len(data) > max_bytes:
        raise ParseFailure(f"The file is too large (limit {max_bytes // (1024 * 1024)} MB).", "file_too_large")
    kind = detect_kind(data)
    if kind is None:
        raise ParseFailure("Unsupported or corrupt file. Please upload a PDF or DOCX resume.", "unsupported_type")
    return kind


def extract_text(data: bytes, kind: str | None = None) -> Extracted:
    kind = kind or detect_kind(data)
    if kind == "pdf":
        ex = _extract_pdf(data)
    elif kind == "docx":
        ex = _extract_docx(data)
    else:
        raise ParseFailure("Unsupported or corrupt file. Please upload a PDF or DOCX resume.", "unsupported_type")
    ex.text = _clean(ex.text)
    if len(ex.text) > MAX_CHARS:
        ex.text = ex.text[:MAX_CHARS]
        ex.warnings.append(f"Resume text was truncated to {MAX_CHARS:,} characters.")
    if len(ex.text.strip()) < MIN_CHARS:
        raise ParseFailure(
            "We could not read any text from this file. It may be a scanned image or empty - "
            "please upload a text-based PDF or DOCX.",
            "no_text",
        )
    if ex.hidden_chars:
        ex.flags.append(
            Flag(
                type="hidden_text",
                severity="critical",
                message=f"{ex.hidden_chars} characters of hidden text (white or tiny font) were removed and ignored.",
            )
        )
    return ex


def _clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "").replace("­", "")
    text = re.sub(r"[ \t\f\v]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# --------------------------------------------------------------------------- PDF
def _is_light(color: int) -> bool:
    r, g, b = (color >> 16) & 255, (color >> 8) & 255, color & 255
    return r >= 245 and g >= 245 and b >= 245


def _is_dark_fill(rgb) -> bool:  # noqa: ANN001
    if not rgb:
        return False
    try:
        return sum(rgb) / 3 < 0.7
    except TypeError:
        return False


def _extract_pdf(data: bytes) -> Extracted:
    import pymupdf

    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:  # FileDataError and friends
        raise ParseFailure("This PDF is corrupt or unreadable.", "corrupt") from exc
    try:
        if doc.needs_pass:
            raise ParseFailure("This PDF is password-protected. Remove the password and upload it again.", "encrypted")
        ex = Extracted("", kind="pdf", page_count=doc.page_count)
        if doc.page_count == 0:
            raise ParseFailure("This PDF has no pages.", "empty_file")
        pages = min(doc.page_count, MAX_PAGES)
        if doc.page_count > MAX_PAGES:
            ex.warnings.append(f"Only the first {MAX_PAGES} of {doc.page_count} pages were read.")
        parts: list[str] = []
        for pno in range(pages):
            page = doc[pno]
            try:
                parts.append(_page_text(page, ex))
            except ParseFailure:
                raise
            except Exception:  # a single bad page should not sink the whole resume
                ex.warnings.append(f"Page {pno + 1} could not be read.")
        ex.text = "\n\n".join(parts)
        return ex
    except ParseFailure:
        raise
    except Exception as exc:
        raise ParseFailure("This PDF could not be read. Try re-saving it and uploading again.", "corrupt") from exc
    finally:
        doc.close()


def _page_text(page, ex: Extracted) -> str:  # noqa: ANN001
    import pymupdf

    d = page.get_text("dict", sort=True)
    dark: list = []
    try:
        for dr in page.get_drawings():
            if dr.get("fill") and _is_dark_fill(dr["fill"]):
                dark.append(pymupdf.Rect(dr["rect"]))
    except Exception:
        dark = []
    blocks: list[str] = []
    for b in d.get("blocks", []):
        if b.get("type") != 0:
            continue
        lines: list[str] = []
        for ln in b.get("lines", []):
            seg: list[str] = []
            for sp in ln.get("spans", []):
                t = sp.get("text", "")
                if not t.strip():
                    seg.append(t)
                    continue
                hidden = sp.get("size", 10) < 3.0
                if not hidden and _is_light(int(sp.get("color", 0))):
                    r = pymupdf.Rect(sp["bbox"])
                    hidden = not any(r.intersects(dk) for dk in dark)
                if hidden:
                    ex.hidden_chars += len(t.strip())
                else:
                    seg.append(t)
            line = "".join(seg).rstrip()
            if line.strip():
                lines.append(line)
        if lines:
            blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


# --------------------------------------------------------------------------- DOCX
def _extract_docx(data: bytes) -> Extracted:
    try:
        import docx
        from docx.shared import Pt

        document = docx.Document(io.BytesIO(data))
    except Exception as exc:
        raise ParseFailure("This DOCX file is corrupt or unreadable.", "corrupt") from exc
    ex = Extracted("", kind="docx", page_count=None)
    lines: list[str] = []

    def para_text(p) -> str:  # noqa: ANN001
        out: list[str] = []
        for run in p.runs:
            t = run.text
            if not t.strip():
                out.append(t)
                continue
            hidden = bool(run.font.hidden)
            try:
                if run.font.size is not None and run.font.size < Pt(3):
                    hidden = True
                rgb = run.font.color.rgb if run.font.color is not None and run.font.color.type is not None else None
                if rgb is not None and str(rgb).upper() == "FFFFFF":
                    hidden = True
            except Exception:
                pass
            if hidden:
                ex.hidden_chars += len(t.strip())
            else:
                out.append(t)
        return "".join(out)

    try:
        for p in document.paragraphs:
            lines.append(para_text(p))
        for table in document.tables:
            for row in table.rows:
                seen = set()
                cells = []
                for cell in row.cells:
                    if id(cell._tc) in seen:
                        continue
                    seen.add(id(cell._tc))
                    cells.append(" ".join(para_text(p) for p in cell.paragraphs).strip())
                lines.append(" | ".join(c for c in cells if c))
    except Exception as exc:
        raise ParseFailure("This DOCX file could not be read.", "corrupt") from exc
    ex.text = "\n".join(lines)
    return ex

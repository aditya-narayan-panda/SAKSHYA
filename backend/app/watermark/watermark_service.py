"""
WatermarkService — per-decryption forensic marker that is INVISIBLE by default.

Formats (only these are accepted at Protect time — MUST-5):
  * PDF  : REAL dual-channel. (1) ``/SakshyaWatermarkID`` in the document metadata, and
           (2) a PDF text-rendering-mode-3 (``3 Tr``, invisible) 1 pt text run at (2, 2)
           on EVERY page's content stream. Either channel alone is enough to attribute a
           leak, so stripping metadata does not defeat it.
  * DOCX : metadata-only marker (core.xml description). Reported as such — NOT a
           forensic-grade, tamper-resistant watermark.
  * anything else: ``UnsupportedWatermarkType`` (never stored with a NULL watermark).

Visible layer (OPT-IN, ``apply_visible=True``): tiled micro-pattern + diagonal stamp that
survives screenshots/photos. It is OFF by default so two recipients' copies are
pixel-identical yet byte-different and forensically distinct (MUST-4). The micro-text
carries the ``SAKSHYA::WM-…`` prefix too, so if the invisible channels are stripped but
the visible layer survives, extraction still works.

Honest note on "invisible": render mode 3 draws nothing, so the page is pixel-identical,
but PDF text extractors/copy-paste (pypdf, PDFium) still *return* invisible text runs.
That is intrinsic to Tr 3 and is why the marker is opaque (no recipient name, just a
random 64-bit ID that resolves only via the server-side ledger/DB).
"""
from __future__ import annotations

import io
import os
import re
import uuid
from dataclasses import dataclass
from typing import Optional

from pypdf import PdfReader, PdfWriter


WATERMARK_METADATA_KEY = "/SakshyaWatermarkID"
WATERMARK_PREFIX = "WM-"
MARKER_PREFIX = "SAKSHYA::"
# 16 hex chars = 64 bits. Generator, all extractors and tests share this ONE pattern.
WM_ID_HEX_LEN = 16
WM_ID_REGEX = rf"WM-[A-F0-9]{{{WM_ID_HEX_LEN}}}"
_WM_ID_RE = re.compile(rf"^{WM_ID_REGEX}$")
_MARKER_RE = re.compile(rf"{re.escape(MARKER_PREFIX)}({WM_ID_REGEX})")
_MARKER_RE_BYTES = re.compile(rf"{re.escape(MARKER_PREFIX)}({WM_ID_REGEX})".encode())
_OCTAL_ESC = re.compile(rb"\\([0-7]{3})")


def _unescape_pdf_octal(data: bytes) -> bytes:
    """PDF string literals encode ':' and '-' as \\072 / \\055 (reportlab does); undo that so the
    marker regex can match the raw content stream."""
    return _OCTAL_ESC.sub(lambda m: bytes([int(m.group(1), 8) & 0xFF]), data)

SUPPORTED_EXTENSIONS = (".pdf", ".docx")


class WatermarkError(Exception):
    """Embedding failed or could not be verified."""


class UnsupportedWatermarkType(WatermarkError):
    """File type cannot carry a forensic watermark."""


@dataclass
class WatermarkResult:
    watermark_id: str
    supported: bool
    channel: str  # "pdf-dual" | "docx-metadata"


def generate_watermark_id() -> str:
    """WM-<16 hex> = 64 bits of uuid4 randomness (was 32-bit)."""
    return f"{WATERMARK_PREFIX}{uuid.uuid4().hex[:WM_ID_HEX_LEN].upper()}"


def is_valid_watermark_id(value: str) -> bool:
    return bool(value) and bool(_WM_ID_RE.match(value))


def is_supported_filename(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() in SUPPORTED_EXTENSIONS


# --------------------------------------------------------------------------- #
# PDF — embed
# --------------------------------------------------------------------------- #
def _invisible_marker_overlay(watermark_id: str, width: float = 612.0, height: float = 792.0):
    """One-page overlay carrying ``SAKSHYA::<id>`` in PDF text rendering mode 3 (``3 Tr``),
    1 pt Helvetica at (2, 2). Mode 3 = neither fill nor stroke: nothing is painted."""
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))
    t = c.beginText(2, 2)
    t.setFont("Helvetica", 1)
    t.setTextRenderMode(3)                       # <- real invisible text, not alpha-0 fill
    t.textOut(f"{MARKER_PREFIX}{watermark_id}")
    c.drawText(t)
    c.save()
    buf.seek(0)
    return PdfReader(buf).pages[0]


def embed_pdf_watermark(pdf_bytes: bytes, watermark_id: str) -> bytes:
    """Metadata channel + Tr-3 content marker on EVERY page."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    writer.append_pages_from_reader(reader)
    if len(writer.pages) == 0:
        raise WatermarkError("PDF has no pages")

    new_meta = {k: v for k, v in (reader.metadata or {}).items()}
    new_meta[WATERMARK_METADATA_KEY] = watermark_id
    writer.add_metadata(new_meta)

    overlays: dict[tuple[float, float], object] = {}
    for i, page in enumerate(writer.pages):
        box = page.mediabox
        size = (float(box.width), float(box.height))
        try:
            if size not in overlays:
                overlays[size] = _invisible_marker_overlay(watermark_id, *size)
            page.merge_page(overlays[size])
        except Exception as e:
            raise WatermarkError(f"could not embed invisible marker on page {i + 1}: {e}") from e

    out = io.BytesIO()
    writer.write(out)
    result = out.getvalue()

    # Prove BOTH channels landed (first / middle / last page for the content channel).
    chk = PdfReader(io.BytesIO(result))
    if _extract_pdf_metadata_marker(chk) != watermark_id:
        raise WatermarkError("metadata channel did not verify after embedding")
    n = len(chk.pages)
    for idx in sorted({0, n // 2, n - 1}):
        if _extract_page_marker(chk.pages[idx]) != watermark_id:
            raise WatermarkError(f"content-stream channel did not verify on page {idx + 1}")
    return result


# --------------------------------------------------------------------------- #
# PDF — optional visible layer
# --------------------------------------------------------------------------- #
def _visible_overlay_for_page(width: float, height: float, stamp_lines: list[str], micro_text: str):
    """Tiled micro-pattern + large diagonal stamp, baked into page CONTENT (survives a
    screenshot / photo of the screen)."""
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))

    c.saveState()
    c.setFillColorRGB(0.72, 0.72, 0.72)
    c.setFont("Helvetica", 5.2)
    step_x, step_y = 95, 34
    row = 0
    y = -10
    while y < height + step_y:
        offset = 0 if row % 2 == 0 else step_x / 2
        x = -step_x + offset
        while x < width + step_x:
            c.saveState()
            c.translate(x, y)
            c.rotate(28)
            c.drawString(0, 0, micro_text)
            c.restoreState()
            x += step_x
        y += step_y
        row += 1
    c.restoreState()

    c.saveState()
    c.setFillColorRGB(0.62, 0.09, 0.09)
    try:
        c.setFillAlpha(0.22)
    except Exception:
        pass
    c.setFont("Helvetica-Bold", 20)
    c.translate(width / 2, height / 2)
    c.rotate(38)
    n = len(stamp_lines)
    for i, line in enumerate(stamp_lines):
        c.drawCentredString(0, (n / 2 - i) * 24, line)
    c.restoreState()

    c.save()
    buf.seek(0)
    return PdfReader(buf).pages[0]


def apply_visible_watermark(
    pdf_bytes: bytes,
    watermark_id: str,
    recipient_name: str,
    recipient_id: str,
    timestamp_iso: str,
) -> bytes:
    """OPT-IN visible stamp + micro-pattern on every page. Call AFTER the invisible embed
    and BEFORE hashing/signing so the ledgered hash matches the delivered bytes."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    writer.append_pages_from_reader(reader)
    writer.add_metadata({k: v for k, v in (reader.metadata or {}).items()})

    date_only = timestamp_iso.split("T")[0] if timestamp_iso else ""
    stamp_lines = [
        "CONFIDENTIAL — SAKSHYA PROTECTED",
        f"{recipient_name} · {recipient_id}",
        f"{watermark_id} · {date_only}",
    ]
    # SAKSHYA:: prefix => extract_pdf_watermark() finds it even if the invisible channels are gone.
    micro_text = f"{MARKER_PREFIX}{watermark_id} {recipient_id}"

    for page in writer.pages:
        box = page.mediabox
        width, height = float(box.width), float(box.height)
        try:
            page.merge_page(_visible_overlay_for_page(width, height, stamp_lines, micro_text))
        except Exception:
            # Never let the optional visible layer destroy the document; invisible channels hold.
            continue

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


# --------------------------------------------------------------------------- #
# PDF — extract
# --------------------------------------------------------------------------- #
def _extract_pdf_metadata_marker(reader: PdfReader) -> Optional[str]:
    try:
        meta = reader.metadata or {}
        val = str(meta.get(WATERMARK_METADATA_KEY, ""))
    except Exception:
        return None
    return val if is_valid_watermark_id(val) else None


def _extract_page_marker(page) -> Optional[str]:
    """Look for ``SAKSHYA::WM-…`` in the raw content stream first (covers our Tr-3 run),
    then in extracted text (covers visible micro-text and re-encoded PDFs)."""
    try:
        contents = page.get_contents()
        if contents is not None:
            m = _MARKER_RE_BYTES.search(_unescape_pdf_octal(contents.get_data()))
            if m:
                return m.group(1).decode()
    except Exception:
        pass
    try:
        m = _MARKER_RE.search(page.extract_text() or "")
        if m:
            return m.group(1)
    except Exception:
        pass
    return None


def extract_pdf_watermark(pdf_bytes: bytes) -> Optional[str]:
    """Metadata channel first, then EVERY page (embedding is on all pages)."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    found = _extract_pdf_metadata_marker(reader)
    if found:
        return found
    for page in reader.pages:
        found = _extract_page_marker(page)
        if found:
            return found
    return None


# --------------------------------------------------------------------------- #
# DOCX (metadata-only)
# --------------------------------------------------------------------------- #
def _embed_docx_watermark(docx_bytes: bytes, watermark_id: str) -> bytes:
    import zipfile

    marker = f"<dc:description>{MARKER_PREFIX}{watermark_id}</dc:description>"
    src = io.BytesIO(docx_bytes)
    out = io.BytesIO()
    saw_core = False
    with zipfile.ZipFile(src, "r") as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "docProps/core.xml":
                saw_core = True
                text = data.decode("utf-8")
                if re.search(r"<dc:description\s*/>", text):
                    text = re.sub(r"<dc:description\s*/>", marker, text, count=1)
                elif "<dc:description>" in text:
                    text = re.sub(r"<dc:description>.*?</dc:description>", marker, text, count=1, flags=re.S)
                else:
                    text = text.replace("</cp:coreProperties>", f"{marker}</cp:coreProperties>")
                data = text.encode("utf-8")
            zout.writestr(item, data)
    if not saw_core:
        raise WatermarkError("DOCX has no docProps/core.xml to carry the marker")
    return out.getvalue()


def _extract_docx_watermark(docx_bytes: bytes) -> Optional[str]:
    import zipfile

    try:
        with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
            text = z.read("docProps/core.xml").decode("utf-8")
        m = _MARKER_RE.search(text)
        return m.group(1) if m else None
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Public entry points
# --------------------------------------------------------------------------- #
def watermark_document(file_bytes: bytes, filename: str, watermark_id: str) -> tuple[bytes, WatermarkResult]:
    """Embed ``watermark_id``. Raises UnsupportedWatermarkType for anything but .pdf/.docx and
    WatermarkError if the marker cannot be proven recoverable — never returns an unmarked copy."""
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".pdf":
        return embed_pdf_watermark(file_bytes, watermark_id), WatermarkResult(watermark_id, True, "pdf-dual")
    if ext == ".docx":
        try:
            marked = _embed_docx_watermark(file_bytes, watermark_id)
        except WatermarkError:
            raise
        except Exception as e:
            raise WatermarkError(f"could not watermark DOCX: {e}") from e
        if _extract_docx_watermark(marked) != watermark_id:
            raise WatermarkError("DOCX metadata marker did not verify after embedding")
        return marked, WatermarkResult(watermark_id, True, "docx-metadata")
    raise UnsupportedWatermarkType(f"'{ext or filename}' cannot carry a forensic watermark (allowed: .pdf, .docx)")


def extract_watermark(file_bytes: bytes, filename: str = "") -> Optional[str]:
    """Sniff by magic bytes first (a leaker may rename the file), then by extension."""
    try:
        if file_bytes[:5] == b"%PDF-":
            return extract_pdf_watermark(file_bytes)
        if file_bytes[:2] == b"PK":
            return _extract_docx_watermark(file_bytes)
    except Exception:
        return None
    ext = os.path.splitext(filename)[1].lower()
    try:
        if ext == ".pdf":
            return extract_pdf_watermark(file_bytes)
        if ext == ".docx":
            return _extract_docx_watermark(file_bytes)
    except Exception:
        return None
    return None

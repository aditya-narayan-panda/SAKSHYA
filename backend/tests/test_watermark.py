import io
import re

import pytest
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from app.watermark import watermark_service as ws
from app.watermark.watermark_service import (
    generate_watermark_id, watermark_document, extract_watermark, apply_visible_watermark,
    UnsupportedWatermarkType, WM_ID_REGEX,
)


def _make_sample_pdf(pages: int = 1) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(200, 200))
    for i in range(pages):
        c.drawString(20, 100, f"sample page {i + 1}")
        c.showPage()
    c.save()
    return buf.getvalue()


SAMPLE_PDF = _make_sample_pdf()


def _unescape_pdf_strings(data: str) -> str:
    """reportlab writes ':' and '-' inside PDF strings as octal escapes (\\072, \\055)."""
    return re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), data)


def _content(page) -> str:
    return _unescape_pdf_strings(page.get_contents().get_data().decode("latin-1"))


def _visible_text(pdf_bytes: bytes) -> str:
    """What a human sees = text painted with a visible render mode. Tr 3 runs are excluded
    (pypdf/PDFium return them from extraction, but they draw no pixels)."""
    out = []
    for page in PdfReader(io.BytesIO(pdf_bytes)).pages:
        data = _content(page)
        # drop every BT..ET block whose text state selects render mode 3
        blocks = re.findall(r"BT.*?ET", data, flags=re.S)
        for b in blocks:
            if re.search(r"(^|\s)3\s+Tr(\s|$)", b):
                continue
            out.append(b)
    return "\n".join(out)


def test_pdf_watermark_round_trip():
    wm_id = generate_watermark_id()
    watermarked, result = watermark_document(SAMPLE_PDF, "test.pdf", wm_id)
    assert result.supported is True and result.channel == "pdf-dual"
    assert extract_watermark(watermarked, "test.pdf") == wm_id


def test_unsupported_formats_are_rejected_not_silently_skipped():
    for name in ("notes.txt", "sheet.xlsx", "x.bin"):
        with pytest.raises(UnsupportedWatermarkType):
            watermark_document(b"plain text content", name, generate_watermark_id())
    assert extract_watermark(b"plain text content", "notes.txt") is None


def test_watermark_ids_are_unique_and_64_bit():
    ids = {generate_watermark_id() for _ in range(50)}
    assert len(ids) == 50
    assert all(re.fullmatch(WM_ID_REGEX, i) and len(i) == 3 + 16 for i in ids)


def test_marker_is_on_every_page_in_render_mode_3():
    wm_id = generate_watermark_id()
    out, _ = watermark_document(_make_sample_pdf(5), "five.pdf", wm_id)
    reader = PdfReader(io.BytesIO(out))
    assert len(reader.pages) == 5
    for page in reader.pages:
        data = _content(page)
        assert f"SAKSHYA::{wm_id}" in data
        assert re.search(r"\b3\s+Tr\b", data), "invisible text must use text render mode 3"
    assert reader.metadata["/SakshyaWatermarkID"] == wm_id


def test_no_watermark_text_visible_to_human_reader_by_default():
    wm_id = generate_watermark_id()
    out, _ = watermark_document(SAMPLE_PDF, "test.pdf", wm_id)
    vis = _visible_text(out)
    assert "SAKSHYA" not in vis and wm_id not in vis
    assert "sample page 1" in vis                       # sanity: real content is still there


def test_visible_stamp_is_opt_in_and_preserves_invisible_marker():
    wm_id = generate_watermark_id()
    watermarked, _ = watermark_document(SAMPLE_PDF, "test.pdf", wm_id)
    stamped = apply_visible_watermark(watermarked, wm_id, "Officer-01", "REC-ABC123", "2026-09-27T10:00:00+00:00")
    assert stamped != watermarked
    assert extract_watermark(stamped, "test.pdf") == wm_id
    vis = _visible_text(stamped)
    assert "REC-ABC123" in vis and wm_id in vis           # opt-in stamp really is visible text


def test_visible_micro_text_alone_still_identifies_the_leak():
    """Invisible channels stripped (metadata AND Tr-3 run) but visible micro-text survives."""
    wm_id = generate_watermark_id()
    only_visible = apply_visible_watermark(SAMPLE_PDF, wm_id, "Officer-01", "REC-ABC123", "2026-09-27T10:00:00+00:00")
    assert PdfReader(io.BytesIO(only_visible)).metadata.get("/SakshyaWatermarkID") is None
    assert extract_watermark(only_visible, "leak.pdf") == wm_id
    assert f"SAKSHYA::{wm_id}" in _visible_text(only_visible)


def test_metadata_stripped_content_marker_survives():
    from pypdf import PdfWriter
    wm_id = generate_watermark_id()
    out, _ = watermark_document(_make_sample_pdf(3), "t.pdf", wm_id)
    w = PdfWriter(); w.append_pages_from_reader(PdfReader(io.BytesIO(out)))
    buf = io.BytesIO(); w.write(buf)
    assert PdfReader(io.BytesIO(buf.getvalue())).metadata is None or \
        "/SakshyaWatermarkID" not in (PdfReader(io.BytesIO(buf.getvalue())).metadata or {})
    assert extract_watermark(buf.getvalue(), "t.pdf") == wm_id


def test_two_recipients_byte_different_pixel_identical():
    pytest.importorskip("pypdfium2")
    from PIL import ImageChops
    import pypdfium2 as pdfium

    a_id, b_id = generate_watermark_id(), generate_watermark_id()
    a, _ = watermark_document(SAMPLE_PDF, "t.pdf", a_id)
    b, _ = watermark_document(SAMPLE_PDF, "t.pdf", b_id)
    assert a != b
    ia = pdfium.PdfDocument(a)[0].render(scale=2).to_pil().convert("RGB")
    ib = pdfium.PdfDocument(b)[0].render(scale=2).to_pil().convert("RGB")
    assert ImageChops.difference(ia, ib).getbbox() is None
    assert extract_watermark(a, "t.pdf") == a_id and extract_watermark(b, "t.pdf") == b_id

"""Visible and metadata buyer stamp on every page of a private PDF."""

from __future__ import annotations

import io

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from sensoria.shared.errors import DomainError

MAX_SOURCE_BYTES = 200 * 1024 * 1024
_FONT = "Helvetica"


def _footer_text(email: str, order_number: str) -> str:
    # Standard PDF fonts cannot render every Unicode glyph, so keep the stamp to Latin-1.
    text = f"Egzemplarz dla: {email} - zamowienie {order_number}"
    return text.encode("latin-1", "replace").decode("latin-1")


def stamp_pdf(source: bytes, *, email: str, order_number: str) -> bytes:
    """Return a copy of ``source`` with a footer stamp on each page."""
    if len(source) > MAX_SOURCE_BYTES:
        raise DomainError("FILE_TOO_LARGE", "Plik jest zbyt duży do znakowania.", 413)
    try:
        writer = PdfWriter(clone_from=io.BytesIO(source))
        text = _footer_text(email, order_number)
        for page in writer.pages:
            width = float(page.mediabox.width)
            overlay = io.BytesIO()
            pdf = canvas.Canvas(overlay, pagesize=(width, float(page.mediabox.height)))
            pdf.setFont(_FONT, 7)
            pdf.setFillGray(0.45)
            pdf.drawCentredString(width / 2, 14, text)
            pdf.save()
            overlay.seek(0)
            page.merge_page(PdfReader(overlay).pages[0])
        writer.add_metadata({"/Subject": text, "/Producer": "SENSORIA"})
        output = io.BytesIO()
        writer.write(output)
        return output.getvalue()
    except DomainError:
        raise
    except Exception:
        raise DomainError(
            "WATERMARK_FAILED", "Nie udało się przygotować pliku. Spróbuj ponownie.", 503
        ) from None

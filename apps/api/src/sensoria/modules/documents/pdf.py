"""Render sales documents to PDF with an embedded Unicode font (Polish diacritics)."""

from __future__ import annotations

import io
from functools import lru_cache
from pathlib import Path
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"
REGULAR, BOLD = "DejaVuSans", "DejaVuSans-Bold"


def format_grosz(value: int) -> str:
    """Integer-only money formatting: 7900 -> '79,00 zł'."""
    sign = "-" if value < 0 else ""
    zloty, grosz = divmod(abs(value), 100)
    grouped = f"{zloty:,}".replace(",", " ")
    return f"{sign}{grouped},{grosz:02d} zł"


@lru_cache(maxsize=1)
def _register_fonts() -> None:
    pdfmetrics.registerFont(TTFont(REGULAR, str(FONT_DIR / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont(BOLD, str(FONT_DIR / "DejaVuSans-Bold.ttf")))


def _party(pdf: canvas.Canvas, x: float, y: float, title: str, lines: list[str]) -> None:
    pdf.setFont(BOLD, 9)
    pdf.drawString(x, y, title)
    pdf.setFont(REGULAR, 9)
    for index, line in enumerate(lines):
        pdf.drawString(x, y - 14 * (index + 1), line)


def render_document(data: dict[str, Any], *, title: str, number: str, issued: str) -> bytes:
    _register_fonts()
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4, pageCompression=1)
    pdf.setTitle(f"{title} {number}")
    width, height = A4
    pdf.setFont(BOLD, 18)
    pdf.drawString(40, height - 60, f"{title} {number}")
    pdf.setFont(REGULAR, 9)
    pdf.drawString(
        40, height - 78, f"Data wystawienia: {issued} · zamówienie {data['order_number']}"
    )
    seller = data.get("seller") or {}
    buyer = data["buyer"]
    _party(pdf, 40, height - 110, "Sprzedawca", seller.get("lines", []))
    _party(pdf, 320, height - 110, "Nabywca", buyer.get("lines", []))
    y = height - 220
    columns = [40, 250, 290, 350, 410, 460, 510]
    headers = ["Pozycja", "Ilość", "Cena brutto", "VAT", "Netto", "Podatek", "Brutto"]
    pdf.setFont(BOLD, 8)
    for x, label in zip(columns, headers, strict=True):
        pdf.drawString(x, y, label)
    pdf.line(40, y - 4, width - 40, y - 4)
    pdf.setFont(REGULAR, 8)
    y -= 18
    for line in data["lines"]:
        pdf.drawString(columns[0], y, str(line["name"])[:40])
        pdf.drawString(columns[1], y, str(line["quantity"]))
        pdf.drawString(columns[2], y, format_grosz(line["unit_gross_grosz"]))
        pdf.drawString(columns[3], y, line["vat_label"])
        pdf.drawString(columns[4], y, format_grosz(line["net_grosz"]))
        pdf.drawString(columns[5], y, format_grosz(line["tax_grosz"]))
        pdf.drawString(columns[6], y, format_grosz(line["gross_grosz"]))
        y -= 14
    y -= 8
    pdf.line(40, y + 6, width - 40, y + 6)
    if data.get("discount_grosz"):
        pdf.drawString(40, y - 6, f"Rabat: -{format_grosz(data['discount_grosz'])}")
        y -= 14
    pdf.setFont(BOLD, 9)
    pdf.drawString(40, y - 8, "Podsumowanie VAT")
    pdf.setFont(REGULAR, 8)
    y -= 24
    for group in data["vat_groups"]:
        pdf.drawString(
            40,
            y,
            f"{group['vat_label']}: netto {format_grosz(group['net_grosz'])}, "
            f"podatek {format_grosz(group['tax_grosz'])}, "
            f"brutto {format_grosz(group['gross_grosz'])}",
        )
        y -= 12
    y -= 10
    pdf.setFont(BOLD, 12)
    pdf.drawString(40, y, f"Zapłacono: {format_grosz(data['total_grosz'])}")
    pdf.setFont(REGULAR, 8)
    pdf.drawString(40, y - 16, f"Metoda płatności: {data['payment_method']}")
    pdf.save()
    return buffer.getvalue()

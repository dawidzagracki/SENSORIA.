"""Runs inside the api container: prints JSON with demo covers (PNG) and PDFs (base64)."""

import base64
import io
import json
import os
import textwrap

import sensoria
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A5
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

FONTS = os.path.join(os.path.dirname(sensoria.__file__), "assets", "fonts")
pdfmetrics.registerFont(TTFont("DV", os.path.join(FONTS, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DVB", os.path.join(FONTS, "DejaVuSans-Bold.ttf")))


def cover(title: str, subtitle: str, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> str:
    w, h = 720, 960
    image = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(image)
    for y in range(h):
        t = y / h
        draw.line([(0, y), (w, y)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    big = ImageFont.truetype(os.path.join(FONTS, "DejaVuSans-Bold.ttf"), 54)
    small = ImageFont.truetype(os.path.join(FONTS, "DejaVuSans.ttf"), 28)
    y = 220
    for line in textwrap.wrap(title, 16):
        draw.text((60, y), line, font=big, fill="white")
        y += 70
    y += 20
    for line in textwrap.wrap(subtitle, 30):
        draw.text((60, y), line, font=small, fill=(255, 255, 255))
        y += 38
    draw.text((60, h - 90), "SENSORIA.", font=small, fill="white")
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def pdf(title: str, pages: list[tuple[str, ...]], footer: str | None = None) -> str:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A5)
    width, height = A5
    c.setTitle(title)
    for index, (heading, body, *rest) in enumerate(pages, start=1):
        outline = rest[0] if rest else heading
        if outline:
            c.bookmarkPage(f"p{index}")
            c.addOutlineEntry(outline, f"p{index}", 0)
        c.setFont("DVB", 16)
        y = height - 60
        for line in textwrap.wrap(heading, 38):
            c.drawString(40, y, line)
            y -= 22
        c.setFont("DV", 10.5)
        y -= 10
        for paragraph in body.split("\n\n"):
            for line in textwrap.wrap(paragraph, 70):
                c.drawString(40, y, line)
                y -= 15
            y -= 8
        c.setFont("DV", 8)
        c.drawString(40, 28, footer or f"{title} · strona {index}")
        c.showPage()
    c.save()
    return base64.b64encode(buffer.getvalue()).decode()


LOREM = [
    "Zmysły towarzyszą nam od pierwszych chwil życia. To, jak dziecko odbiera dźwięki, dotyk, ruch i światło, "
    "wpływa na to, jak się uczy, bawi i buduje relacje. Ten materiał ma charakter demonstracyjny.",
    "Obserwuj, co uspokaja, a co pobudza Twoje dziecko. Krótkie, regularne rytuały — kąpiel, kołysanie, "
    "ciepły koc — pomagają układowi nerwowemu wrócić do równowagi.",
    "Nie ma jednej recepty. Zapisuj spostrzeżenia, rozmawiaj z terapeutą i pozwól dziecku być przewodnikiem "
    "w odkrywaniu własnych potrzeb sensorycznych.",
]
EBOOK = [(f"Rozdział {n}: " + t, "\n\n".join(LOREM)) for n, t in enumerate(
    ["Zmysły i codzienność", "Dotyk i bliskość", "Dźwięk i cisza", "Ruch i równowaga", "Rytuały dnia",
     "Kiedy szukać wsparcia"], start=1)]
_LESSONS = ["Czym jest regulacja emocji", "Ciało jako sygnał", "Oddech i zabawa",
            "Rozmowa o trudnych uczuciach", "Plan na tydzień"]
COURSE = []
for _n, _t in enumerate(_LESSONS, start=1):
    COURSE.append((f"Lekcja {_n}: " + _t, "\n\n".join(LOREM), f"Lekcja {_n}: {_t}"))
    COURSE.append((f"Lekcja {_n}: ćwiczenie", "\n\n".join(reversed(LOREM)), None))
FOOTER = "Fragment bezpłatny · pełna wersja dostępna w sensoria.shop"
print(json.dumps({
    "covers": {
        "book": cover("Integracja sensoryczna w codzienności", "Praktyczny poradnik dla rodziców", (47, 111, 94), (20, 52, 60)),
        "audio": cover("Kiedy zmysły mówią głośniej", "Audiobook · czyta Zosia", (92, 70, 140), (36, 28, 70)),
        "ebook": cover("Zmysły w domu", "E-book PDF · krótki przewodnik", (200, 120, 70), (120, 60, 50)),
        "course": cover("Regulacja emocji u dziecka", "Kurs PDF · 5 lekcji", (50, 120, 160), (20, 50, 90)),
        "v1": cover("Konsultacja psychologiczna", "Voucher · 50 minut", (150, 90, 120), (80, 40, 70)),
        "v2": cover("Diagnoza integracji sensorycznej", "Voucher · pełna diagnoza", (70, 130, 110), (30, 70, 70)),
    },
    "pdfs": {
        "ebook": pdf("Zmysły w domu", EBOOK),
        "ebook_sample": pdf("Zmysły w domu — fragment", EBOOK[:2], FOOTER),
        "course": pdf("Regulacja emocji u dziecka", COURSE),
        "course_sample": pdf("Regulacja emocji — fragment", COURSE[:1], FOOTER),
    },
}))

"""Render voucher PDFs (with QR code) from durable jobs; safe for concurrent workers."""

from __future__ import annotations

import asyncio
import io
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import qrcode
from qrcode.constants import ERROR_CORRECT_Q
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sensoria.config import get_settings
from sensoria.database import SessionFactory
from sensoria.modules.documents.pdf import BOLD, FONT_DIR, REGULAR
from sensoria.modules.storage.service import StorageService

from .models import Voucher, VoucherPDFJob

logger = logging.getLogger("sensoria.vouchers.pdf")
MAX_ATTEMPTS = 5
LOCK_TIMEOUT = timedelta(minutes=10)
WARSAW = ZoneInfo("Europe/Warsaw")
VARIANT_LABELS = {"ONLINE": "Wizyta online", "IN_PERSON": "Wizyta stacjonarna"}


def _fonts() -> None:
    for name, file in ((REGULAR, "DejaVuSans.ttf"), (BOLD, "DejaVuSans-Bold.ttf")):
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / file)))


def qr_png(target: str) -> bytes:
    qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_Q, box_size=8, border=2)
    qr.add_data(target)
    qr.make(fit=True)
    buffer = io.BytesIO()
    qr.make_image().save(buffer)
    return buffer.getvalue()


def render_voucher_pdf(
    voucher: Voucher, *, origin: str, valid_until: datetime | None = None
) -> bytes:
    """Build a one-page voucher; only trusted snapshot fields are printed."""
    _fonts()
    snapshot: dict[str, Any] = voucher.issue_snapshot
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4, pageCompression=1)
    pdf.setTitle(f"Voucher {voucher.code}")
    width, height = A4
    pdf.setFillColorRGB(0.45, 0.07, 0.2)
    pdf.rect(0, height - 130, width, 130, stroke=0, fill=1)
    pdf.setFillColorRGB(1, 1, 1)
    pdf.setFont(BOLD, 26)
    pdf.drawString(48, height - 70, "SENSORIA")
    pdf.setFont(REGULAR, 12)
    pdf.drawString(48, height - 95, "Voucher na wizytę")
    pdf.setFillColorRGB(0.1, 0.05, 0.08)
    pdf.setFont(BOLD, 20)
    pdf.drawString(48, height - 180, str(snapshot.get("service_name", "Usługa")))
    pdf.setFont(REGULAR, 12)
    variant = VARIANT_LABELS.get(str(snapshot.get("variant_kind", "")), "")
    if variant:
        pdf.drawString(48, height - 202, variant)
    valid_until_text = (valid_until or voucher.valid_until).astimezone(WARSAW).strftime("%d.%m.%Y")
    pdf.drawString(48, height - 226, f"Ważny do: {valid_until_text} (włącznie)")
    gift = snapshot.get("gift")
    y = height - 252
    if isinstance(gift, dict):
        pdf.drawString(48, y, f"Dla: {gift.get('recipient_name', '')}")
        y -= 20
        if gift.get("dedication"):
            pdf.setFont(REGULAR, 11)
            words, line = str(gift["dedication"]).split(), ""
            for word in words:
                if pdf.stringWidth(f"{line} {word}".strip(), REGULAR, 11) > width - 200:
                    pdf.drawString(48, y, line)
                    y -= 15
                    line = word
                else:
                    line = f"{line} {word}".strip()
            if line:
                pdf.drawString(48, y, line)
    pdf.setFont(BOLD, 28)
    pdf.drawString(48, 360, voucher.code)
    pdf.setFont(REGULAR, 10)
    pdf.drawString(48, 342, "Kod vouchera — podaj go podczas rezerwacji wizyty.")
    image = ImageReader(io.BytesIO(qr_png(f"{origin}/voucher/{voucher.code}")))
    pdf.drawImage(image, width - 48 - 170, 270, width=170, height=170)
    pdf.setFont(REGULAR, 9)
    pdf.drawString(48, 120, "Status vouchera można sprawdzić, skanując kod QR.")
    pdf.drawString(48, 106, "Voucher jest jednorazowy i nie podlega wymianie na gotówkę.")
    pdf.save()
    return buffer.getvalue()


async def process_voucher_pdf_jobs(
    session_factory: async_sessionmaker[AsyncSession] = SessionFactory,
    *,
    batch_size: int = 20,
    now: datetime | None = None,
) -> int:
    """Claim due jobs with SKIP LOCKED, render, store and attach the PDF; returns completed."""
    origin = get_settings().SITE_URL or "http://localhost"
    moment = now or datetime.now(UTC)
    completed = 0
    async with session_factory() as session, session.begin():
        jobs = list(
            (
                await session.scalars(
                    select(VoucherPDFJob)
                    .where(
                        or_(
                            (VoucherPDFJob.status == "pending")
                            & (VoucherPDFJob.available_at <= func.now()),
                            (VoucherPDFJob.status == "processing")
                            & (VoucherPDFJob.locked_at <= moment - LOCK_TIMEOUT),
                        )
                    )
                    .order_by(VoucherPDFJob.available_at, VoucherPDFJob.id)
                    .limit(batch_size)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        for job in jobs:
            voucher = await session.get(Voucher, job.voucher_id)
            job.attempts += 1
            try:
                if voucher is None:
                    raise LookupError("voucher_missing")
                if voucher.pdf_file_id is None:
                    content = await asyncio.to_thread(render_voucher_pdf, voucher, origin=origin)
                    async with session.begin_nested():
                        stored = await StorageService().store_voucher_pdf(
                            session,
                            voucher_id=voucher.id,
                            year=voucher.issued_at.year,
                            content=content,
                        )
                        voucher.pdf_file_id = stored.id
                job.status = "complete"
                job.completed_at = moment
                job.error_code = None
                completed += 1
            except Exception as error:
                logger.error("Render PDF vouchera nie powiódł się [%s].", type(error).__name__)
                job.error_code = type(error).__name__[:80]
                if job.attempts >= MAX_ATTEMPTS:
                    job.status = "failed"
                else:
                    job.status = "pending"
                    job.available_at = moment + timedelta(minutes=2**job.attempts)
    return completed


async def voucher_pdf_scheduler(interval_seconds: int = 15) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            await process_voucher_pdf_jobs()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.error("Worker PDF voucherów zakończył się błędem [%s].", type(error).__name__)

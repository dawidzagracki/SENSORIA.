"""Email layout and the transactional templates; every variable is HTML-escaped."""

from __future__ import annotations

import html
from collections.abc import Callable
from typing import Any

from sensoria.shared.errors import DomainError

INK, MUTED, ACCENT, SURFACE, BORDER = "#2a0c18", "#6e4356", "#c81e5e", "#fff1f5", "#f0d5e0"


def _e(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _money(grosz: int) -> str:
    zloty, rest = divmod(abs(int(grosz)), 100)
    return f"{zloty:,}".replace(",", " ") + f",{rest:02d} zł"


def _button(url: str, label: str) -> str:
    return (
        f'<p style="margin:24px 0"><a href="{_e(url)}" style="background:{ACCENT};color:#fff;'
        f"text-decoration:none;padding:12px 22px;border-radius:999px;font-weight:700;"
        f'display:inline-block">{_e(label)}</a></p>'
    )


def layout(title: str, body_html: str) -> str:
    return (
        '<!doctype html><html lang="pl"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{_e(title)}</title></head>"
        f'<body style="margin:0;background:{SURFACE};font-family:Arial,Helvetica,sans-serif;'
        f'color:{INK}"><table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        '<tr><td align="center" style="padding:24px 12px">'
        f'<table role="presentation" width="600" style="max-width:600px;background:#fff;'
        f'border:1px solid {BORDER};border-radius:16px"><tr><td style="padding:28px 32px">'
        f'<p style="margin:0 0 20px;font-size:20px;font-weight:800;letter-spacing:.04em">'
        f'SENSORIA<span style="color:{ACCENT}">.</span></p>'
        f'<h1 style="font-size:22px;margin:0 0 16px">{_e(title)}</h1>{body_html}'
        f'<hr style="border:0;border-top:1px solid {BORDER};margin:28px 0 12px">'
        f'<p style="font-size:12px;color:{MUTED};margin:0">Ta wiadomość została wysłana '
        "automatycznie. Jeśli to nie Ty złożyłaś zamówienie, zignoruj ją.</p>"
        "</td></tr></table></td></tr></table></body></html>"
    )


Rendered = tuple[str, str, str]


def _require(variables: dict[str, Any], *names: str) -> None:
    missing = [name for name in names if name not in variables]
    if missing:
        raise DomainError("MAIL_VARIABLES_MISSING", f"Brak zmiennych szablonu: {missing}", 500)


def order_confirmation(v: dict[str, Any]) -> Rendered:
    _require(v, "order_number", "amount_grosz", "order_url")
    subject = f"Dziękujemy za zamówienie {v['order_number']}"
    body = (
        f"<p>Otrzymaliśmy Twoją płatność za zamówienie <strong>{_e(v['order_number'])}</strong> "
        f"na kwotę <strong>{_e(_money(v['amount_grosz']))}</strong>.</p>"
        + _button(v["order_url"], "Zobacz zamówienie")
    )
    text = (
        f"Dziękujemy! Płatność za zamówienie {v['order_number']} ({_money(v['amount_grosz'])}) "
        f"została potwierdzona.\nSzczegóły: {v['order_url']}"
    )
    return subject, layout(subject, body), text


def payment_failed(v: dict[str, Any]) -> Rendered:
    _require(v, "order_number", "retry_url")
    subject = f"Płatność za zamówienie {v['order_number']} nie powiodła się"
    body = (
        "<p>Płatność nie została zrealizowana, a środki nie zostały pobrane.</p>"
        "<p>Zamówienie jest zarezerwowane przez ograniczony czas — możesz spróbować ponownie.</p>"
        + _button(v["retry_url"], "Spróbuj zapłacić ponownie")
    )
    text = (
        f"Płatność za zamówienie {v['order_number']} nie powiodła się. "
        f"Spróbuj ponownie: {v['retry_url']}"
    )
    return subject, layout(subject, body), text


def digital_access(v: dict[str, Any]) -> Rendered:
    _require(v, "order_number", "titles", "library_url")
    subject = "Twoje materiały są gotowe"
    items = "".join(f"<li>{_e(title)}</li>" for title in v["titles"])
    body = (
        f"<p>Zamówienie <strong>{_e(v['order_number'])}</strong> jest opłacone. "
        f"Masz dostęp do:</p><ul>{items}</ul>" + _button(v["library_url"], "Otwórz bibliotekę")
    )
    text = (
        f"Zamówienie {v['order_number']} jest opłacone. Dostęp: "
        f"{', '.join(v['titles'])}.\nBiblioteka: {v['library_url']}"
    )
    return subject, layout(subject, body), text


def voucher_delivery(v: dict[str, Any]) -> Rendered:
    _require(v, "service_name", "code", "valid_until", "voucher_url")
    subject = f"Twój voucher: {v['service_name']}"
    body = (
        f"<p>Voucher na <strong>{_e(v['service_name'])}</strong> jest gotowy.</p>"
        f'<p style="font-size:22px;font-weight:800;letter-spacing:.08em">{_e(v["code"])}</p>'
        f"<p>Ważny do: <strong>{_e(v['valid_until'])}</strong>. "
        "Plik PDF znajdziesz w załączniku.</p>" + _button(v["voucher_url"], "Pokaż voucher")
    )
    text = (
        f"Voucher: {v['service_name']}\nKod: {v['code']}\nWażny do: {v['valid_until']}\n"
        f"{v['voucher_url']}"
    )
    return subject, layout(subject, body), text


def voucher_gift(v: dict[str, Any]) -> Rendered:
    _require(v, "recipient_name", "buyer_hint", "service_name", "code", "valid_until")
    subject = "Masz prezent od bliskiej osoby"
    dedication = (
        f'<blockquote style="border-left:3px solid {ACCENT};margin:16px 0;padding-left:14px;'
        f'color:{MUTED}"><em>{_e(v["dedication"])}</em></blockquote>'
        if v.get("dedication")
        else ""
    )
    body = (
        f"<p>Cześć {_e(v['recipient_name'])}! {_e(v['buyer_hint'])} przygotowała dla Ciebie "
        f"voucher: <strong>{_e(v['service_name'])}</strong>.</p>{dedication}"
        f'<p style="font-size:22px;font-weight:800;letter-spacing:.08em">{_e(v["code"])}</p>'
        f"<p>Ważny do: <strong>{_e(v['valid_until'])}</strong>. PDF jest w załączniku.</p>"
    )
    text = (
        f"Cześć {v['recipient_name']}! Voucher: {v['service_name']}. Kod: {v['code']}. "
        f"Ważny do: {v['valid_until']}."
    )
    return subject, layout(subject, body), text


def shipment_sent(v: dict[str, Any]) -> Rendered:
    _require(v, "order_number", "carrier", "tracking_number")
    subject = f"Zamówienie {v['order_number']} zostało wysłane"
    link = v.get("tracking_url")
    body = (
        f"<p>Twoja paczka jest w drodze ({_e(v['carrier'])}).</p>"
        f"<p>Numer przesyłki: <strong>{_e(v['tracking_number'])}</strong></p>"
        + (_button(link, "Śledź przesyłkę") if link else "")
    )
    text = f"Paczka {v['order_number']} wysłana ({v['carrier']}), nr {v['tracking_number']}."
    if link:
        text += f"\nŚledzenie: {link}"
    return subject, layout(subject, body), text


def pickup_ready(v: dict[str, Any]) -> Rendered:
    _require(v, "order_number")
    subject = f"Zamówienie {v['order_number']} czeka na odbiór"
    body = f"<p>Zamówienie <strong>{_e(v['order_number'])}</strong> jest gotowe do odbioru.</p>"
    return subject, layout(subject, body), f"Zamówienie {v['order_number']} czeka na odbiór."


def voucher_expiry_reminder(v: dict[str, Any]) -> Rendered:
    _require(v, "service_name", "code", "valid_until", "days_remaining", "account_url")
    subject = f"Voucher wygasa za {v['days_remaining']} dni"
    body = (
        f"<p>Voucher na <strong>{_e(v['service_name'])}</strong> ({_e(v['code'])}) jest ważny do "
        f"<strong>{_e(v['valid_until'])}</strong>.</p>"
        f"<p>{_e(v.get('extension_information', ''))}</p>"
        + _button(v["account_url"], "Moje vouchery")
    )
    text = (
        f"Voucher {v['code']} ({v['service_name']}) wygasa {v['valid_until']}. "
        f"{v.get('extension_information', '')}\n{v['account_url']}"
    )
    return subject, layout(subject, body), text


def _link_mail(
    subject: str, intro: str, label: str, key: str
) -> Callable[[dict[str, Any]], Rendered]:
    def render(v: dict[str, Any]) -> Rendered:
        _require(v, key)
        body = f"<p>{_e(intro)}</p>" + _button(v[key], label)
        return subject, layout(subject, body), f"{intro}\n{v[key]}"

    return render


TEMPLATES: dict[str, Callable[[dict[str, Any]], Rendered]] = {
    "order_confirmation": order_confirmation,
    "payment_failed": payment_failed,
    "digital_access": digital_access,
    "voucher_delivery": voucher_delivery,
    "voucher_gift": voucher_gift,
    "shipment_sent": shipment_sent,
    "pickup_ready": pickup_ready,
    "voucher_expiry_reminder": voucher_expiry_reminder,
    "login_link": _link_mail(
        "Zaloguj się do SENSORIA",
        "Kliknij, aby zalogować się. Link jest jednorazowy i ważny 15 minut.",
        "Zaloguj się",
        "link",
    ),
    "password_reset": _link_mail(
        "Ustaw nowe hasło",
        "Aby ustawić nowe hasło, kliknij poniższy przycisk.",
        "Ustaw hasło",
        "link",
    ),
    "email_verification": _link_mail(
        "Potwierdź adres e-mail",
        "Potwierdź adres e-mail, aby zakończyć rejestrację.",
        "Potwierdź adres",
        "link",
    ),
    "email_change": _link_mail(
        "Potwierdź nowy adres e-mail",
        "Potwierdź nowy adres e-mail na koncie SENSORIA. Link ważny 24 godziny.",
        "Potwierdź adres",
        "link",
    ),
}


def render_template(key: str, variables: dict[str, Any]) -> Rendered:
    renderer = TEMPLATES.get(key)
    if renderer is None:
        raise DomainError("MAIL_TEMPLATE_UNKNOWN", "Nieznany szablon wiadomości.", 500)
    return renderer(variables)

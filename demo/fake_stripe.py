"""Demo payment gateway: mimics the parts of Stripe Checkout the shop uses.

Creates sessions over POST /v1/checkout/sessions, shows a "pay" page and, on confirmation, sends
the same signed webhook Stripe would send. For presentations only — never deploy this.
"""

from __future__ import annotations

import hashlib
import hmac
import html
import json
import os
import time
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_demo")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "http://api:8000/payments/webhooks/stripe")
PUBLIC_URL = os.environ.get("PUBLIC_URL", "http://localhost:9911")
SESSIONS: dict[str, dict[str, object]] = {}

PAGE = """<!doctype html><html lang="pl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Płatność (tryb demonstracyjny)</title>
<style>body{{font-family:system-ui,sans-serif;background:#f6f4f0;margin:0;display:grid;place-items:center;min-height:100vh}}
main{{background:#fff;border-radius:16px;padding:32px;max-width:420px;width:calc(100% - 32px);box-shadow:0 8px 30px #0001}}
h1{{font-size:20px;margin:0 0 4px}}p{{color:#555}}.amount{{font-size:32px;font-weight:700;margin:16px 0}}
button{{width:100%;padding:14px;border:0;border-radius:10px;font-size:16px;cursor:pointer;margin-top:10px}}
.pay{{background:#2f6f5e;color:#fff}}.alt{{background:#eee}}a{{display:block;text-align:center;margin-top:16px;color:#555}}
.demo{{background:#fff3cd;border-radius:8px;padding:8px 12px;font-size:13px}}</style>
<main><p class="demo">Tryb demonstracyjny — żadne prawdziwe pieniądze nie są pobierane.</p>
<h1>{name}</h1><div class="amount">{amount}</div>
<form method="post" action="/pay/{sid}/confirm">
<button class="pay" name="method" value="blik">Zapłać BLIK-iem (demo)</button>
<button class="alt" name="method" value="card">Zapłać kartą (demo)</button></form>
<a href="{cancel}">Anuluj i wróć do sklepu</a></main></html>"""


def send_webhook(sid: str, amount: int) -> None:
    event = {
        "id": "evt_" + uuid.uuid4().hex,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": sid,
                "payment_status": "paid",
                "amount_total": amount,
                "currency": "pln",
            }
        },
    }
    raw = json.dumps(event).encode()
    ts = int(time.time())
    sig = hmac.new(WEBHOOK_SECRET.encode(), f"{ts}.".encode() + raw, hashlib.sha256).hexdigest()
    request = urllib.request.Request(
        WEBHOOK_URL,
        data=raw,
        method="POST",
        headers={"Content-Type": "application/json", "Stripe-Signature": f"t={ts},v1={sig}"},
    )
    urllib.request.urlopen(request, timeout=20).read()  # noqa: S310


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: bytes, ctype: str, headers: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        form = parse_qs(self.rfile.read(length).decode())
        path = urlparse(self.path).path
        if path == "/v1/checkout/sessions":
            sid = "cs_test_" + uuid.uuid4().hex[:16]
            SESSIONS[sid] = {
                "amount": int(form["line_items[0][price_data][unit_amount]"][0]),
                "name": form["line_items[0][price_data][product_data][name]"][0],
                "success": form["success_url"][0].replace("{CHECKOUT_SESSION_ID}", sid),
                "cancel": form["cancel_url"][0],
            }
            out = {
                "id": sid,
                "url": f"{PUBLIC_URL}/pay/{sid}",
                "expires_at": int(time.time()) + 1800,
                "payment_intent": "pi_" + sid,
            }
            self._send(200, json.dumps(out).encode(), "application/json")
        elif path.startswith("/pay/") and path.endswith("/confirm"):
            sid = path.split("/")[2]
            session = SESSIONS.get(sid)
            if session is None:
                self._send(404, b"Nieznana sesja", "text/plain; charset=utf-8")
                return
            send_webhook(sid, int(session["amount"]))  # type: ignore[call-overload]
            self._send(303, b"", "text/plain", {"Location": str(session["success"])})
        else:
            self._send(404, b"", "text/plain")

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path.startswith("/pay/"):
            sid = path.split("/")[2]
            session = SESSIONS.get(sid)
            if session is None:
                self._send(404, "Sesja wygasła.".encode(), "text/plain; charset=utf-8")
                return
            amount = f"{int(session['amount']) / 100:,.2f} zł".replace(",", " ").replace(".", ",")  # type: ignore[call-overload]
            page = PAGE.format(
                name=html.escape(str(session["name"])),
                amount=amount,
                sid=sid,
                cancel=html.escape(str(session["cancel"])),
            )
            self._send(200, page.encode(), "text/html; charset=utf-8")
        else:
            self._send(200, b"demo gateway", "text/plain")

    def log_message(self, *args: object) -> None:
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 9911), Handler).serve_forever()  # noqa: S104

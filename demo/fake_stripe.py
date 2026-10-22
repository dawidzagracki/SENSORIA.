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
from urllib.parse import parse_qs, urlencode, urlparse

WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_demo")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "http://api:8000/payments/webhooks/stripe")
PUBLIC_URL = os.environ.get("PUBLIC_URL", "http://localhost:9911")
SESSIONS: dict[str, dict[str, object]] = {}
GOOGLE_CODES: dict[str, dict[str, object]] = {}
GOOGLE_ACCOUNTS = [
    ("Anna Kowalska", "Anna", "Kowalska", "anna.kowalska@sensoria.demo"),
    ("Ewa Nowak", "Ewa", "Nowak", "ewa.nowak@sensoria.demo"),
    ("Jan Pokazowy", "Jan", "Pokazowy", "jan.pokazowy@sensoria.demo"),
]
GOOGLE_PAGE = """<!doctype html><html lang="pl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Zaloguj się przez Google (demo)</title>
<style>body{{font-family:system-ui,sans-serif;background:#f6f8fc;margin:0;display:grid;place-items:center;min-height:100vh}}
main{{background:#fff;border-radius:28px;padding:36px;max-width:420px;width:calc(100% - 32px)}}
h1{{font-size:24px;font-weight:400;margin:8px 0 4px}}p{{color:#444;margin:0 0 16px}}
a{{display:flex;gap:12px;align-items:center;padding:12px;border-radius:16px;color:#1f1f1f;text-decoration:none}}a:hover{{background:#f0f4f9}}
.av{{width:36px;height:36px;border-radius:50%;background:#1a73e8;color:#fff;display:grid;place-items:center;font-weight:600}}
small{{color:#5f6368;display:block}}.demo{{background:#fff3cd;border-radius:8px;padding:8px 12px;font-size:13px;margin-bottom:16px}}</style>
<main><p class="demo">Tryb demonstracyjny — to nie jest prawdziwe logowanie Google.</p>
<h1>Wybierz konto</h1><p>aby kontynuować w Sensoria</p>{items}</main></html>"""
CITIES = [
    ("Olsztyn", "10", 53.7784, 20.4801, ["ul. Kościuszki", "al. Warszawska", "ul. Knosały", "ul. Dworcowa", "ul. Jagiellońska"]),
    ("Warszawa", "00", 52.2297, 21.0122, ["ul. Marszałkowska", "ul. Puławska", "ul. Świętokrzyska", "ul. Wolska", "ul. Targowa"]),
    ("Kraków", "31", 50.0647, 19.9450, ["ul. Długa", "ul. Dietla", "ul. Starowiślna", "al. Pokoju", "ul. Wielicka"]),
    ("Gdańsk", "80", 54.3520, 18.6466, ["ul. Długa", "ul. Grunwaldzka", "ul. Podwale Staromiejskie", "ul. Słowackiego", "ul. Chmielna"]),
    ("Wrocław", "50", 51.1079, 17.0385, ["ul. Świdnicka", "ul. Legnicka", "ul. Piłsudskiego", "ul. Grabiszyńska", "ul. Kazimierza Wielkiego"]),
    ("Poznań", "60", 52.4064, 16.9252, ["ul. Półwiejska", "ul. Głogowska", "ul. Święty Marcin", "ul. Dąbrowskiego", "ul. Garbary"]),
    ("Łódź", "90", 51.7592, 19.4560, ["ul. Piotrkowska", "ul. Kilińskiego", "ul. Pomorska", "al. Mickiewicza", "ul. Zachodnia"]),
    ("Szczecin", "70", 53.4285, 14.5528, ["al. Niepodległości", "ul. Wojska Polskiego", "ul. Krzywoustego", "ul. Bohaterów Warszawy", "ul. Jagiellońska"]),
    ("Lublin", "20", 51.2465, 22.5684, ["ul. Krakowskie Przedmieście", "ul. Lipowa", "al. Racławickie", "ul. Zamojska", "ul. Wileńska"]),
    ("Katowice", "40", 50.2649, 19.0238, ["ul. Mariacka", "ul. 3 Maja", "ul. Chorzowska", "ul. Francuska", "ul. Warszawska"]),
    ("Białystok", "15", 53.1325, 23.1688, ["ul. Lipowa", "ul. Sienkiewicza", "ul. Branickiego", "ul. Warszawska", "ul. Legionowa"]),
    ("Gdynia", "81", 54.5189, 18.5305, ["ul. Świętojańska", "ul. Śląska", "ul. Chylońska", "ul. Morska", "ul. Wielkopolska"]),
]
LOCKERS: list[tuple[str, str, str, str, str, float, float]] = []
for _c, (_city, _pre, _lat, _lon, _streets) in enumerate(CITIES):
    for _i, _street in enumerate(_streets):
        LOCKERS.append((
            f"{_city[:3].upper()}{_i + 1:02d}M",
            _street,
            str(3 + _i * 7),
            f"{_pre}-{100 + _i * 37:03d}",
            _city,
            round(_lat + (_i - 2) * 0.012 + (_i % 2) * 0.004, 5),
            round(_lon + ((_i * 3) % 5 - 2) * 0.014, 5),
        ))
# keep the three codes the e2e/seed already use
LOCKERS = [
    ("OLS01M", "ul. Kościuszki", "12", "10-502", "Olsztyn", 53.7784, 20.4801),
    ("OLS02M", "al. Warszawska", "98", "10-702", "Olsztyn", 53.7541, 20.4583),
    ("OLS03M", "ul. Knosały", "5", "10-015", "Olsztyn", 53.7899, 20.5012),
] + [entry for entry in LOCKERS if not entry[0].startswith("OLS")]


def fold(text: str) -> str:
    table = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")
    return text.translate(table).lower()


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math

    p = math.pi / 180
    a = 0.5 - math.cos((lat2 - lat1) * p) / 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * (1 - math.cos((lon2 - lon1) * p)) / 2
    return 12742 * math.asin(math.sqrt(a))


def locker(entry: tuple[str, str, str, str, str, float, float]) -> dict[str, object]:
    code, street, building, post_code, city, lat, lon = entry
    return {
        "name": code,
        "display_name": f"Paczkomat {code}",
        "status": "Operating",
        "type": ["parcel_locker"],
        "functions": ["parcel_collect", "parcel_send"],
        "opening_hours": "24/7",
        "location": {"latitude": lat, "longitude": lon},
        "address_details": {"street": street, "building_number": building, "post_code": post_code, "city": city},
    }

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
        if path == "/google/token":
            code = (form.get("code") or [""])[0]
            if code in GOOGLE_CODES:
                self._send(200, json.dumps({"access_token": "at_" + code, "token_type": "Bearer"}).encode(), "application/json")
            else:
                self._send(400, b'{"error":"invalid_grant"}', "application/json")
        elif path == "/v1/checkout/sessions":
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
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/v1/points":
            query = parse_qs(parsed.query)
            city = fold((query.get("city") or [""])[0])
            code = (query.get("post_code") or [""])[0].replace("-", "")
            near = (query.get("relative_point") or [""])[0]
            if near:
                lat, lon = (float(part) for part in near.split(","))
                ranked = sorted(LOCKERS, key=lambda entry: distance_km(lat, lon, entry[5], entry[6]))
                entries = [entry for entry in ranked if distance_km(lat, lon, entry[5], entry[6]) <= 15][:20]
            else:
                entries = [
                    entry
                    for entry in LOCKERS
                    if (city and (city in fold(entry[4]) or city in fold(entry[1]) or city == fold(entry[0])))
                    or (code and entry[3].replace("-", "").startswith(code[:2]))
                ][:20]
            hits = [locker(entry) for entry in entries]
            self._send(200, json.dumps({"items": hits}).encode(), "application/json")
        elif path.startswith("/v1/points/"):
            match = [entry for entry in LOCKERS if entry[0] == path.rsplit("/", 1)[1]]
            if match:
                self._send(200, json.dumps(locker(match[0])).encode(), "application/json")
            else:
                self._send(404, b"{}", "application/json")
        elif path == "/google/auth":
            query = parse_qs(parsed.query)
            redirect = (query.get("redirect_uri") or [""])[0]
            state = (query.get("state") or [""])[0]
            items = ""
            for name, given, family, email in GOOGLE_ACCOUNTS:
                href = "/google/pick?" + urlencode({"email": email, "name": name, "given": given, "family": family, "redirect_uri": redirect, "state": state})
                items += f'<a href="{html.escape(href)}"><span class="av">{given[0]}</span><span>{html.escape(name)}<small>{html.escape(email)}</small></span></a>'
            self._send(200, GOOGLE_PAGE.format(items=items).encode(), "text/html; charset=utf-8")
        elif path == "/google/pick":
            query = parse_qs(parsed.query)
            code = "gc_" + uuid.uuid4().hex
            GOOGLE_CODES[code] = {
                "email": query["email"][0], "name": query["name"][0],
                "given_name": query["given"][0], "family_name": query["family"][0],
                "email_verified": True,
            }
            target = query["redirect_uri"][0] + "?" + urlencode({"code": code, "state": query["state"][0]})
            self._send(302, b"", "text/plain", {"Location": target})
        elif path == "/google/userinfo":
            token = (self.headers.get("Authorization") or "").removeprefix("Bearer ").removeprefix("at_")
            profile = GOOGLE_CODES.get(token)
            if profile is None:
                self._send(401, b"{}", "application/json")
            else:
                self._send(200, json.dumps(profile).encode(), "application/json")
        elif path.startswith("/pay/"):
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

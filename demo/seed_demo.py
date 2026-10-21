#!/usr/bin/env python3
"""Fill the presentation stack (./demo/compose.sh) with a complete, working showcase.

Everything goes through the real HTTP API (admin panel + shop + fake payment gateway), so each
screen shows data produced by the same code paths a real shop would use. Safe to re-run on a fresh
database only (`./demo/compose.sh down -v` first).
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "http://localhost:8090"
GATEWAY = "http://localhost:9911"
MAILPIT = "http://localhost:8025"
OWNER = ("wlascicielka@sensoria.demo", "Demo-Sensoria-2026")
STAFF = ("obsluga@sensoria.demo", "Demo-Sensoria-2026")
CUSTOMER = ("anna.kowalska@sensoria.demo", "Demo-Sensoria-2026")
DEMO_EMAIL = "demo@sensoria.demo"


def compose(*args: str, stdin: bytes | None = None, env: dict[str, str] | None = None) -> bytes:
    cmd = [os.path.join(ROOT, "demo", "compose.sh"), *args]
    return subprocess.run(cmd, input=stdin, capture_output=True, check=True, env={**os.environ, **(env or {})}).stdout


def step(label: str, ok: bool, extra: object = "") -> None:
    print(("OK   " if ok else "FAIL ") + label + ("" if ok else f"  {extra}"))
    if not ok:
        step.failed = True  # type: ignore[attr-defined]


step.failed = False  # type: ignore[attr-defined]


class Client:
    def __init__(self) -> None:
        self.cookies: dict[str, str] = {}

    def req(self, method, path, body=None, headers=None, raw=None, ctype=None, base=BASE, follow=True):
        h = dict(headers or {})
        if self.cookies:
            h["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
        data = raw
        if body is not None:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        if ctype:
            h["Content-Type"] = ctype
        request = urllib.request.Request(base + path, data=data, method=method, headers=h)
        try:
            resp = urllib.request.urlopen(request, timeout=60)
        except urllib.error.HTTPError as error:
            resp = error
        for cookie in resp.headers.get_all("Set-Cookie") or []:
            key, _, value = cookie.split(";")[0].partition("=")
            self.cookies[key] = value
        payload = resp.read()
        try:
            return resp.status, json.loads(payload), resp.headers
        except ValueError:
            return resp.status, payload, resp.headers


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):  # type: ignore[no-untyped-def]
        return None


def multipart(fields: dict[str, str], fname: str, content: bytes, ctype: str):
    boundary = "----demo" + uuid.uuid4().hex
    parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields.items()]
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{fname}"\r\nContent-Type: {ctype}\r\n\r\n'.encode()
        + content
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


# ------------------------------------------------------------------ infrastructure
def wait_for_api() -> None:
    for _ in range(60):
        try:
            if urllib.request.urlopen(BASE + "/api/health", timeout=5).status == 200:
                return
        except Exception:
            time.sleep(2)
    sys.exit("API nie odpowiada — uruchom ./demo/compose.sh up -d --build")


def prepare_database() -> None:
    compose("exec", "-T", "api", "alembic", "upgrade", "head")
    compose("exec", "-T", "api", "python", "-m", "sensoria.seed")
    for email, name, role in ((OWNER[0], "Anna Parakiewicz", "owner"), (STAFF[0], "Marta Nowak", "staff")):
        compose("exec", "-T", "-e", f"ADMIN_PASSWORD={OWNER[1]}", "api", "python", "-m",
                "sensoria.modules.admin.cli", "--email", email, "--name", name, "--role", role)
    script = f"""
import asyncio
from datetime import UTC, datetime
from sqlalchemy import select
from sensoria.database import SessionFactory
from sensoria.modules.accounts.models import Customer
from sensoria.modules.accounts.router import hasher

async def main():
    async with SessionFactory() as s, s.begin():
        if await s.scalar(select(Customer).where(Customer.email == '{CUSTOMER[0]}')) is None:
            s.add(Customer(email='{CUSTOMER[0]}', password_hash=hasher.hash('{CUSTOMER[1]}'),
                           first_name='Anna', last_name='Kowalska', phone='600100200',
                           email_verified_at=datetime.now(UTC)))
asyncio.run(main())
"""
    compose("exec", "-T", "api", "python", "-", stdin=script.encode())
    step("baza, konta administratorów i klientki", True)


def make_audio(tmp: str) -> list[tuple[str, str, float]]:
    texts = [
        ("Wstęp", "Witaj. To jest demonstracyjny fragment audiobooka o zmysłach i codzienności dziecka. Posłuchaj uważnie, jak brzmi cisza między słowami."),
        ("Dotyk", "Dotyk jest pierwszym językiem, jakim rozmawiamy z dzieckiem. Ciepłe dłonie, spokojny oddech i jednostajne kołysanie potrafią zdziałać więcej niż tysiąc słów."),
        ("Dźwięk", "Hałas dla jednych jest tłem, dla innych burzą. Naucz się rozpoznawać, kiedy dziecku jest za głośno, i stwórz mu bezpieczny kącik ciszy."),
    ]
    out = []
    for index, (title, text) in enumerate(texts):
        aiff, mp3 = os.path.join(tmp, f"c{index}.aiff"), os.path.join(tmp, f"c{index}.mp3")
        subprocess.run(["say", "-v", "Zosia", "-o", aiff, text], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", aiff, "-codec:a", "libmp3lame", "-b:a", "64k", mp3], check=True)
        seconds = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp3]))
        out.append((title, mp3, seconds))
    return out


def main() -> None:
    wait_for_api()
    prepare_database()
    assets = json.loads(compose("exec", "-T", "api", "python", "-", stdin=open(os.path.join(ROOT, "demo", "make_assets.py"), "rb").read()))
    covers = {k: base64.b64decode(v) for k, v in assets["covers"].items()}
    pdfs = {k: base64.b64decode(v) for k, v in assets["pdfs"].items()}
    tmp = tempfile.mkdtemp()
    chapters_audio = make_audio(tmp)

    admin = Client()
    s, b, _ = admin.req("POST", "/api/admin/auth/login", {"email": OWNER[0], "password": OWNER[1]})
    step("logowanie do panelu", s == 200, b)
    csrf = b["csrf_token"]

    def A(method, path, body=None, **kw):
        return admin.req(method, "/api/admin" + path, body, headers={"Origin": BASE, "X-CSRF-Token": csrf}, **kw)

    # settings
    for key, value in {
        "company.seller.v1": {"name": "Sensoria Terapia — Anna Parakiewicz", "street": "ul. Knosały 7B/A", "postal_code": "10-015", "city": "Olsztyn", "nip": "5260250995"},
        "orders.delivery.v1": {"parcel_locker_cost_grosz": 1200, "courier_cost_grosz": 1800, "free_shipping_threshold_grosz": 15000, "incentive_threshold_grosz": 5000, "vat_rate": "RATE_23"},
        "ops.alerts.v1": {"email": "wlascicielka@sensoria.demo"},
    }.items():
        s, b, _ = A("PUT", f"/settings/{key}", {"value": value})
        step(f"ustawienie {key}", s == 200, b)

    # withdraw the placeholder products from the generic seed
    s, listing, _ = A("GET", "/products?limit=50")
    for item in (listing.get("items") if isinstance(listing, dict) else []) or []:
        if item.get("price") in (0, None) or "demonstrac" in (item.get("short_description") or "").lower():
            A("POST", f"/products/{item['id']}/withdraw")

    def upload_cover(key: str) -> dict:
        body, ctype = multipart({}, f"{key}.png", covers[key], "image/png")
        s, b, _ = A("POST", "/products/images", raw=body, ctype=ctype)
        step(f"okładka {key}", s == 201, b)
        return {"url": b["url"], "alt": "Okładka"}

    def create(payload: dict, cover: str) -> str:
        image = upload_cover(cover)
        payload["images"] = [{"url": image["url"], "alt": payload["name"]}]
        s, b, _ = A("POST", "/products", payload)
        step(f"produkt {payload['name']}", s == 201, b)
        return b["id"]

    def publish(pid: str, name: str) -> None:
        s, b, _ = A("POST", f"/products/{pid}/publish")
        step(f"publikacja {name}", s == 200, b)

    def upload_file(pid: str, label: str, fname: str, content: bytes, ctype: str, chapter: int | None = None) -> None:
        fields = {"label": label}
        if chapter is not None:
            fields["chapter_position"] = str(chapter)
        body, ct = multipart(fields, fname, content, ctype)
        s, b, _ = A("POST", f"/products/{pid}/files", raw=body, ctype=ct)
        step(f"plik {label}", s == 201, b)

    desc = "Materiał demonstracyjny przygotowany na prezentację sklepu Sensoria."
    v1 = create({"kind": "VOUCHER", "name": "Konsultacja psychologiczna", "price": 22000, "vat_rate": "RATE_23",
                 "short_description": "Voucher na 50-minutową konsultację — stacjonarnie lub online.", "description": desc,
                 "voucher": {"validity_months": 12, "service_name": "Konsultacja psychologiczna",
                             "variants": [{"kind": "IN_PERSON", "price": 25000}, {"kind": "ONLINE", "price": 22000}]}}, "v1")
    publish(v1, "voucher 1")
    v2 = create({"kind": "VOUCHER", "name": "Diagnoza integracji sensorycznej", "price": 35000, "vat_rate": "RATE_23",
                 "short_description": "Voucher na pełną diagnozę SI w gabinecie.", "description": desc,
                 "voucher": {"validity_months": 6, "service_name": "Diagnoza integracji sensorycznej",
                             "variants": [{"kind": "IN_PERSON", "price": 35000}]}}, "v2")
    publish(v2, "voucher 2")
    book = create({"kind": "BOOK", "name": "Integracja sensoryczna w codzienności", "price": 6900, "compare_at_price": 7900,
                   "vat_rate": "RATE_5", "short_description": "Praktyczny poradnik dla rodziców i opiekunów.", "description": desc,
                   "book": {"stock_quantity": 40, "low_stock_threshold": 5, "weight_grams": 380, "length_mm": 210, "width_mm": 140,
                            "height_mm": 18, "isbn": "978-83-000-0000-0", "binding": "miękka", "shipping_business_days": 2,
                            "shipping_method": "InPost Paczkomat / kurier"}}, "book")
    publish(book, "książka")
    total = round(sum(sec for _, _, sec in chapters_audio))
    lengths = [round(sec) for _, _, sec in chapters_audio]
    lengths[-1] += total - sum(lengths)
    audio = create({"kind": "AUDIOBOOK", "name": "Kiedy zmysły mówią głośniej", "price": 3900, "vat_rate": "RATE_23",
                    "short_description": "Audiobook czytany przez Zosię — słuchaj w przeglądarce.", "description": desc,
                    "audiobook": {"duration_seconds": total, "narrator": "Zosia", "file_format": "MP3",
                                  "chapters": [{"title": t, "length_seconds": l, "position": i} for i, ((t, _, _), l) in enumerate(zip(chapters_audio, lengths))]}}, "audio")
    for index, (title, path, _) in enumerate(chapters_audio):
        upload_file(audio, f"Rozdział {index + 1}: {title}", f"rozdzial-{index + 1}.mp3", open(path, "rb").read(), "audio/mpeg", index)
    publish(audio, "audiobook")
    chapter_blocks = [
        {"title": "Zmysły i codzienność", "page_count": 4, "blocks": [
            {"type": "h2", "text": "Zmysły w codziennym życiu"},
            {"type": "p", "text": "Każdy z nas odbiera świat inaczej. To rozdział demonstracyjny czytnika wewnątrz sklepu."},
            {"type": "list", "items": ["dotyk i bliskość", "dźwięk i cisza", "ruch i równowaga"]},
            {"type": "quote", "text": "Dziecko uczy się całym ciałem."}]},
        {"title": "Rytuały dnia", "page_count": 4, "blocks": [
            {"type": "h2", "text": "Małe rytuały"},
            {"type": "p", "text": "Krótkie, powtarzalne rytuały pomagają dziecku wrócić do równowagi."}]},
    ]
    ebook = create({"kind": "DIGITAL", "name": "Zmysły w domu", "price": 4900, "compare_at_price": 5900, "vat_rate": "RATE_5",
                    "short_description": "E-book PDF — krótki przewodnik po zmysłach dziecka.", "description": desc,
                    "digital": {"label": "EBOOK_PDF", "file_format": "PDF", "page_count": 6, "edition": "I"}}, "ebook")
    upload_file(ebook, "Zmysły w domu (PDF)", "zmysly-w-domu.pdf", pdfs["ebook"], "application/pdf")
    s, b, _ = A("PUT", f"/products/{ebook}/chapters", {"chapters": chapter_blocks}); step("rozdziały czytnika e-booka", s == 200, b)
    publish(ebook, "e-book")
    course = create({"kind": "DIGITAL", "name": "Regulacja emocji u dziecka — kurs PDF", "price": 9900, "vat_rate": "RATE_23",
                     "short_description": "Kurs PDF w 5 lekcjach z ćwiczeniami dla rodziców.", "description": desc,
                     "digital": {"label": "COURSE_PDF", "file_format": "PDF", "page_count": 5, "edition": "I"}}, "course")
    upload_file(course, "Kurs PDF", "kurs.pdf", pdfs["course"], "application/pdf")
    s, b, _ = A("PUT", f"/products/{course}/chapters", {"chapters": chapter_blocks}); step("rozdziały czytnika kursu", s == 200, b)
    publish(course, "kurs")

    # categories / audience tags straight in SQL (no admin endpoint for them)
    sql = f"""
    INSERT INTO product_categories (product_id, category_id)
      SELECT p.id, c.id FROM products p CROSS JOIN categories c
      WHERE (p.id IN ('{v1}','{v2}') AND c.slug = (SELECT slug FROM categories ORDER BY name LIMIT 1))
         OR (p.id IN ('{book}','{audio}','{ebook}','{course}'))
      ON CONFLICT DO NOTHING;
    INSERT INTO product_audience_tags (product_id, audience_tag_id)
      SELECT p.id, t.id FROM products p CROSS JOIN audience_tags t WHERE p.id IN ('{v1}','{v2}','{book}','{audio}','{ebook}','{course}')
      ON CONFLICT DO NOTHING;"""
    compose("exec", "-T", "db", "psql", "-U", "sensoria", "-d", "sensoria", "-c", sql)
    step("kategorie i odbiorcy", True)

    # free samples (separate prepared files)
    for slug, key, kind, extra in (("zmysly-w-domu", "ebook_sample", "pdf", ["--pages", "2"]), ("regulacja-emocji-u-dziecka-kurs-pdf", "course_sample", "pdf", ["--pages", "1"])):
        path = os.path.join(tmp, key + ".pdf")
        open(path, "wb").write(pdfs[key])
        compose("cp", path, f"api:/tmp/{key}.pdf")
        try:
            compose("exec", "-T", "api", "python", "-m", "sensoria.modules.catalog.sample_cli", "--slug", slug, "--file", f"/tmp/{key}.pdf", "--kind", kind, *extra)
            step(f"fragment {slug}", True)
        except subprocess.CalledProcessError as error:
            step(f"fragment {slug}", False, error.stderr)

    # discount codes
    for code, kind, value in (("WITAJ10", "percentage", 10), ("ZMYSLY20", "fixed_amount", 2000)):
        s, b, _ = A("POST", "/discount-codes", {"code": code, "type": kind, "value": value, "min_order_value": 5000})
        step(f"kod rabatowy {code}", s == 201, b)

    # legal + info pages and FAQ
    compose("exec", "-T", "api", "python", "-m", "sensoria.modules.content.legal_pages", "--publish")
    fix = """
import asyncio
from sqlalchemy import text
from sensoria.database import SessionFactory
async def main():
    async with SessionFactory() as s, s.begin():
        await s.execute(text(\"\"\"UPDATE content_pages SET blocks = replace(replace(replace(blocks::text,
          'NIP: [UZUPEŁNIJ]', 'NIP: 526-025-09-95'), 'adres e-mail: [UZUPEŁNIJ]', 'adres e-mail: kontakt@sensoria.demo'),
          '[UZUPEŁNIJ: krótki życiorys, wykształcenie, doświadczenie i zdjęcie — treść zatwierdza autorka]',
          'Anna Parakiewicz — terapeutka i autorka materiałów o integracji sensorycznej. Prezentacyjny opis autorki.')::jsonb\"\"\"))
asyncio.run(main())
"""
    compose("exec", "-T", "api", "python", "-", stdin=fix.encode())
    for slug in ("regulamin", "polityka-prywatnosci", "polityka-cookies", "dostawa-i-platnosci", "o-autorce"):
        s, b, _ = A("POST", f"/pages/{slug}/publish")
        step(f"strona {slug}", s == 200, b)
    for category, q, a in (
        ("Zamówienia", "Jak złożyć zamówienie?", "Dodaj produkty do koszyka, uzupełnij dane i zapłać BLIK-iem lub kartą. Konto nie jest potrzebne."),
        ("Zamówienia", "Czy dostanę fakturę?", "Paragon wystawiamy automatycznie. Fakturę VAT wystawimy po podaniu NIP w zamówieniu."),
        ("Pliki cyfrowe", "Kiedy dostanę e-booka lub audiobooka?", "Od razu po opłaceniu — w bibliotece konta i w wiadomości e-mail."),
        ("Pliki cyfrowe", "Czy mogę zwrócić produkt cyfrowy?", "Po rozpoczęciu pobierania prawo odstąpienia wygasa za Twoją zgodą wyrażoną w zamówieniu."),
        ("Vouchery", "Jak zrealizować voucher?", "Podaj kod z vouchera w gabinecie lub podczas rezerwacji wizyty online."),
        ("Dostawa", "Ile kosztuje dostawa książki?", "Paczkomat 12 zł, kurier 18 zł, odbiór w gabinecie bezpłatnie; od 150 zł dostawa gratis."),
    ):
        s, b, _ = A("POST", "/faq", {"category": category, "question": q, "answer": a, "published": True})
        step(f"FAQ: {q}", s == 201, b)

    # ---------------------------------------------------------------- purchases through the shop
    def buy(email, items, *, name=("Jan", "Nowak"), method="blik", delivery=None, code=None, pay=True, review_consent=True):
        shop = Client()
        for pid, variant in items:
            body = {"product_id": pid, "quantity": 1}
            if variant:
                body["variant_id"] = variant
            s, b, _ = shop.req("POST", "/api/cart/items", body)
            step(f"koszyk +{pid[:8]}", s == 200, b)
        if code:
            s, b, _ = shop.req("POST", "/api/cart/discount", {"code": code}); step(f"rabat {code}", s == 200, b)
        if delivery:
            s, b, _ = shop.req("PATCH", "/api/cart/delivery", {"method": delivery}); step(f"dostawa {delivery}", s == 200, b)
        cfg = shop.req("GET", "/api/cart/checkout-config")[1]
        payload = {"email": email, "first_name": name[0], "last_name": name[1], "phone": "600100200", "invoice_kind": "private",
                   "payment_method": method, "terms_accepted": True, "digital_consent": True,
                   "review_requests_consent": review_consent, "consent_version": cfg["consent_version"]}
        if delivery:
            payload["delivery_method"] = delivery
            if delivery != "pickup_in_person":
                payload["shipping_address"] = {"street": "ul. Lipowa 5/3", "postal_code": "10-123", "city": "Olsztyn"}
        s, b, _ = shop.req("POST", "/api/cart/checkout", payload, headers={"Idempotency-Key": uuid.uuid4().hex})
        step(f"zamówienie {email}", s == 201, b)
        order_id, token = b["order_id"], b["access_token"]
        s, b, _ = shop.req("POST", f"/api/payments/orders/{order_id}/session?token={token}")
        step("sesja płatności", s == 200, b)
        if pay:
            sid = b["payment_url"].rsplit("/", 1)[1]
            opener = urllib.request.build_opener(NoRedirect)
            try:
                opener.open(urllib.request.Request(f"{GATEWAY}/pay/{sid}/confirm", data=b"method=blik", method="POST"), timeout=30)
            except urllib.error.HTTPError as error:
                step("płatność w bramce demo", error.code == 303, error.code)
        return order_id, token, shop

    s, v1d, _ = Client().req("GET", "/api/products/konsultacja-psychologiczna")
    variant = v1d["voucher"]["variants"][0]["id"]
    ids = {"book": book, "audio": audio, "ebook": ebook, "course": course}
    o1, t1, _ = buy(CUSTOMER[0], [(ebook, None), (course, None), (v1, variant)], name=("Anna", "Kowalska"), code="WITAJ10")
    buy(CUSTOMER[0], [(audio, None), (book, None)], name=("Anna", "Kowalska"), delivery="courier")
    o2, t2, shop2 = buy("karolina.wisniewska@sensoria.demo", [(book, None), (audio, None)], name=("Karolina", "Wiśniewska"), delivery="courier")
    o3, t3, _ = buy("piotr.zielinski@sensoria.demo", [(book, None)], name=("Piotr", "Zieliński"), delivery="pickup_in_person", method="card")
    buy(DEMO_EMAIL, [(audio, None)], name=("Demo", "Klient"), pay=False)  # stays pending_payment
    time.sleep(25)  # PDF + mail workers

    # reviews (consent was given at checkout) and moderation
    for order_id, token, product, rating, text in ((o1, t1, "Zmysły w domu", 5, "Bardzo przystępny przewodnik, praktyczne wskazówki."), (o2, t2, "Kiedy zmysły mówią głośniej", 5, "Piękny głos lektorki, słucham z dzieckiem do snu.")):
        s, el, _ = Client().req("GET", f"/api/reviews/eligible?order_id={order_id}&order_token={token}")
        item = next((i["order_item_id"] for i in el.get("items", []) if i["name"] == product), None) if isinstance(el, dict) else None
        if item:
            s, b, _ = Client().req("POST", f"/api/reviews?order_token={token}", {"order_id": order_id, "order_item_id": item, "rating": rating, "body": text})
            step(f"opinia: {product}", s == 201, b)
    s, q, _ = A("GET", "/reviews")
    for review in (q.get("items") if isinstance(q, dict) else []) or []:
        A("POST", f"/reviews/{review['id']}/decision", {"approve": True})
    # support case + voucher redemption
    s, b, _ = Client().req("POST", f"/api/support/cases?order_token={t2}", {"order_id": o2, "kind": "complaint", "message": "Okładka książki ma zagięty róg."}); step("zgłoszenie reklamacyjne", s == 201, b)
    s, vch, _ = Client().req("GET", f"/api/vouchers/orders/{o1}?order_token={t1}")
    if isinstance(vch, dict) and vch.get("items"):
        step("voucher wystawiony", True)
    print("\nGOTOWE" if not step.failed else "\nZAKOŃCZONO Z BŁĘDAMI — sprawdź linie FAIL")  # type: ignore[attr-defined]
    print(f"Sklep: {BASE}\nPanel: {BASE}/admin/logowanie  ({OWNER[0]} / {OWNER[1]})\nKonto klientki: {CUSTOMER[0]} / {CUSTOMER[1]}\nPoczta (Mailpit): {MAILPIT}")


if __name__ == "__main__":
    main()

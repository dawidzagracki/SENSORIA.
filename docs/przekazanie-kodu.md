# Przekazanie kodu i szkolenie — etap [90]

Dokument dla osoby, która przejmuje utrzymanie. Zakłada podstawową znajomość Pythona, TypeScriptu i Dockera.

## 1. Co to jest

Sklep SENSORIA: vouchery na wizyty, książki papierowe (InPost / odbiór w gabinecie), e-booki, kursy PDF i audiobooki,
z kontem klientki, biblioteką (czytnik i odtwarzacz), płatnościami Stripe, dokumentami sprzedaży, kolejką e-maili i panelem
administracyjnym.

| Warstwa | Technologia |
|---|---|
| API | Python 3.12, FastAPI, SQLAlchemy 2 (async), asyncpg, Alembic |
| Frontend | Next.js 15 (App Router), TypeScript, Tailwind (tokeny w `tailwind.config.ts`) |
| Baza | PostgreSQL 16 (wyszukiwarka FTS z polskim słownikiem) |
| Infrastruktura | Docker Compose: db, api, web, caddy (TLS) |

## 2. Mapa katalogów

```
apps/api/src/sensoria/modules/
  catalog/    produkty, kategorie, SEO, wyszukiwanie, próbki, ceny i historia cen, magazyn, obrazy
  orders/     koszyk, kalkulator VAT, dostawa, checkout, wysyłki, odbiory
  payments/   Stripe (sesja płatności, webhooki, token dostępu do zamówienia)
  library/    uprawnienia do treści cyfrowych, pobrania, znakowanie PDF, czytnik, odtwarzacz
  documents/  paragony i faktury (numeracja bez luk, PDF)
  vouchers/   wystawianie, PDF z QR, weryfikacja publiczna, przypomnienia, prezenty
  mail/       outbox, szablony, SMTP, worker z ponowieniami, mosty z innych modułów
  accounts/   konta klientek, logowanie, profil, zgody RODO
  admin/      konta i sesje administratorów, wszystkie trasy panelu
  reviews/ support/ content/ ops/   opinie, zgłoszenia, strony/FAQ/cookies, alerty
apps/web/app/(shop)/      strony sklepu       apps/web/app/(isolated)/   panel, czytnik, odtwarzacz
apps/web/components/admin panel              docs/   dokumentacja, makiety (nie edytować), audyt
scripts/                  kopie zapasowe, odtwarzanie, wdrożenie, monitoring
```

## 3. Uruchomienie lokalne

```bash
cp .env.example .env     # ustaw POSTGRES_PASSWORD, DATABASE_URL, SECRET_KEY, SITE_URL, NEXT_PUBLIC_API_URL
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose exec api python -m sensoria.seed
ADMIN_PASSWORD='min-12-znakow' docker compose exec -e ADMIN_PASSWORD api \
  python -m sensoria.modules.admin.cli --email ja@example.com --name Ja --role owner
```

Sklep: http://localhost, panel: http://localhost/admin/logowanie. Bez kluczy Stripe i SMTP aplikacja działa, ale
płatności są wyłączone, a e-maile czekają w outboxie (patrz „Testowanie z atrapami” niżej).

## 4. Testy i kontrola jakości

```bash
# API (potrzebna osobna baza *_test — nigdy produkcyjna)
cd apps/api
uv run --frozen --all-groups ruff check src/sensoria tests && uv run --frozen --all-groups ruff format --check src/sensoria tests
uv run --frozen --all-groups mypy --strict src/sensoria tests
uv run --frozen --all-groups pytest

# Frontend
npm --prefix apps/web run lint && npm --prefix apps/web run format:check && npm --prefix apps/web run typecheck
npm --prefix apps/web test
npm --prefix apps/web run build
```

Testy API używają prawdziwego PostgreSQL w transakcji wycofywanej po teście. Płatności testujemy podpisanymi zdarzeniami
(`stripe_client.sign_payload`), pocztę — atrapą transportu. **Zasada projektu:** każda reguła pieniężna, prawna lub
bezpieczeństwa ma test, który ją łamie.

### Testowanie z atrapami (cały stos)

Atrapa Stripe (mały serwer HTTP zwracający `{"id","url","expires_at"}` pod `STRIPE_API_BASE`) + Mailpit
(`axllent/mailpit`, SMTP 1025, UI 8025) pozwalają przejść pełny zakup bez zewnętrznych kont. Webhook wysyłasz sam,
podpisując ciało HMAC-SHA256 sekretem `STRIPE_WEBHOOK_SECRET`.

## 5. Zasady, których nie wolno łamać

1. **Pieniądze to całkowite grosze** (`int`, typ `Money`). Nigdy `float`.
2. **Cena i VAT pochodzą z serwera**, nigdy od klienta. Snapshoty w zamówieniu są niezmienne.
3. **Migracje:** nigdy nie edytuj wydanych rewizji; nowa zmiana = nowa rewizja; na produkcji bez `downgrade`.
4. **Webhook Stripe** jest jedynym miejscem, które oznacza zamówienie jako opłacone — w jednej transakcji z magazynem,
   rabatem, voucherami, uprawnieniami, dokumentem i mailami (`payments/service.py::_confirm_paid`).
5. **Dostęp do plików** tylko przez uprawnienie (`entitlements`) i krótkotrwały link; pliki leżą poza katalogiem publicznym.
6. **Treści redakcyjne to dane** (bloki JSON), nie HTML — nie dodawaj `dangerouslySetInnerHTML` dla treści użytkowników.
7. **Nie loguj sekretów** (hasła, tokeny, nagłówki Authorization, parametry SQL).
8. Zmiany stylu przez **tokeny** w `tailwind.config.ts`, nie wartości wpisane w komponentach.

## 6. Typowe zadania

| Zadanie | Gdzie |
|---|---|
| Nowy szablon maila | `modules/mail/templates.py` (funkcja + wpis w `TEMPLATES`), test w `tests/test_mail.py` |
| Nowa ścieżka panelu | `modules/admin/routes_*.py`, rejestracja w `admin/router.py`, UI w `components/admin/` |
| Nowe ustawienie biznesowe | model walidacji + wpis w `REGISTRY` w `admin/routes_settings.py` |
| Nowa migracja | `uv run alembic revision -m "…"` (ręcznie, z `op.f()` dla nazw), dopisz do `tests/test_migrations.py` |
| Rotacja kluczy Stripe/SMTP | zmiana w `.env` + `docker compose up -d api` |

## 7. Znane ograniczenia i rzeczy do decyzji

* Teksty prawne (regulamin, polityka prywatności, cookies) wpisujesz w panelu — **wymagają weryfikacji prawnika**.
* Baner cookies zapisuje wybory, ale w sklepie nie działają jeszcze narzędzia analityczne ani marketingowe, które by z nich
  korzystały — dodając takie narzędzie, uruchamiaj je dopiero po zgodzie (`sensoria_cookie_consent`).
* Cache listy katalogu jest procesowy (patrz `AGENTS.md`); przy wielu workerach inwalidacja nie jest globalna.
* Znakowanie PDF dodaje widoczną stopkę z adresem e-mail i numerem zamówienia oraz metadane; nie jest to DRM.
* Kopie zapasowe wymagają skonfigurowania `rclone` do Dysku Google przez właściciela konta.

## 8. Plan szkolenia (2 × 2 godziny)

**Sesja 1 — sklep i panel:** przejście zakupu od koszyka po bibliotekę (Mailpit + atrapa Stripe), potem panel wg
`docs/instrukcja-panelu.md`: zamówienie, wysyłka, voucher, opinia, zgłoszenie, raport.

**Sesja 2 — utrzymanie:** `docs/wdrozenie-vps.md` i `docs/operacje.md`: wdrożenie, kopia i **odtworzenie próbne**,
alerty, aktualizacja, wycofanie, awaria webhooka, rotacja kluczy.

**Ćwiczenia kontrolne:** (1) odtwórz kopię do bazy kontrolnej, (2) wyślij ponownie zdarzenie webhooka i pokaż, że nie
dubluje voucherów, (3) dodaj produkt z plikiem PDF i sprawdź znakowanie, (4) wyłącz SMTP i pokaż, że maile czekają i
dochodzą po przywróceniu.

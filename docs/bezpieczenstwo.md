# Bezpieczeństwo — etap [85]

Dokument opisuje zabezpieczenia **faktycznie zaimplementowane w kodzie** i sposób ich sprawdzenia. Nie zastępuje
testu penetracyjnego przed uruchomieniem sprzedaży.

## HTTPS i nagłówki

| Zabezpieczenie | Gdzie | Jak sprawdzić |
|---|---|---|
| Certyfikat TLS (Let's Encrypt) i HSTS | `docker/Caddyfile` | `curl -sI https://domena/` → `Strict-Transport-Security` |
| CSP z nonce per żądanie (`script-src 'self' 'nonce-…' 'strict-dynamic'`), `frame-ancestors 'none'`, `object-src 'none'` | `apps/web/middleware.ts` | nagłówek `Content-Security-Policy` na każdej stronie; test Playwright przeciw buildowi produkcyjnemu |
| `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, COOP | `apps/web/next.config.ts`, `apps/api/src/sensoria/shared/security_headers.py` (API: dodatkowo CSP `default-src 'none'`) | `tests/test_help_and_ops.py::test_security_headers…` |
| Pliki prywatne nigdy nie są serwowane statycznie (`/uploads/*` → 404) | Caddy; brak montowania wolumenu | audyt etapu [04] oraz `curl` |

Styl `style-src 'unsafe-inline'` jest wymagany przez atrybuty `style` ustawiane przez React (paski postępu, skala tekstu);
style nie wykonują kodu. Skrypty **nie** używają `unsafe-inline`.

## Uwierzytelnianie i sesje

* **Klientki:** Argon2id, sesje po stronie serwera (cookie `HttpOnly`, `SameSite=Lax`), CSRF double-submit + Origin,
  blokady prób logowania (osobno e-mail i IP), logowanie linkiem jednorazowym z limitami, brak ujawniania, czy konto istnieje.
* **Panel:** osobna tabela kont i sesji, Argon2id (t=3, m=64 MiB), **blokada 15 min po 5 błędach**, jednolity czas i komunikat
  błędu (także dla nieznanego e-maila), cookie `SameSite=Strict` ograniczone do `/api/admin`, token CSRF rotowany przy
  każdym wczytaniu panelu + sprawdzanie `Origin`, sesja: 2 h bezczynności / 12 h bezwzględnie, unieważnianie po wylogowaniu.
  Hasła ≥ 12 znaków. Role (`owner`, `staff`) egzekwowane po stronie serwera.
* **Dostęp gościa do zamówienia:** token HMAC (z `SECRET_KEY`) w linku z e-maila; nieznane i cudze identyfikatory dają ten sam 404.

## Ograniczenia liczby żądań

| Zasób | Limit |
|---|---|
| logowanie klientki | blokady e-mail/IP (istniejące, etap [54]) |
| logowanie do panelu | 5 błędów → blokada 15 min |
| link logowania | limity e-mail/IP/okno (etap [55]) |
| sprawdzanie vouchera po kodzie | 20/min/IP |
| fragmenty (próbki) | limity współdzielone w PostgreSQL (etap [21]) |
| zapis zgód cookies | 30/min/IP |
| sesja płatności | 30/min/IP |
| dodanie opinii | 10/godz./IP; zgłoszenie reklamacji: 10/godz./IP |

Liczniki są w PostgreSQL (`rate_limit_windows`), więc działają przy wielu procesach API. Adres IP jest haszowany kluczem HMAC.

## Typowe podatności

| Ryzyko | Środek |
|---|---|
| SQL injection | wyłącznie zapytania parametryzowane (SQLAlchemy); wyszukiwanie przez `plainto_tsquery`; znaki `%`/`_` w wyszukiwarce FAQ są escapowane |
| XSS | treści redakcyjne, opinie i strony to **dane** (bloki JSON/tekst), renderowane jako tekst; brak `dangerouslySetInnerHTML` dla treści użytkowników (tylko JSON-LD z escapowaniem `<`, `>`, `&`); szablony maili escapują każdą zmienną |
| CSRF | patrz wyżej; mutujące trasy panelu wymagają `Origin` + tokena |
| IDOR | każdy dostęp do zamówień, bibliotek, dokumentów i voucherów weryfikuje token zamówienia lub właściciela konta; testy „cudzy token → 404” |
| Przesyłanie plików | typ wykrywany po bajtach (PDF/MP3/PNG/JPEG/WebP), limity rozmiaru, losowe nazwy plików, zapis atomowy bez nadpisywania, blokada symlinków i `..`, walidacja czytelności PDF, zdjęcia serwowane z `nosniff` i CSP `default-src 'none'` |
| Fałszowanie płatności | webhook Stripe: podpis HMAC + tolerancja czasu, kwota i waluta porównywane z zamówieniem, idempotencja po `event.id`; klient nigdy nie przekazuje kwoty |
| Wyścigi | blokady wierszy (`FOR UPDATE`) przy płatności, magazynie, voucherach, numeracji dokumentów, limitach kodów rabatowych |
| Wyciek sekretów | sekrety wyłącznie w `.env`; logi bez haseł/tokenów/parametrów SQL; linki w mailach logowania są usuwane z outboxa po wysyłce |
| Kolejność CSV | eksport neutralizuje komórki zaczynające się od `=`, `+`, `-`, `@` |
| Nadużycie pobrań | linki z limitem 5 użyć / 24 h, odnawialne; PDF znakowany danymi nabywcy |

## Zależności

Sprawdzaj regularnie (np. co miesiąc i przed wdrożeniem):

```bash
cd apps/web && npm audit --omit=dev
cd apps/api && uv run --frozen --all-groups pip-audit   # jeśli zainstalowany; alternatywnie: uv pip list --outdated
```

Wyniki ostatniego sprawdzenia: patrz `docs/audit/raport-koncowy.md`.

## Znane ograniczenia

* Brak uwierzytelniania dwuskładnikowego dla panelu (rozważ po uruchomieniu; konta panelu to niewielka liczba osób).
* Znakowanie PDF jest odstraszające i identyfikujące, nie jest DRM.
* Cache listy katalogu jest procesowy (patrz `AGENTS.md`).
* Test penetracyjny i przegląd prawny nie były wykonywane w ramach prac programistycznych.

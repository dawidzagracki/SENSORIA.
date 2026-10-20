# Raport końcowy — weryfikacja etapów [01]–[90]

Data: 2026-10-20. Repozytorium: gałąź `main`, commity po `c619bde` (stan wyjściowy). Szczegóły stanu przed pracami:
[../raport-stanu-poczatkowego.md](../raport-stanu-poczatkowego.md).

## Wyniki kontroli (uruchomione, nie deklarowane)

| Kontrola | Wynik |
|---|---|
| API: `ruff check`, `ruff format --check`, `mypy --strict` | czyste (185 plików) |
| API: `pytest` na PostgreSQL 16 (świeża baza i **ponowne uruchomienie bez czyszczenia**) | 304 przeszły |
| `alembic check` (modele = migracje) | czysto; pilnuje tego test |
| Web: `tsc --noEmit`, `eslint`, `prettier --check` | czyste |
| Web: `vitest` | 113 przeszły (31 plików) |
| Web: `next build` (produkcyjny, Linux) | przechodzi |
| Playwright — istniejący zestaw na atrapie API (`npm run a11y`) | 41 / 41 |
| Playwright — **pełny stos** (Caddy → build produkcyjny z CSP → API → PostgreSQL), axe WCAG 2.1 AA, brak przewijania poziomego 360/768/1280 | 21 / 21, 0 naruszeń critical/serious |
| Skrypt E2E na stosie: sklep → płatność (atrapa Stripe z podpisanym webhookiem) → biblioteka → PDF z podpisem → voucher z QR → paragon → e-maile przez SMTP (Mailpit) → panel → opinie → zgłoszenia | wszystkie kroki przeszły |
| Kopia zapasowa → odtworzenie próbne → odtworzenie nadpisujące (`--apply`) | przetestowane na stosie, dane i pliki wróciły, `health/deep` = ok |
| `pip-audit` (zależności produkcyjne API) | brak znanych podatności (po podniesieniu `cryptography` do 50.x) |
| `npm audit --omit=dev` | 1 wysoka + 1 umiarkowana: **postcss wbudowany w Next 15** (używany przy budowaniu CSS, nie przy obsłudze żądań); poprawka wymaga Next 16 (zmiana głównej wersji — wymaga Twojej decyzji) |

## Czego NIE da się potwierdzić bez Twoich danych

| Etap | Co zweryfikowano | Co zostaje po Twojej stronie |
|---|---|---|
| [32]–[34] płatności | pełna ścieżka z atrapą Stripe i podpisanymi zdarzeniami | klucze Stripe, rejestracja webhooka, test płatności kartą testową |
| [61] poczta i DNS | wysyłka SMTP do Mailpit, retry, szablony | dostawca poczty, SPF/DKIM/DMARC dla domeny |
| [86] kopie na Dysk Google | szyfrowanie, odtworzenie, retencja, skrypt | `rclone config` z kontem Google i pierwsza kopia zdalna |
| [89] wdrożenie na VPS | produkcyjne obrazy, Caddy, procedura, skrypt wdrożenia | serwer, domena, DNS, wykonanie kroków z `docs/wdrozenie-vps.md` |
| [80] teksty prawne | edytor, publikacja, strony | treść regulaminu i polityk (weryfikacja prawna) |
| [84] audyt dostępności | automaty + lista kontrolna | ręczne przejście listy (czytnik ekranu, kontrast gradientów) |
| [90] szkolenie | instrukcje i plan | samo szkolenie |

## Decyzje do podjęcia

1. Aktualizacja do Next.js 16 (usuwa ostrzeżenie `npm audit`) — to zmiana głównej wersji stosu.
2. Dwuskładnikowe uwierzytelnianie panelu (obecnie hasło + blokady).
3. Czy publikować dane demonstracyjne katalogu (`sensoria.modules.catalog.seed`) — na produkcji: nie.

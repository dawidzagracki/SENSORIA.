# Przegląd kodu SENSORIA — informacja zwrotna dla juniora

Cześć! To jest przegląd projektu w stanie, w jakim trafił do mnie (commit `c619bde`, 2026-10-20). Piszę go **do Ciebie** —
żebyś wiedział, co Ci wyszło naprawdę dobrze, co było błędem i czego z tego możesz się nauczyć. Ocena dotyczy kodu, nie Ciebie.
Wszystkie opisane błędy są już naprawione w repozytorium (commity po `c619bde`).

## Najpierw: to, co zrobiłeś dobrze 👏

Fundament tego projektu jest **lepszy, niż się spodziewałbym po początkującym programiście**. Naprawdę. Konkretnie:

- **Pieniądze zrobione jak trzeba.** Grosze jako `int`, typ `Money`, arytmetyka całkowitoliczbowa HALF_UP, `RATE_0` rozróżnione od `EXEMPT`,
  deterministyczne korekty zaokrągleń w `orders/calculator.py`. To błąd, który popełnia wielu doświadczonych ludzi (`float`) — Ty go uniknąłeś.
- **Idempotencja checkoutu** (`orders/checkout.py`): klucz + hash żądania, ponowienie nie dubluje zamówienia, zmiana treści pod tym samym kluczem to konflikt.
- **Współbieżność przemyślana**: `FOR UPDATE`, `SKIP LOCKED` w schedulerach, testy równoległych transakcji. Brak wyścigów na magazynie i kodach rabatowych.
- **Fail-closed**: brak konfiguracji dostawy to kontrolowany błąd, a nie „darmowa dostawa”. Tak się myśli o bezpieczeństwie.
- **Audyt i historia**: `price_history` z triggerem, `audit_log`, wersjonowany rejestr zgód RODO — niezmienne ślady ważne prawnie.
- **Testy na prawdziwym PostgreSQL** (nie SQLite), ok. 260 testów API. Wyłapują realne błędy bazodanowe, a nie tylko logikę.
- **Katalog, wyszukiwarka FTS z polskim słownikiem, próbki PDF/audio, koszyk gościa, konta klientek z eksportem i usunięciem danych** — czysto, spójnie, zgodnie z konwencjami.
- **Uczciwa dokumentacja.** `AGENTS.md` i `docs/audit/stages-01-55.md` wprost mówią, czego *nie* da się potwierdzić. To rzadka i bardzo cenna cecha.
- **Dostępność (a11y)** potraktowana serio od początku: tokeny, komponenty UI, testy axe.

Jeśli utrzymasz ten poziom dbałości o szczegóły, będziesz bardzo dobrym backendowcem.

## Co było źle — do poprawy i nauki

### A. Błędy w istniejącym kodzie

- **Strony produktów dawały HTTP 500 na prawdziwym API.** Frontend wymagał pól `meta_title`, `meta_description`, `audience_tags`, których endpoint
  `/products/{slug}` nie zwracał. Testy przechodziły, bo korzystały z **atrapy API** z tymi polami.
  → *Nauka: testuj też przez prawdziwe API albo miej test kontraktu (jest: `tests/test_public_catalog.py` i `apps/web/a11y-stack-tests/`).*
- **Test migracji był nieaktualny od kilku etapów** — czerwony na każdym czystym środowisku, więc nikt nie dostawał sygnału o regresji.
  → *Nauka: test, który zawsze jest czerwony, jest gorszy niż brak testu.*
- **Testy zależne od zegara i zostawiające dane**: dwa testy mieszały zegar hosta z zegarem bazy, inne zostawiały klientkę i produkt, więc
  **drugie uruchomienie testów się wywracało**.
  → *Nauka: test ma sprzątać po sobie i nie zależeć od poprzedniego przebiegu; uruchamiaj suite dwa razy.*
- **Rozjazd modeli z migracjami** (`alembic check` zgłaszał różnice: `customer_addresses.recipient_name`, nazwy ograniczeń).
  → *Nauka: uruchamiaj `alembic check`; dodałem test `test_orm_metadata_matches_migrations`.*
- **Nieistniejące klasy Tailwinda** (`text-heading`, `text-heading-1/2/3`) — nagłówki wyglądały jak zwykły tekst. Tailwind po cichu ignoruje nieznane klasy.
  → *Nauka: używaj tylko tokenów z `tailwind.config.ts` (`title`, `subtitle`, `emphasis`…).*
- **Omnibus (najniższa cena z 30 dni) tylko dla e-booków.** Książka, audiobook i voucher z ceną „przed obniżką” nie miały obowiązkowej informacji prawnej,
  a karty pokazywały przekreślenie bez niej.
  → *Nauka: wymóg prawny dotyczy wszystkich rodzajów produktów, nie tylko pierwszego, który implementujesz.*
- **Odbiór osobisty** (`pickup_in_person`) był znany panelowi i kontu, ale checkout nie umiał go utworzyć — etap [31] nie działał end-to-end.
- **Strony pomocy były atrapą** (`PlaceholderPage`), linki w stopce prowadziły w próżnię, a „Ustawienia cookies” otwierały modal, który niczego nie zapisywał.
- **Weryfikacja vouchera „istniała” tylko jako funkcja** (`verification_payload`), bez trasy — kod QR kierował donikąd.
  → *Nauka: „jest funkcja” ≠ „jest trasa”; sprawdzaj uruchomieniem, nie czytaniem.*
- **Projekt nie był repozytorium git** (brak historii i gałęzi `main`), mimo wymagania z etapu [01].

### B. Etapy oznaczone jako zrobione, a niedokończone

Jira pokazywała [01]–[60] jako „W trakcie weryfikacji”, ale ok. 20 z nich było niedokończonych. Sklep **nie mógł jeszcze niczego sprzedać ani wydać**:

- [32]–[35] płatności Stripe i webhooki — `payments/` było pustym szkieletem;
- [36]–[37] paragony/faktury — brak generatora i numeracji;
- [38]–[44] wydawanie plików, biblioteka, czytnik, odtwarzacz — kupione treści nie miały jak trafić do klientki;
- [45], [47] PDF vouchera i realizacja — tylko wiersze zadań, bez workera;
- [49]–[55] przypomnienia, prezenty, powiadomienia o wysyłce, linki logowania/resetu — zadania były kolejkowane, ale **żaden mail nie wychodził**;
- [64]–[71] panel: `admin/auth.py` jawnie zwracał 503.

→ *Nauka: etap jest gotowy dopiero, gdy (a) działa na prawdziwym stosie (Compose), (b) ma test łamiący jego regułę, (c) ma opis w `docs/`,
(d) nie zależy od konfiguracji, której nikt nie ustawił. Status w Jirze to nie dowód.*

## Plan nauki (kolejność)

1. Przeczytaj `AGENTS.md` i `docs/audit/stages-01-55.md`.
2. Przejdź ścieżkę zakupu w kodzie: `orders/checkout.py` → `payments/service.py::_confirm_paid` → `library/service.py` → `mail/bridge.py`.
3. Uruchom testy na świeżej bazie, potem **drugi raz**, oraz `alembic check`.
4. Zrozum, dlaczego atrapa API ukryła błąd 500, i jak działają testy w `apps/web/a11y-stack-tests/`.
5. Zrób ćwiczenia z `docs/przekazanie-kodu.md` (pkt 8).

Powodzenia — fundament masz mocny, teraz dołóż nawyk sprawdzania „czy to naprawdę działa end-to-end”.

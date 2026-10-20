# Raport: co było zrobione w projekcie, zanim przejął go Claude

Dokument dla Twojego juniora (i dla Ciebie). Opisuje **stan kodu w chwili przekazania** (commit `c619bde`, 2026-10-20),
co z tego było dobre, czego brakowało i **co było po prostu błędne** — z konkretnymi przykładami i wnioskami do nauki.
Nie jest to ocena osoby, tylko opis kodu; tam, gdzie coś wyszło dobrze, też to piszę.

Źródła: kod i testy z commitu początkowego, istniejący audyt `docs/audit/stages-01-55.md` (z 2026-10-17), moje własne uruchomienie
testów i przegląd kodu oraz późniejsze testy na pełnym stosie (Docker).

## 1. W jednym akapicie

Fundament i **sklep jako taki** (katalog, koszyk, rachunek VAT, dostawa, checkout tworzący zamówienie, konta klientek, RODO)
były zbudowane **bardzo solidnie** — z testami, transakcjami, idempotencją i dbałością o pieniądze. Jednak **sklep nie mógł
sprzedać ani wydać niczego**: nie było płatności, dostępu do kupionych plików, dokumentów, wysyłki e-maili, logowania do panelu ani
panelu. Jira pokazywała etapy [01]–[60] jako „W trakcie weryfikacji”, ale ok. 20 z nich było niedokończonych (to samo mówił
audyt z 17 października). Dodatkowo kilka błędów ukrywało się dlatego, że testy sprawdzały atrapy, a nie prawdziwe API.

## 2. Co było zrobione dobrze (warto się uczyć)

| Obszar | Co zobaczyć w kodzie | Dlaczego to dobre |
|---|---|---|
| Pieniądze | `shared/types.py::Money`, `shared/pricing.py`, `orders/calculator.py` | grosze jako `int`, arytmetyka całkowitoliczbowa HALF_UP, VAT `RATE_0` ≠ `EXEMPT`, deterministyczne korekty zaokrągleń |
| Idempotencja | `orders/checkout.py` (klucz + hash żądania), `price_history` | ponowienie nie dubluje zamówienia; zmiana treści z tym samym kluczem to konflikt |
| Współbieżność | `FOR UPDATE`, `SKIP LOCKED` w schedulerach, testy równoległych transakcji | brak wyścigów przy magazynie i kodach rabatowych |
| Fail-closed | `admin/auth.py` (przed zmianą), konfiguracja dostawy | brak konfiguracji = kontrolowany błąd, nigdy „darmowa dostawa” |
| Historia i audyt | `price_history` z triggerem, `audit_log`, rejestr zgód RODO | niezmienne ślady, ważne prawnie |
| Dokumentacja decyzji | `AGENTS.md`, `docs/*.md`, szczery `docs/audit/stages-01-55.md` | audyt wprost mówi, czego **nie** da się potwierdzić — to rzadkie i cenne |
| Testy | ~260 testów API na prawdziwym PostgreSQL (nie SQLite), testy a11y | wyłapują realne błędy bazodanowe |

## 3. Stan funkcji w chwili przekazania

**Działało (i było przetestowane):** szkielety FastAPI/Next.js/Docker/Caddy/CI, migracje i `audit_log`, tokeny designu i komponenty UI,
modele produktów (4 rodzaje), kategorie, SEO, ceny i historia cen, publiczne API katalogu, wyszukiwarka FTS z polskim słownikiem,
próbki PDF/audio, strona główna, brak wyników, koszyk gościa (z kalkulatorem VAT, kodami rabatowymi, progami dostawy, wyborem
Paczkomatu), checkout zapisujący zamówienie `pending_payment` ze zgodami, księga magazynowa, modele voucherów (kody, ważność,
prośby o przedłużenie, przypomnienia, prezenty), logika wysyłek, konta klientek (rejestracja, logowanie, reset, link w mailu,
profil, adresy, zgody, eksport i usunięcie danych), historia zamówień i voucherów po stronie klientki.

**Nie istniało albo nie działało, choć Jira sugerowała postęp:**

| Etapy | Czego brakowało |
|---|---|
| [32]–[35] | płatności Stripe, webhooki, obsługa porażek, strona potwierdzenia — `payments/` było pustym szkieletem |
| [36]–[37] | dokumenty sprzedaży (paragon/faktura) — brak generatora i numeracji |
| [38]–[44] | wydawanie plików: uprawnienia, linki, znakowanie PDF, biblioteka, czytnik, odtwarzacz — kupione treści cyfrowe nie miały jak trafić do klientki |
| [45], [47] | PDF vouchera i QR — istniały tylko wiersze zadań, bez workera; brak realizacji vouchera i rejestru |
| [49]–[50], [52] | przypomnienia, prezenty i powiadomienia o wysyłce kolejkowały zadania, ale **nic nie wysyłało maili** |
| [54]–[55] | logowanie e-mailem/resetem — linki powstawały, ale mail nigdy nie wychodził |
| [61]–[63] | poczta transakcyjna: brak transportu, szablonów i workera |
| [64]–[71] | panel: `admin/auth.py` jawnie zwracał 503; brak kont, ról i jakichkolwiek ekranów |
| [72]–[90] | opinie, zgłoszenia, strony prawne, cookies, bezpieczeństwo, kopie, monitoring, wdrożenie, dokumentacja przekazania |

## 4. Błędy i niespójności znalezione w istniejącym kodzie

Poniżej to, co **było błędem**, a nie brakiem funkcji. Wszystko jest już naprawione w repozytorium (commity po `c619bde`).

1. **Strony produktów zwracały HTTP 500 na prawdziwym API.** Frontend (`parseCatalogProductDetail`) wymagał pól `meta_title`,
   `meta_description`, `audience_tags`, których endpoint `/products/{slug}` nie zwracał. Testy Playwright przechodziły, bo korzystały
   z **atrapy API** (`test-fixtures/catalog-api.mjs`), która te pola miała. *Wniosek: testy end-to-end muszą iść przez prawdziwe API
   albo mieć test kontraktu — teraz oba są (`tests/test_public_catalog.py` pilnuje kluczy, `a11y-stack-tests/` jedzie przez cały stos).*
2. **Test migracji był nieaktualny od kilku etapów** (lista dozwolonych tabel i rewizji) — padał na każdym czystym środowisku, więc
   nikt nie dostawał sygnału o regresji. Do tego dwa testy zależały od zegara hosta vs. zegara bazy (dryf maszyny wirtualnej Dockera
   powodował losowe porażki) oraz zostawiały dane (klientka, produkt), przez co **drugie uruchomienie testów się wywracało**.
   *Wniosek: test, który zawsze czerwony lub zależny od poprzedniego przebiegu, jest gorszy niż brak testu.*
3. **Rozjazd modeli z migracjami** (`alembic check` zgłaszał różnice): kolumna `customer_addresses.recipient_name` i nazwy ograniczeń.
   Dodano test pilnujący zgodności (`test_orm_metadata_matches_migrations`).
4. **Nieistniejące klasy Tailwinda** (`text-heading`, `text-heading-1/2/3`) w koszyku, checkoutcie i stronach konta — nagłówki wyglądały
   jak zwykły tekst. Tokeny to `title`, `subtitle`, `emphasis`… (patrz `tailwind.config.ts`). *Wniosek: Tailwind po cichu ignoruje nieznane klasy.*
5. **Najniższa cena z 30 dni (Omnibus)** liczona tylko dla e-booków; książka, audiobook i voucher z ceną „przed obniżką” nie miały
   obowiązkowej informacji, a karty w katalogu pokazywały przekreślenie bez niej. Teraz API liczy ją dla wszystkich rodzajów, a UI ukrywa
   przekreśloną cenę, gdy nie da się jej ustalić.
6. **Niespójność odbioru osobistego**: kod panelu i konta znał metodę `pickup_in_person`, ale checkout nie potrafił jej wytworzyć
   (tylko paczkomat i kurier) — „odbiór w gabinecie” z etapu [31] nie istniał. Dodano go (bezpłatny, bez adresu).
7. **Strony „pomocy” były atrapą** (`PlaceholderPage`), a linki w stopce prowadziły do `/pomoc?temat=…` bez treści; „Ustawienia cookies”
   otwierały demonstracyjny modal, który niczego nie zapisywał.
8. **Audyt zawierał nieścisłość**: wskazywał, że publiczna weryfikacja vouchera „istnieje”, a w kodzie nie było takiej trasy
   (funkcja `verification_payload` nie była używana). Kod QR kierował więc w próżnię. *Wniosek: „istnieje funkcja” ≠ „istnieje trasa”;
   sprawdzaj uruchomieniem.*
9. **Repozytorium nie było repozytorium git** (brak historii, brak gałęzi `main`), mimo wymagań z etapu [01]. Zainicjowano git i zacommitowano
   stan wyjściowy jako punkt odniesienia.

Podczas moich prac wyszły też **dwa własne błędy, wyłapane testami** (warto je znać jako przykład działania siatki bezpieczeństwa):
puste zmienne `STRIPE_*`/`SMTP_*` z `.env.example` były traktowane jako „skonfigurowane” (naprawione + test), oraz limit żądań liczył okna
z mikrosekundami i nigdy się nie uruchamiał (wyłapał to test na 32 żądaniach).

## 5. Czego nauczyć juniora (kolejność)

1. Przeczytaj `AGENTS.md` i `docs/audit/stages-01-55.md` — zobacz, jak zapisano zasady i **uczciwe** luki.
2. Przejdź ścieżkę zakupu w kodzie: `orders/checkout.py` → `payments/service.py::_confirm_paid` → `library/service.py` → `mail/bridge.py`.
3. Uruchom testy na świeżej bazie, potem **drugi raz** (powinny przechodzić za każdym razem) i `alembic check`.
4. Zrozum, dlaczego atrapa API ukryła błąd 500 (pkt 4.1) i jak działają testy w `apps/web/a11y-stack-tests/`.
5. Zrób ćwiczenia z `docs/przekazanie-kodu.md` (pkt 8).

## 6. Jak oceniać „gotowe” w tym projekcie

Etap jest gotowy, gdy: (a) działa na **prawdziwym stosie** (Compose), (b) ma test, który łamie jego regułę, (c) ma opis w `docs/`
i (d) nie opiera się na konfiguracji, której nikt nie ustawił. Status „W trakcie weryfikacji” w Jirze nie był dowodem żadnego z tych punktów.

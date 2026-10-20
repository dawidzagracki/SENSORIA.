# Audyt SENSORIA — etapy 01–55

Data audytu: 2026-10-17 (Europe/Warsaw). Gałąź: `feat/catalog-search`.

## Wynik końcowy

**Aplikacja startuje po poprawkach na izolowanym zestawie audytowym. Cały projekt nie może zostać uznany za działający end-to-end ani za gotowy do kolejnego etapu.** Brakuje kluczowych ścieżek płatności, prywatnych pobrań, dokumentów, czytnika/odtwarzacza, realizacji voucherów i integracji wysyłki maili. Oryginalne opisy niektórych etapów są niedostępne; wszystkie 17 znalezionych makiet projektu z Downloads zostało jednak skopiowanych, wyrenderowanych i obejrzanych. Etapy, których wymaganych kryteriów lub integracji nie potwierdzono, mają wynik **NIE MOŻNA POTWIERDZIĆ** albo **NIEZAAKCEPTOWANY**; nie są one „gotowe” na podstawie wcześniejszych raportów.

Nie wykonywano prawdziwych płatności ani wysyłek. Testy uruchomiono na oddzielnej bazie PostgreSQL `_test` oraz własnym zestawie Compose `sensoria-audit`. Nie zmieniano ani nie usuwano danych lub wolumenów wcześniej działającego zestawu `sensoria-*` z innego checkoutu. `docker compose down -v` nie było użyte.

## Środowisko i dowody

- Izolowany Compose: PostgreSQL 16, API, Next.js i Caddy. `docker compose ... ps` po zwykłym `down`/`up`: DB i API healthy, web i Caddy uruchomione. `/api/health` przez Caddy zwróciło 200; `/` zwróciło 200.
- Migracje: `alembic upgrade head` na świeżej izolowanej bazie, seed idempotentny, `alembic check` → `No new upgrade operations detected`.
- Wolumen: kontrolny plik testowy przeżył restart API, `--force-recreate api` i zwykłe `down`/`up` z tym samym SHA-256. Tryb `0600`, właściciel `10001:10001`; katalog `/app/uploads` `0700`. API działa jako UID 10001. Kontrolny plik usunięto po pomiarze; nie kasowano wolumenu.
- Caddy: ścieżki `/uploads/products/*`, `/uploads/samples/*`, `/uploads/documents/*`, `/uploads/vouchers/*` i `/uploads/generated/*` zwróciły 404 przy właściwym Host `localhost`. Caddy nie montuje wolumenu uploads. Bez właściwego Host dev Caddy przekazuje nierozpoznany host do strony web; to nie dało dostępu do pliku, lecz test używał poprawnego hosta. Walidacja produkcyjnego Caddyfile przeszła.
- API: Ruff check, Ruff format check, strict mypy i testy na PostgreSQL: **239 passed, 1 skipped** (skip: test symlinka, którego Windows nie pozwolił utworzyć). `alembic check` czysty.
- Web po bieżących poprawkach: format check, lint i TypeScript `tsc --noEmit` zakończone kodem 0; Playwright/a11y **41 passed** przy jednym workerze. Vitest z wcześniejszego przebiegu: **78 passed**. Axe pozostawił `incomplete` dla ręcznej oceny kontrastu tekstu; nie raportujemy pełnego potwierdzenia kontrastu przez automat. Next production build skompilował aplikację, ale worker zakończył się błędem natywnym Windows `3221226505`; build nie jest zaliczony.
- Obrazy produkcyjne API i web zbudowały się podczas wcześniejszego audytu, przed bieżącą poprawką CSS. `docker compose config --quiet` przeszło. Nie uruchamiano całego workflow GitHub Actions/CI.
- Trasy runtime zapisano w [`api-routes.txt`](evidence/api-routes.txt). To dowód obecności tras, nie dowód spełnienia autoryzacji każdego scenariusza.
- Zrzuty ekranów po poprawkach, 360 px, tablet 768 px i desktop są w [`evidence/after/`](evidence/after/). Przed poprawkami zachował się zrzut produktu vouchera desktop/360 w [`evidence/baseline/`](evidence/baseline/). Renderowane obrazy wszystkich 17 dostępnych makiet są w [`evidence/mockups/`](evidence/mockups/). Nie ma „before” dla każdego widoku, więc nie twierdzimy, że dla każdego ekranu wykonano formalny zrzut A/B.

## Źródła, makiety i ograniczenia macierzy

Po uzupełnieniu z `Downloads` dostępnych jest 17 unikalnych PDF-ów projektu: `00`–`11`, `16`, `18`–`20` oraz `index` (z pominięciem nieistniejących numerów 12–15 i 17). Duplikaty z sufiksami `(1)`/`(2)` potwierdzono SHA-256 i skopiowano tylko raz. Każdy PDF wyrenderowano i obejrzano. Porównanie ekranu aplikacji, wyniki i zrzuty są w [`mockup-downloads-review.md`](mockup-downloads-review.md); częściowo działające trasy sprawdzono w viewportach 360/768/1024/1280 px. Wykryte przepełnienie tabletowe stron vouchera i e-booka naprawiono. Makiety czytnika/odtwarzacza, biblioteki, zamówień, panelu i potwierdzenia nie mają odpowiadających tras — ich brak pozostaje blokadą funkcjonalną, nie samą różnicą wizualną.

Repo nie zawiera pełnych, oryginalnych opisów etapów 02, 17–20, 28, 30–34. Pełny opis etapu 01 dostarczył użytkownik w załączniku 2026-10-20; jego kryteria audytujemy poniżej. Nie dopisujemy pozostałych brakujących kryteriów z domysłu. Wiersze poniżej podają wyłącznie nazwę z dokumentacji, kodu lub promptów; nie zastępują brakujących źródeł akceptacji. Etapy 35–55 oceniamy względem promptów obecnych w historii tego zadania.

### Szczegółowa ocena etapu 01 — struktura monorepo

Źródło: pełny opis „Cel Utworzyć repozytorium sensoria-shop ze strukturą monorepo…” dostarczony przez użytkownika 2026-10-20. Oceniono stan repozytorium dostępny w tej sesji. Nie kopiowano makiet ani specyfikacji do `docs/`.

| Kryterium | Wynik | Dowód / ograniczenie |
|---|---|---|
| Repozytorium Git, `main` oraz gałęzie robocze `feat/*`, `fix/*` | NIESPEŁNIONE | Bieżąca gałąź to `feat/catalog-search`, ale lokalne `git branch --list` nie wykazało `main`, a repo nie ma skonfigurowanego remote. `git status` zgłasza wszystkie pliki jako nieśledzone (`??`); nie da się potwierdzić poprawnego klonowania ani historii repo. Git odmawia części operacji z powodu `dubious ownership`; nie zmieniano globalnej konfiguracji `safe.directory`. |
| Struktura monorepo: `apps/api`, `apps/web`, `docs/makiety`, `docker`, `.github/workflows` | SPEŁNIONE | Wszystkie wymagane katalogi istnieją. |
| `.gitignore` blokuje `.env`, cache, środowiska i uploads | SPEŁNIONE | `git check-ignore -v .env` wskazuje regułę `.gitignore:2:.env`; plik `.env` nie został wypisany jako nieśledzony. |
| README zawiera opis i trzy kroki uruchomienia | SPEŁNIONE | `README.md` ma sekcję „Przygotowanie i uruchomienie — 3 kroki”, polecenia i lokalizację dokumentacji. |
| AGENTS.md obejmuje wymagane konwencje | SPEŁNIONE | Plik opisuje stack, strukturę, nazewnictwo, grosze jako `int`, język, polecenia, bazę/migracje i zakres „Czego nie dotykać”. |
| Konfiguracja backendu: Ruff, mypy strict, pytest | NIESPEŁNIONE | Literalny `ruff check apps/api` zgłosił 42 błędy (41 E501 i 1 F401) w pięciu istniejących rewizjach Alembic. Nie poprawiano wydanych migracji, zgodnie z AGENTS.md. Zakres projektu `ruff check src/sensoria tests` z `apps/api` przechodzi. `uv` nie jest dostępne, więc nie uruchomiono komendy przez wskazany menedżer zależności; mypy i pytest nie były częścią kryteriów stage-01 i nie są tu oceniane. |
| Konfiguracja frontendu: ESLint, Prettier, `tsc --noEmit` | SPEŁNIONE | Skrypty `lint`, `format:check` i `typecheck` istnieją w `apps/web/package.json`; `npm run typecheck` zakończył się kodem 0. |
| Pre-commit uruchamia lint i instalacja hooka działa | NIESPRAWDZONE | `.pre-commit-config.yaml` przechodzi walidację, a `pre-commit run backend-ruff --files apps/api/src/sensoria/main.py` zakończył się `Passed`. Hook Ruff poprawiono, aby sprawdzał kod API i testy, nie zamrożone migracje. Instalacji hooka w `.git/hooks` nie wykonano; repozytorium nie ma remote i systemowy `uv`/Python 3.12 nie są dostępne. |
| `docs/makiety/` zawiera 22 PDF-y, a `docs/specyfikacja.pdf` istnieje | NIESPEŁNIONE | Po skopiowaniu dostarczonej makiety 12 w katalogu jest 18 PDF-ów: 00–12, 16, 18–20 i index. Brakuje czterech makiet (13–15 i 17) do wymaganej liczby 22. `docs/specyfikacja.pdf` nie istnieje. Brakujących plików nie wolno odtwarzać z domysłu. |
| `git clone` i instalacja pre-commit bez błędów | NIESPRAWDZONE | Brak remote i brak dostępnego `pre-commit`/`uv`; nie wykonano klonowania do nowego katalogu. |

**Ocena etapu 01: NIEZAAKCEPTOWANY.** Wykazane braki to 18 zamiast 22 makiet, brak `docs/specyfikacja.pdf`, repozytorium bez remote i bez pierwszego commitu (lokalną gałąź przygotowano jako `main`), nieudowodnione klonowanie/instalacja hooka oraz 42 błędy literalnego `ruff check apps/api` w wydanych migracjach. Zgodny z AGENTS zakres `ruff check src/sensoria tests` przechodzi; poprawiony hook pre-commit również przechodzi. Frontendowy `npx tsc --noEmit` przeszedł. Nie zmieniano migracji ani nie wyciszano reguł Ruffa.

## Macierz etapów 01–55

Status etapu opisuje całość dostępnego zakresu: **ZAAKCEPTOWANY** wymaga potwierdzenia wszystkich obowiązkowych kryteriów; **NIEZAAKCEPTOWANY** oznacza wykazany brak; **NIE MOŻNA POTWIERDZIĆ** oznacza brak źródła lub dowodu kluczowej integracji. Szczegółowe kryteria, których źródło istnieje, oceniono w dokumentacji i kontrolach wskazanych w dowodach. Brak oryginalnego opisu oznacza, że nie można uczciwie sporządzić jego kompletnej listy kryteriów.

| Etap | Nazwa / zakres ze źródła | Źródło i makieta | Wynik etapu | Dowód, poprawki i pozostałe braki |
|---:|---|---|---|---|
| 01 | Struktura monorepo i konwencje projektu | Załącznik użytkownika 2026-10-20; obecnie 18 PDF-ów lokalnych | NIEZAAKCEPTOWANY | Szczegółowa macierz kryteriów znajduje się wyżej. Brakuje 4 z wymaganych 22 PDF-ów i `docs/specyfikacja.pdf`; lokalne `main` przygotowano, ale brak remote i pierwszego commitu. Frontend `tsc --noEmit` oraz zakresowy Ruff i hook pre-commit przechodzą; literalny Ruff całego `apps/api` zgłasza 42 błędy w wydanych migracjach. Instalacja hooka/klonowanie niesprawdzone. |
| 02 | Tytuł etapu niepotwierdzony; produkt voucher jest tylko nazwą makiety | PDF 02, `docs/produkt-voucher.md` | NIE MOŻNA POTWIERDZIĆ | Stronę porównano i poprawiono; pełne kryteria źródłowe etapu niedostępne. |
| 03 | Frontend Next.js | README/AGENTS | NIE MOŻNA POTWIERDZIĆ | Routing, lint, format i TypeScript przechodzą; produkcyjny build po ponowieniu zakończył się poprawnie. Brak pełnego opisu etapu i pełnego E2E sklepu. |
| 04 | Kontenery | Compose, AGENTS | NIE MOŻNA POTWIERDZIĆ | Izolowany zestaw działa, test persistence po restart/recreate/down-up zaliczony; pełne wymagania źródłowe nieznane. |
| 05 | CI | `.github/workflows/ci.yml` | NIE MOŻNA POTWIERDZIĆ | Kontrole lokalne i oba obrazy przechodzą; workflow CI na zdalnym runnerze nieuruchomiony. |
| 06 | Konfiguracja i sekrety | AGENTS, `.env.example` | NIE MOŻNA POTWIERDZIĆ | Sekrety nie były wyświetlane; brak pełnego audytu rotacji/production environment. |
| 07 | Fundament DB i audit_log | migracje/AGENTS | NIE MOŻNA POTWIERDZIĆ | Świeża PostgreSQL, upgrade i autogenerate check przechodzą; kompletna semantyka audytu wszystkich modułów niepotwierdzona. |
| 08 | Tokeny wizualne | `tailwind.config.ts`, AGENTS | NIE MOŻNA POTWIERDZIĆ | Widoki używają tokenów; ręczny audyt każdego ekranu i kontrastu nieukończony. |
| 09 | Wspólne komponenty UI | AGENTS, axe | NIE MOŻNA POTWIERDZIĆ | 40 testów a11y przechodzi; axe ma nierozstrzygnięte `incomplete` kontrastu. |
| 10 | Wspólna rama sklepu | layout i dostępne PDF-y | NIE MOŻNA POTWIERDZIĆ | Header/footer są na istniejących stronach i przechodzą część testów; brak makiet większości ekranów. |
| 11 | Responsywność i dostępność | checklista, Playwright | NIE MOŻNA POTWIERDZIĆ | Playwright 41/41; nowe capture/regresje obejmują 360/768/1024/1280. Ręczna ocena kontrastu i zoom 200% niepotwierdzone. |
| 12 | Modele katalogu | AGENTS, migracje, API tests | NIE MOŻNA POTWIERDZIĆ | Indeksy ORM/migracje naprawione i autogenerate check czysty; pełne kryteria etapu brakują. |
| 13 | Kategorie, odbiorcy, SEO | AGENTS, API tests | NIE MOŻNA POTWIERDZIĆ | API i FTS testują; pełna zgodność wszystkich oryginalnych kryteriów niepotwierdzona. |
| 14 | Ceny i historia cen | AGENTS, migration `f31a9d4b` | NIE MOŻNA POTWIERDZIĆ | Testy backendu i PostgreSQL przeszły; brak kompletnej walidacji biznesowej i źródła odbioru. |
| 15 | Publiczne API katalogu | `docs/api-katalogu.md`, PDF 01 | NIE MOŻNA POTWIERDZIĆ | Live routes, przegląd katalogu i testy przeszły; wizualnie tylko częściowa zgodność. |
| 16 | PostgreSQL FTS | AGENTS, testy katalogu | NIE MOŻNA POTWIERDZIĆ | PostgreSQL 16 oraz pełne testy przeszły; workflow i wszystkie kryteria źródła niepotwierdzone. |
| 17 | Brak źródła | Brak | NIE MOŻNA POTWIERDZIĆ | Oryginalny opis niedostępny. |
| 18 | Brak źródła | Brak | NIE MOŻNA POTWIERDZIĆ | Oryginalny opis niedostępny. |
| 19 | Brak źródła; nazwa czytnika wspomniana w promptach późniejszych | PDF 19 dostępny w Downloads | NIE MOŻNA POTWIERDZIĆ | Makietę wyrenderowano i obejrzano; brak czytnika w zbudowanym web. |
| 20 | Brak źródła; odtwarzacz wymieniony później | PDF 20 dostępny w Downloads | NIE MOŻNA POTWIERDZIĆ | Makietę wyrenderowano i obejrzano; brak odtwarzacza w zbudowanym web. |
| 21 | Próbki PDF/audio | `sample_storage.py`, `samples.py`, testy | NIE MOŻNA POTWIERDZIĆ | Kontrolowany endpoint istnieje; redakcyjne próbki i pełne testy Caddy/Range niepotwierdzone. |
| 22 | Strona główna | `docs/strona-glowna.md`, index PDF | NIE MOŻNA POTWIERDZIĆ | Home zrzuty desktop/tablet/360 i Playwright; index nie jest dokładną makietą home, zgodność tylko częściowa. |
| 23 | Stan braku wyników | `docs/stan-braku-wynikow.md` | NIE MOŻNA POTWIERDZIĆ | Testy wyszukiwania/katalogu przechodzą; pełny audit wizualny i kryteria źródła niepotwierdzone. |
| 24 | Trwały koszyk | AGENTS, Playwright/API | NIE MOŻNA POTWIERDZIĆ | Browser testy add/update/remove i licznika naprawiono; brak pełnego checkout-to-order i merge po loginie. |
| 25 | Kalkulator koszyka | AGENTS, backend tests | NIE MOŻNA POTWIERDZIĆ | Backend suite na PostgreSQL; brak kompletnego E2E z potwierdzonym zamówieniem/płatnością. |
| 26 | Rabaty | `docs/kody-rabatowe.md` | NIE MOŻNA POTWIERDZIĆ | Moduł testowany; brak płatności i pełnego zamówienia oraz kompletnego audytu reguł promocji. |
| 27 | Wycena dostawy | `docs/dostawa-koszyka.md`, PDF 04 | NIE MOŻNA POTWIERDZIĆ | Checkout/konfiguracja istnieje; punkty odbioru i kompletne fulfilment E2E niepotwierdzone. |
| 28 | Brak źródła (uwaga: dokumentacja checkoutu obejmuje etap 29, nie dopisujemy zakresu 28) | Brak | NIE MOŻNA POTWIERDZIĆ | Oryginalny opis niedostępny. |
| 29 | Checkout gościa | `docs/checkout.md`, PDF 04 | NIEZAAKCEPTOWANY | Brak `/orders`/płatności/webhooku; nie można potwierdzić utworzenia zamówienia i pełnego checkoutu. UI checkoutu testowane, lecz fixture nie zastępuje integracji. |
| 30 | Brak źródła | Brak | NIE MOŻNA POTWIERDZIĆ | Oryginalny opis niedostępny. |
| 31 | Metody dostawy/snapshoty (tytuł z późniejszych odwołań) | Prompt 47/52/53, `docs/dostawa-koszyka.md` | NIEZAAKCEPTOWANY | Checkout ma metody parcel locker/courier, ale nie ma odbioru osobistego w kontrakcie aktualnego `/cart/checkout`; brak pełnego zamówienia/snapshotu. |
| 32 | Operator płatności (tytuł z odwołań) | README i prompt 33 | NIEZAAKCEPTOWANY | `payments` nie ma endpointów biznesowych/operatora. |
| 33 | Potwierdzanie płatności | Prompt etapu 33 | NIEZAAKCEPTOWANY | Brak webhooka i przejścia płatności; `payments/router.py` jawnie wskazuje brak endpointów biznesowych. |
| 34 | Niepowodzenie/wygaśnięcie płatności | Odwołania z etapów 35+ | NIEZAAKCEPTOWANY | Brak cyklu płatności i zdarzeń, które mogłyby uruchomić pełną obsługę. |
| 35 | Potwierdzenie zamówienia | Prompt 35 | NIEZAAKCEPTOWANY | Brak trwałego modelu orders, tokenu zamówienia i publicznego endpointu potwierdzenia. |
| 36 | Dokumenty sprzedaży | Prompt 36 | NIEZAAKCEPTOWANY | Nie ma dokument generator endpointu ani order/payment snapshot end-to-end; magazyn sam nie realizuje kryterium. |
| 37 | Dane nabywcy | Prompt 37, PDF 04 | NIEZAAKCEPTOWANY | Checkout nie tworzy zamówienia i nie ma właściwego nabywcy na zamówieniu; panel szczegółów zamówienia nie istnieje. |
| 38 | Prywatny magazyn | Prompt 38, Compose/Caddy | NIEZAAKCEPTOWANY | StorageService, uprawnienia, wolumen i deny Caddy sprawdzone; brak autoryzowanych pełnych downloads i wymaganego pomiaru 200 MB. |
| 39 | Uprawnienia entitlements | Prompt 39 | NIEZAAKCEPTOWANY | Brak `/api/entitlements` i płatności atomowo tworzącej prawa. |
| 40 | Linki pobrań | Prompt 40 | NIEZAAKCEPTOWANY | Brak `/api/download/{token}`/tokenów, Range/session limit. |
| 41 | Znakowanie PDF | Prompt 41 | NIEZAAKCEPTOWANY | Brak PdfWatermarkService, worker statusu/fallback i wysyłki pliku znakowanego. |
| 42 | Biblioteka | Prompt 42, PDF 06 dostępny w Downloads | NIEZAAKCEPTOWANY | `/konto/biblioteka` i agregującego API brak; mockup wyrenderowano i obejrzano. |
| 43 | Czytnik | Prompt 43, PDF 19 dostępny w Downloads | NIEZAAKCEPTOWANY | Brak tras rozdziałów/postępu, strukturalnej treści i ekranu; mockup obejrzany. |
| 44 | Odtwarzacz | Prompt 44, PDF 20 dostępny w Downloads | NIEZAAKCEPTOWANY | Brak odtwarzacza/audio endpoint/postępu; mockup obejrzany. |
| 45 | Kody, QR, PDF voucherów | Prompt 45, PDF 02 | NIEZAAKCEPTOWANY | Public verification/PDF/QR i account vouchers routes istnieją, ale voucher nie jest transakcyjnie wystawiany po płatności; obecny produkt używa jawnie przykładowego biletu. |
| 46 | Ważność i przedłużanie | Prompt 46 | NIE MOŻNA POTWIERDZIĆ | Effective status/requests/history istnieją i suite przechodzi, lecz administracyjna autoryzacja i pełna integracja [47]/[48]/[49] niepotwierdzone. |
| 47 | Rejestr realizacji | Prompt 47, PDF 07 dostępny w Downloads | NIEZAAKCEPTOWANY | Brak admin voucher redemption/revert/ledger API i panelu rejestru; mockup obejrzany. |
| 48 | Moje vouchery | Prompt 48, PDF 11 dostępny w Downloads | NIE MOŻNA POTWIERDZIĆ | `/konto/vouchery` i API istnieją, lecz powiązanie z realnym paid order i realistyczny odczyt prywatnej karty niepotwierdzone; mockup obejrzany. |
| 49 | Przypomnienia voucherów | Prompt 49 | NIEZAAKCEPTOWANY | Scheduler/outbox może kwalifikować i tworzyć zadania; brak worker [63], ponownej weryfikacji przed providerem i potwierdzonej wysyłki. |
| 50 | Voucher prezentowy | Prompt 50, PDF 02 | NIEZAAKCEPTOWANY | Dane/form UI/jobs istnieją, lecz brak potwierdzonego order/payment + mail worker; nie potwierdzono E2E prezentu. |
| 51 | Magazyn książek | Prompt 51 | NIE MOŻNA POTWIERDZIĆ | Ledger/reservation logic i testy są; brak płatności/zwrotu E2E oraz testu niezależnych równoległych transakcji wymaganych przez etap. |
| 52 | Nadanie | Prompt 52, PDF 07 dostępny w Downloads | NIEZAAKCEPTOWANY | Routes istnieją, ale wyłączone fail-closed przez brak admin auth; pełny panel, outbox worker i paid-order integration brak; mockup obejrzany. |
| 53 | Śledzenie klientki | Prompt 53, PDF 06/10 dostępne w Downloads | NIE MOŻNA POTWIERDZIĆ | `/accounts/shipments` i karta biblioteki istnieją w części; brak historii zamówień [57] i ekranów biblioteki/historii; pełny ownership E2E nieuruchomiony. |
| 54 | Konto klientki | Prompt 54, PDF 09 dostępny w Downloads | NIE MOŻNA POTWIERDZIĆ | Register/session/password/reset APIs/pages i testy istnieją; brak faktycznego transportu mail [63] i pełnego niezależnego concurrency/security audit; mockup obejrzany. |
| 55 | Logowanie linkiem | Prompt 55, PDF 09 dostępny w Downloads | NIEZAAKCEPTOWANY | API/confirmation page istnieją, ale brak trwałego mail worker; nie wykonano realnego end-to-end z odbiornikiem i nie potwierdzono dostarczenia; mockup obejrzany. |

## Skrócona ocena makiet i ekranów

Kompletny rejestr 17 PDF-ów, wizualne uwagi, route coverage i dowody viewportów znajduje się w [`mockup-downloads-review.md`](mockup-downloads-review.md).

Nie wykonano zrzutów „przed” wszystkich widoków, ponieważ nie cofano kodu użytkownika. Zrzuty świeżego stanu aplikacji zapisano w `evidence/after/`; pełne mapowanie, różnice i statusy znajdują się w `mockup-downloads-review.md`. Makiety 06/07/09/10/11/19/20 są teraz dostępne, ale brakujące strony aplikacji nadal nie istnieją.

## Szczegółowy rejestr napraw i kontroli

Zobacz [`fixes.md`](fixes.md). Zachowane zrzuty są w `evidence/`; lokalne drobne różnice wizualne i brak per-screen baseline są opisane bez deklaracji pełnej zgodności.

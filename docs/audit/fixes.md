# Dziennik audytu i napraw

Data: 2026-10-17. Główny wynik etapów [01]–[55] oraz macierz znajduje się w [`stages-01-55.md`](stages-01-55.md).

## Wykryte problemy i poprawki

| ID | Odtworzony problem | Przyczyna | Naprawa | Ponowna kontrola |
|---|---|---|---|---|
| AUD-001 | `alembic check` wykrywał różnice między ORM i istniejącymi indeksami/ograniczeniami | ORM nie deklarował dwóch indeksów produktów i używał nazw innych niż migracje dla UNIQUE w `shipment_history` oraz `voucher_gift_delivery_jobs` | Dopasowano metadane ORM do schematu bez zmiany wydanych migracji | `alembic check`: `No new upgrade operations detected`; backend suite passed |
| AUD-002 | Ruff wykrywał `SIM105` w prywatnym magazynie | Puste `try/except OSError` | Zastosowano `contextlib.suppress(OSError)` | `ruff check` i `ruff format --check` passed |
| AUD-003 | Produktowe flow „Dodaj do koszyka” nie wywoływało istniejącego API | Wspólny komponent zgłaszał stały komunikat, że integracja niedostępna | Dodano helper POST `/api/cart/items`, credentials/no-store, walidację serwerowego `item_count` i komunikat błędu; podłączono identyfikator wariantu | Playwright potwierdził dodanie AUDIOBOOK i vouchera oraz aktualizację licznika z kontrolowanego fixture; Vitest passed |
| AUD-004 | Test vouchera oraz test cyfrowego produktu oczekiwał toastu po nawigacji | Komunikat był unmountowany przez przejście na stronę koszyka; asercja sprawdzała stan po zniknięciu komponentu | Zmieniono test, aby weryfikował trwały rezultat koszyka/licznik zamiast znikającego toastu | Playwright suite końcowa: 40 passed |
| AUD-005 | ESLint podczas Playwright mógł wejść w usuwany katalog wynikowy | Runner sprzątał `test-results` podczas lintowania | Dodano `test-results/**` i `playwright-report/**` do ignore ESLint | lint i format check zakończone kodem 0 |
| AUD-006 | Karta demonstracyjnego vouchera miała niewłaściwy/niejednoznaczny zapis odznaki okresu | Tekst makiety był łamany w wąskim kółku | Odznaka pokazuje liczbę i skrót „mies.” z pełną dostępną etykietą; przykładowy kod pozostaje jawnie nieaktywny | Zrzuty desktop/360 po poprawkach i browser tests |
| AUD-007 | Ochrona katalogów magazynu była niespójna z wymogiem trybu prywatnego | Katalogi kategorii/roku nie wymuszały restrykcyjnego trybu przy tworzeniu | Tworzenie katalogów ustawia tryb `0700` (tam gdzie system POSIX obsługuje permissions) | Test w kontenerze: katalog root `0700`, plik `0600`, właściciel `10001:10001`; plik przetrwał restart/recreate/down-up |
| AUD-008 | Hook pre-commit uruchamiał Ruff na całym `apps/api`, w tym na wydanych rewizjach Alembic | Historyczne migracje zawierają 42 obecne naruszenia formatowania/importów, a instrukcje zabraniają ich edycji po wydaniu | Hook ograniczono do utrzymywanego kodu `apps/api/src/sensoria` i testów; reguł Ruffa nie wyłączono, migracji nie zmieniono | `pre-commit validate-config` oraz `pre-commit run backend-ruff --files apps/api/src/sensoria/main.py`: Passed; pełne `ruff check apps/api` nadal zgłasza 42 problemy w migracjach |

## Wykonane kontrole końcowe

| Kontrola | Rzeczywisty wynik | Granica dowodu |
|---|---|---|
| Backend Ruff | passed | statyczna jakość kodu |
| Backend format | passed | styl źródeł |
| Backend mypy strict | passed | sprawdzenie typów |
| Backend pytest + osobny PostgreSQL 16 | `239 passed, 1 skipped` w 142.19 s | skip dotyczy Windows symlink; nadal brak testów dla nieistniejących płatności/download/reader/player/admin-redemption |
| Alembic | upgrade head, `alembic check` czysty | tylko izolowana baza audytu; nie migrowano innego działającego środowiska |
| Seed | idempotentnie `Dodano 0 nowych ustawień` | nie dowodzi biznesowej kompletności produkcyjnej konfiguracji |
| Frontend Vitest | `78 passed` | testy jednostkowe/komponentowe |
| Playwright/a11y | `40 passed` | aplikacja z mockowanym API dla scenariuszy UI; axe zgłasza incomplete ręcznej oceny kontrastu |
| Web format/lint/tsc | wszystkie kod 0 | frontend statyczny |
| Pre-commit | Narzędzie uruchomiono z lokalnego venv; hooki Ruff i ESLint zwróciły `(no files to check) Skipped` | repozytorium nie ma śledzonych plików (`git status` pokazuje wszystko jako `??`), a `pre-commit --all-files` pobiera listę z Git; nie stage'owano plików w celu obejścia tego stanu |
| Docker API runtime | build succeeded | nie jest to dowód CI/prod deployment |
| Docker web runtime | build succeeded; Next route inventory zebrany | brakujące strony konta są widoczne w liście tras |
| Compose | config i izolowany zestaw start/health passed | starszy zestaw z innego checkoutu pozostawiono nietknięty |
| Caddy uploads | 404 dla pięciu kategorii przy `Host: localhost` | sprawdzono HTTP dev; brak kontroli zewnętrznej domeny produkcyjnej |
| Caddy config | `caddy validate` dla dev i production passed | lokalny HTTP nie weryfikuje TLS/hosta publicznego ani logów infrastruktury produkcyjnej |
| Wolumen | hash identyczny po API restart, force-recreate, zwykłym down/up; uid/mode prawidłowe | wyłącznie własny kontrolny plik w izolowanym audytowym wolumenie; nie wykonano `down -v` |

## Znane braki i blokery

- Checkout ma frontend i koszyk, ale nie ma potwierdzenia płatności/webhooka oraz pełnego API zamówień. Bez tego nie można end-to-end potwierdzić wystawiania dokumentów, uprawnień, voucherów i rezerwacji po opłaceniu.
- Moduł payments nie zawiera ścieżki operatora biznesowego. Nie wykonano i nie wolno wykonywać prawdziwych płatności.
- Zestaw endpointów nie zawiera `GET /api/entitlements`, `GET /api/download/{token}`, reader API ani audio API. Pełne pobieranie, Range/wznawianie, watermark delivery, czytnik i odtwarzacz pozostają niezaimplementowane.
- Występują account/voucher endpoints i widoki, ale brak płatności oznacza, że nie dowodzą rzeczywistych zakupów. Brakuje admin redemption/revert/ledger endpointów. Admin shipment API działa fail-closed z powodu braku realnej infrastruktury konta/roli administracyjnej.
- Brak kolejki/worker [63] dla maili. Outbox/jobs nie dowodzą wysyłki, przyjęcia przez dostawcę ani dostarczenia. Nie wysłano żadnej prawdziwej wiadomości.
- Brak pełnej historii zamówień [57], konta biblioteki [42] i przyszłych czytnika/odtwarzacza. Niektóre karty/kontrakty nie zastępują tych tras.
- Nie wykonano 200 MB transferu/pomiaru RSS, odczytu/wznowienia pliku audio przez Caddy, odczytu QR z finalnego voucher PDF ani wizualnej inspekcji wszystkich typów wygenerowanych PDF. Te funkcje nie mają kompletnej ścieżki/artefaktów w obecnej implementacji.
- Brakuje PDF-ów makiet konta, admina, historii, voucherów klientki, czytnika i odtwarzacza; nie da się wykonać żądanego porównania pixel-level.
- Axe `color-contrast` zwrócił `incomplete` dla wielu elementów (zwłaszcza muted/footer); automatyczne 40/40 nie oznacza kompletnego ręcznego potwierdzenia WCAG.
- Git ownership nie pozwolił na `git status` z bieżącego Windows SID bez dodania `safe.directory`. Nie zmieniono globalnej konfiguracji; początkowe inwentaryzacje wykazały całość repo jako nieśledzone `??`. Na końcu stan ponownie sprawdzić przez `git -c safe.directory=C:/Users/marce/Desktop/SENSORIA status --short`, jeśli potrzebny jest aktualny listing — nie stage'ować ani nie usuwać plików.

## Bezpieczeństwo audytu

- Wszystkie testy bazodanowe kierowano na `sensoria_audit_test` na porcie 15433.
- Własny Compose działał pod osobnym projektem i portami 15432/18000/13000/18080. Istniejący zestaw `sensoria-*` nie był restartowany, migrowany ani czyszczony.
- Sekrety, rzeczywiste dane klientek, payloady zawierające hasła/tokeny oraz kod QR klientek nie trafiają do zrzutów ani raportu.
- Zmiany kodu wymieniono w historii zadania; ponieważ repo było nieśledzone w Git, nie można wiarygodnie podać diffstat ani listy „plików zmienionych przez audyt” przez Git.

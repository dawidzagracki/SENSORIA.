# sensoria-shop

Monorepo dla przyszłego sklepu internetowego. API ma szkielet FastAPI, asynchroniczną warstwę bazy, migracje oraz fundament modeli produktów. Nie ma jeszcze endpointów katalogu, koszyka ani innych endpointów biznesowych.

## Stos i wymagania

- Python 3.12, FastAPI, SQLAlchemy 2.0 async, asyncpg, Alembic i Pydantic Settings (`apps/api/`).
- PostgreSQL 16; serwer musi działać lokalnie lub być dostępny pod podanym adresem.
- uv do zależności i środowiska Python.
- Node.js 22 i npm; Next.js 15 oraz TypeScript (`apps/web/`).
- Tailwind CSS 3 w aplikacji frontendowej.
- Docker Engine lub Docker Desktop oraz Docker Compose v2.24.4+ — lokalne kontenery API, web, PostgreSQL i Caddy.
- Obraz frontendowy używa Node.js 22 Alpine; `apps/web/.dockerignore` chroni kontekst aplikacji, a budowanie z katalogu głównego filtruje `.dockerignore`.

## Przygotowanie i uruchomienie — 3 kroki

Polecenia są dla PowerShell w katalogu głównym repozytorium.

1. Zainstaluj Python 3.12 i uv, a następnie zależności backendu:

   ```powershell
   uv sync --project apps/api --frozen --all-groups
   ```

2. Skopiuj główny przykład do ignorowanego `.env` i ustaw lokalną konfigurację. Backend ładuje ten plik z katalogu repozytorium. Przy uruchomieniu poza Dockerem ustaw `DATABASE_URL` na PostgreSQL pod `localhost`.

   ```powershell
   Copy-Item .env.example .env
   # Edytuj .env; użyj fikcyjnych danych lokalnych i ustaw API_URL dla web.
   npm --prefix apps/web ci
   ```

   `DATABASE_URL` ma format `postgresql+asyncpg://user:password@host:5432/database`. `.env.example` zawiera wyłącznie wartości fikcyjne. Testy korzystają z oddzielnej bazy wskazanej przez `TEST_DATABASE_URL`, zakończonej `_test`.

3. Zastosuj migrację bazową, zainstaluj hooki i uruchom API:

   ```powershell
   Push-Location apps/api
   uv run --frozen --all-groups alembic upgrade head
   Pop-Location
   uv run --project apps/api pre-commit install
   Push-Location apps/api
   uv run uvicorn sensoria.main:app --reload
   Pop-Location
   ```

API działa pod `http://127.0.0.1:8000`; development udostępnia `/docs` i `/redoc`, a kontrola bazy `/health`. Aplikacja wymaga poprawnej konfiguracji i PostgreSQL. `/health` wykonuje `SELECT 1`; niedostępna baza daje 503.

## Konfiguracja i sekrety — etap [06]

Jedynym wzorcem jest główny [`.env.example`](.env.example). Skopiuj go do `.env` w katalogu głównym; `.env` oraz lokalne warianty są ignorowane. Nie nadpisuj istniejącego lokalnego `.env`. Przykład nie zawiera prawdziwych danych.

| Zmienna                                             | Rola i źródło                                                                                                                    | Wymagana / poufność                                        |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| `DATABASE_URL`                                      | SQLAlchemy async. Lokalnie wskazuje PostgreSQL; Compose nadpisuje host na `db`. Dane połączenia pochodzą z lokalnego PostgreSQL. | Wymagana, poufna                                           |
| `ENVIRONMENT`                                       | `development` albo `production`; dobierz do uruchomienia.                                                                        | Wymagana, nie sekret                                       |
| `SECRET_KEY`                                        | Backendowy klucz; wygeneruj lokalnie poleceniem poniżej. Przykład jest placeholderem.                                            | Wymagana, sekret; produkcja: losowy klucz ≥32 znaków       |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Inicjalizacja kontenera PostgreSQL. W produkcji ustaw w prywatnym środowisku wdrożenia.                                          | Compose wymagane; hasło poufne                             |
| `TEST_DATABASE_URL`                                 | Oddzielna, pusta baza PostgreSQL 16 dla pytest; testowy serwer/baza.                                                             | Tylko testy, poufna                                        |
| `API_URL`                                           | Adres backendu używany przez serwer Next.js; lokalnie `localhost:8000`, Compose `api:8000`.                                      | Wymagana przy renderowaniu strony, serwerowa, bez sekretów |
| `NEXT_PUBLIC_API_URL`                               | Adres API dla przeglądarki, np. przez Caddy `/api`.                                                                              | Wymagana dla buildu; publiczna, build-time                 |
| `SITE_URL`                                           | Publiczny origin sklepu dla canonical, Open Graph, JSON-LD, robots i sitemap. Production wymaga HTTPS.                            | Wymagana dla publicznych metadanych, nie sekret             |
| `SITE_OG_IMAGE`                                      | Opcjonalny publiczny obraz marki używany dla kategorii bez własnego `og_image`.                                                  | Opcjonalna, publiczny adres                                |
| `DOMAIN`                                            | Host Caddy; `localhost` lokalnie, własna domena w produkcji.                                                                     | Wymagana dla Compose, nie sekret                           |
| `COMPOSE_PROJECT_NAME`                              | Prefiks nazw sieci i wolumenów Compose; domyślnie `sensoria`.                                                                    | Opcjonalna, nie sekret                                     |
| `HTTP_PORT`, `HTTPS_PORT`                           | Porty hosta Caddy.                                                                                                               | Opcjonalne, nie sekret                                     |
| `API_PORT`, `WEB_PORT`, `DB_PORT`                   | Bezpośrednie porty developerskie na localhost.                                                                                   | Opcjonalne, tylko development                              |
| `CADDY_HTTP_PORT`                                   | Lokalny port HTTP Caddy w developerskim override.                                                                                | Opcjonalna, tylko development                              |
| `SENSORIA_ENV_FILE`                                 | Wewnętrzny override pliku ustawień używany w izolowanych testach walidacji. Zwykle nie ustawiaj.                                 | Test harness, nie sekret                                   |

Utwórz losowy klucz w swoim terminalu i wklej go wyłącznie do lokalnego `.env` lub menedżera sekretów wdrożenia:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

W development przykładowy klucz jest dozwolony. W production wymagany jest nie-placeholder o długości co najmniej 32 znaków. `ENVIRONMENT` nie ma domyślnej wartości: niepoprawny lub brakujący wpis zatrzymuje start. Production wyłącza `/docs`, `/redoc` i `/openapi.json`; development udostępnia je. Odpowiedzi błędów zachowują wspólny polski format; production nie zwraca szczegółów technicznych. Logi zawierają ramki wywołań, nie treść wyjątku ani wartości lokalne; parametry SQL są ukryte.

Compose wczytuje `.env` dla interpolacji, a API dostaje plik przez `env_file`; jawne `environment` nadpisuje URL bazy (na host `db`), profil i klucz oraz czyści testowy `TEST_DATABASE_URL` z kontenera runtime. Bazowy plik wybiera production, developerski override development. Web dostaje jawnie tylko `API_URL` oraz publiczny `NEXT_PUBLIC_API_URL`, bez sekretów. Ustawienia serwera i sekrety runtime nie są kopiowane do obrazów. `.env` używany przez Compose do interpolacji sam z siebie nie trafia do usług.

`NEXT_PUBLIC_*` jest publiczne. Next.js wbudowuje te wartości w kod przeglądarkowy podczas `next build`; zmiana wymaga ponownego builda. Nie umieszczaj tam haseł ani kluczy. `API_URL` jest konfiguracją runtime serwera Next.js i może różnić się od publicznego URL-a.

Obecne CI używa wyłącznie fikcyjnych wartości i tymczasowego PostgreSQL, więc nie wymaga GitHub Secrets. Dla przyszłych integracji dodawaj sekrety wyłącznie w **Settings → Secrets and variables → Actions**, odczytuj przez `${{ secrets.NAME }}` i nigdy nie zapisuj ich w YAML. Obecnie nie są używane klucze Stripe, poczty ani Dysku Google.

Zmienne narzędziowe nie wymagają wpisu w `.env`: Next.js ustawia `NODE_ENV`, obrazy web wyłączają telemetrię przez `NEXT_TELEMETRY_DISABLED`, uv konfiguruje środowisko w Dockerfile przez `UV_PROJECT_ENVIRONMENT`, `UV_COMPILE_BYTECODE` i `UV_LINK_MODE`, polling HMR ustawiają `WATCHFILES_FORCE_POLLING` oraz `WATCHPACK_POLLING`, a Caddy używa `XDG_DATA_HOME` i `XDG_CONFIG_HOME`. `PATH` jest wewnętrzną zmienną obrazu.

## Migracje

Z katalogu `apps/api`, na przeznaczonej do tego bazie:

```powershell
uv run --frozen --all-groups alembic upgrade head
uv run --frozen --all-groups alembic downgrade base
```

Rewizja `0001_initial_baseline` jest pustą rewizją bazową. Rewizja `0002_database_foundation` tworzy tabele `app_settings` i `audit_log`; nie wdraża tabel sklepu. Przed downgrade upewnij się, że `DATABASE_URL` wskazuje na lokalną bazę deweloperską/testową, nigdy produkcyjną.

### Fundament schematu — etap [07]

Modele leżą w `apps/api/src/sensoria/shared/app_settings.py` i `audit_log.py`. Oba używają wspólnej `Base` oraz `UUIDMixin`; `app_settings` używa też `TimestampMixin`. `Base.metadata` nadaje przewidywalne nazwy `pk_<tabela>`, `fk_<tabela>_<kolumna>_<tabela_docelowa>`, `uq_<tabela>_<kolumna>`, `ix_<tabela>_<pierwsza_kolumna>` i `ck_<tabela>_<nazwa>`. Alembic importuje modele wspólne i przyszłe moduły przed autogeneracją.

- `app_settings`: `id UUID`, unikalny niepusty `key`, niepusty JSONB `value`, `description`, `created_at` i `updated_at` jako `TIMESTAMP WITH TIME ZONE`. JSONB pozwala przechowywać typowane ustawienia (tekst, liczby całkowite, logiczne wartości, obiekty i listy), a baza sprawdza poprawność JSON. Nie zapisuj tu sekretów. Klucze oraz unikalność są walidowane ograniczeniami bazy.
- `audit_log`: UUID `id`, bazowy `created_at`, tekstowy `actor_type` (`customer`, `administrator`, `system`), nullable UUID `actor_id`, tekstowy `entity_type` i UUID `entity_id`, `action` oraz wymagany JSONB `payload`. Para `entity_type`/`entity_id` jest polimorficznym odniesieniem, dlatego nie ma kluczy obcych do jeszcze nieistniejących tabel domenowych. Indeksy obejmują aktora, obiekt, akcję i GIN dla wyszukiwania zawartości JSONB.
- `payload=None` w SQLAlchemy JSONB jest JSON `null`, nie SQL `NULL`; kolumna jest `NOT NULL`. Test sprawdza `IS NULL` oraz `jsonb_typeof`.
- `UUIDMixin` używa `uuid.uuid4` po stronie aplikacji jako callable; nie ma sekwencji ani generatora UUID w DB. `created_at` i początkowe `updated_at` ustala PostgreSQL przez `now()`. Późniejsze `updated_at` ustawia SQLAlchemy `onupdate=func.now()`; bezpośrednie UPDATE poza SQLAlchemy nie aktualizuje znacznika. `audit_log` ma tylko `created_at`, bo rekordy audytowe nie są edytowane.
- Rozszerzenie `pgcrypto` jest instalowane przez migrację, lecz nie generuje UUID. Serwer musi mieć rozszerzenie dostępne, a rola migracyjna uprawnienie `CREATE` do bazy (albo uprawnienia administratora, jeśli hosting ogranicza instalowanie rozszerzeń). Downgrade usuwa tabele i ich indeksy, ale celowo pozostawia rozszerzenie: migracja nie może bezpiecznie ustalić, czy istniało wcześniej lub jest współdzielone.
- `Money` mapuje całkowite grosze na `BIGINT`, odrzuca `float` (także `100.0`) oraz `bool`, i respektuje zakres PostgreSQL. `format_money(44700)` zwraca `447,00 zł` bez arytmetyki zmiennoprzecinkowej. `VatRate` to walidowany tekst, nie natywny ENUM; `EXEMPT` jest różny od `RATE_0`. `Currency` dopuszcza wyłącznie `PLN`.

Migruj wyłącznie dedykowaną bazę aplikacji/testową. Rzeczywisty przebieg w obie strony:

```powershell
Push-Location apps/api
uv run --frozen --all-groups alembic upgrade head
uv run --frozen --all-groups alembic downgrade base
uv run --frozen --all-groups alembic upgrade head
uv run --frozen --all-groups alembic check
Pop-Location
```

Uruchom idempotentny seed z katalogu `apps/api`: `uv run --frozen --all-groups python -m sensoria.seed`. Nie nadpisuje wartości istniejących. Ponieważ specyfikacja i dotychczasowe wymagania nie podają domyślnych wartości ustawień biznesowych, `DEFAULT_SETTINGS` jest pusty; test sprawdza działanie mechanizmu na jawnie przekazanym ustawieniu testowym. Seed nie zapisuje `audit_log`.

## Jakość i testy

Z katalogu głównego:

```powershell
uv sync --project apps/api --frozen --all-groups
Push-Location apps/api
uv run --frozen --all-groups ruff check src/sensoria tests
uv run --frozen --all-groups ruff format src/sensoria tests
uv run --frozen --all-groups ruff format --check src/sensoria tests
uv run --frozen --all-groups mypy --strict src/sensoria tests
uv run --frozen --all-groups pytest
Pop-Location
npm --prefix apps/web run lint
npm --prefix apps/web run format:check
Push-Location apps/web
npx tsc --noEmit
Pop-Location
uv run --project apps/api pre-commit run --all-files
```

Testy integracyjne odczytują `TEST_DATABASE_URL` z głównego `.env` (można go nadpisać zmienną procesu). Wymagają osobnej bazy PostgreSQL 16 o nazwie z końcówką `_test`; nie używają SQLite. Fixture wycofuje transakcję każdego testu, a test migracji sprawdza bazę testową przez upgrade/downgrade/upgrade.

### Modele katalogu — etap [12]

`apps/api/src/sensoria/modules/catalog/` zawiera wspólny model `Product`, typy, walidację publikacji, trwałe slugi oraz seed demonstracyjny. Rodzaje mają tekstową reprezentację `VOUCHER`, `BOOK`, `AUDIOBOOK`, `DIGITAL`; e-book PDF i kurs PDF rozróżnia `DigitalLabel`, pozostając wariantami `DIGITAL`.

Mapowanie rodzaju do etykiety interfejsu: `VOUCHER` → „VOUCHER”, `BOOK` → „KSIĄŻKA”, `AUDIOBOOK` → „AUDIOBOOK”, a `DIGITAL` pokazuje etykietę szczegółów `COURSE_PDF` → „KURS PDF” albo `EBOOK_PDF` → „E-BOOK PDF”. Sama etykieta nie zmienia `ProductKind`.

Migracja `2cd55ccecab2_catalog_products` jest dodana po wydanej rewizji `0002_database_foundation`. Stosuj ją tylko na lokalnej/testowej bazie:

```powershell
Push-Location apps/api
uv run --frozen --all-groups alembic upgrade head
uv run --frozen --all-groups alembic downgrade 0002_database_foundation
uv run --frozen --all-groups alembic upgrade head
Pop-Location
```

Downgrade usuwa tylko tabele i walidatory katalogu. `app_settings`, `audit_log` oraz współdzielone `pgcrypto` pozostają. Nie wykonuj downgrade na produkcji ani na bazie użytkownika.

| Tabela | Zawartość i relacje |
| --- | --- |
| `products` | `id UUID` (aplikacyjny), `kind VARCHAR`, `name VARCHAR(200) NOT NULL`, `slug VARCHAR(180) NOT NULL UNIQUE`, opcjonalne `short_description`, `description`, `price BIGINT`, `compare_at_price BIGINT`, `vat_rate VARCHAR`, status `DRAFT` domyślny w ORM i bazie, opcjonalny `published_at TIMESTAMPTZ`, `sort_order INTEGER NOT NULL DEFAULT 0`, bazowe `created_at`/`updated_at`. Cena i VAT mogą być puste w szkicu; publikacja wymaga poprawnych wartości. `compare_at_price` jest ceną porównawczą, nie najniższą ceną z 30 dni. |
| `product_images` | UUID, FK `product_id → products` z `ON DELETE CASCADE`, URL i alt, pozycja `>=0`; pozycja jest unikalna w obrębie produktu, a galeria sortowana po pozycji. Obrazy są tylko odwołaniami URL — brak uploadu. |
| `product_voucher` | PK=FK produktu, `validity_months INTEGER NOT NULL DEFAULT 12`, nazwa usługi. |
| `product_voucher_variants` | UUID, FK vouchera z kaskadą, stabilne `IN_PERSON`/`ONLINE`, `price BIGINT >=0`, unikalna para voucher/wariant. Gabinet i online to warianty jednego produktu. |
| `product_book` | PK=FK produktu, stan `INTEGER NOT NULL DEFAULT 0` i ograniczenie `>=0`; opcjonalne waga, wymiary i ISBN z kontrolą dodatnich wymiarów. |
| `product_audiobook` | PK=FK produktu, opcjonalny dodatni czas trwania i lektor. |
| `product_audiobook_chapters` | UUID, FK audiobooka z kaskadą, tytuł, dodatnia długość i pozycja; pozycja unikalna w audiobooku. |
| `product_digital` | PK=FK produktu, opcjonalna dodatnia liczba stron, format, wydanie oraz wymagany tekstowy `COURSE_PDF`/`EBOOK_PDF`. |

Typy statusów, rodzaju, wariantu i etykiety cyfrowej są walidowanymi tekstami, nie natywnymi ENUM PostgreSQL. `Money` zapisuje całkowite grosze jako `BIGINT`; `VatRate` używa istniejącego tekstowego typu z [07]. PK=FK wymusza jeden-do-jednego, a klucze obce zależnych tabel mają `ON DELETE CASCADE`. Nazwy ograniczeń korzystają z `Base.metadata.naming_convention`. Odroczone constraint triggery sprawdzają przy zatwierdzaniu transakcji, czy szczegóły pasują do `kind`, a opublikowany produkt ma wymagane pola, obraz i poprawny zestaw szczegółów (w tym stan książki, wariant vouchera i rozdział audiobooka).

`publish_product()` jest centralną ścieżką publikacji: najpierw waliduje komplet danych, potem w savepoincie ustawia `PUBLISHED` i pobiera `published_at` z `now()` PostgreSQL. Niepowodzenie walidacji nie zmienia statusu ani czasu. Nie zmieniaj sluga przy zmianie nazwy; `create_and_publish_product()` obsługuje kolizję przez stabilne sufiksy i bazowe UNIQUE chroni również równoległe zapisy. Właściwości `is_physical`, `is_digital`, `requires_shipping` oraz `is_available` są wyliczane, nie utrwalane. Relacje są `lazy="raise"`; odczytuj je jawnie przez `selectinload`, aby uniknąć niejawnego I/O w async.

Przyjęta klasyfikacja: tylko `BOOK` jest fizyczny i wymaga wysyłki; `AUDIOBOOK` oraz `DIGITAL` są cyfrowe. Voucher oznacza usługę, więc jest nie-fizyczny i niedigitalny. Opublikowana książka jest dostępna tylko przy stanie większym od zera; inne prawidłowo opublikowane rodzaje są dostępne według statusu. Stan magazynowy nie zmniejsza się przy dodaniu do koszyka, lecz dopiero po opłaceniu zamówienia w późniejszym etapie.

Uruchom cztery lokalne produkty demonstracyjne z katalogu `apps/api`:

```powershell
uv run --frozen --all-groups python -m sensoria.modules.catalog.seed
```

Seed dodaje tylko brakujące slugi i nie aktualizuje istniejących wpisów. Nazwy przykładów są podane w opisie zadania. Ceny 25 000/22 000 groszy dla wariantów vouchera również pochodzą z podanych przykładów; cena podstawowa vouchera to najniższy z nich. Ceny 0, `EXEMPT`, stan książki 1, metadane rozdziału, lektor oraz URL-e `example.invalid` są jawnie fikcyjnymi danymi demonstracyjnymi, a nie wartościami z makiet lub specyfikacji. ISBN, wymiary i liczba stron pozostają puste. Pliki odpłatne nie są pobierane ani publikowane. Seed nie jest katalogiem produkcyjnym.

W `docs/makiety/` znajduje się obecnie 18 PDF-ów: makiety 00–12, 16, 18–20 oraz index. Do deklarowanego zestawu 22 brakuje plików 13–15 i 17; `docs/specyfikacja.pdf` również nie jest dostępna. Nie dało się więc potwierdzić danych bibliograficznych, VAT, parametrów fizycznych ani kompletności pól względem pełnej specyfikacji. Przed użyciem oferty produkcyjnej trzeba zastąpić demonstracyjne wartości rzeczywistymi danymi zatwierdzonymi przez właściciela projektu.

Kontrole API: `uv run --frozen --all-groups ruff check src/sensoria tests`, `ruff format --check src/sensoria tests`, `mypy --strict src/sensoria tests` oraz `pytest`. Testy integracyjne wymagają osobnej bazy PostgreSQL 16 z `TEST_DATABASE_URL` zakończonym `_test`.

### Kategorie, odbiorcy i SEO — etap [13]

Rewizja `08f9476a46d2_categories_audience_seo` rozszerza schemat katalogu po rewizji [12]. Dodaje `categories`, `audience_tags`, tabele łączące `product_categories` i `product_audience_tags`, a także pola SEO nullable do `products` i `categories`. Nie zmienia ani nie usuwa wcześniejszych rewizji. Downgrade tej rewizji pozostawia produkty i rewizję [12], usuwa wyłącznie nowe tabele/pola; celowo odmówi downgrade, jeśli opublikowana książka ma stan 0, bo przywróciłoby to poprzednią walidację niezgodną z danymi.

Kategorie i słowniki mają UUID, bazowe znaczniki czasu, unikalne slugi oraz indeksy. FK `parent_id` nie pozwala usunąć rodzica z dziećmi; ograniczenia w migracji blokują samoodniesienie, cykl i drzewa głębsze niż dwa poziomy, także przy bezpośrednim SQL. Powiązania produktu z kategoriami i odbiorcami mają złożony PK, który blokuje duplikat, a oba FK usuwają tylko powiązanie (`ON DELETE CASCADE`), nie sam produkt/kategorię/słownik. Kategorie początkowe są płaskie. Licznik API liczy bezpośrednie przypisania `PUBLISHED` przez `COUNT(DISTINCT products.id)`; nie obejmuje potomków, szkiców ani produktów wycofanych, działa bez cache i nie dołącza galerii/odbiorców do zapytania liczącego.

Seed lokalny uruchom z `apps/api`: `uv run --frozen --all-groups python -m sensoria.modules.catalog.seed`. Dodaje cztery kategorie i trzy słowniki oraz przypisania dla demonstracyjnych produktów [12]. Istniejących nazw, rekordów i relacji nie nadpisuje. Marker w `app_settings` zapisuje, że decyzja seed dla danego demonstracyjnego produktu została wykonana, więc ponowne uruchomienie nie odtwarza ręcznie usuniętych relacji. Dane seed są fikcyjne, nie stanowią oferty.

Publiczne, tylko do odczytu endpointy API:

- `GET /catalog/public/products/{slug}` — wyłącznie `PUBLISHED`, z opisami, galerią, kategoriami, odbiorcami, cenami/wariantami, dostępnością i wyliczonymi metadanymi SEO;
- `GET /catalog/public/categories` — kategorie wraz z licznikiem bezpośrednich, opublikowanych produktów;
- `GET /catalog/public/categories/{slug}` — dane kategorii i wszystkie jej bezpośrednio przypisane opublikowane produkty;
- `GET /catalog/public/sitemap` — wszystkie opublikowane produkty i wszystkie istniejące kategorie z rzeczywistym `updated_at`; brak paginacji.

Frontend zachowuje istniejące adresy i dodaje `/produkt/{slug}` oraz `/kategoria/{slug}`. Jeden generator w `apps/web/lib/catalog-urls.ts` buduje linki katalogu, canonical, Open Graph, JSON-LD i sitemap. Strony pobierają dane rzeczywiście z API przez `API_URL`; metadane i strona używają tego samego memoizowanego odczytu w ramach żądania. Canonical produktu nie zależy od kategorii ani parametrów zapytania. `SITE_URL` jest wymaganym serwerowym publicznym originem, w production musi używać HTTPS. `SITE_OG_IMAGE` to opcjonalny istniejący obraz marki, używany dla kategorii bez własnego obrazu; adresy `.invalid` z fikcyjnego seed są odrzucane jako obrazy publiczne.

`NULL` w `meta_title`, `meta_description` i `og_image` oznacza wartość automatyczną. Tytuł bierze się z nazwy; opis produktu z `short_description`, potem `description`, a przy braku z nazwy produktu. Opis kategorii bierze się z `description`. Opisy usuwają znaczniki HTML, normalizują białe znaki i są skracane na granicy wyrazu w pobliżu 160 znaków. Ponieważ fallbacki są wyliczane przy odczycie, zmiana nazwy/opisu odświeża tylko pola automatyczne; wpisane ręcznie wartości nie są nadpisywane. Obrazu produktu używa się z pierwszego obrazu galerii, chyba że `og_image` ma wartość ręczną. Kategorii brakuje obecnie osobnego obrazu/brand assetu; dopóki nie ustawiono `og_image` lub `SITE_OG_IMAGE`, metadane kategorii nie zawierają obrazu. Nie wygenerowano ani nie wymyślono grafiki zastępczej.

Strony produktów renderują Product i BreadcrumbList JSON-LD, kategorie BreadcrumbList, a strona główna Organization. Cena Schema.org jest dokładnym tekstem dziesiętnym wyprowadzonym z groszy, `priceCurrency` to PLN, a `availability` korzysta z `is_available`; `compare_at_price` nie zastępuje ceny. Różne warianty vouchera są przedstawione jako oddzielne oferty z tymi cenami, które pokazuje strona. Stawka VAT jest opisana przez `additionalProperty` / `PropertyValue`, bez wymyślonej właściwości `vat_rate`; widoczny komponent Price pokazuje również stawkę. `RATE_0` pozostaje odrębne od `EXEMPT`. JSON-LD jest serializowany przez `JSON.stringify` i escapuje znaki mogące zamknąć element `script`.

`/sitemap.xml` jest dynamiczna, pobiera komplet danych przy żądaniu i zwraca błąd zamiast fałszywej pustej mapy, gdy API jest niedostępne. Obejmuje `/`, `/sklep`, `/pomoc`, wszystkie istniejące kategorie i wszystkie opublikowane produkty; wyklucza `/konto`, `/koszyk`, `/zamowienie` i `/dev`. `/robots.txt` zezwala na publiczny sklep, wyklucza powyższe obszary i wskazuje sitemap. Konto, koszyk i zamówienie mają metadane `noindex`. `robots.txt` nie jest kontrolą dostępu i nie gwarantuje usunięcia URL-a z indeksu; nie deklarujemy indeksacji ani rozszerzonych wyników Google. W repo nie ma danych specyfikacji `docs/specyfikacja.pdf`; wpisy seed są demonstracyjne.

### Ceny brutto, VAT i historia cen — etap [14]

`products.price` i `compare_at_price` to kwoty brutto w groszach. `sensoria.shared.pricing.split_gross_price(gross_grosz, vat_rate)` zwraca brutto, netto, podatek, stawkę i etykietę. Dla stawek 23%, 8% i 5% netto jest zaokrąglane do grosza metodą HALF_UP (dokładna arytmetyka całkowitoliczbowa); podatek to różnica brutto minus zaokrąglone netto. Dla `RATE_0` i `EXEMPT` podatek wynosi 0, ale oznaczenia pozostają różne: `0%` oraz `zw.`.

Każda zmiana `price`, `compare_at_price` lub `vat_rate` przez ORM zapisuje kompletny stan w `price_history` i zdarzenie w istniejącym `audit_log` podczas flushu tej samej transakcji. Produkt, historia i audyt cofają się razem przy rollbacku. `price_change_context` przyjmuje autora (`ActorType`, opcjonalne UUID) i wymagany powód per operacja; wykonaj flush wewnątrz kontekstu. Bez niego zmiana jest przypisana do `system` z jawnym powodem systemowym. Nie przekazuj haseł, kluczy ani zbędnych danych osobowych do audytu.

PostgreSQL trigger blokuje zwykłe bulk/raw SQL zmieniające ceny bez aktywnego ORM flush; takie zapisy nie tworzą audytu i są odrzucane. Wartości historyczne można dopisywać, ale nie edytować ani usuwać przez ORM lub trigger. FK `RESTRICT` nie pozwala usunąć produktu z historią; produkt wycofuj statusem `WITHDRAWN`. Trigger jest zabezpieczeniem przed pomyłkową ścieżką zapisu, nie granicą bezpieczeństwa wobec roli DB mogącej wykonywać dowolny SQL. Migracja `f31a9d4b` zapisuje dla istniejących produktów snapshot z rzeczywistym czasem migracji i audyt systemowy; wcześniejszej historii cen nie da się odtworzyć.

`lowest_price_last_30_days(session, product_id, at)` zwraca najniższą obowiązującą cenę brutto z przedziału `[at - 30 dni, at)`, gdzie `at` musi zawierać strefę czasową i jest normalizowane do UTC. Uwzględnia cenę obowiązującą na początku okna nawet wtedy, gdy jej snapshot jest starszy. Zmiana dokładnie w `at` i wpisy przyszłe są pomijane; brak danych zwraca `None`.

Nowa migracja: `uv run --frozen --all-groups alembic upgrade head` z `apps/api`. Weryfikacja integracyjna wymaga oddzielnej bazy PostgreSQL 16 wskazanej przez `TEST_DATABASE_URL` (nazwa zakończona `_test`): `uv run --frozen --all-groups pytest`. Test migracji wykonuje downgrade tylko do rewizji katalogu [12], po czym ponownie aktualizuje bazę; nigdy nie uruchamiaj tego na bazie aplikacji ani produkcyjnej. Migracja odmawia dodania constraintu, jeżeli istnieją rekordy z `compare_at_price <= price` lub z ceną porównawczą przy braku ceny — popraw takie dane świadomie, bez automatycznego przestawiania wartości.

Weryfikacja: `alembic upgrade head`, `alembic downgrade 2cd55ccecab2`, ponownie `alembic upgrade head`; testy backendowe `ruff check`, `ruff format --check`, `mypy --strict`, `pytest`; frontend `npm test`, `npm run lint`, `npm run format:check`, `npx tsc --noEmit`, `npm run build`. Migracje/destrukcyjne kontrole wykonuj tylko na wskazanej, pustej bazie PostgreSQL 16 kończącej się `_test`.

### Publiczne API katalogu — etap [15]

API listy i szczegółów, parametry filtrów, schemat odpowiedzi, przykłady, liczniki, sortowanie, wyszukiwanie FTS, indeksy i ograniczenia cache opisano w [`docs/api-katalogu.md`](docs/api-katalogu.md). Endpointy backendu to `/products` i `/products/{slug}`; przez Caddy dostępne są publicznie pod `/api/products` i `/api/products/{slug}`. Cache TTL steruje opcjonalne `CATALOG_CACHE_TTL_SECONDS` (domyślnie 30 sekund, zakres 0–300, zero wyłącza cache).

## Frontend — etap [03]

Z katalogu głównego zainstaluj zależności z zachowaniem lockfile:

```powershell
npm --prefix apps/web ci
```

Next.js uruchamiany poza Dockerem nie ładuje automatycznie głównego `.env` z tego układu monorepo. Utwórz `apps/web/.env.local` z `ENVIRONMENT=development`, `SITE_URL=http://localhost` oraz niesekretnymi `API_URL=http://localhost:8000` i `NEXT_PUBLIC_API_URL=http://localhost:8000`. Opcjonalnie podaj `SITE_OG_IMAGE` z istniejącym, publicznie osiągalnym obrazem marki. `ENVIRONMENT` i `SITE_URL` są ustawieniami serwerowymi — nie dodawaj ich z prefiksem `NEXT_PUBLIC_`. Compose jawnie ustawia `ENVIRONMENT=development` w override i `ENVIRONMENT=production` w bazowym pliku. `NEXT_PUBLIC_*` jest publiczne i wbudowywane podczas buildu.

Serwer Next.js używa `API_URL` przy pobieraniu statusu backendu w Server Component. W przeglądarce oddzielny klient używa `NEXT_PUBLIC_API_URL`. Przykładowo przyszły kontener Next.js może łączyć się z API pod `API_URL=http://api:8000`; przeglądarka użytkownika potrzebuje publicznego adresu osiągalnego z jego komputera. To opis przyszłej topologii, bez konfiguracji Dockera.

Uruchom backend zgodnie z wcześniejszymi instrukcjami i pozostaw go działającego. W osobnym terminalu z katalogu `apps/web` uruchom:

```powershell
npm run dev
```

### System tokenów wizualnych — etap [08]

Źródłami odczytu kolorów i typografii są `docs/makiety/01-katalog-desktop.pdf` oraz `docs/makiety/08-produkt-ebook-desktop.pdf`. Pięć jednoznacznie wskazanych, oryginalnych PDF-ów skopiowano z `Downloads` bez zmiany zawartości; duplikaty `(1)` miały zgodne sumy SHA-256. Brakuje pozostałych 17 z wymaganych 22 makiet oraz `docs/specyfikacja.pdf`. Kolory interfejsu zapisane są jeden raz w `apps/web/tailwind.config.ts`; CSS i podgląd pobierają je z konfiguracji.

Role `surface`, `surface-muted`, `ink`, `ink-muted`, `accent` i `border` pochodzą z danych wektorowych PDF-ów. Różnice tekstu ujednolicono przez użycie ciemniejszego `ink` `#2a0c18` zamiast `#33101f` i ciemniejszego `ink-muted` `#6e4356` zamiast `#7a5064`. Wspólny akcent marki `#f0568c` ma kontrast 5,51:1 z `ink`; białego tekstu na nim nie używamy (3,27:1). Dodatkowa rola `accent-action` używa źródłowego `#c81e5e` dla akcji i etykiet z białym tekstem (5,52:1). PDF-owa etykieta E-BOOK PDF miała biały tekst na jasnym akcencie; propozycja konfiguracji używa `ink` (5,51:1). Kolor nie zastępuje tekstowej nazwy.

Stany success, warning, danger i info nie występują w dostępnych dwóch PDF-ach. Użytkownik zatwierdził pary `#14532d`/`#dcfce7`, `#854d0e`/`#fef3c7`, `#991b1b`/`#fee2e2` i `#1e40af`/`#dbeafe`; kontrasty wynoszą kolejno 8,30:1, 6,15:1, 6,80:1 i 7,15:1. Podgląd pokazuje też etykiety „AKTYWNY”, „WYGASA WKRÓTCE” i „ZREALIZOWANY”.

PDF-y nie przypisują odrębnych kolorów do pięciu typów produktów. W `/dev/tokeny` oznaczenia pokazują więc pięć jawnych propozycji z istniejącej palety, bez kolorów okładek: `VOUCHER` — biały na `#c81e5e` (5,52:1), `KSIĄŻKA` — `#2a0c18` na `#fff1f5` (16,45:1), `AUDIOBOOK` — `#1e40af` na `#dbeafe` (7,15:1), `KURS PDF` — `#854d0e` na `#fef3c7` (6,15:1), `E-BOOK PDF` — `#2a0c18` na `#f0568c` (5,51:1). Nazwy pozostają widoczne, a przypisania kolorów typów czekają na akceptację. W makiecie e-booka źródłowe białe litery na `#f0568c` miały 3,27:1; konfiguracja stosuje ciemny `ink`.

Gradient stopki z `01-katalog-desktop.pdf` zapisano osobno jako tło powierzchni: biały do `#fffafc`; kontrast tekstu liczony jest na obu końcach. Gradienty na okładkach i grafice produktów wyłączono z palety UI. Przezroczyste obiekty występują w ilustracjach; nie zostały uznane za tła tekstu UI. PDF-y nie dają jednoznacznych tokenów cienia; dwa warianty cienia w konfiguracji są propozycją, nie wartością odczytaną z makiety. Nagłówki działowe w PDF są widocznie rozstrzelone; `letter-spacing: 0,08em` odtwarza ten efekt przez CSS, bez spacji między literami. To wartość robocza do dopasowania po dostarczeniu fontów.

Nazwy rodzin odczytane z osadzonych fontów to DejaVu Sans Bold, Liberation Serif (Regular i Italic) oraz Liberation Sans (Regular i Bold). Pełnych plików fontów nie znaleziono w repozytorium, dlatego nie są jeszcze ładowane przez `next/font/local`; potrzebne są oryginalne pliki z polskimi znakami i prawem do użycia lokalnego. Wartości rozmiarów typografii odtwarzają skalę osadzenia PDF (transformacja 0,75); rodziny pochodzą z PDF, ale subsety fontów osadzone w PDF nie zastępują pełnych plików web.

Breakpoints to `sm: 360px`, `md: 768px`, `lg: 1024px`, `xl: 1280px`; skala odstępów opiera się na 4 px. Zaokrąglenie kart pochodzi z geometrii wektorowej, a cień jest oznaczony jako propozycja, bo PDF-y nie dają jednoznacznego źródła cieni. Nowe wartości dodawaj do konfiguracji Tailwind z opisem źródła; nie wpisuj literalnych kolorów, rozmiarów, cieni ani odstępów do komponentów i CSS.

Po `npm --prefix apps/web ci`, uruchom `npm --prefix apps/web run dev`, a następnie otwórz `http://localhost:3000/dev/tokeny`. Strona odczytuje dane z konfiguracji, liczy kontrast i jest renderowana dynamicznie tylko przy serwerowym `ENVIRONMENT=development`. W Compose tryb development ustawia override; bazowa usługa web ma `ENVIRONMENT=production`, gdzie trasa zwraca 404. Przy uruchomieniu Next poza Compose wpisz `ENVIRONMENT=development` do `apps/web/.env.local`.

Strony są dostępne pod `/`, `/sklep`, `/koszyk`, `/zamowienie`, `/konto` i `/pomoc`. Strona główna pobiera `/health` po stronie serwera, bez cache, przy każdym żądaniu. Przy niedostępnym API wyświetla komunikat po polsku. Podstrony pozostają placeholderami; etap [10] dodaje wspólną ramę nawigacyjną, bez funkcji sklepu.

### Etap [10] — wspólna rama sklepu

Trasy sklepu są w `apps/web/app/(shop)/`; grupa nie zmienia publicznych adresów. Jej layout renderuje pasek informacyjny, nagłówek, nawigację, koszyk i stopkę. Strona tokenów jest w `apps/web/app/(isolated)/dev/tokeny/` i nie otrzymuje ramy sklepu. Grupę `(isolated)` przeznaczono również dla przyszłego panelu administracyjnego, czytnika i odtwarzacza. Root layout nadal zapewnia język dokumentu, metadane i link „Przejdź do treści”; każda strona ma własny, pojedynczy `<main id="main-content">`.

Tekst paska oraz wspólną mapę kategorii i stopki utrzymuje `apps/web/components/layout/site-config.ts`. Kategorie prowadzą do istniejącej trasy `/sklep` z parametrem `typ`; linki pomocy i formalności prowadzą do `/pomoc?temat=...`. Te parametry są punktami na istniejących placeholderach, nie implementują filtrów ani treści prawnych. Nie ma osobnej trasy autora ani stron formalnych w obecnym zakresie.

Licznik koszyka nie pokazuje wartości demonstracyjnej. Ponieważ cookie `cart_token` jest ograniczone do ścieżki `/api/cart`, serwerowy render strony nie otrzymuje tego cookie; po hydratacji `CartCountProvider` pobiera `GET /api/cart` bez cache i przyjmuje wyłącznie potwierdzone `item_count`. Udana mutacja może od razu przekazać kolejny snapshot przez `acceptConfirmedCount()`, a starsze żądanie początkowe nie nadpisze nowszego stanu. Przy niedostępnym API licznik pozostaje opisany jako niedostępny. Rozszerzenie zakresu cookie na całą witrynę wymagałoby osobnej decyzji bezpieczeństwa.

„Ustawienia cookies” ma typowany punkt podłączenia callbacka. Nie ma jeszcze systemu zgód [79]: w development przycisk otwiera wyłącznie demonstrację, a w production pozostaje nieaktywny do podłączenia właściwego mechanizmu. Demonstracja nie zapisuje zgód i nie jest panelem cookies.

Testy i kontrole frontendu uruchamiaj z `apps/web`:

```powershell
npm test
npm run lint
npm run format:check
npx tsc --noEmit
npm run build
```

### Komponenty UI — etap [09]

Wspólne komponenty w `apps/web/components/ui/` korzystają z tokenów [08], zachowują natywne semantyczne elementy i nie wywołują API ani nie zawierają reguł sklepu. W `docs/makiety/` przechowujemy 18 dostępnych PDF-ów projektu; cztery makiety (13–15 i 17) oraz `docs/specyfikacja.pdf` pozostają brakujące. Dostępne makiety wykorzystano jako wzorzec kart, cen, filtrów, pól, zgód i kart wyboru; plików nie zmieniano.

| Komponent                         | Najważniejsze props                                                                                                            | Zachowanie                                                                                                                     |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| `Button`                          | `variant`, `size`, `loading`, `loadingLabel`, standardowe propsy buttona                                                       | `primary`, `secondary`, `text`; `sm`, `md`, `lg`; domyślnie `type="button"`; loading blokuje kliknięcie i ustawia `aria-busy`. |
| `TextField`, `Textarea`, `Select` | `label`, `hint`, `error`, `id`, propsy natywnej kontrolki                                                                      | Automatyczne unikalne ID, etykieta, wymagane pole i połączone opisy; `Select` pozostaje natywny.                               |
| `Checkbox`                        | `label`, `variant`, `title`, `description`, `hint`, `error`, `trailingContent`                                                 | Natywny checkbox w małej etykiecie lub całej klikalnej karcie.                                                                 |
| `Radio`                           | `label`, `name`, `value`, `description`, `hint`, `error`                                                                       | Natywne radio; grupę buduj z `fieldset` i `legend`.                                                                            |
| `RadioCard`                       | `title`, `description`, `name`, `value`, `trailingContent`, propsy radio                                                       | Karta jest etykietą natywnego radio; opcje jednej grupy muszą mieć wspólne `name`.                                             |
| `Badge`                           | `label`                                                                                                                        | Etykiety pięciu typów produktu oraz statusów z przypisaniami kolorów w konfiguracji [08].                                      |
| `Price`                           | `amountInGrosze`, `previousAmountInGrosze`, `vatRate`                                                                          | Formatuje całkowite, bezpieczne grosze bez float; `EXEMPT` pokazuje „zw. z VAT”, `RATE_0` „VAT 0%”.                            |
| `ProductCard`                     | `image`, `imageAlt`, `title`, `description`, `type`, `priceInGrosze`, `previousPriceInGrosze`, `metric`, `href`, `onAddToCart` | Wyświetla typowaną treść i emituje wyłącznie callback; obraz/link/akcję przekazuje rodzic.                                     |
| `Accordion`                       | `items`, `mode`, `defaultExpandedIds`                                                                                          | Domyślnie `single`; opcjonalnie `multiple`; strzałki i Home/End przenoszą fokus. Zamknięty panel ma `hidden`.                  |
| `Modal`                           | `open`, `onOpenChange`, `title`, `children`                                                                                    | Natywny dialog modalny, Escape, pułapka fokusu platformy, przywrócenie fokusu i blokada przewijania tła.                       |
| `Alert`                           | `variant`, `title`, `icon`, `children`                                                                                         | `info`, `success`, `warning`, `error`; błąd jest pilnym `alert`, pozostałe warianty `status`.                                  |
| `Breadcrumbs`                     | `items`, `label`                                                                                                               | Nawigacja z listą, linkami poprzednich poziomów i `aria-current="page"`.                                                       |

Galeria `/dev/tokeny` pokazuje wszystkie warianty i stany, lokalne przykłady produktów, kontrole, ceny, statusy i aktywny modal. Obsługa akordeonu działa dla jednego panelu naraz; można jawnie ustawić `mode="multiple"`. Przykłady nie wysyłają zamówień ani płatności. Kliknięcie demonstracyjnego przycisku pokazuje lokalny komunikat.

Buttony, pola, linki i wybory mają widoczny focus; kontrolki akcji zachowują co najmniej 44 px wysokości klikanej powierzchni. Przyciski ładowania mają stałą powierzchnię spinnera. Komunikaty pól łączą hint, error i dodatkowe `aria-describedby`. Zamknięte panele akordeonu nie przyjmują fokusu. `<dialog>.showModal()` zapewnia modalność oraz klawiaturową pułapkę fokusu przeglądarki; kod przywraca fokus i styl przewijania dokumentu po zamknięciu. Rzeczywisty test przeglądarkowy wykonuje weryfikację natywnej pułapki.

Kwoty należy przekazywać jako całkowite bezpieczne grosze. `formatMoney` nie używa obliczeń zmiennoprzecinkowych. Dane w galerii są lokalnymi przykładami. Testy uruchamiaj poleceniem `npm --prefix apps/web test` (Vitest, Testing Library, jsdom); kontrola w przeglądarce pozostaje osobnym sprawdzeniem dla zachowań natywnego dialogu.

Kontrole i build, z katalogu `apps/web`:

```powershell
npm run lint
npm run format:check
npx tsc --noEmit
npm test
npm run build
```

Kontrole i build, z katalogu `apps/web`:

```powershell
npm run lint
npm run format:check
npx tsc --noEmit
npm test
npm run build
npm run start
```

### Responsywność i dostępność — etap [11]

Nowe ekrany sprawdzaj checklistą `docs/lista-kontrolna-ekranu.md`. Układ ma być mobile-first, nie może przepełniać szerokości 360 px, a tabele na telefonie mają przyjmować postać kart z etykietami wartości. Zasady fokusowania, altów, powiększenia, ograniczenia ruchu i obsługi klawiaturą są w `AGENTS.md`.

Automatyczny skan axe działa na wyrenderowanej aplikacji przez Playwright. Z katalogu `apps/web` po `npm ci` uruchom:

```powershell
npx playwright install chromium
npm run a11y
```

Harness uruchamia lokalny serwer Next na porcie 3102 z `ENVIRONMENT=development` i niedostępnym testowym `API_URL`, sprawdza istniejące trasy sklepu, 404 oraz `/dev/tokeny` przy 360/390/640/768/1024/1280 px (axe skanuje 360 i 1280 px), a następnie otwarte menu, modal i accordion. 640 px to wyłącznie symulacja węższego viewportu przybliżenia 200%, nie rzeczywista zmiana zoomu przeglądarki. Serwer jest zamykany po zakończeniu. W CI zadanie `frontend` instaluje Chromium z zależnościami systemowymi i uruchamia ten sam skan. Naruszenia axe o wpływie `critical` albo `serious` przerywają test; naruszenia `moderate`/`minor` są raportowane, a wyniki `incomplete` oznaczają ręczną ocenę. Nie są wyciszane.

Axe nie potwierdza sensu tekstów alternatywnych, logicznej kolejności czytnika, rzeczywistego zoomu 200% ani wszystkich zachowań z klawiatury. Te elementy wymagają ręcznego sprawdzenia i zapisania w checkliście. Skan WCAG 2.1 A/AA nie jest certyfikacją zgodności z WCAG.

## Kontenery — etap [04]

Wymagany Docker Engine albo Docker Desktop oraz Docker Compose v2.24.4 lub nowszy (override używa tagu `!override`). Z katalogu głównego skopiuj przykład środowiska i ustaw własne wartości lokalne:

```powershell
Copy-Item .env.example .env
# Użyj lokalnych wartości przykładowych albo ustaw własne wartości developerskie.
docker compose config --quiet
docker compose up --build -d
```

Plik `.env` z katalogu głównego jest ignorowany przez Git. Dla production użyj własnych ustawień i losowego `SECRET_KEY` — fikcyjny przykład nie przejdzie walidacji. Compose buduje URL z `POSTGRES_*` i kieruje go do `db`; lokalny `DATABASE_URL` jest używany poza Compose. Ponieważ Compose składa URL bez kodowania, wybieraj dla `POSTGRES_PASSWORD` hasło z bezpiecznych znaków URL, np. wygenerowane przez `secrets.token_urlsafe`.

Domyślne `docker compose up` wczytuje `docker-compose.override.yml`: startuje PostgreSQL 16, API z Uvicorn reload, Next.js dev i Caddy w lokalnym HTTP. Dostępne adresy:

- Frontend przez proxy: `http://localhost`.
- Backend przez proxy: `http://localhost/api/health` (Caddy usuwa `/api` przed przekazaniem do API).
- Bezpośrednie porty developerskie, tylko na komputerze lokalnym: frontend `http://localhost:3000`, API `http://localhost:8000`, PostgreSQL `localhost:5432`.

`API_URL=http://api:8000` jest ustawiane dla serwera Next.js wewnątrz sieci Compose. `NEXT_PUBLIC_API_URL=http://localhost/api` trafia do przeglądarki. Tylko ta publiczna wartość jest argumentem buildu web; zmiana jej wymaga przebudowania obrazu. Sekrety API i ustawienia serwerowe są przekazywane w runtime i nie są kopiowane do obrazu.

Przydatne polecenia z katalogu głównego:

```powershell
docker compose ps
docker compose logs -f api web caddy
docker compose exec api alembic upgrade head
docker compose exec api whoami
docker compose exec api id
docker compose exec web whoami
docker compose exec web id
docker compose exec db id
docker compose exec caddy id
docker compose down
docker compose up -d
```

Healthcheck PostgreSQL używa `pg_isready`; API ma healthcheck HTTP, który wykonuje `/health` i tym samym sprawdza `SELECT 1` w bazie. Obraz DB buduje się z `docker/postgres.Dockerfile`: runtime pozostaje PostgreSQL 16 Alpine z dotychczasowym UID 70, a osobny etap Debian Bookworm dostarcza przypięty słownik `hunspell-pl`. Zachowuje to zgodność właściciela istniejącego wolumenu danych. Migracja tworzy `unaccent`, `pg_trgm`, konfiguracje językowe, wektory, triggery i indeksy. CI instaluje ten sam przypięty pakiet do serwisu PostgreSQL 16 przed testami. Frontend i Caddy ruszają po odpowiednich zależnościach. Migracje uruchamiaj jawnie poleceniem `docker compose exec api alembic upgrade head`; kontener API nie wykonuje ich automatycznie. `docker compose down` zatrzymuje usługi i zachowuje nazwane wolumeny danych PostgreSQL, uploads oraz Caddy. `docker compose down -v` usuwa również nazwane wolumeny zadeklarowane w Compose — nie używaj go jako zwykłego sposobu zatrzymywania projektu.

Kod API, migracje i frontend są montowane do kontenerów developerskich; Caddy przekazuje też WebSocket wymagany przez Next.js HMR. Zależności Pythona i Node.js pozostają w kontenerach/nazwanych wolumenach. API i web działają jako użytkownicy nie-root, Caddy jako UID 10001, a PostgreSQL jako `postgres` z Alpine (UID 70). `id` w powyższych poleceniach pokazuje UID/GID użytkownika `docker exec`, a `docker compose top` pozwala sprawdzić procesy kontenerów.

### Tryb produkcyjny i HTTPS

Uruchom bazowy plik bez developerskiego override (Compose nie czyta wtedy `docker-compose.override.yml`):

```powershell
docker compose -f docker-compose.yml config --quiet
docker compose -f docker-compose.yml up --build -d
```

Ustaw `DOMAIN` na domenę wskazującą na serwer i `NEXT_PUBLIC_API_URL=https://<twoja-domena>/api`, po czym zbuduj obraz web ponownie. Caddy automatycznie uzyskuje i odnawia publiczny certyfikat, gdy DNS domeny wskazuje na serwer, host ma osiągalne porty TCP 80/443 (UDP 443 jest opcjonalny dla HTTP/3), a zapisywalne nazwane wolumeny `/data` i `/config` zachowują stan Caddy. Nie uruchamiaj tego wariantu dla domeny, której nie kontrolujesz.

Migracja w tym wariancie: `docker compose -f docker-compose.yml exec api alembic upgrade head`.

Produkcyjny Caddy kieruje `/api/*` do `api:8000` po usunięciu prefiksu `/api`; pozostałe żądania kieruje do `web:3000`. Nie-root Caddy nasłuchuje wewnątrz kontenera na 8080/8443, mapowanych na standardowe porty hosta 80/443. Nagłówki: HSTS `max-age=31536000` (bez `includeSubDomains` i `preload`), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` oraz `Referrer-Policy: strict-origin-when-cross-origin`. HSTS jest użyteczny wyłącznie po HTTPS; przeglądarka ignoruje tę politykę z odpowiedzi HTTP.

Lokalny wariant HTTPS można uruchomić bazowym plikiem z `DOMAIN=localhost` zamiast automatycznego override. Caddy wystawi wtedy certyfikat z lokalnego CA, nie publiczny certyfikat Let's Encrypt. Komputer użytkownika musi zaufać lokalnemu root CA z wolumenu Caddy (`/data/caddy/pki/authorities/local/root.crt`); bez tego przeglądarka pokaże ostrzeżenie certyfikatu. Domyślny override działa po zwykłym HTTP bez instalowania certyfikatu.

Budowanie używa głównego kontekstu repozytorium, więc aktywnym filtrem jest główny `.dockerignore`; osobne `apps/api/.dockerignore` i `apps/web/.dockerignore` są gotowe dla budowania z kontekstów aplikacji. Oba filtry wykluczają pliki środowiskowe, dane lokalne, artefakty i zależności hosta, pozostawiając pliki lock potrzebne do builda.

Build nie pobiera statusu API, bo strona jest renderowana dynamicznie na żądanie. `npm run start` uruchamia wcześniej zbudowaną aplikację.

## Dokumentacja projektu

- Specyfikacja: `docs/specyfikacja.pdf` — brakujący plik.
- Makiety: `docs/makiety/` — obecnie 5 z wymaganych 22 PDF-ów; pozostałe 17 wymagają dostarczenia.

Nie twórz zastępczych PDF-ów. Dodaj do `docs/` wyłącznie oryginalne, dostarczone materiały.

## Publiczne fragmenty PDF i audio — etap [21]

API udostępnia publiczny fragment produktu cyfrowego lub audiobooka, jeśli produkt jest opublikowany, a jego osobny plik próbki istnieje w magazynie i `sample_enabled` jest włączone. Szczegóły publiczne zwracają jedynie `sample_available` oraz liczbę stron lub czas; nie zwracają klucza ani ścieżki pliku. Trasy za Caddy to `POST /api/products/{slug}/sample/open` i `GET /api/products/{slug}/sample?grant=…`. Otwarcie wymaga jawnej akcji użytkownika; przycisk PDF otwiera podgląd, a audiobook ma odtwarzacz próbki z obsługą Range.

W etapie [38] nie ma jeszcze docelowego magazynu plików. Tymczasowy adapter lokalny `LocalSampleStorage` zapisuje próbki w oddzielnych katalogach `SAMPLE_STORAGE_ROOT/pdf/` i `SAMPLE_STORAGE_ROOT/audio/`; w Dockerze domyślny root to `/app/uploads/samples`, w nazwanym wolumenie `uploads_data`. Pełne płatne pliki nie są rozwiązywane ani serwowane przez ten adapter. W kodzie adaptera jest `TODO [38]` do podłączenia docelowego magazynu. Katalogi dostają tryb `0700`, pliki `0600` na systemach POSIX. Nie umieszczaj żadnego pełnego materiału w `public/`, katalogu próbek ani jego podkatalogach.

Każdy próbny plik trzeba przygotować redakcyjnie osobno — endpoint nie wycina fragmentu z pełnej publikacji. Dla PDF przygotuj plik, w którym stopka jest częścią każdej strony i brzmi dokładnie: „Fragment bezpłatny · pełna wersja dostępna w sensoria.shop”. Obejrzyj wyrenderowane strony przed instalacją. Następnie z katalogu `apps/api` włącz go do magazynu i ustaw metadane produktu:

```powershell
uv run --frozen --all-groups python -m sensoria.modules.catalog.sample_cli --slug <slug-produktu> --file <ścieżka-do-przygotowanego-fragmentu.pdf> --kind pdf --pages <liczba-stron>
uv run --frozen --all-groups python -m sensoria.modules.catalog.sample_cli --slug <slug-audiobooka> --file <ścieżka-do-przygotowanego-fragmentu.mp3> --kind audio --duration-seconds <liczba-sekund>
```

CLI sprawdza typ pliku, kopiuje go pod losową nazwę UUID do przestrzeni właściwego rodzaju i zapisuje klucz wewnętrzny w podtypie produktu. Nie podawaj pełnego pliku. W Compose API potrzebuje prawa zapisu do nazwanego `uploads_data`; nie montuj go do Caddy ani web. Przy uruchomieniu lokalnym bez Dockera ustaw `SAMPLE_STORAGE_ROOT` na prywatny katalog w `apps/api` i nie dodawaj go do Git. Ustawienia limitów i zaufanego proxy znajdują się w głównym `.env.example`.

Otwarcie liczy się po `POST /open`, gdy produkt i plik próbki są dostępne. `X-Sample-Open-Id` z UUID deduplikuje ponowienie tej samej akcji przez okres sesji; nowe świadome otwarcie używa nowego identyfikatora. Licznik produktu aktualizuje się atomowo w PostgreSQL. Żądania `GET`/Range nie zwiększają licznika otwarć, ale zużywają osobny limit transferów i limit żądań krótkiej sesji; endpoint nie obsługuje `HEAD`. Limit domyślny to 12 otwarć na IP na 60 sekund, 120 transferów na IP na 60 sekund, maksymalnie 24 transfery w 30-minutowej sesji. Limity są przechowywane w PostgreSQL, więc są wspólne dla workerów; klucze IP są HMAC, a stare okna są usuwane podczas obsługi kolejnych żądań.

Adres klienta pochodzi z połączenia bezpośredniego. `X-Forwarded-For` jest honorowany tylko wtedy, gdy bezpośredni peer należy do `TRUSTED_PROXY_CIDRS`; tę listę należy ustawić zgodnie z rzeczywistą siecią zaufanego reverse proxy. Nie ustawiaj jej na zakresy, z których mogą łączyć się niezaufani klienci. Przy błędnej konfiguracji nagłówki przekazywane są ignorowane.

Przeglądarkowy czytnik PDF może udostępniać własną funkcję zapisania publicznego fragmentu — nie jest to blokowane ani obiecywane jako niemożliwe. Chroniony pozostaje pełny materiał, który musi być przechowywany poza przestrzenią próbek. Aktualnie nie dostarczono redakcyjnego fragmentu żadnego produktu ani docelowego magazynu [38]. Pliki `apps/api/tests/fixtures/sample-fragment-fixture.pdf` i `sample-audio-fixture.mp3` są wyłącznie fixture testowymi; PDF ma widoczną stopkę w samym pliku i nie stanowi fragmentu prawdziwego produktu.

## CI — etap [05]

Workflow `.github/workflows/ci.yml` uruchamia się przy każdym pull requeście oraz przy pushu do `main`. Trzy zadania (`backend`, `frontend`, `docker`) działają równolegle. Starszy przebieg tego samego PR może zostać anulowany; przebiegi różnych PR-ów mają oddzielne grupy. Workflow ma tylko uprawnienie `contents: read`.

- **backend** przygotowuje Python 3.12 i uv, instaluje zależności z `uv.lock` bez aktualizacji, uruchamia Ruff lint i format check, mypy strict oraz pytest. Testy używają serwisu PostgreSQL 16. Tworzone są osobne bazy `sensoria` i `sensoria_test`; fikcyjne dane służą wyłącznie temu jobowi.
- **frontend** używa Node.js 22 i `npm ci` z `apps/web/package-lock.json`, a następnie ESLint, Prettier `--check`, `tsc --noEmit` i build Next.js. API URL-e są fikcyjne; build nie zależy od API.
- **docker** buduje produkcyjne targety `runtime` z `docker/api.Dockerfile` i `docker/web.Dockerfile`, używając kontekstu głównego repozytorium. Nie publikuje obrazów. Wartość `NEXT_PUBLIC_API_URL` jest publicznym adresem testowym.

Cache zależności uv jest kluczowany względem `apps/api/uv.lock`; cache npm korzysta z `apps/web/package-lock.json` i nie zawiera `node_modules`. BuildKit używa osobnych cache dla obrazów API i web. Instalacje nadal respektują lockfile (`uv sync --frozen`, `npm ci`).

Lokalne odpowiedniki kontroli (z katalogu głównego, poza testem pytest wymagającym PostgreSQL 16 i ustawionych `DATABASE_URL`, `TEST_DATABASE_URL`, `ENVIRONMENT`, `SECRET_KEY`):

```powershell
uv sync --project apps/api --frozen --all-groups
Push-Location apps/api
uv run --frozen --all-groups ruff check src/sensoria tests
uv run --frozen --all-groups ruff format --check src/sensoria tests
uv run --frozen --all-groups mypy --strict src/sensoria tests
uv run --frozen --all-groups pytest
Pop-Location
npm --prefix apps/web ci
npm --prefix apps/web run lint
npm --prefix apps/web run format:check
Push-Location apps/web; npx tsc --noEmit; Pop-Location
npm --prefix apps/web run build
docker build --file docker/api.Dockerfile --target runtime --tag sensoria-api:local .
docker build --file docker/web.Dockerfile --target runtime --build-arg NEXT_PUBLIC_API_URL=https://example.invalid/api --tag sensoria-web:local .
```

### Ręczna ochrona gałęzi `main`

Workflow sam nie włącza ochrony gałęzi. W repozytorium GitHub otwórz **Settings → Rules → Rulesets** i utwórz aktywny ruleset dla gałęzi `main`. Nie dodawaj aktorów do listy bypass. Włącz wymaganie pull requestów, wymagane status checks `backend`, `frontend` i `docker`, blokadę force push oraz ochronę przed usunięciem. Nie wymagaj akceptacji drugiej osoby. Jeśli interfejs oferuje opcję bypass dla administratorów, pozostaw ją wyłączoną. W klasycznej ochronie gałęzi ustaw odpowiednik tych reguł i włącz zastosowanie także do administratorów.

Nazwy status checks mogą pojawić się na liście dopiero po pierwszym przebiegu Actions. Po zapisaniu reguł sprawdź ich aktywność w ustawieniach GitHub. Sam plik workflow ani lokalne wykonanie kontroli nie potwierdzają, że `main` jest chronione.

## Strona główna — etap [22]

Strona `/` jest serwerowym komponentem w `apps/web/app/(shop)/page.tsx`, opakowanym wspólnym layoutem sklepu z [10]. Jej treści redakcyjne pochodzą z whitelisted, typowanego `GET /catalog/public/homepage`; endpoint zwraca wyłącznie dozwolone pola z `app_settings`, a nie całą tabelę. Wpis `homepage.content.v1` jest dodawany idempotentnie przez `uv run --frozen --all-groups python -m sensoria.seed` z katalogu `apps/api`; późniejsza wartość ustawiona w bazie nie jest nadpisywana. Przy braku wpisu endpoint zwraca zatwierdzone domyślne treści strony.

Produkty kompozycji są pobierane zbiorczo przez `GET /products` z filtrem rodzaju, a polecane przez osobne zbiorcze żądanie `sort=recommended`. Strona wybiera tylko produkty publiczne zwrócone przez API; identyfikatory w ustawieniach są opcjonalnym wskazaniem redakcyjnym, a po wycofaniu lub zmianie rodzaju następuje deterministyczny fallback do pierwszego produktu danego rodzaju. Nie ma twardo wpisanych nazw, slugów ani cen. Brak produktu nie tworzy fikcyjnej karty.

Sekcja polecanych korzysta z `ProductCard`. Dodawanie do koszyka jest nadal niedostępne do czasu etapu [24]; interfejs pokazuje tę informację i nie udaje sukcesu. Cztery obietnice są konfigurowalną treścią redakcyjną, ale ich obecność nie dowodzi uruchomienia płatności ani dostaw, które pozostają poza zakresem.

JSON-LD strony używa współdzielonych generatorów `Organization` i `WebSite`, publicznego `SITE_URL` oraz stabilnych identyfikatorów. Nie dodaje `SearchAction`. W `apps/web/public` nie ma zatwierdzonego logo, więc nie jest ono deklarowane w schemacie.

## Brak wyników katalogu — etap [23]

Po udanym wyszukiwaniu lub zastosowaniu filtrów z `total = 0` strona `/sklep` pokazuje stan pusty z edytowalnym polem zapytania, redakcyjnymi podpowiedziami z publicznej allowlisty `app_settings`, opcjonalnym kontaktem oraz rekomendacjami `suggestions.related_products` z API. `total > 0` przy pustej stronie jest odrębnym stanem paginacji; błąd API i loading również pozostają odrębne. Szczegóły konfiguracji, zachowanie „Wyczyść filtry” i lokalne testy opisano w [docs/stan-braku-wynikow.md](docs/stan-braku-wynikow.md).

## Koszyk trwały — etap [24]

Koszyk gościa jest przechowywany w PostgreSQL (`carts`, `cart_items`), a nie w przeglądarce. `GET /api/cart` zwraca pustą odpowiedź bez tworzenia rekordu, jeśli brak poprawnego cookie. Pierwszy `POST /api/cart/items` tworzy koszyk i ustawia `cart_token`: losowy token w cookie `HttpOnly`, `Secure`, `SameSite=Lax`, z `Path=/api/cart`, ważny 30 dni. Baza przechowuje wyłącznie SHA-256 tokenu; `expires_at` jest ustawiane przez PostgreSQL na `now() + interval '30 days'` i nie jest przedłużane odczytem. Zarówno cookie, jak i rekord koszyka wygasają według tego samego okresu. `DELETE /api/cart` usuwa pozycje, zachowując pusty koszyk i dotychczasowy termin ważności.

Domyślny developerski Caddy działa po HTTP, więc przeglądarka nie odeśle mu cookie `Secure`. Do ręcznego testu przeglądarkowego uruchom bazowy Compose bez override, ustaw `DOMAIN=localhost`, otwórz `https://localhost/api/cart` i zaakceptuj lokalny certyfikat zaufanego lokalnego CA Caddy. Testy API używają klienta HTTPS i jawnie odsyłają cookie w nagłówku. Cookie pozostaje `Secure` także w development; nie wyłączaj tej flagi. Bezpośredni adres backendu nie przechodzi przez publiczną ścieżkę cookie `/api/cart`.

Cena i VAT pochodzą z bieżącego produktu/wariantu i są zapisywane w snapshotach w groszach. Serwer odrzuca pola ceny/VAT z żądania. Książki scalają się w jedną pozycję i sumują ilość, z blokadą rekordu produktu przy kontroli stock. `DIGITAL` i `AUDIOBOOK` przyjmują wyłącznie ilość 1 i są deduplikowane. Każde świadome dodanie `VOUCHER` tworzy osobną pozycję ilości 1. Zmiana ilości nie odświeża snapshotu; rozliczenie w odpowiedzi koszyka jest wyliczane ponownie wyłącznie z snapshotów.

Endpointy to `GET /api/cart`, `POST /api/cart/items`, `PATCH /api/cart/items/{id}`, `DELETE /api/cart/items/{id}` i `DELETE /api/cart`. Id koszyka i `customer_id` nie są przyjmowane od klienta. `PATCH`/`DELETE` sprawdzają, czy pozycja należy do koszyka z cookie; dla obcego albo nieznanego ID zwracają ten sam 404. Koszyki konta mają przygotowane pole UUID `customer_id`, na razie bez FK, ponieważ moduł kont nie ma modelu klienta.

`merge_guest_cart_after_login(session, guest_token=..., authenticated_customer_id=...)` jest transakcyjną usługą dla przyszłego handlera logowania. Wywołujący musi przekazać ID z już zweryfikowanego principalu, nigdy z danych requestu. Blokada doradcza serializuje tworzenie koszyka danego konta, a rekordy koszyków i produktów są blokowane w transakcji. Konflikt dostępności lub przekroczenie stock powoduje rollback całości i pozostawia koszyk gościa do korekty. Po sukcesie zachowywany jest snapshot istniejącej pozycji konta, nowe pozycje zachowują snapshot gościa, osobne vouchery są przenoszone, a koszyk gościa z tokenem zostaje usunięty. Wynik zawiera identyfikatory pozycji, których snapshoty różniły się między koszykami. Ponowienie z dawnym tokenem jest bezpiecznym no-op.

Moduł `accounts` nie ma jeszcze logowania ani tożsamości klienta. Dlatego automatyczne wywołanie usługi po prawdziwym logowaniu pozostaje niepodłączone i nie należy traktować koszyka konta jako dostępnego dla użytkownika.

Wygasłe koszyki gości usuwa cykliczne zadanie uruchamiane w lifespanie API. Każdy worker wykonuje je co `CART_CLEANUP_INTERVAL_SECONDS` (domyślnie 3600 s), z limitem `CART_CLEANUP_BATCH_SIZE` (domyślnie 500). `FOR UPDATE SKIP LOCKED` rozdziela rekordy między workery i nie pozwala usunąć koszyka zablokowanego przez scalanie. Jednorazowo można też uruchomić `uv run --frozen --all-groups python -m sensoria.modules.orders.cleanup` z katalogu `apps/api`. Testy integracyjne koszyka: `uv run --frozen --all-groups pytest tests/test_cart.py`; wymagają izolowanej bazy PostgreSQL 16 wskazanej przez `TEST_DATABASE_URL` z nazwą kończącą się `_test`.

### Kalkulator koszyka — etap [25]

`GET /api/cart` i odpowiedzi po dodaniu lub zmianie ilości zawierają pole `calculation`. `CartCalculator` czyta `unit_price_snapshot`, `vat_rate_snapshot` i ilość każdej pozycji; nigdy nie pobiera aktualnej ceny z katalogu. Kwoty są całkowitymi groszami. Dla każdej pozycji najpierw oblicza brutto (`snapshot × quantity`) i dzieli je istniejącym `split_gross_price` metodą HALF_UP. Następnie po stawkach procentowych liczy kontrolne netto od sumy brutto. Różnicę rozdziela między pozycje według malejącego brutto, a przy remisie rosnącego UUID. `rounding_adjustment_grosz` jest podpisaną zmianą netto w groszach; podatek pozycji zmienia się o przeciwną wartość. Grupy 23%, 8%, 5% i 0% są osobne. `EXEMPT` pozostaje poza grupami procentowymi, z netto równym brutto, podatkiem 0 i oznaczeniem `zw.`.

Pole `delivery` jest osobnym wierszem rozliczenia. Przy fizycznym koszyku bez wybranej metody zwraca wyceny, ale `amount_due_is_final=false`; UI nie może nazywać subtotalu produktów kwotą końcową. Koszt i VAT są odczytywane z ustawień `app_settings` przez etap [27]. Kalkulator odrzuca płatną dostawę bez jawnego rozliczenia VAT.

`CartCalculation` jest wersjonowanym, serializowalnym kontraktem snapshotu zamówienia; checkout utrwala wynik obok zamówienia i pozycji w jednej transakcji. Zmiana ilości powoduje przeliczenie od podstaw, nie inkrementalną korektę wcześniejszego wyniku. Frontend tylko formatuje kwoty zwrócone przez API.

Testy kalkulatora (w tym 1000 powtarzalnych koszyków losowych) uruchamiaj w `apps/api`: `uv run --frozen --all-groups pytest tests/test_cart_calculator.py tests/test_cart.py`. Testy integracyjne `test_cart.py` wymagają odrębnej bazy PostgreSQL 16 `_test` zgodnie z konfiguracją testów.

### Kody rabatowe — etap [26]

Kody rabatowe zapisują się w `discount_codes`; jeden koszyk może mieć jeden przypisany kod. Kwoty i progi są w groszach, a `percentage.value=10` oznacza 10%. API `POST /api/cart/discount` weryfikuje kod dla aktualnego koszyka i zwraca nowe serwerowe rozliczenie; `DELETE /api/cart/discount` odłącza kod. Próg minimalny dotyczy brutto produktów przed rabatem i nie obejmuje dostawy. Reguły alokacji rabatu i użycia po płatności opisuje [docs/kody-rabatowe.md](docs/kody-rabatowe.md).

`used_count` nie rośnie podczas użycia kodu w koszyku ani utworzenia zamówienia oczekującego. Checkout rezerwuje limit do wygaśnięcia zamówienia; `record_paid_discount_use` nadal wymaga zaufanej integracji płatności [32]. Zamówienie utrwala użyty kod i kalkulację.

### Wycena dostawy — etap [27]

Koszyk wymaga przesyłki tylko wtedy, gdy zawiera produkt fizyczny (`BOOK`). Koszyk pusty i wyłącznie cyfrowy nie pokazuje sekcji dostawy ani komunikatu o progu. Podstawa progu to suma wszystkich produktów po rabacie, w tym cyfrowych, bez dostawy; dokładne osiągnięcie progu kwalifikuje do darmowej dostawy (`>=`). Zachęta pojawia się tylko, gdy brakująca kwota jest dodatnia i mniejsza od jawnie skonfigurowanej granicy.

Konfiguracja jest wpisem `app_settings` o kluczu `orders.delivery.v1`: `parcel_locker_cost_grosz`, `courier_cost_grosz`, `free_shipping_threshold_grosz`, `incentive_threshold_grosz` (wszystkie grosze jako int) oraz `vat_rate` (`VatRate`). Wartości są walidowane i odczytywane bez cache, więc edycja działa bez wdrożenia. Brak lub błędny wpis daje kontrolowany błąd dla koszyka fizycznego; nie oznacza darmowej przesyłki. Koszty przewozu i VAT nie zostały dotąd zatwierdzone w projekcie, dlatego wymagają uzupełnienia przez operatora przed użyciem wysyłki. `5000` groszy jako granica zachęty jest propozycją, nie wymaganiem biznesowym. Szczegóły kontraktu, wiadomości i testów znajdują się w [docs/dostawa-koszyka.md](docs/dostawa-koszyka.md).

`PATCH /api/cart/delivery` przyjmuje `parcel_locker`, `courier` albo `pickup_in_person` (odbiór w gabinecie, zawsze bezpłatny); kosztu ani VAT klient nie przesyła. Bez wyboru metoda jest wymagana, a kwota pozostaje nieostateczna. Wybór jest zapisywany razem z koszykiem i przenoszony przy scalaniu koszyków, o ile koszyk konta nie ma już metody. Kurier wymaga adresu, Paczkomat — potwierdzonego punktu InPost, odbiór w gabinecie — żadnych danych adresowych.

### Checkout gościa — etap [29]

`/zamowienie` składa gościnne zamówienie przez `POST /api/cart/checkout`, identyfikowane istniejącym HttpOnly cookie koszyka. Backend waliduje cenę/VAT snapshotów, dostępność, stock, rabat, zgodę i dane warunkowe, a w jednej transakcji zapisuje oczekujące zamówienie, pozycje, rozliczenie, rejestr zgód oraz 30-minutowe rezerwacje. Ten sam klucz idempotencji i ten sam payload zwracają to samo zamówienie. Scheduler API zwalnia wygasłe rezerwacje. Szczegóły oraz ograniczenia integracji płatności, dostawy i wydania cyfrowego opisuje [docs/checkout.md](docs/checkout.md). Po utworzeniu zamówienia odpowiedź zawiera `access_token` (HMAC z `SECRET_KEY`, nie jest zapisywany); płatność uruchamia `POST /api/payments/orders/{id}/session?token=…` (Stripe Checkout). Wydanie odroczone po 14 dniach nie jest dostępne — zamówienie z treścią cyfrową wymaga zgody na natychmiastowe udostępnienie.

## Płatności, dostęp do treści, dokumenty i poczta — etapy [32]–[63]

* **Płatności (Stripe)** — `modules/payments`: sesja Stripe Checkout (BLIK, karta, Google/Apple Pay), webhook z weryfikacją podpisu i czasu, idempotencja po `event.id`, kontrola kwoty i waluty, ponowienie nieudanej płatności, strona `/zamowienie/potwierdzenie`. Zamówienie staje się `paid` wyłącznie z webhooka — w jednej transakcji z magazynem, rabatem, voucherami, uprawnieniami, dokumentem i kolejką maili. Konfiguracja: `STRIPE_*` w `.env`; bez nich płatności są wyłączone.
* **Treści cyfrowe** — `modules/library`: uprawnienia (`entitlements`), prywatny magazyn plików, linki pobrania (24 h, 5 użyć, odnawialne), znakowanie PDF danymi nabywcy, biblioteka konta (`/konto/biblioteka`), czytnik (`/konto/czytnik/{id}`) i odtwarzacz audiobooków z Range i zapamiętywaniem postępu (`/konto/odtwarzacz/{id}`). Goście wchodzą linkiem z maila (`?order_token=`).
* **Vouchery** — PDF z kodem QR generowany przez worker (`vouchers/pdf_worker.py`), publiczne sprawdzenie `/voucher/{kod}` (limit zapytań), prezenty dwuetapowo (ważność liczy się od przyjęcia wiadomości przez dostawcę poczty).
* **Dokumenty** — `modules/documents`: paragon i faktura VAT z numeracją bez luk (`PAR/2026/00001`, `FV/…`), PDF z czcionką DejaVu (polskie znaki). Dane sprzedawcy w panelu → Ustawienia.
* **Poczta** — `modules/mail`: outbox z idempotencją, szablony (potwierdzenie, nieudana płatność, dostęp, voucher, prezent, wysyłka, odbiór, przypomnienie, prośba o opinię, alerty, konto), transport SMTP, worker z ponowieniami (1 min → 12 h), mosty z kolejek innych modułów. Konfiguracja `SMTP_*`, `MAIL_FROM`; bez nich wiadomości czekają w outboxie.

## Panel, opinie, obsługa klientek i zgodność — etapy [64]–[90]

* **Panel** (`/admin`) — logowanie i role (właścicielka/obsługa), pulpit, zamówienia (wysyłka, odbiór, notatki, ponowny dostęp), produkty (pliki, rozdziały, zdjęcia, stan), vouchery (realizacja, rejestr, przedłużanie), klienci, kody rabatowe, strony i FAQ, raporty z CSV, opinie, zgłoszenia, ustawienia, dziennik. Instrukcja: [docs/instrukcja-panelu.md](docs/instrukcja-panelu.md).
* **Opinie** — tylko z potwierdzonego zakupu, moderacja, prośba o opinię po zgodzie (`review_requests`), ocena w danych strukturalnych tylko z prawdziwych opinii.
* **Prawo i obsługa** — odstąpienie od umowy (14 dni, wyłączenie dla treści cyfrowych ze zgodą), zwroty i reklamacje, najniższa cena z 30 dni (Omnibus), baner cookies z rejestrem zgód, strony prawne i „o autorce” z panelu, centrum pomocy z wyszukiwarką.
* **Bezpieczeństwo i operacje** — [docs/bezpieczenstwo.md](docs/bezpieczenstwo.md), [docs/operacje.md](docs/operacje.md) (kopie zapasowe na Dysk Google, monitoring, alerty, dzienniki), [docs/wdrozenie-vps.md](docs/wdrozenie-vps.md), [docs/audit/wcag-2.1-aa.md](docs/audit/wcag-2.1-aa.md), przekazanie i szkolenie: [docs/przekazanie-kodu.md](docs/przekazanie-kodu.md).

## Git

Gałąź główna to `main`; gałęzie robocze używają `feat/*` lub `fix/*`. Stosujemy Conventional Commits: `feat:`, `fix:`, `chore:`, `docs:` i `test:`. `.gitignore` ignoruje `.env`, ale nie chroni przed `git add -f` ani nie usuwa sekretów wcześniej śledzonych lub zapisanych w historii. Jeśli sekret został wypchnięty, unieważnij go i wygeneruj nowy; samo usunięcie pliku nie czyści historii. Nie wykonuj rotacji ani przepisywania historii automatycznie.

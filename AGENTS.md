# Instrukcje projektu

## Stack i wersje

- Python 3.12, FastAPI, SQLAlchemy 2.0 w trybie async, asyncpg i Alembic — API.
- Next.js 15 i TypeScript — frontend.
- PostgreSQL 16 — baza danych.
- uv — jedyny menedżer zależności i środowiska Python; manifest i lockfile: `apps/api/pyproject.toml` oraz `apps/api/uv.lock`.
- Docker Compose: PostgreSQL 16, API, Next.js i Caddy; Caddy obsługuje TLS dla publicznej domeny. Konfiguracja developerska jest domyślnym override.
- Obrazy API i web są wieloetapowe; runtime działa jako użytkownik nie-root. Obraz web używa Node.js 22, zgodnego z Next.js 15.

Nie zmieniaj głównych wersji stosu bez polecenia.

## Struktura katalogów

- `apps/api/src/sensoria/` — pakiet API w układzie src: konfiguracja, aplikacja, baza, obsługa błędów i moduły.
- `apps/api/src/sensoria/modules/catalog/` — produkty, kategorie, odbiorcy, SEO, publiczne filtrowanie oraz PostgreSQL FTS.
- `apps/api/src/sensoria/modules/orders/` — trwały koszyk gościa oraz punkt integracji scalania koszyka po logowaniu; zamówienia pozostają poza zakresem.
- `apps/api/src/sensoria/modules/{payments,vouchers,accounts,admin}/` — szkielety bez implementacji płatności, voucherów, klientów, logowania ani administracji.
- `apps/api/src/sensoria/shared/` — elementy wspólne, m.in. błędy domenowe i schematy odpowiedzi.
- `apps/api/alembic/` — środowisko migracji i rewizje; nie zmieniaj wydanych rewizji.
- `apps/api/tests/` — testy backendu. Testy integracyjne używają oddzielnego PostgreSQL wskazanego przez `TEST_DATABASE_URL`.
- `apps/web/` — frontend Next.js.
- `apps/web/app/` — Next.js 15 App Router i polskie trasy.
- `apps/web/components/`, `apps/web/lib/` i `apps/web/types/` — komponenty, klienty API i typy frontendu.
- `apps/web/app/(shop)/produkt/[slug]/` i `kategoria/[slug]/` — minimalne serwerowe widoki danych opublikowanego produktu i kategorii; `app/sitemap.ts` oraz `app/robots.ts` generują dynamiczne dokumenty SEO.
- `apps/web/components/layout/` — wspólna rama sklepu, mapa linków, pasek informacyjny oraz adaptery licznika koszyka i zgód.
- `apps/web/app/(shop)/` — publiczne trasy opakowane ramą sklepu; route group nie zmienia URL-i.
- `apps/web/app/(isolated)/` — strony bez nagłówka i stopki sklepu, w tym `/dev/tokeny`; przeznaczone też dla przyszłych obszarów admina, czytnika i odtwarzacza.
- `docs/` — specyfikacja i dostarczone makiety; nie zmieniaj ich zawartości.
- `docker/` — Dockerfile API, web i Caddy oraz konfiguracje Caddy dla produkcji i lokalnego HTTP.
- `docker-compose.yml` — cztery usługi, wspólna sieć, healthchecki i nazwane wolumeny.
- `docker-compose.override.yml` — targety developerskie, montowanie kodu i porty lokalne.
- `.dockerignore` — filtr głównego kontekstu budowania; `apps/*/.dockerignore` przeznaczone są dla przyszłych kontekstów ograniczonych do aplikacji.
- `.github/workflows/ci.yml` — równoległe kontrole backendu, frontendu i produkcyjnych obrazów Docker dla PR oraz pushy do `main`.

## Konwencje nazewnicze

- Python: `snake_case` dla modułów, funkcji i zmiennych; klasy `PascalCase`.
- TypeScript: `camelCase` dla funkcji i zmiennych; typy, klasy i komponenty React `PascalCase`.
- URL-e: `kebab-case`.
- Stosuj też standardowe konwencje danego języka.

## Baza i sesje

- Używaj SQLAlchemy 2.0 async z asyncpg. Współdzielone mogą być engine i fabryka sesji; każda operacja/żądanie dostaje własną `AsyncSession`, zamykaną po użyciu.
- Deklaracje ORM typuj `Mapped[...]` i `mapped_column()`. Nie używaj starego wzorca `Column` jako atrybutu modelu.
- Modele dziedziczą po wspólnej `sensoria.database.Base`; używają `UUIDMixin` i `TimestampMixin` tam, gdzie pasują. `Base.metadata` ma naming convention dla `pk`, `fk`, `uq`, `ix` i `ck`.
- UUID kluczy głównych generuje aplikacja przez callable `uuid.uuid4`; nie dodawaj sekwencyjnych ID ani generatora UUID w PostgreSQL.
- Znaczniki czasu mają typ z timezone i źródło bazodanowe `now()`. `updated_at` ma `onupdate=func.now()`, które obsługuje zapisy SQLAlchemy, ale nie bezpośrednie SQL poza ORM.
- Kwoty mapuj jako `Money` na PostgreSQL `BIGINT`; odrzucaj `float` i `bool`. VAT `RATE_0` i `EXEMPT` są odrębnymi wartościami; typ VAT jest tekstowy, nie PostgreSQL ENUM. Jedyna waluta to PLN.
- Nie twórz `AsyncSession` jako globalnego singletonu.
- Publiczne API katalogu wystawia `/products` i `/products/{slug}`; w Compose publiczny prefiks `/api` usuwa Caddy. Ceny w query są groszami, parametry SQL pozostają parametryzowane, a sortowanie korzysta z jawnej mapy zakończonej `id`.
- Katalog publiczny obejmuje wyłącznie produkty `PUBLISHED` z `published_at <= now()`. Relacje ładuj jawnie eager loadingiem; nie ujawniaj chronionych plików cyfrowych.
- Cache listy ma krótki TTL (`CATALOG_CACHE_TTL_SECONDS`), kluczujący wszystkie filtry i paginację. Jest procesowy; ORM unieważnia po commit. Nie deklaruj spójności wielu workerów ani zapisów poza ORM.
- Schemat bazy zmieniaj przez Alembic. Nie używaj `create_all()` zamiast migracji.
- Nie modyfikuj już wydanych migracji. Zmiany schematu wprowadzaj nową rewizją.
- Migracje uruchamiaj wyłącznie na właściwie wskazanej bazie. Nigdy nie wykonuj downgrade na produkcji.
- Obecna rewizja bazowa jest celowo pusta, bo nie ma jeszcze modeli domenowych.
- Rewizja `0002_database_foundation` tworzy wyłącznie `app_settings` i `audit_log`; nie zmieniaj wydanych rewizji.
- Rozszerzenie `pgcrypto` jest instalowane przez migrację, ale UUID nadal generuje aplikacja. Downgrade zachowuje rozszerzenie, bo może być współdzielone lub istnieć przed migracją.

## Publiczne fragmenty produktów

- Fragment PDF/audio jest osobnym, redakcyjnie przygotowanym plikiem; nie wycinaj go na żądanie z pełnego materiału.
- Tymczasowy adapter `sensoria.modules.catalog.sample_storage.LocalSampleStorage` ma osobne przestrzenie `samples/pdf` i `samples/audio`, losowe klucze UUID oraz blokuje traversal i symlinki. Pełnych plików nie umieszczaj w katalogu publicznym ani magazynie próbek. Docelowy adapter należy podłączyć w etapie [38]; bieżące miejsce ma oznaczenie `TODO [38]`.
- Endpoint próbki nie przyjmuje ścieżki pliku od klienta, ujawnia ścieżek/kluczy magazynu ani nie udostępnia pełnego pliku. Odpowiedź PDF jest inline; audio obsługuje ograniczone żądania Range.
- `sample_open_count` zwiększa się atomowo po jawnym POST otwarcia; identyczny `X-Sample-Open-Id` deduplikuje ponowienie. Range nie zwiększa liczby otwarć, ale podlega limitom transferu.
- Limity IP i krótkich sesji są przechowywane w PostgreSQL, więc współdzielone między workerami. `X-Forwarded-For` można uwzględnić wyłącznie za adresem zaufanego proxy skonfigurowanym w `TRUSTED_PROXY_CIDRS`.
- Lokalne próbki są w `SAMPLE_STORAGE_ROOT` (Docker: `/app/uploads/samples` w wolumenie `uploads_data`) z katalogami `0700` i plikami `0600` na POSIX. CLI: `uv run --frozen --all-groups python -m sensoria.modules.catalog.sample_cli --slug <slug> --file <przygotowany-plik> --kind pdf --pages <liczba>` albo `--kind audio --duration-seconds <sekundy>`. Nie podawaj pełnego pliku. Przygotowany PDF musi zawierać stopkę „Fragment bezpłatny · pełna wersja dostępna w sensoria.shop” wewnątrz każdej strony; sprawdź render przed instalacją.
- Testowe pliki w `apps/api/tests/fixtures/` są jawnie oznaczone jako fixture i nie mogą być użyte jako próbki produktu. Brak redakcyjnego materiału oznacza brak włączonego przycisku fragmentu.

## Koszyk — etap [24]

- Koszyk gościa jest przechowywany w PostgreSQL; cookie `cart_token` jest losowe, `Secure`, `HttpOnly`, `SameSite=Lax`, ważne 30 dni, a baza przechowuje tylko SHA-256 tokenu. GET nie tworzy pustego rekordu i nie przedłuża ważności.
- Cena oraz VAT pozycji pochodzą z serwerowego produktu/wariantu. Snapshoty są trwałe i nie odświeżają się przy GET, zmianie ilości ani zmianie katalogu.
- BOOK sumuje ilość przy tym samym produkcie/wariancie i blokuje rekord produktu podczas kontroli stanu. DIGITAL/AUDIOBOOK dopuszczają jedną kopię, a każde dodanie VOUCHER tworzy oddzielną pozycję ilości 1.
- Klient nie wybiera `cart_id` ani `customer_id`; operacje na pozycji muszą ograniczać odczyt/mutację do bieżącego koszyka. Cookie nie jest uwierzytelnieniem konta.
- `merge_guest_cart_after_login` wolno wywołać wyłącznie po prawdziwym uwierzytelnieniu, z identyfikatorem zaufanego principalu. Operacja jest transakcyjna, zgłasza konflikt stock bez częściowego scalenia i unieważnia token przez usunięcie koszyka gościa po sukcesie. Nie udostępniaj klientowi endpointu przyjmującego `customer_id`.
- Zadanie `cleanup_scheduler` usuwa partie wygasłych koszyków gości (`CART_CLEANUP_BATCH_SIZE`) w interwale `CART_CLEANUP_INTERVAL_SECONDS`; `SKIP LOCKED` koordynuje workery. Koszyk konta nigdy nie podlega 30-dniowemu czyszczeniu.
- `CartCalculator` używa snapshotów pozycji, rozlicza pozycje przed grupami VAT i koryguje netto deterministycznie według brutto oraz UUID. `EXEMPT` jest osobne od stawki 0%. Dostawa ma osobny kontrakt; nie zgaduj jej VAT bez jawnego wyniku etapu [27]. Snapshot `CartCalculation` jest wersjonowanym kontraktem do utrwalenia z zamówieniem [29].

## Dostawa koszyka — etap [27]

- Dostawy wymaga wyłącznie `Product.requires_shipping` (obecnie `BOOK`), nie nazwa ani kategoria. Podstawa darmowej dostawy to suma brutto wszystkich produktów po rabacie, bez dostawy.
- `app_settings` z kluczem `orders.delivery.v1` jest walidowany przy każdym odczycie koszyka, bez cache. Kwoty paczkomatu, kuriera, próg i próg zachęty są ścisłymi nieujemnymi groszami; VAT jest jawną wartością `VatRate`. Brak/błędna konfiguracja nie może zostać potraktowana jako darmowa dostawa.
- Kwalifikacja używa `products_gross_after_discount >= threshold`, także dokładnie na granicy. Zachętę pokazuj wyłącznie, gdy dodatnia różnica jest mniejsza od konfigurowalnego `incentive_threshold_grosz`.
- Fizyczny koszyk bez zapisanej metody wymaga jej wyboru; kwota do zapłaty nie jest finalna. Klient wybiera tylko identyfikator metody, nigdy koszt ani VAT. Cyfrowy/pusty koszyk nie pokazuje dostawy ani zachęty.
- Dostawa jest osobnym rozliczonym wierszem z własną stawką VAT, netto i podatkiem. Nie kopiuj VAT produktu. Koszt 0 nadal zachowuje skonfigurowaną stawkę klasyfikacyjną; `RATE_0` nie zastępuje stawki dostawy.
- Reguły wyboru konkretnego punktu, adresu i realizacji przewozu pozostają poza [27].

## Katalog produktów — etap [12]

- Rodzaj produktu przechowuj w polu `kind`; nie używaj nazwy `type`. `ProductKind` ma dokładnie `VOUCHER`, `BOOK`, `AUDIOBOOK` i `DIGITAL`. E-book PDF i kurs PDF są etykietami wariantów `DIGITAL`, a nie osobnymi rodzajami.
- Wspólne dane i pieniądze w groszach należą do `products`; parametry rodzaju trafiają do jednej właściwej tabeli szczegółów. Używaj wyłącznie wspólnej `Base`, `UUIDMixin`, `TimestampMixin`, `Mapped[...]`, `mapped_column()` oraz naming convention.
- Slug jest zapisanym, unikalnym adresem produktu. Generuj go z polskiej nazwy przy tworzeniu; zmiana nazwy nie zmienia istniejącego sluga. Kolizje rozstrzygaj sufiksem i zawsze polegaj też na ograniczeniu UNIQUE bazy.
- Kwoty `price`, `compare_at_price` i wariantów przechowuj jako całkowite grosze (`Money`/`BIGINT`), bez `float`. `compare_at_price` jest ceną porównawczą/przed obniżką, nie najniższą ceną z 30 dni.
- E-book należy do `DIGITAL`. Wydania cyfrowe nie przechowują plików w tej tabeli; obsługa plików jest późniejszym etapem.
- Dostępność książki wymaga statusu `PUBLISHED` i dodatniego stanu. Nie zmniejszaj stanu przy dodaniu do koszyka; zmniejszanie następuje dopiero po opłaceniu zamówienia.
- `requires_shipping` dotyczy tylko `BOOK`. Voucher na usługę klasyfikujemy jako nie-fizyczny i niedigitalny; `AUDIOBOOK` oraz `DIGITAL` są cyfrowe. Właściwości wyliczane nie są kolumnami.
- Relacje asynchronicznie odczytuj przez jawne eager loading (`selectinload`); relacje modeli katalogu mają blokadę lazy loading. `is_available` nie może uruchamiać niejawnego zapytania.
- Publikuj przez centralną usługę katalogu. Waliduj nazwę, slug, cenę (zero groszy jest poprawną wartością), VAT, obraz, szczegóły właściwego rodzaju i warunki rodzaju. Status i `published_at` zmieniaj wyłącznie po przejściu walidacji; czas publikacji pochodzi z PostgreSQL.
- Dane z `sensoria.modules.catalog.seed` są wyłącznie demonstracyjne i nie mogą być traktowane jako oferta ani stawki podatkowe. Seed ma być idempotentny oraz nie nadpisywać danych edytowanych przez użytkownika.
- Nowa rewizja po `0002_database_foundation` nie może zmieniać ani usuwać wydanych migracji. Jej downgrade cofa tylko tabele katalogowe i zachowuje `app_settings`, `audit_log` oraz współdzielone rozszerzenie.

## Ceny i historia cen — etap [14]

- `Product.price` i `compare_at_price` są cenami brutto w całkowitych groszach (`Money`/`BIGINT`). Netto i podatek wyliczaj ze wspólnej `sensoria.shared.pricing.split_gross_price`; używaj arytmetyki całkowitoliczbowej HALF_UP, a podatek wyznaczaj jako brutto minus netto.
- `VatRate.RATE_0` i `VatRate.EXEMPT` pozostają różne. Etykiety to odpowiednio `0%` i `zw.`; zwolnienie ma netto równe brutto i podatek zero.
- Jeśli `compare_at_price` istnieje, musi być ściśle większa od `price`. Sprawdza to wejściowy schemat, ORM oraz constraint PostgreSQL. Migracja przerwie się na istniejących błędnych danych; nie poprawiaj ich automatycznie.
- `price_history` dopisuje kompletny snapshot brutto/ceny porównawczej/VAT i audyt przy ORM flush produktu. Oba wpisy i zmiana produktu są jedną transakcją. Nie aktualizuj ani nie usuwaj historii; FK `RESTRICT` wymaga wycofywania produktu zamiast jego kasowania.
- Autor i powód dla jawnej operacji przekazuj w `async with price_change_context(session, actor_type=..., actor_id=..., reason=...)` i wykonaj flush wewnątrz bloku. Bez kontekstu ORM zapisuje jawny autora `system` i powód systemowy. Kontekst jest przechowywany per sesja, nie globalnie.
- Trigger PostgreSQL blokuje insert/zmianę cen poza ORM flush oraz blokuje UPDATE/DELETE historii. To chroni przed pomyłkowym bulk/raw SQL; aplikacyjna rola DB z prawem do dowolnego SQL może celowo ustawić wewnętrzną zmienną transakcyjną, więc nie jest to granica bezpieczeństwa wobec administratora bazy.
- `version` z identity zapewnia deterministyczny porządek także przy równych `valid_from`. Historia używa UTC `timestamptz`, czasu `now()` bazy i indeksów produktu/czasu.
- `lowest_price_last_30_days(session, product_id, at)` wymaga świadomego, strefowego `at` i liczy `[at - 30 dni, at)`. Uwzględnia snapshot obowiązujący na początku okna, a nie `compare_at_price` ani cenę z zegara systemowego.
- Rewizja `f31a9d4b` wykonuje jednorazowy snapshot istniejących produktów na czas migracji, bez odtwarzania wcześniejszych cen. Downgrade usuwa nową tabelę historii i jej trigger; wykonuj go wyłącznie na dedykowanej bazie testowej.

## Kategorie, odbiorcy i SEO — etap [13]

- Kategorie i `AudienceTag` należą do wspólnego modułu `catalog` i wspólnej `Base`. Produkt może mieć wiele kategorii oraz wiele znaczników; używaj tabel łączących z kluczem złożonym, bez duplikatów. Kategorie początkowe są płaskie, hierarchia może mieć maksymalnie dwa poziomy.
- Slugi kategorii generuj przez istniejące `sensoria.modules.catalog.slug.slugify`; pozostają trwałe po zmianie nazwy. Kolizje rozstrzygaj sufiksem i polegaj na unikalnym ograniczeniu bazy.
- Liczniki kategorii liczą bezpośrednie, opublikowane produkty, zawsze z warunkiem `PUBLISHED` i `COUNT(DISTINCT ...)`; nie dodawaj tabel galerii/odbiorców do liczenia. Nie wliczaj potomków, chyba że odrębny kontrakt jawnie to określi.
- Nullable `meta_title`, `meta_description` i `og_image` oznaczają fallback automatyczny; tekstowa wartość oznacza ręczną i nie może być nadpisywana. Opisy SEO usuwają HTML, normalizują spacje i są skracane na granicy słowa około 160 znaków.
- Obraz produktu w SEO bierze się z pierwszego obrazu galerii. Kategoria używa ręcznego obrazu lub `SITE_OG_IMAGE`; nie twórz fikcyjnej grafiki. Jeśli brak pliku lub adresu obrazu, pomiń obraz i zgłoś brak.
- Publiczne strony produktów i kategorii pobierają dane z backendu po `API_URL`, nigdy z listy wpisanej na froncie. `SITE_URL` to serwerowy publiczny origin; production wymaga HTTPS. Nie ujawniaj wewnętrznego URL-a API jako canonical/OG/JSON-LD.
- Stosuj wspólne generatory `productPath`, `categoryPath` i `publicUrl` do linków, canonical, OG, breadcrumbs JSON-LD i sitemap. Produkt ma jeden canonical niezależnie od kategorii i parametrów zapytania.
- JSON-LD odzwierciedla wyłącznie widoczne dane: ceny jako dokładne ciągi dziesiętne z groszy, PLN, `is_available`, VAT rozróżniający `RATE_0`/`EXEMPT` i rzeczywiste warianty. Nie dodawaj fikcyjnych ocen ani wymyślonych danych firmy. Escapuj `<`, `>` i `&` w JSON wstawianym do elementu `script`.
- Sitemap jest dynamiczna i nie może przedstawiać błędu backendu jako pustej poprawnej mapy. Wyklucz szkice, wycofane produkty i prywatne/transakcyjne/dev URL-e. Robots nie jest kontrolą dostępu; obszary prywatne/transakcyjne dostają też `noindex` w metadanych.
- Seed katalogu uruchamiaj z `apps/api`: `uv run --frozen --all-groups python -m sensoria.modules.catalog.seed`. Seed jest idempotentny i nie nadpisuje istniejących opisów, słowników ani relacji; marker inicjalizacji zapobiega odtwarzaniu ręcznie usuniętych przypisań.
- Rewizja `08f9476a46d2_categories_audience_seo` jest po rewizji katalogu [12]. Nie zmieniaj jej ani starszych rewizji po wydaniu; schemat poprawiaj kolejną migracją. Downgrade testuj wyłącznie na dedykowanym PostgreSQL `_test` i nie usuwaj produktów z [12].

## Wyszukiwanie katalogu — etap [16]

- Rozszerzaj listę `/products` przez opcjonalne `q`; nie twórz konkurencyjnego endpointu. Puste `q` zachowuje zwykłą listę, a limit wynosi 160 znaków.
- PostgreSQL `search_vector` zachowuje polskie znaki i `search_vector_unaccented` służy zapytaniom ASCII. Oba wektory mają indeks GIN. Wagi: A — nazwa, B — krótki opis i nazwy kategorii, C — pełny opis.
- Obraz PostgreSQL buduj z `docker/postgres.Dockerfile`. Przypięty Debian `hunspell-pl` 7.5.0-1 dostarcza reguły morfologiczne. Konfiguracje FTS są tworzone przez Alembic; `unaccent` poprzedza wariant słownika transliterowanego. Zachowuj oryginalne nazwy i opisy.
- Baza aktualizuje wektory triggerami produktu, relacji `product_categories` i zmiany nazwy kategorii. Nie dubluj tej logiki w serwisie API. Trigger usuwa tagi HTML z kopii indeksowanej.
- `plainto_tsquery` przyjmuje frazę jako parametr. Nigdy nie interpoluj tekstu do SQL ani nie przekazuj go do składni `to_tsquery`.
- Wyszukiwanie domyślnie sortuje według rankingu z wagami, potem czasu publikacji i UUID. Jawne sortowanie zachowuje kontrakt [15]. Liczniki filtrów nadal uwzględniają `q`.
- `search_queries` zapisuje niepuste, zatwierdzone wyszukiwania wraz z `total`, także po cache hit. Nie dodawaj identyfikatorów klienta ani logowania każdego naciśnięcia klawisza.
- `suggestions` jest oddzielne od `items` i uruchamia się tylko przy `total = 0`. Popularność wynika z rzeczywistej historii; powiązane produkty pochodzą ze wspólnej kategorii najbliższego tytułu.
- Klucz cache obejmuje znormalizowane `q`. Triggery DB nie rozsyłają unieważnień do procesowego cache innych workerów; nie deklaruj globalnej spójności.
- Migrację `b16f0a9c7d31` testuj na dedykowanej bazie PostgreSQL 16 `_test`. Nie edytuj rewizji wcześniejszych.

## Pieniądze

- Kwoty przechowuj jako całkowitą liczbę groszy.
- W Pythonie używaj `int`; nigdy `float` do przechowywania kwot pieniężnych.
- W TypeScript używaj całkowitych wartości groszy w bezpiecznym zakresie (`Number.isSafeInteger`).

## Język

- Kod, identyfikatory i komentarze pisz po angielsku.
- Komunikaty przeznaczone dla użytkownika pisz po polsku.
- Dokumentację i raporty przygotowuj po polsku.

## Instalacja i komendy

Z katalogu głównego repozytorium, chyba że podano inaczej:

```powershell
uv sync --project apps/api --frozen --all-groups
Push-Location apps/api
uv run --frozen --all-groups ruff check src/sensoria tests
uv run --frozen --all-groups ruff format src/sensoria tests
uv run --frozen --all-groups ruff format --check src/sensoria tests
uv run --frozen --all-groups mypy --strict src/sensoria tests
uv run --frozen --all-groups pytest
uv run --frozen --all-groups python -m sensoria.seed
Pop-Location
uv run --project apps/api pre-commit install
uv run --project apps/api pre-commit run --all-files
npm --prefix apps/web run lint
npm --prefix apps/web run format:check
Push-Location apps/web; npx tsc --noEmit; Pop-Location
npm --prefix apps/web run build
docker build --file docker/api.Dockerfile --target runtime --tag sensoria-api:local .
docker build --file docker/web.Dockerfile --target runtime --build-arg NEXT_PUBLIC_API_URL=https://example.invalid/api --tag sensoria-web:local .
Push-Location apps/web; npm run dev; Pop-Location
Push-Location apps/web; npm run start; Pop-Location
```

Docker Compose (Docker Engine/Desktop i Compose v2.24.4 lub nowszy; katalog główny):

```powershell
Copy-Item .env.example .env
# Ustaw lokalne POSTGRES_PASSWORD, DATABASE_URL i SECRET_KEY w .env.
docker compose config --quiet
docker compose up --build -d
docker compose ps
docker compose logs -f api web caddy
docker compose exec api alembic upgrade head
docker compose down
```

Zwykłe `docker compose up` ładuje `docker-compose.override.yml` i uruchamia tryb developerski. Produkcję uruchamiaj jawnie bez override: `docker compose -f docker-compose.yml up --build -d`. Ustaw wtedy własne `DOMAIN` i `NEXT_PUBLIC_API_URL=https://<domena>/api`; zmiana `NEXT_PUBLIC_API_URL` wymaga przebudowania obrazu web. Nie commituj głównego `.env`. `docker compose down` zachowuje nazwane wolumeny; `docker compose down -v` je usuwa.

Migracje wykonuj jawnie w kontenerze API poleceniem `docker compose exec api alembic upgrade head` po starcie bazy. Nie są uruchamiane automatycznie przy starcie i nie wykonuj downgrade na produkcji.

Frontend używa npm i `package-lock.json`; zależności instaluj przez `npm --prefix apps/web ci`. TypeScript ma `strict: true`. Trasy aplikacji są w App Routerze. Kod Server Components pobiera backend przez `API_URL`; kod przeglądarkowy używa bezpośrednio `process.env.NEXT_PUBLIC_API_URL`. Nie przekazuj konfiguracji serwerowej do komponentów klienckich. Zmienne `NEXT_PUBLIC_*` są publiczne i wbudowywane podczas `next build`; ich zmiana wymaga ponownego builda.

Wspólna rama sklepu jest w `apps/web/components/layout/` i `apps/web/app/(shop)/layout.tsx`. Zachowuj jeden `<main id="main-content">` na stronę oraz pierwszy w `body` dostępny klawiaturą link „Przejdź do treści”. Strony bez ramy sklepu trafiają do route group `(isolated)`, nie są ukrywane CSS-em. Mapę linków oraz tekst paska informacyjnego trzymaj w `components/layout/site-config.ts`. Linki muszą prowadzić do istniejących tras; jeśli przyszła strona nie istnieje, dokumentuj tymczasowy cel/parametr i nie twórz martwego `#`.

Licznik koszyka może przyjąć nową wartość wyłącznie jako potwierdzony snapshot serwera przez `acceptConfirmedCount` lub `GET /api/cart`. Nie używaj localStorage ani wspólnego statycznego cache dla danych koszyka. Nie pokazuj wartości demonstracyjnej, gdy istnieje integracja [24]; przy braku potwierdzenia oznacz licznik jako niedostępny zamiast pokazywać pusty koszyk. Cookie `cart_token` ma ograniczone `Path=/api/cart`, więc serwerowy render strony nie otrzymuje go; klient po hydratacji pobiera bezcache'owy snapshot z API. System zgód [79] również nie istnieje: demo cookies nie zapisuje zgód i nie może być opisywane jako gotowy panel.

## System tokenów frontendowych

- Używaj semantycznych tokenów projektu z `apps/web/tailwind.config.ts`, np. `surface`, `ink`, `accent`, `success`; kolory nazywaj rolami, nie nazwami odcieni.
- Nie wpisuj kolorów, rozmiarów typografii, odstępów, zaokrągleń ani cieni bezpośrednio w komponentach lub `globals.css`. Dodawaj wartości do konfiguracji i opisz ich źródło.
- Nie dodawaj odcieni ani wariantów na zapas. Wartości niepotwierdzone makietami oznacz jako propozycje i uzyskaj akceptację przed traktowaniem ich jako zatwierdzone.
- Odstępy korzystają ze skali o kroku 4 px; breakpointy: `sm: 360px`, `md: 768px`, `lg: 1024px`, `xl: 1280px`.
- Wersaliki zapisuj jako normalne słowa, a rozstrzelenie realizuj przez `letter-spacing`, nigdy przez spacje między literami.
- Kolory etykiet produktów nie zastępują ich tekstowych nazw. Kolor nie może być jedynym nośnikiem znaczenia.
- Wspólne kontrolki UI trzymaj w `apps/web/components/ui/`; wymagaj etykiet, powiązanych opisów błędów, widocznego fokusu i obsługi klawiatury.
- Komponenty UI nie wywołują API i nie implementują koszyka, cen promocyjnych, dostawy, płatności ani reguł voucherów. Otrzymują dane i callbacki przez typowane props.
- Button ma warianty `primary`, `secondary`, `text` i rozmiary `sm`, `md`, `lg`; domyślny `type` to `button`, a loading blokuje ponowną aktywację.
- Pola formularza łączą label, hint, błąd i dodatkowe `aria-describedby`; radio w grupach używają wspólnego `name` oraz `fieldset`/`legend`.
- Modal używa natywnego `<dialog>.showModal()` i przy zamknięciu przywraca fokus oraz poprzedni stan przewijania dokumentu. Accordion obsługuje strzałki i Home/End; zamknięte panele pozostają `hidden`.
- Ceny UI przyjmują bezpieczne całkowite grosze; formatowanie nie używa float. `EXEMPT` i `RATE_0` są wyświetlane osobno.
- Wysokości tokenów `touch`/kontrole w konfiguracji są wyjątkiem dla minimum obszaru dotykowego 44 px; pozostałe rozmiary nadal korzystają z tokenów [08].
- Kwoty frontendu podawaj jako całkowite grosze i formatowanie wykonuj bez operacji zmiennoprzecinkowych.
- Galerię komponentów rozwijaj w `/dev/tokeny`; nie buduj tam pełnych stron ani logiki sklepu.
- Fonty ładuj lokalnie po dostarczeniu pełnych plików; subsetów osadzonych w PDF nie kopiuj jako webfontów.
- Trasę `/dev/tokeny` renderuj dynamicznie i ograniczaj serwerowym `ENVIRONMENT=development`; w production używaj `notFound()`, nigdy `NEXT_PUBLIC_ENVIRONMENT`.

## Responsywność i dostępność — etap [11]

- Buduj układy mobile-first: style bazowe obsługują najwęższe ekrany, a media queries rozszerzają je w górę przez breakpointy z [08] (`sm: 360px`, `md: 768px`, `lg: 1024px`, `xl: 1280px`).
- Przy szerokości 360 px strona nie może mieć poziomego przewijania. Nie maskuj problemu globalnym `overflow-x: hidden`; znajdź i popraw element powodujący przepełnienie.
- Każdy element interaktywny ma aktywny obszar minimum 44 × 44 px; mała ikona może korzystać z paddingu albo powiązanej etykiety.
- Tabele na wąskim ekranie prezentuj jako karty, z etykietą przy każdej wartości. Dotyczy to przyszłych ekranów 07 (panel sklepu z zamówieniami) i 10 (historia zamówień); nie buduj ich w ramach [11].
- Obrazy mają jawne wymiary albo proporcje, aby rezerwować miejsce przed ich załadowaniem. Długie słowa, adresy i treści nie mogą wypychać kontenerów poza ekran.
- Każda strona ma dokładnie jeden `h1`; zachowuj logiczną hierarchię nagłówków bez przeskoków i dokładnie jeden semantyczny `main`.
- Obraz przekazujący treść otrzymuje sensowny tekst `alt`; obraz dekoracyjny otrzymuje `alt=""`. Każde pole formularza ma powiązaną etykietę.
- Wszystkie elementy interaktywne mają widoczny focus; kolejność focusu jest logiczna. Nie używaj dodatnich `tabindex` do naprawiania kolejności DOM.
- Kolor nie jest jedynym nośnikiem informacji. Zachowuj tekstowe etykiety, komunikaty i wzorce dostępne poza kolorem.
- Link „Przejdź do treści”, semantyczne obszary strony, połączenia błędów z polami oraz klawiaturowe zachowania menu, accordionu i modala muszą pozostać działające.
- `prefers-reduced-motion: reduce` wyłącza dekoracyjne animacje, przejścia i płynne przewijanie. Interfejs nie może zależeć od zdarzenia końca animacji; stany, np. loading, pozostają zrozumiałe bez ruchu.
- Powiększenie do 200% nie może powodować utraty treści ani funkcjonalności. `viewport` nie może blokować powiększania.
- Każdy nowy ekran sprawdź listą `docs/lista-kontrolna-ekranu.md`; automat axe uzupełnia, ale nie zastępuje ręcznej oceny altów, sensu etykiet, fokusu, zoomu i zachowań.
- Frontendowa kontrola axe uruchamia się lokalnie przez `npm --prefix apps/web run a11y` i w zadaniu CI `frontend`. Naruszenia `critical` i `serious` blokują przebieg; wyniki `moderate`/`minor` oraz `incomplete` są raportowane do oceny, a `incomplete` wymaga sprawdzenia ręcznego.

Migracje (tylko na właściwie wskazanej bazie deweloperskiej/testowej):

```powershell
Push-Location apps/api
uv run --frozen --all-groups alembic upgrade head
uv run --frozen --all-groups alembic downgrade base
Pop-Location
```

Seed ustawień (z katalogu `apps/api`): `uv run --frozen --all-groups python -m sensoria.seed`. Seed jest idempotentny i zachowuje wartości już obecne. Dodaje zatwierdzone, niepoufne treści strony głównej `homepage.content.v1`; nie dodawaj wartości biznesowych, których specyfikacja nie określa.

Jedynym wzorcem konfiguracji jest główny `.env.example`; lokalne wartości trzymaj w ignorowanym `.env` w katalogu głównym. Backend Pydantic Settings ładuje ten plik. Next.js uruchamiany poza Dockerem może wymagać osobnego `apps/web/.env.local` zawierającego wyłącznie niesekretne `API_URL` i `NEXT_PUBLIC_API_URL`; Compose przekazuje te wartości jawnie. `NEXT_PUBLIC_*` jest publiczne i wbudowywane podczas buildu, nigdy nie umieszczaj tam sekretów. Wymagane ustawienia API: `DATABASE_URL`, `ENVIRONMENT` (`development` albo `production`) i `SECRET_KEY`; production wymaga losowego klucza o długości co najmniej 32 znaków. W Compose bazowy plik wybiera production, a domyślny override development. Testy integracyjne wymagają `TEST_DATABASE_URL` wskazującego osobną bazę PostgreSQL 16 o nazwie zakończonej `_test`; testy nie używają SQLite. Nie uruchamiaj destrukcyjnych testów ani migracji na bazie aplikacji lub produkcyjnej. Logi i odpowiedzi błędów nie mogą ujawniać sekretów, haseł, nagłówków Authorization ani parametrów SQL.

Zmienne środowiskowe rozróżniaj według źródła: aplikacyjne i Compose są opisane w głównym `.env.example`; `TEST_DATABASE_URL` jest testowa; `SENSORIA_ENV_FILE` służy wyłącznie do izolowania testów walidacji; `NODE_ENV`, `NEXT_TELEMETRY_DISABLED`, `UV_*`, `WATCHFILES_FORCE_POLLING`, `WATCHPACK_POLLING`, `XDG_*` i `PATH` są ustawieniami narzędzi/kontenerów. Nie dodawaj nieużywanych sekretów przyszłych integracji.

## Git

- Główna gałąź: `main`.
- Gałęzie robocze: `feat/*` i `fix/*`.
- Conventional Commits: `feat:`, `fix:`, `chore:`, `docs:` i `test:`.

## Czego nie dotykać

- Nie zmieniaj już wydanych migracji.
- Nie modyfikuj dostarczonej specyfikacji ani makiet w `docs/`. Początkowe skopiowanie dostarczonych plików do `docs/` jest częścią przygotowania projektu.
- Nie nadpisuj zmian użytkownika.
- Nie wykonuj zmian niezwiązanych z zadaniem ani szerokiego refaktoringu.
- Nie zmieniaj stosu technologicznego ani architektury bez polecenia.
- Nie implementuj funkcji sklepu, integracji płatności ani autoryzacji. Zmiany infrastruktury Docker ogranicz do wymagań zleconego etapu; nie dodawaj CI bez polecenia.

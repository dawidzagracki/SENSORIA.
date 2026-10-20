# Publiczne API katalogu

Publiczne trasy są dostępne bezpośrednio pod `/products` i `/products/{slug}`. W środowisku Compose Caddy usuwa publiczny prefiks `/api`, więc odpowiadają im adresy `/api/products` i `/api/products/{slug}`.

## Lista produktów

`GET /api/products` zwraca `items`, `total`, `page`, `per_page`, `total_pages` i `facets`. `total` oznacza liczbę unikalnych, opublikowanych produktów przed paginacją. Pusta lista ma `total = 0` i `total_pages = 0`; strona poza zakresem ma status 200 i pustą `items`.

Parametry:

| Parametr | Znaczenie |
| --- | --- |
| `category` | slug kategorii; pasuje do niej i jej bezpośrednich dzieci (drzewo ma najwyżej dwa poziomy) |
| `kind` | `VOUCHER`, `BOOK`, `AUDIOBOOK` albo `DIGITAL`; to rodzaj produktu, nie kategoria |
| `audience` | slug istniejącego znacznika odbiorcy |
| `price_min`, `price_max` | nieujemne, całkowite grosze; granice włączne, np. 5000 oznacza 50,00 zł |
| `delivery` | `digital` dla `DIGITAL`/`AUDIOBOOK`, `parcel` dla `BOOK`; voucher nie jest arbitralnie przypisywany do żadnej z tych metod |
| `q` | opcjonalna fraza, maksymalnie 160 znaków; białe znaki na brzegach są pomijane |
| `sort` | `recommended`, `price_asc`, `price_desc`, `newest`, `bestselling`; przy `q` brak sortowania oznacza trafność, bez `q` domyślnie `recommended` |
| `page` | numer strony od 1; domyślnie 1 |
| `per_page` | 1–48; domyślnie 12; większa wartość jest odrzucana |

Filtry łączą się przez przecięcie. Kategorie i odbiorcy mogą być wielokrotne w relacji, ale produkt liczony jest tylko raz. Ceny są cenami brutto w groszach.

Sorty kończą się stabilnym `id`: rekomendowane używają rosnącego `sort_order`, malejącego `published_at`, następnie `id`; ceny sortują po `price`; nowe po malejącym `published_at`. Moduł zamówień nie ma jeszcze wiarygodnego miernika sprzedaży. `bestselling` ma tymczasowo zerową sprzedaż dla każdego produktu i deterministycznie sortuje po `id`; nie jest to ranking sprzedaży.

## Liczniki filtrów

Każdy licznik zachowuje pozostałe filtry i zastępuje bieżący filtr opcją, której dotyczy. Liczniki nie zależą od strony ani sortowania. Kategorie, rodzaje, odbiorcy, dostawy i trzy przedziały cenowe zawierają również opcje z zerem.

Przedziały nie nakładają się: `Do 50 zł` to 0–5000 groszy włącznie; `Powyżej 50 do 150 zł` to 5001–15000 groszy włącznie; `Powyżej 150 zł` zaczyna się od 15001 groszy. Jedno zapytanie `UNION ALL` z licznikami skorelowanymi wykorzystuje `COUNT(DISTINCT products.id)` — bez zapytania dla każdej opcji.

Gdy `q` jest aktywne, wyniki i wszystkie liczniki zachowują wyszukiwanie oraz pozostałe filtry. Licznik danej grupy zastępuje tylko aktywny wybór tej grupy.

## Wyszukiwanie pełnotekstowe

`GET /api/products?q=integracja%20sensoryczna` używa indeksowanego PostgreSQL FTS. Trigger utrzymuje dwa wektory: `search_vector` dla oryginalnej pisowni oraz `search_vector_unaccented` dla zapytań bez polskich znaków. Oba mają wagi: A — nazwa, B — opis krótki i nazwy kategorii, C — opis pełny. Wynik sortuje `ts_rank_cd`; kanał bez znaków ma wagę 0,25, potem rozstrzygają `published_at DESC` i `id ASC`. Jawny `sort` zastępuje trafność. Bez `q` działa dotychczasowe sortowanie rekomendowane.

Konfiguracja `sensoria_polish` używa polskiego słownika Hunspell/ispell z pakietu Debian Bookworm `hunspell-pl` (`libreoffice-dictionaries` 7.5.0-1, MPL-2.0). `docker/postgres.Dockerfile` pobiera przypięty pakiet, konwertuje słownik ISO-8859-2 do UTF-8 i zachowuje licencję w obrazie. Druga konfiguracja używa przetransliterowanego wariantu słownika, poprzedzonego filtrem `unaccent`; odmiana działa także dla zapytań ASCII. Oryginalne pola produktów są niezmienione. Kanał znormalizowany nie rozróżnia `łąka` i `laka`, kanał oryginalny zachowuje dokładniejsze dopasowanie. Compose i serwis PostgreSQL CI instalują ten sam pakiet. Migracja dodaje rozszerzenia `unaccent` i `pg_trgm`.

Wektory aktualizują się transakcyjnie triggerami PostgreSQL przy zapisie produktu, zmianie przypisań kategorii i zmianie nazwy kategorii. HTML w opisach jest usuwany z indeksowanej kopii. Oba wektory mają indeks GIN. `pg_trgm` służy tylko do znalezienia najbliższego tytułu przy braku wyników FTS (podobieństwo co najmniej 0,05).

Puste `q` działa jak brak parametru. Fraza ma limit 160 znaków i trafia przez `plainto_tsquery`; nie jest parsowana jako składnia tsquery ani interpolowana do SQL. Znaki sterujące inne niż białe znaki dają wspólny błąd `SEARCH_QUERY_INVALID`.

Gdy `total = 0` dla niepustego `q`, odpowiedź zawiera osobne `suggestions`: popularne hasła z `search_queries` i do czterech opublikowanych produktów ze wspólnej kategorii najbliższego tytułu. Przy braku kandydata lub kategorii lista pokrewnych jest pusta. Pozostałe aktywne filtry ograniczają kandydata i produkty pokrewne; `q` jest pomijane dla kandydatów. Podpowiedzi nie zwiększają `total` ani `items`. Strona poza zakresem przy `total > 0` nie uruchamia podpowiedzi.

Każde zakończone żądanie z niepustym `q` zapisuje tekst frazy, wersję case-folded bez znaków diakrytycznych, `total` przy aktywnych filtrach i czas bazy. Zapis działa też przy cache hit i zerowym wyniku; nie obejmuje ID klienta. Powtórzenia oraz kolejne strony tworzą osobne wpisy. Popularność oznacza liczbę wyszukiwań, nie unikalnych osób. Brak autouzupełniania.

Przykład:

```http
GET /api/products?q=terapii&category=kursy-pdf
```

```json
{"items":[],"total":0,"page":1,"per_page":12,"total_pages":0,"facets":{"categories":[],"kinds":[],"audiences":[],"deliveries":[],"prices":[]},"suggestions":{"popular_queries":["integracja sensoryczna"],"related_products":[]}}
```

Parametryzowany warunek generowany przez SQLAlchemy ma postać:

```sql
WHERE products.status = $1 AND products.published_at <= now()
  AND (products.search_vector @@ plainto_tsquery($2::regconfig, $3)
       OR products.search_vector_unaccented @@ plainto_tsquery($4::regconfig, unaccent($5::regdictionary, $3)))
  AND products.price <= $6
```

Klucz cache zawiera znormalizowane `q`. Historia zapisuje się również przy trafieniu w cache. Cache jest procesowy; triggery aktualizują wektor także dla surowego SQL, ale nie unieważniają pamięci innych workerów. W takim przypadku stara odpowiedź może być podana do końca krótkiego TTL.

## Szczegóły produktu

`GET /api/products/{slug}` zwraca bezpieczne dane wspólne, szczegóły rodzaju, uporządkowane obrazy, przypisane kategorie i do czterech podobnych produktów ze wspólnej kategorii. „Zobacz też” sortowane jest stabilnie według rekomendacji. Brak kategorii oznacza pustą listę rekomendacji. Pliki cyfrowe i szkice nie są ujawniane. Nieopublikowany, zaplanowany na przyszłość lub nieistniejący slug daje standardowy błąd 404.

Oba endpointy widzą wyłącznie rekordy `PUBLISHED`, których `published_at` nie jest w przyszłości. Odpowiedź listy udostępnia tylko obraz główny dla karty; szczegóły zawierają pełną galerię. Nie ujawnia wewnętrznego stanu magazynowego ani ścieżek/chronionych plików do pobrania.

## Przykłady

```http
GET /api/products?category=ksiazki-papierowe&price_min=5000&sort=price_asc&page=1&per_page=12
GET /api/products/swiadoma-seksualnosc
```

Skrócony przykład odpowiedzi listy (wartości produktów i liczników wynikają z bazy):

```json
{
  "items": [{
    "id": "b8d2b27c-3a71-48ad-9bc8-48a25ab420ec",
    "slug": "swiadoma-seksualnosc",
    "name": "Świadoma seksualność",
    "kind": "BOOK",
    "digital_label": null,
    "short_description": "Przykładowy opis",
    "price": 7900,
    "compare_at_price": null,
    "image": {"url": "/media/ksiazka.webp", "alt": "Okładka książki"},
    "book": {"weight_grams": null, "length_mm": null, "width_mm": null, "height_mm": null, "isbn": "978-83-000-0000-0"},
    "audiobook": null,
    "digital": null,
    "voucher": null
  }],
  "total": 1,
  "page": 1,
  "per_page": 12,
  "total_pages": 1,
  "facets": {"categories": [], "kinds": [], "audiences": [], "deliveries": [], "prices": []}
}
```

W przykładzie identyfikator i liczniki są demonstracyjne. Każdy błąd używa wspólnego obiektu `error` projektu; błędne parametry mają status 422, brak produktu 404, a zakres `per_page` ponad 48 ma stabilny kod `PER_PAGE_OUT_OF_RANGE`.

## Cache i indeksy

Lista jest cache'owana w pamięci procesu przez `CATALOG_CACHE_TTL_SECONDS` (domyślnie 30 sekund, zakres 0–300; 0 wyłącza cache). Klucz zawiera kategorię, rodzaj, odbiorcę, oba limity cen, dostawę, znormalizowane `q`, sortowanie, stronę i rozmiar strony po normalizacji wartości domyślnych. Cache zawiera całą odpowiedź, łącznie z licznikami. Zatwierdzone zmiany ORM produktów, szczegółów, zdjęć, kategorii, odbiorców i powiązań unieważniają wszystkie warianty; rollback nie unieważnia ich jako zatwierdzonej zmiany. ORM-owe bulk UPDATE/DELETE też unieważniają po commit.

Cache jest lokalny dla procesu. W wielu workerach zmiana unieważnia cache tylko workera wykonującego zapis; pozostałe workery mogą podać starą odpowiedź do wygaśnięcia TTL. Bez wspólnego cache/pub-sub nie deklarujemy globalnej spójności. Bezpośredni SQL poza ORM omija hooki aplikacji. Nie używaj takich zapisów do zmiany danych katalogowych w trakcie działania API.

Migracja `a15c0f3d2e71` dodaje indeksy `(status, price)` dla filtrów ceny oraz `(status, sort_order, published_at)` dla rekomendacji. Rewizja `b16f0a9c7d31` dodaje dwa GIN, polskie konfiguracje FTS, triggery i `search_queries`. Istniejące indeksy tabel łącznikowych kategorii i odbiorców obsługują powiązania. Migrację wykonuj wyłącznie na właściwej bazie deweloperskiej/testowej:

```powershell
Push-Location apps/api
uv run --frozen --all-groups alembic upgrade head
uv run --frozen --all-groups pytest
Pop-Location
```

# Katalog `/sklep`

Strona używa wspólnego API `GET /products` z etapów [15] i [16]. Serwer Next.js odczytuje parametry URL i pobiera wynik przed renderowaniem; produkty, liczniki i filtrowanie są więc obecne w początkowym HTML. Zmiana filtra, sortowania lub strony używa `router.push`, utrwala stan w adresie i obsługuje historię Wstecz/Dalej. Odpowiedzi są odświeżane przez render serwerowy. API ma własny krótki cache; klient nie dubluje żądania tuż po hydratacji.

Obsługiwane parametry: `category`, `kind`, `audience`, `price_min`, `price_max`, `delivery`, `sort`, `page`, `per_page` i `q`. `kind` jest zachowywany w URL i żądaniu API, mimo że makieta nie pokazuje osobnej sekcji rodzaju. Kategorie i odbiorcy wybiera się pojedynczo; cena jest jednym wyborem zakresu; dostawa jest pojedynczym wyborem. Każda zmiana filtra lub sortowania resetuje `page=1`; zmiana strony pozostawia pozostałe parametry. Czyszczenie filtrów usuwa kategorię, rodzaj, odbiorcę, zakres ceny i dostawę, ale zachowuje wyszukiwanie, sortowanie i `per_page`.

Zakresy cen są rozłączne i liczone jako brutto w groszach: do 50 zł to `0–5000`, 50–150 zł to `5001–15000`, a powyżej 150 zł zaczyna się od `15001`. Liczniki pochodzą z `facets` API, nie z aktualnie widocznej strony. Licznik „Wszystkie” jest pobierany osobnym zapytaniem z zachowaniem pozostałych filtrów i pominięciem kategorii, gdy aktywna jest kategoria. Licznik materiałów w nagłówku korzysta z bieżącego `total`, gdy katalog jest nieprzefiltrowany; przy aktywnych filtrach pobiera osobny nieprzefiltrowany wynik API. `total` oznacza dopasowania przed paginacją, a nie liczbę kart na bieżącej stronie.

Panel filtrów jest modalem z istniejącego UI i pokazuje się poniżej breakpointu `lg` (1024 px); przyciski pozostają widoczne od 360 px do 1023 px. Licznik aktywnych zawężeń liczy kategorię, rodzaj, odbiorcę, dostawę i cały zakres ceny jako po jednym; nie liczy `q`, strony, rozmiaru strony ani sortowania. Widok „Lista/Siatka” działa lokalnie na tych samych danych i domyślnie jest siatką.

Karty używają `ProductCard` oraz pól z API. Metryka jest tworzona wyłącznie z dostępnych danych rodzaju (format/liczba stron, czas audiobooka, ważność vouchera lub ISBN). Integracja koszyka [24] nie istnieje; kliknięcie przycisku informuje o tym wprost i nie pokazuje fikcyjnego sukcesu. Karta prowadzi do istniejącej trasy `/produkt/{slug}`.

## Weryfikacja

Testy logiki adresu uruchamiaj z `apps/web` poleceniem `npm test`. Kontrole frontendu: `npm run lint`, `npm run format:check`, `npx tsc --noEmit`, `npm run build`. Do testów przeglądarkowych użyj `npm run a11y`; uruchamiają lokalne, jawnie sztuczne API z `test-fixtures/catalog-api.mjs`, więc potwierdzają zachowanie UI, nie integrację z etapami [15] i [16]. Test na prawdziwym API wymaga tych etapów oraz migracji bazy. Jeśli API jest niedostępne, strona pokazuje komunikat z ponowieniem, a nie pusty katalog jako poprawny wynik.

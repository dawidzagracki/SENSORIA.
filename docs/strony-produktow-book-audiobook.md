# Strony produktów: książka i audiobook

Trasa `/sklep/[slug]` wybiera widok wyłącznie z pola `kind` odpowiedzi API. `BOOK` i `AUDIOBOOK` korzystają ze wspólnych elementów produktów: breadcrumbs, okładki z zarezerwowanym proporcjonalnym miejscem, nagłówka, ceny, akcji zakupu i podobnych produktów. Wspólne warianty `VOUCHER` i `DIGITAL` pozostają na tej samej trasie.

## Dane

- Książka: `book.stock_quantity`, wymiary w milimetrach, waga w gramach, ISBN, oprawa, czas wysyłki i metoda dostawy. Pola redakcyjne/wysyłkowe są opcjonalne; frontend nie dopisuje danych, których API nie podało. Stan 0 wyłącza zakup, zakres 1–4 pokazuje komunikat o ostatnich egzemplarzach, a od 5 nie pokazuje komunikatu o niskim stanie. Dokładna liczba sztuk nie jest tekstem sprzedażowym.
- Audiobook: całkowity czas i czasy rozdziałów jako sekundy, lektor, format. Formatowanie nie zaokrągla źródła; kolejność rozdziałów pochodzi z pozycji. API waliduje sumę rozdziałów przy publikacji, a strona ujawnia rozbieżność istniejących danych zamiast ją korygować.
- Nowa migracja `e920_product_media` dodaje opcjonalną oprawę i parametry wysyłki książki oraz format audiobooka. Nie wypełnia ich przykładowymi wartościami.

## Granice integracji

Koszyk [24], próbka audio [21], player [44], magazyn [51] oraz proces zamówienia nie są wdrożone. Akcje zakupu nie symulują powodzenia. Próbka pozostaje wyłączona; plik nie jest publicznie udostępniany. Informacje o prawie odstąpienia na stronie nie zapisują zgody ani nie uruchamiają wydania pliku.

Produkty bez zapisanego stanu wysyłki pokazują brak danych. Treść o terminie 14 dni pochodzi z wymagań etapu; szczegóły muszą odpowiadać docelowemu regulaminowi. JSON-LD używa widocznej aktualnej ceny w PLN i dostępności; książka ze stanem 0 otrzymuje `OutOfStock`.

## Weryfikacja

Testy Playwright używają jawnie demonstracyjnego API z `apps/web/test-fixtures/catalog-api.mjs`. Nie są potwierdzeniem prawdziwych danych, koszyka, dostawy ani wydania pliku. Testy backendu i migracji muszą używać odizolowanego PostgreSQL 16 zgodnie z `TEST_DATABASE_URL`.

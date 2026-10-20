# Etap [58] — ponowienie zamówienia

## Zakres implementacji

- `POST /api/orders/{id}/reorder` wymaga sesji klientki, kontroli CSRF oraz
  nagłówka `Idempotency-Key`; źródłowe zamówienie musi należeć do tej klientki
  i mieć status `paid`.
- `POST /api/accounts/vouchers/{id}/reorder` stosuje te same zabezpieczenia i
  wymaga vouchera z opłaconej pozycji należącej do bieżącej klientki.
- Oba endpointy dodają pozycje do aktualnego koszyka opartego o istniejące
  nieprzewidywalne cookie. Nie tworzą zamówienia, rezerwacji ani płatności.
- Nowy zakup korzysta z bieżącego opublikowanego produktu, dokładnego wariantu,
  aktualnej ceny i zwykłego kalkulatora koszyka. Historyczny rabat, cena,
  dostawa i dane prezentu nie są kopiowane. Aktualny kod rabatowy już obecny w
  koszyku przechodzi istniejącą walidację koszyka.
- Książki są dodawane do ilości możliwej po uwzględnieniu stanu, rezerwacji i
  istniejącej ilości koszyka. Cyfrowe produkty i audiobooki zachowują limit
  jednej sztuki. Vouchery pozostają odrębnymi pozycjami i sztukami.
- Operacja zapisuje raport JSONB i audit log w tej samej transakcji co zmiany
  koszyka. `GET /api/cart` zwraca niezamknięty raport, więc jest on widoczny po
  przekierowaniu i odświeżeniu. Zamknięcie raportu zapisuje `dismissed_at` przez
  `POST /api/cart/reorder-report/{operation_id}/dismiss`.
- Klucz idempotencji przechowywany jest jako SHA-256, a transakcyjna blokada
  doradcza serializuje ponowienia klientki. Retry po utracie odpowiedzi
  odzyskuje ten sam koszyk i raport, a nie dodaje pozycji ponownie.

## Powiązania i ograniczenia

Cookie koszyka zachowuje wąski zakres `Path=/api/cart`. Dlatego interfejs
wywołuje aliasy `POST /api/cart/reorder/orders/{id}` i
`POST /api/cart/reorder/vouchers/{id}`. Wymagane endpointy
`POST /api/orders/{id}/reorder` oraz `/api/accounts/vouchers/{id}/reorder` także
pozostają dostępne dla klientów serwerowych, które przekazują bieżące cookie.
Cookie nadal ma flagi `HttpOnly`, `Secure` i `SameSite=Lax`; frontend nie
zapisuje go w pamięci przeglądarki.

W repozytorium nie ma tabeli `entitlements`. Ostrzeżenie „Masz już ten materiał w
bibliotece” jest więc oparte na opłaconej historii pozycji tego konta, a nie na
aktualnym stanie uprawnienia. Nie blokuje zakupu. Integracja z rzeczywistą
tabelą uprawnień powinna zastąpić tę projekcję, kiedy będzie dostępna.

## Migracja i weryfikacja

Nowa migracja `f58000000001_cart_reorder_reports` tworzy trwały raport operacji.
Nie zmienia wcześniejszych migracji. Testy `tests/test_reorder.py` wymagają
oddzielnej bazy PostgreSQL wskazanej przez `TEST_DATABASE_URL`, której nazwa
kończy się `_test`.

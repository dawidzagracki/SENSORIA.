# Kody rabatowe — etap [26]

## Model i reprezentacja

`discount_codes.code` zachowuje oryginalną wielkość liter. Przy wpisywaniu kodu usuwane są białe znaki z początku i końca, a wyszukiwanie porównuje `lower(btrim(code))`. Unikalny indeks PostgreSQL na tym wyrażeniu blokuje duplikaty niezależnie od wielkości liter i otaczających spacji.

`type=percentage` oznacza całkowitą wartość procentową (np. `10` to 10%). `type=fixed_amount` oznacza całkowitą kwotę w groszach. `min_order_value` również jest w groszach. CHECK constraints walidują zakresy i daty. Progi ważności są półotwarte: `valid_from <= teraz < valid_to`.

Panel administracyjny [70] nie istnieje; na tym etapie kody wprowadza się przez warstwę administracyjną/bazę zgodną z modelem. Nie ma publicznego endpointu tworzenia kodów.

## API

- `POST /api/cart/discount` — JSON `{"code":"WIOSNA10"}`; odpowiedź zawiera kod oraz świeże `calculation` serwera.
- `DELETE /api/cart/discount` — usuwa kod i zwraca przeliczenie bez rabatu.

Oba endpointy rozpoznają wyłącznie bieżący koszyk z cookie `cart_token`. Nie przyjmują identyfikatora koszyka ani wartości rabatu. Próg minimalny porównuje sumę brutto snapshotów produktów przed rabatem, bez dostawy. Nieprawidłowy kod zwraca HTTP 400 i nie zastępuje kodu już przypisanego.

Po zmianie zawartości koszyka kod jest ponownie walidowany. Jeśli warunki przestały być spełnione, kod zostaje odłączony i odpowiedź mutującego endpointu zawiera `discount_notice`. Zmiany ceny/VAT bieżącego katalogu nie modyfikują snapshotów pozycji.

## Obliczenia

Kalkulator wylicza rabat całkowity raz: percentage zaokrągla połową w górę do grosza całego subtotalu; fixed amount jest ograniczony do subtotalu. Kwotę rozdziela proporcjonalnie: najpierw całkowitoliczbowy iloraz dla każdej pozycji, a pozostałe grosze według malejącej wartości brutto pozycji i stabilnego UUID. Nie przekracza wartości pozycji. Po alokacji VAT jest liczony ponownie dla kwot brutto po rabacie, po czym [25] wyrównuje zaokrąglenia wewnątrz każdej grupy stawki. Rabat nie zmienia snapshotów.

## Użycie kodu po płatności

`record_paid_discount_use(session, discount_code_id, order_id)` jest serwisem dla przyszłego zaufanego potwierdzenia płatności. Wywołujący ma uruchomić go w tej samej transakcji co obsługę potwierdzenia. Wiersz kodu jest blokowany, a `discount_redemptions` zapewnia idempotencję per kod i UUID zamówienia. Limit jest kontrolowany atomowo przy płatności. Moduły zamówień i płatności nie zawierają jeszcze procesu [29]/webhooka, więc serwis nie jest obecnie podłączony do rzeczywistej płatności. Nie ma rezerwacji użyć między koszykiem a płatnością; do chwili integracji checkoutu ostatnie użycie może zostać zaakceptowane w wielu koszykach, ale nie zostanie naliczone ponad limit — późniejsze potwierdzenie odmówi użycia po wyczerpaniu limitu.

Snapshot kodu i rabatu w utrwalonym zamówieniu wymaga etapu [29]. Bieżący etap nie tworzy zamówień.

## Frontend

`DiscountSummary` w widoku `/koszyk` wysyła wyłącznie kod i renderuje kwoty zwrócone przez API. Przeglądarka nie oblicza rabatu ani VAT. Koszyk nadal nie renderuje pełnej listy pozycji i nie jest ukończonym widokiem [28].

Testy backendowe: `uv run --frozen --all-groups pytest tests/test_cart_calculator.py tests/test_cart.py` z `TEST_DATABASE_URL` wskazującym odrębną bazę PostgreSQL 16 kończącą się `_test`.

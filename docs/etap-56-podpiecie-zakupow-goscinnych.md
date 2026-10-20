# Etap [56] — podpięcie zakupów gościa do zweryfikowanego konta

## Zakres i źródło własności

Zamówienie pozostaje tym samym rekordem. Nowe nullable `orders.customer_id` wskazuje konto, do którego wcześniej gościnne zamówienie zostało bezpiecznie przypisane. Pozycje, kody voucherów, snapshoty sprzedaży, płatność i daty nie są kopiowane ani zmieniane. Vouchery pozostają powiązane z pozycją zamówienia, więc własność wynika z łańcucha `customer → order → order_item → voucher`. Etap nie tworzy entitlements; tej tabeli nie ma w bieżącym repozytorium.

Do podpięcia kwalifikuje się tylko nieprzypisane zamówienie o stanie `paid`, którego adres checkoutowy po `trim` i porównaniu bez wielkości liter odpowiada zweryfikowanemu adresowi klientki. Zamówienie przypisane do innego konta koszyka albo z voucherem mającym konfliktujące zgłoszenie nie jest przejmowane. Samo wpisanie adresu, rejestracja niezweryfikowana i posiadanie cookie koszyka nie potwierdzają własności.

## Uruchamianie

Serwis `reconcile_guest_purchases` wywołuje się w transakcji uwierzytelnienia:

- po potwierdzeniu e-maila;
- po logowaniu hasłem lub linkiem, jeżeli e-mail jest już zweryfikowany;
- przy rejestracji wyłącznie wtedy, gdy konto ma już wiarygodnie zweryfikowany e-mail (obecny przepływ rejestracji tego nie robi).

Serwis nie zatwierdza transakcji. Blokuje rekord klientki, używa transakcyjnej blokady advisory dla identyfikatora konta i blokuje kandydatów w uporządkowanej kolejności. Błąd wycofuje przypisanie, import adresu/rachunku i wpis audytowy razem. Ponowne wywołanie jest idempotentne. Współbieżny test wykonuje dwie operacje przez osobne sesje PostgreSQL i sprawdza, że nowy rekord przypisze tylko jedna z nich.

Dla naprawy pojedynczego konta dostępne jest polecenie z katalogu `apps/api`:

```powershell
uv run --frozen --all-groups python -m sensoria.modules.accounts.purchase_linking_cli --customer-id <UUID> --dry-run
uv run --frozen --all-groups python -m sensoria.modules.accounts.purchase_linking_cli --customer-id <UUID>
```

Polecenie wymaga istniejącego, zweryfikowanego konta. Tryb `--dry-run` wycofuje transakcję i raportuje liczniki; tryb wykonawczy zapisuje wynik i audit log. Wynik nie zawiera adresów, kodów voucherów ani danych zamówień.

## Dane konta

Zamówienia pozostają źródłem prawdy dla danych historycznych. Przy przypisaniu importujemy pomocniczo:

- adres dostawy tylko dla dostawy kurierskiej, nie adres paczkomatu, gabinetu ani punktu odbioru; adres jest deduplikowany według znormalizowanych pól i nazwy odbiorcy;
- pierwszy napotkany snapshot danych rozliczeniowych dla danego rodzaju nabywcy (PRIVATE/COMPANY); istniejący profil nie jest nadpisywany. NIP jest ponownie normalizowany i walidowany.

Import nie zmienia snapshotu fakturowego zamówienia. Wartości wejściowe są odrzucane, jeśli są niekompletne lub niepoprawne.

## Widoczność

Po zalogowaniu klientka otrzymuje jednorazową informację o liczbie przypisanych zamówień. Dane voucherów oraz przesyłek korzystają z `orders.customer_id`, a API konta nadal identyfikuje klientkę z sesji i zwraca odpowiedzi `private, no-store`. Dla niezweryfikowanego konta widok pokazuje wyłącznie informację, że wcześniejsze zakupy pojawią się po potwierdzeniu e-maila; nie ujawnia ich liczby.

## Brakujące integracje i ograniczenia

- Moduł płatności/webhooków nie istnieje w tym repozytorium. Nie ma więc punktu, który po późniejszym potwierdzeniu płatności automatycznie przypisze zamówienie. Obecne reconciliation obejmuje zamówienia już zapisane jako `paid` przy potwierdzeniu e-maila lub następnym logowaniu; dla spóźnionej płatności wymagany będzie hook w [33] albo ponowne uruchomienie serwisu.
- Nie ma tabeli entitlements ani pełnej historii zamówień. Voucher jest widoczny przez relację do przypisanego zamówienia; przyszła biblioteka cyfrowa musi dodać analogiczną integrację uprawnień.
- [59] nie ma interfejsu zarządzania danymi konta ani endpointu do edycji adresów/profilu rozliczeniowego. Bieżące tabele są minimalnym kontraktem danych i zasilane są historycznymi snapshotami.
- Nie ma ogólnej procedury usuwania konta [60]. FK `orders.customer_id` używa `ON DELETE SET NULL`; procedura usuwania musi osobno rozstrzygnąć retencję zakupów i sposób zachowania dostępu, zanim zostanie wdrożona.
- `Cart.customer_id` nie jest przepisywane. Koszyk nie jest dowodem własności historycznych zamówień i zachowuje własne zasady scalania.

## Weryfikacja

Na oddzielnej bazie PostgreSQL `sensoria_stage56_final_test` pełny backend zakończył się wynikiem 241 passed, 1 skipped. Testy obejmowały migracje, rollback, idempotencję i dwa niezależne równoległe reconciliation; w wyścigu dokładnie jedna transakcja przypisała zamówienie. Endpoint potwierdzenia login linku ma osobny test wywołania integracji, a rzeczywista logika serwisu jest testowana na PostgreSQL. Frontend: lint, format, TypeScript, build produkcyjny oraz 80 testów Vitest przeszły. Obraz API `sensoria-api:stage56` zbudował się poprawnie. Pre-commit uruchomiono, ale oba hooki pominęły pliki, bo checkout nie ma jeszcze śledzonych plików Git. Jedno ostrzeżenie Pytest dotyczy braku prawa zapisu do głównego `.pytest_cache`; nie wpływa na wynik testów. Sama obecność przypisanego rekordu nie zastępuje brakującego webhooka, historii zamówień ani interfejsu [59].



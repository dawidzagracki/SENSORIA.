# Etap [50] — dane prezentowe vouchera

## Przepływ danych

Checkbox przy produkcie przekazuje `is_gift` do istniejącego endpointu koszyka. Stan trafia do konkretnego `cart_items.gift_data`; pozycje voucherów już są osobne i nie scalają się, więc odbiorcy ani terminy prezentów nie mogą się zlać. Koszyk pozwala wyłączyć prezent, co usuwa jego robocze dane. Checkout przyjmuje dane dla identyfikatora konkretnej pozycji koszyka, sprawdza zgodność z aktualnym koszykiem i utrwala snapshot w `order_items.gift_snapshot`. Po potwierdzeniu płatności serwis [45] kopiuje snapshot do vouchera i tworzy trwałe zlecenie `voucher_gift_delivery_jobs` w tej samej transakcji co voucher.

Snapshot zawiera imię odbiorcy, opcjonalny e-mail, dedykację, tryb, wybraną datę i rozstrzygnięty czas, strefę, godzinę lokalną oraz wersję. E-mail i dedykacja są danymi osobowymi; nie wolno logować całego snapshotu. E-mail kupującej i dane fakturowe nie są zastępowane danymi obdarowanej.

## Termin i ważność

`vouchers.gifts.v1` przechowuje domyślną godzinę lokalną `09:00`, strefę `Europe/Warsaw` i limit dedykacji 300 znaków. Ustawienie jest rekordem `app_settings`; repozytorium nie ma panelu edycji ustawień. Dzień musi być ISO `YYYY-MM-DD` i nie może być wcześniejszy niż dzisiejsza data warszawska. Jeżeli wybrany dzień to dziś, lecz godzina 09:00 już minęła, termin rozwiązuje się do bieżącej chwili (wysyłka możliwie szybko), bez przesuwania na kolejny dzień.

Ważność prezentu pozostaje niedostępna do potwierdzonej wysyłki. `issued_at` nie jest zmieniane. Po potwierdzeniu przyjęcia wiadomości przez operatora `confirm_gift_delivery_sent` ustala `gift_sent_at` i termin jako koniec ostatniego dnia ważności w `Europe/Warsaw`, po dodaniu miesięcy kalendarzowych od lokalnej daty wysyłki. Opóźnienie kolejki nie skraca okresu. Funkcja wymaga wywołania przez przyszły worker [63]; na dziś nie ma takiego transportu, więc nie ma potwierdzonych wysyłek ani produkcyjnego wyliczenia opartego na faktycznym przyjęciu przez dostawcę.

Do chwili `gift_delivery_status = sent` centralny stan vouchera zwraca `scheduled`, a więc nie traktuje go jako aktywnego/realizowalnego. Nie nadano fałszywego znaczenia statusowi `active` w kolumnie trwałej.

## Zależności i jawne ograniczenia

- Repozytorium nie zawiera działającego systemu szablonów/wiadomości [62], kolejki i workera [63], ani autoryzacji klienta. Utworzona tabela jest trwałym zleceniem/danym harmonogramu prezentu, a nie kolejką wysyłkową; nie oznacza zakolejkowania przez dostawcę ani wysłania.
- W repozytorium `VoucherPDFJob` jest tylko modelem — brak generatora/worker PDF [45]. Prezentowe dane są utrwalone jako snapshot, ale ich renderowanie na bilecie i załączanie do wiadomości nie działa. Nie należy wysyłać samego standardowego PDF bez dedykacji.
- Nie ma endpointu zmiany dedykacji/terminu, bo nie ma uwierzytelnienia kupującej ani chronionego panelu administratora. Pola przed wysyłką nie można obecnie bezpiecznie edytować. Nie należy dodawać anonimowego endpointu opartego na publicznym kodzie.
- Nie dodano schedulera konkurującego z istniejącym schedulerem. `deliver_at` i status `pending` stanowią kontrakt wejściowy do przyszłego workera [63].
- Potwierdzenie zakupu kupującej i osobna wiadomość obdarowanej nie są wysyłane. Zlecenie kieruje wiadomość na adres obdarowanej, a gdy go nie podano — na adres kupującej zapisany przy zamówieniu, żeby mogła przekazać PDF osobiście.
- Makieta strony produktu jest dostępna w `docs/makiety/02-produkt-voucher-desktop.pdf`; makieta nie definiuje układu pól checkoutu. Zmiana wprowadza aktywną opcję produktu zgodną z tym opisem, lecz formularz szczegółów prezentu znajduje się w checkoutcie.

## Bezpieczne uruchomienie

Po migracji `f50000000001_voucher_gifts` można zmienić `app_settings.value` dla `vouchers.gifts.v1` w narzędziu administracyjnym/operacyjnej konfiguracji bazy. Wartość wymaga `local_send_time` w formacie `HH:MM`, strefy dokładnie `Europe/Warsaw` oraz `dedication_max_length: 300`. Aktualnie nie ma UI do tej edycji. Wysyłki testowe należy kierować do lokalnego transportu po wdrożeniu [63]; obecny kod sam nie nawiązuje połączenia pocztowego.

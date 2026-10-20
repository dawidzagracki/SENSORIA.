# Wybór punktu odbioru InPost

Stan decyzji: 2026-10-15.

## Wybrane rozwiązanie

Checkout korzysta z dostępnej klawiaturą wyszukiwarki po mieście lub kodzie pocztowym oraz listy wyników wewnątrz istniejącego modala [09]. Nie ładuje zewnętrznego Geowidgetu. Dzięki temu nie potrzebuje klucza Geowidgetu powiązanego z domeną ani skryptów i stylów mapy w przeglądarce. Zapasowy wpis kodu działa niezależnie od listy: backend pobiera szczegóły kodu od InPost, a regex jest wyłącznie walidacją formatu.

Backend odpytuje stały endpoint Points API dla Polski `https://api-pl-points.easypack24.net/v1/points`; nie przyjmuje URL-a od klienta. Wyszukiwanie używa `city` albo `post_code`, `type=parcel_locker` i `functions=parcel_collect`. Adapter sam filtruje rekordy do `status=Operating`, typu `parcel_locker` i funkcji `parcel_collect`. Szczegóły punktu są pobierane ponownie przy zapisie wyboru oraz przed utworzeniem zamówienia. Punkty POP i punkty nieczynne są odrzucane.

Dokumentacja InPost wymienia zasób Points API ShipX i opisuje pobieranie listy punktów; oficjalna dokumentacja obecnego Global API wskazuje osobny zakres OAuth `api:points:read`, a jego migracja w Polsce jest etapowana. Dlatego wybrano legacy polski Points API, którego dokumentacja punktów prezentuje żądania GET bez tokenu; nie zakładamy, że token Geowidget daje uprawnienia API. Przed wdrożeniem produkcyjnym należy potwierdzić z opiekunem InPost, że dostęp do legacy listy punktów oraz jej warunki wykorzystania pozostają właściwe dla umowy Sensoria.

Źródła sprawdzone 2026-10-15:

- [InPost Developers: Geowidget integration](https://developers.inpost-group.com/geowidget-integration) — token widgetu jest kluczem powiązanym z domeną; widget ładuje własne skrypty i style; opisana konfiguracja `parcelCollect` dotyczy punktów `parcel_locker` i funkcji `parcel_collect`.
- [InPost Developers: Authentication](https://developers.inpost-group.com/authentication) — Global API korzysta z OAuth 2.1, a punkty wymagają zakresu `api:points:read`.
- [InPost Developers: Migration Guide](https://developers.inpost-group.com/migration-guide) — migracja polskich operatorów jest etapowana; Points API Global jest wspólnym zasobem.
- [InPost: Aktualizacja dokumentacji ShipX](https://inpost.pl/aktualnosci-aktualizacja-dokumentacji-api-shipx) — ShipX obejmuje usługi InPost i wskazuje dokumentację integracji/punktów.
- [Dokumentacja punktów InPost](https://dokumentacja-inpost.atlassian.net/wiki/spaces/PL/pages/18153493/Points%2BParcel%2BLocker%2BParcelPoint) — opis listy, szczegółów, filtrowania `city`, `post_code`, `type`, `functions`, paginacji i formatu odpowiedzi.

## Konfiguracja i sekrety

Nie ma konfiguracji klucza widgetu, bo widget nie jest ładowany. Nie ma też poufnego tokenu Points API w aplikacji dla wybranego publicznego endpointu listy. Timeout połączeń backendu ustawia `INPOST_POINTS_TIMEOUT_SECONDS` (domyślnie 5 s, dopuszczalne 1–20 s). Adres API jest stały w adapterze, a nie konfigurowany danymi użytkownika. Próba HTTP ponawia się najwyżej raz; awaria zwraca kontrolowany HTTP 503. Nie buforujemy wyników, więc dane statusu punktu nie są utrzymywane poza świeżym odczytem.

W razie migracji do Global API trzeba dodać backendowe OAuth client credentials, token odświeżany po stronie serwera i scope `api:points:read`. Sekrety nie mogą trafić do `NEXT_PUBLIC_*`, kodu web ani logów. W produkcyjnym środowisku przed użyciem należy potwierdzić dostępność Global Points API dla polskiego konta InPost.

## Przepływ danych i prywatność

- Żądanie operatora wykonuje wyłącznie backend. Przeglądarka podaje tekst miasta/kodu albo kod punktu; nie podaje adresu punktu ani URL-a.
- Do wyszukiwarki InPost trafia ręcznie wpisane miasto lub kod pocztowy. Geolokalizacja nie jest używana ani uruchamiana.
- Wyniki przekazują checkoutowi kod, nazwę, adres, miasto, kod pocztowy, godziny, typ/funkcję, status oraz czas serwerowej weryfikacji.
- Zapisany wybór koszyka jest tylko snapshotem roboczym. Checkout ponownie pobiera punkt przed rozpoczęciem transakcji rezerwującej stan i zapisuje drugi snapshot w zamówieniu; późniejsze zmiany API nie modyfikują danych zamówienia.
- Po zmianie metody na kuriera backend usuwa wybór punktu z koszyka.
- Polityka prywatności [80] powinna informować o przekazaniu ręcznie wpisanego miasta/kodu operatorowi InPost oraz o celu (wyszukanie i weryfikacja punktu). Ten etap nie dodaje geolokalizacji ani kontowego śledzenia preferencji.

## Konto klienta [59]

Moduł konta nie udostępnia modelu klienta ani uwierzytelnienia. W `PickupPointPreferenceStore` przygotowano typowany kontrakt odczytu/zapisu ostatnio używanego punktu po rzeczywistym `customer_id`. Nie zapisujemy preferencji na podstawie gościnnego e-maila ani samego otwarcia modala. Integracja, podpowiadanie i ponowna weryfikacja preferencji pozostają niespełnione do etapu [59].

## Lokalna weryfikacja

Adapter i kontrolowany transport można testować przez zastąpienie `_request_json`; takie testy nie są dowodem łączności z kontem InPost. Konfiguracja wymaga jedynie `INPOST_POINTS_TIMEOUT_SECONDS`. Rzeczywista lista może zawierać zmienny status i czasowo niedostępne API; przy awarii nie akceptujemy kodu tylko na podstawie formatu.

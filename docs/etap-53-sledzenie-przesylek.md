# Etap [53] — śledzenie przesyłek na koncie

## Kontrakt API

`GET /api/accounts/shipments` zwraca prywatną listę zamówień klientki zawierających pozycje `BOOK`. Tożsamość pochodzi wyłącznie z `request.state.customer_id` ustawianego przez zaufaną warstwę uwierzytelniania; do czasu wdrożenia logowania endpoint odmawia dostępu (401). Nie przyjmuje identyfikatora klienta ani adresu e-mail. Odpowiedź ma `Cache-Control: private, no-store`, `Referrer-Policy: no-referrer` i `X-Robots-Tag`.

Dane dostawy pochodzą z `orders.shipping_data` i `orders.delivery_point_snapshot` zapisanych przy zamówieniu. W API zwracane są wyłącznie potrzebne pola adresowe. Numer przesyłki pochodzi z bieżącego rekordu `shipments`, a link jest budowany przez `build_shipment_tracking_url` z polityki `orders.shipment_tracking.v1`; nie jest przechowywany ani przyjmowany od klienta. Brak poprawnej konfiguracji daje `tracking_link_status=unconfigured` i brak linku.

## Prezentacja

Wspólny typ i komponent znajdują się w `apps/web/lib/shipment-presentation.ts` i `apps/web/components/account/shipment-tracking.tsx`. Statusy realizacji pochodzą z `orders.fulfillment_status`. Opisy względne używają lokalnych dni kalendarzowych urządzenia; SSR stosuje `Europe/Warsaw` jako deterministyczny fallback. Dziś, wczoraj i 2–6 dni są względne, starsze daty bezwzględne. Każdy opis ma semantyczny element `time` i dokładny `dateTime`.

Link przewoźnika otwiera się po kliknięciu w nowej karcie z `noopener noreferrer`; numer pozostaje tekstem, można go skopiować, a w razie niedostępnego Clipboard API ręcznie zaznaczyć.

## Zakres i zależności

W repozytorium nie ma makiet `06-konto-biblioteka-desktop.pdf` ani `10-moje-zamowienia-desktop.pdf`, strony biblioteki [42] ani historii zamówień [57]. Komponent udostępnia wariant biblioteczny i wariant bloku zamówienia, ale nie tworzy fikcyjnych ekranów. Logowanie klientów także nie jest jeszcze zaimplementowane, więc autoryzowane dane nie są obecnie dostępne w działającej sesji. Odbiór osobisty ma kontrakt stanów w [52], lecz obecny checkout nie zapisuje tej metody ani konfiguracji miejsca odbioru; komponent pokaże bezpieczny tekst zastępczy, jeśli brak informacji.

Zadanie nie odpytuje API przewoźnika i nie twierdzi, że status „w drodze” jest aktualizowany na żywo. Wiadomość o nadaniu pozostaje kontraktem zadania kolejki z [52]; worker [63] i szablon [62] nie istnieją, więc nie ma rzeczywiście wysłanej wiadomości do sprawdzenia.

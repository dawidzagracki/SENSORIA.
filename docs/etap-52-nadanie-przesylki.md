# Etap [52] — nadanie i odbiór książek

## Model

Zamówienie zachowuje osobny `status` płatności i `fulfillment_status`. Przyjęty zakres dopuszcza jedną paczkę na zamówienie, bez wysyłek częściowych. `shipments.order_id` jest unikalny. Zmiany przewoźnika i numeru są dopisywane do `shipment_history`; pierwotne `shipped_at` nie zmienia się przy korekcie.

`fulfillment_ready_at` jest początkiem wieku kolejki „Do wysyłki”. Powinien być ustawiany przez [33] w transakcji potwierdzającej płatność, przez `mark_fulfillment_ready_after_payment`. Ta integracja nie istnieje jeszcze w module payments, więc obecnie wiek i licznik nie obejmą zamówienia, dopóki hook płatności nie zostanie podłączony.

Wykonawca jest UUID z zaufanego principalu administratora; czas nadania pochodzi z serwera. Aktualny moduł admin nie dostarcza uwierzytelniania ani ról. Trasy `/api/admin/orders/...` są dlatego zamknięte fail-closed (HTTP 503 `ADMIN_AUTH_UNAVAILABLE`), nie przyjmują tożsamości w body i nie pozwalają wykonać operacji publicznie.

## Ustawienie URL-i śledzenia

W `app_settings` należy utrzymywać klucz `orders.shipment_tracking.v1` w postaci:

```json
{
  "carriers": {
    "inpost": {
      "label": "InPost",
      "template": "https://<zweryfikowany-host>/(ścieżka)?id={tracking_number}",
      "host": "<ten-sam-zweryfikowany-host>"
    }
  }
}
```

To jest kształt kontraktu, nie gotowy wzorzec produkcyjny. Wartość należy zweryfikować z aktualnymi materiałami przewoźnika przed wpisaniem. Walidator wymaga HTTPS, hosta zgodnego z konfiguracją i dokładnie jednego `{tracking_number}`; numer jest kodowany jako komponent URL. Nie używamy niezaufanego nagłówka Host. Ustawień nie da się obecnie edytować w panelu (brak [68]); bez skonfigurowanego wpisu operacja nadania jest niedostępna.

InPost wskazuje śledzenie przesyłek na [oficjalnej stronie](https://inpost.pl/sledzenie-przesylek). Materiały pomocy opisują typowy 24-cyfrowy numer przesyłki; walidacja używa tego tylko jako ostrzeżenia, nigdy jako dowodu istnienia przesyłki. Nietypowy, ale niepusty bezpieczny numer można zapisać po potwierdzeniu przez obsługę.

## Powiadomienie

Nadanie zapisuje rekord `shipment_notification_jobs` w tej samej transakcji co zmianę realizacji i audyt. Unikalny `idempotency_key` chroni ponowienia. Korekta numeru przed podjęciem zlecenia aktualizuje źródło danych, z którego przyszły worker powinien odczytać przesyłkę; korekta podczas `sending` zwraca konflikt. Korekta domyślnie nie tworzy wiadomości; jawna opcja dodaje nowe zlecenie.

W repozytorium nie ma ogólnego transportu wiadomości [63] ani szablonu powiadomienia o nadaniu [62]. Status `pending` oznacza wyłącznie trwałe zlecenie; nie oznacza zakolejkowania u dostawcy, wysłania ani dostarczenia. Potrzebny worker ma przed wysyłką atomowo przejść `pending` → `sending` i użyć bieżącego rekordu przesyłki. Wynik niejednoznaczny dostawcy wymaga obsługi zgodnej z jego idempotencją.

## Odbiór osobisty i panel

W modelu zamówienia przygotowano `ready_for_pickup` i `picked_up`, czasy oraz administratorów. Operacje sprawdzają opłacenie i metodę `pickup_in_person`, nie tworzą numeru przesyłki, historii shipment ani śledzenia; zlecenie gotowości jest osobnym rodzajem outbox.

Aktualny checkout przyjmuje tylko `parcel_locker` i `courier`, więc ścieżki odbioru osobistego nie można obecnie osiągnąć przez istniejący checkout. Wymaga podłączenia [31]. Nie ma też panelu [66] ani jego ramy, dlatego nie dodano martwego formularza UI. API i formularze kontraktowe są przygotowane za fail-closed autoryzacją.

## „Do wysyłki”

Serwis liczy zamówienia, nie sztuki: opłacone zamówienia z produktem `BOOK`, metodą parcel locker/courier, stanem `awaiting_fulfillment` i ustawionym `fulfillment_ready_at`. Najstarszy wiek liczony jest od tej chwili, nie od utworzenia zamówienia. Cyfrowe, nieopłacone, anulowane, nadane i odbiór osobisty są wykluczone. Do podłączenia `fulfillment_ready_at` potrzebny jest webhook [33].

# Wycena dostawy koszyka

## Konfiguracja

Usługa czyta przy każdym żądaniu koszyka jeden wpis `app_settings` o kluczu
`orders.delivery.v1`. Nie ma cache, więc zmiana JSONB jest widoczna bez ponownego
wdrożenia. Oczekiwany kształt:

Wartość `app_settings.value` musi być obiektem z polami `parcel_locker_cost_grosz`,
`courier_cost_grosz`, `free_shipping_threshold_grosz`, `incentive_threshold_grosz`
oraz `vat_rate`. Kwoty i progi są całkowitymi groszami. `15000` oznacza 150,00 zł.
Wartość `incentive_threshold_grosz=5000` jest propozycją ustawienia (50,00 zł), a
nie progiem narzuconym specyfikacją. Przed użyciem operator musi wprowadzić
zatwierdzone koszty paczkomatu i kuriera oraz potwierdzoną stawkę VAT. Brak wpisu
lub błędny JSON powoduje kontrolowany HTTP 503 dla koszyka wymagającego dostawy;
system nie zamienia błędnej konfiguracji na darmową wysyłkę.

VAT jest niezależną wartością `VatRate` i musi zostać ustalony zgodnie z
zatwierdzoną konfiguracją podatkową. Nie jest kopiowany ze stawki produktu.
Rozliczenie dostawy jest osobnym wierszem ze stawką, netto i VAT; grupy VAT
produktów pozostają rozliczeniem samych pozycji, a podsumowanie pełnego brutto
to produkty po rabacie plus dostawa. Zero złotych dostawy nadal zwraca
skonfigurowaną stawkę, nie stawkę `RATE_0`.

## Reguły

- Dostawy wymaga wyłącznie produkt `BOOK` (domena `Product.requires_shipping`).
- Podstawa progu to suma brutto wszystkich produktów po rabacie, bez dostawy.
- Kwalifikacja używa `wartość >= próg`; dokładny próg daje darmową dostawę.
- Zachętę pokazujemy tylko dla dodatniej różnicy mniejszej niż skonfigurowany
  `incentive_threshold_grosz`.
- Bez metody przy fizycznym produkcie API zwraca wyceny i `requires_method_selection=true`;
  suma pozostaje nieostateczna. `PATCH /cart/delivery` z metodą `parcel_locker`
  albo `courier` zapisuje wybór. Kwotę wylicza serwer.
- Przy koszyku pustym lub wyłącznie cyfrowym nie pokazujemy wyboru, progu,
  zachęty ani pozornej informacji o darmowej przesyłce.

Wycena jest punktem integracji kosztowej [27]. Wybór konkretnego paczkomatu,
adres i realizacja wysyłki pozostają osobnymi etapami.

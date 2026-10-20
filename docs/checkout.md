# Checkout gościa — etap [29]

Frontend `/zamowienie` pobiera koszyk i wyłącznie publiczne, wersjonowane teksty zgód z API. Backendowy endpoint `POST /cart/checkout` jest publicznie dostępny pod `POST /api/cart/checkout` przez Caddy; przyjmuje dane formularza i `Idempotency-Key`, nie przyjmuje cen, VAT, identyfikatora koszyka ani klienta. Koszyk identyfikuje istniejące HttpOnly cookie `cart_token`.

## Przebieg

1. API blokuje aktywny koszyk, weryfikuje klucz idempotencji i ponownie odczytuje publikację produktu, wariant, cenę, VAT, rabat, metodę dostawy i stan książek.
2. Zmiana ceny/VAT albo brak dostępności kończy się konfliktem bez utworzenia zamówienia.
3. W jednej transakcji API tworzy zamówienie `pending_payment`, pozycje ze snapshotami, rozliczenie JSON, wersjonowane zapisy zgód oraz czasowe rezerwacje książek i limitu kodu rabatowego. Rezerwacje wygasają po 30 minutach; cykliczne zadanie API zwalnia je i oznacza nieopłacone zamówienie jako `expired`.
4. Ponowienie z tym samym kluczem i treścią zwraca to samo zamówienie. Klucz z innym payloadem zwraca konflikt. Koszyk pozostaje dostępny do idempotentnego ponowienia; jego cookie nie jest tokenem konta.

`GET /api/cart/checkout-config` zwraca tylko tekst i wersję zgód. API porównuje przesłaną wersję z aktualną i odrzuca formularz po zmianie treści, prosząc o odświeżenie. Zapis zgody przechowuje rodzaj, wartość, czas serwera, wersję, dokładną wyświetloną treść, zakres produktów i tryb wydania. Marketing pozostaje osobną, dobrowolną wartością.

## Warunki i ograniczenia

- Dostawa jest wymagana tylko dla `BOOK`. Obecnie wybór punktu Paczkomat nie jest dostępny; kurier wymaga skonfigurowanej wyceny [27] i adresu. Adres punktu odbioru nie jest adresem faktury.
- Dla firmy backend weryfikuje sumę kontrolną polskiego NIP. Dla zakupów cyfrowych nie jest wymagany adres wysyłki.
- `DIGITAL` i `AUDIOBOOK` wymagają zgody na natychmiastowe wydanie. Vouchery nie są przez to klasyfikowane jako treść cyfrowa. Tryb wydania po 14 dniach jest jawnie odrzucony, ponieważ kolejka wydania odroczonego nie istnieje.
- Zgody regulaminowej/digitalnej nie ustawia się domyślnie. API obecnie nie posiada niezależnego pola „akceptacja polityki prywatności”; tekst wersjonowanej zgody wymaganej obejmuje oba dokumenty.
- Zamówienie zapisuje wybraną metodę BLIK/karta/portfel. Odpowiedź zawiera `payment_integration` (`stripe` albo `not_configured`, gdy brak kluczy `STRIPE_*`) oraz `access_token` — przy ponowieniu z tym samym kluczem token jest wyliczany ponownie z `SECRET_KEY`, nie jest zapisywany. Płatność startuje osobnym `POST /payments/orders/{id}/session?token=…`; zamówienie staje się opłacone wyłącznie po podpisanym webhooku Stripe.
- Odbiór w gabinecie (`pickup_in_person`) jest bezpłatny i nie wymaga adresu ani punktu. Odroczone wydanie treści cyfrowej po 14 dniach nie istnieje — taki tryb jest odrzucany. Rezerwacja stanu nie zmniejsza fizycznego stocku; jej wygaśnięcie i zwolnienie obsługuje scheduler API, a stan jest rozliczany przy potwierdzonej płatności.

## Weryfikacja

Testy checkoutu znajdują się w `apps/api/tests/test_cart.py`; wymagają izolowanego PostgreSQL 16 wskazanego przez `TEST_DATABASE_URL` z nazwą kończącą się `_test`. Uruchom z `apps/api`:

```powershell
uv run --frozen --all-groups pytest tests/test_cart.py -k "checkout or nip"
```

Frontend testuje kontrakt gościa i pominięcie danych dostawy dla koszyka cyfrowego przez:

```powershell
npm --prefix apps/web test -- components/checkout/checkout-page.test.tsx
```

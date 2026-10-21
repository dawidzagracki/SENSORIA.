# Wersja pokazowa (gałąź `demo/prezentacja`)

Cały sklep działa lokalnie z przykładowymi danymi: produkty, zamówienia, biblioteka, czytnik, audiobook, panel, opinie,
zgłoszenia, rabaty, strony prawne i FAQ. **Płatność i poczta są atrapami** — żadne prawdziwe pieniądze ani maile nie są użyte.

## Uruchomienie

```bash
./demo/start.sh                    # budowa, start i wgranie danych (kilka minut przy pierwszym razie)
./demo/compose.sh down -v && ./demo/start.sh   # zresetowanie do czystego stanu
./demo/compose.sh ps               # sprawdzenie usług
```

Wymaga Dockera, a do wgrania audiobooka macOS-owych `say` i `ffmpeg` (głos „Zosia”).

| Co | Adres |
|---|---|
| Sklep | http://localhost:8090 |
| Panel sklepu | http://localhost:8090/admin/logowanie |
| Poczta (Mailpit) — wszystkie maile ze sklepu | http://localhost:8025 |
| Bramka płatności (demo) | otwiera się sama po „Zamawiam i płacę” |

Konta (hasło wszędzie: `Demo-Sensoria-2026`):
- Panel, właścicielka: `wlascicielka@sensoria.demo`; obsługa (mniejsze uprawnienia): `obsluga@sensoria.demo`
- Klientka (logowanie hasłem lub „Wyślij mi link” — link przychodzi do Mailpit): `anna.kowalska@sensoria.demo`
- Kody rabatowe: `WITAJ10` (−10%), `ZMYSLY20` (−20 zł, od 50 zł)

## Proponowany scenariusz (ok. 15 min)

1. **Strona główna i katalog** — filtry, wyszukiwarka, karty produktów, ceny z VAT.
2. **Produkt** — voucher (wybór wariantu online/stacjonarnie), książka, e-book z darmowym fragmentem PDF, audiobook, kurs.
3. **Zakup jako gość** — koszyk, kod rabatowy, dostawa (Paczkomat/kurier/odbiór w gabinecie), checkout, płatność BLIK w bramce demo,
   strona potwierdzenia, zamówienie dostępne od razu.
4. **Poczta** (Mailpit) — potwierdzenie zamówienia, dostęp do plików, voucher z PDF.
5. **Konto klientki** (Anna) — logowanie, biblioteka, **czytnik** e-booka, historia zamówień, vouchery, dane i zgody (eksport/usunięcie).
6. **Audiobook** — zaloguj się jako Anna; audiobook kupiony w jednym z jej zamówień: odtwarzacz z rozdziałami.
7. **Panel** — pulpit, zamówienia (szczegóły, notatki, ponowne wysłanie dostępu), produkty (edycja, stan magazynu), vouchery
   (realizacja), klienci, opinie (moderacja), zgłoszenia, kody rabatowe, strony i FAQ, raporty (CSV), ustawienia, dziennik.
8. **Strony formalne i cookies** — regulamin, polityka prywatności, ustawienia cookies w stopce, centrum pomocy z odstąpieniem.

## Ograniczenia wersji pokazowej

- Płatność nie jest prawdziwa (atrapa Stripe w `demo/fake_stripe.py`); poczta trafia tylko do Mailpit.
- Dane osobowe, NIP i teksty prawne są demonstracyjne — nie do użycia produkcyjnego.
- Panel nie ma jeszcze 2FA (prace w gałęzi `wip/2fa-totp`).
- Pierwsze wejście po starcie może chwilę trwać; produkcyjny build web jest szybki dalej.

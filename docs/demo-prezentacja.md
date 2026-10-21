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
- Klientka (logowanie hasłem, „Zaloguj się przez Google” — atrapa z listą kont — lub „Wyślij mi link”, który przychodzi do Mailpit): `anna.kowalska@sensoria.demo`; konta Google w atrapie: Anna Kowalska, Ewa Nowak, Jan Pokazowy
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

## Testy przepływów (Playwright, prawdziwy stos)

`apps/web/e2e-demo/` zawiera 47 testów klikających sklep, konto i panel na działającym stosie demo (desktop + telefon):
karta → koszyk → checkout → bramka → potwierdzenie → biblioteka/czytnik/odtwarzacz, filtry i wyszukiwarka, kody rabatowe,
dostawa (gabinet, kurier, Paczkomat), faktura na firmę, rejestracja z potwierdzeniem e-maila (z Mailpit), opinie,
reklamacje, vouchery z QR i PDF, dokumenty, każda sekcja panelu.

```bash
docker run --rm -e DEMO_URL=http://localhost:8090 -e DEMO_HOST_MAP=1 -v "$PWD/apps/web":/work -w /work \
  mcr.microsoft.com/playwright:v1.64.1-noble npx playwright test -c playwright.demo.config.ts --project=desktop
```

(`--project=mobile` dla telefonu). Testy zostawiają zamówienia w bazie — przed pokazem zrób
`./demo/compose.sh down -v && ./demo/start.sh`.

## Błędy znalezione przy przeglądzie (do przeniesienia na `main`)

- karty w katalogu linkowały do pustej strony `/produkt/…`; teraz jedna strona `/sklep/…` + przekierowanie 308;
- przyciski „Do koszyka” w katalogu, na stronie głównej i w „Podobne” były zaślepkami;
- linki w mailach „potwierdź e-mail” i „ustaw hasło” prowadziły do 404 (brak tras `/[token]`);
- zakup przez zweryfikowane konto nie trafiał do historii zamówień do kolejnego logowania;
- zakładka „Faktury” była zaślepką, a lista zamówień zwracała puste dokumenty;
- QR vouchera w koncie miał podwójny prefiks `/api/api`;
- panel: podmiana obrazka produktu kończyła się błędem 500;
- obrazy `next/image` nie działały w obrazie produkcyjnym (rewrite `/api` wypieczony na `localhost:8000`);
- koszyk po opłaceniu zamówienia nie był czyszczony; mobilny koszyk i tabele panelu były nieczytelne;
- stały dziś test prezentu z datą w przeszłości.

## Ograniczenia wersji pokazowej

- Płatność nie jest prawdziwa (atrapa Stripe w `demo/fake_stripe.py`); poczta trafia tylko do Mailpit.
- Dane osobowe, NIP i teksty prawne są demonstracyjne — nie do użycia produkcyjnego.
- Panel nie ma jeszcze 2FA (prace w gałęzi `wip/2fa-totp`).
- Logowanie przez Google na produkcji wymaga `GOOGLE_CLIENT_ID` i `GOOGLE_CLIENT_SECRET` (przycisk pojawia się tylko wtedy); w demo działa atrapa.
- Loga płatności i dostawy (BLIK, Visa, Mastercard, Google Pay, Apple Pay, Stripe, InPost) to uproszczone znaki rysowane w SVG — przed premierą podmień je na oficjalne materiały marek.
- Wyszukiwarka Paczkomatów korzysta z atrapy (6 punktów: Olsztyn, Warszawa, Kraków); na produkcji — prawdziwe API InPost.
- Pierwsze wejście po starcie może chwilę trwać; produkcyjny build web jest szybki dalej.

# Instrukcja panelu sklepu — dla właścicielki i obsługi

Panel znajdziesz pod adresem `https://twoja-domena/admin/logowanie`. Logujesz się adresem e-mail i hasłem
założonym przez administratora technicznego. Po 5 błędnych próbach konto blokuje się na 15 minut. Sesja
wygasa po 2 godzinach bezczynności. Zawsze wyloguj się na cudzym komputerze (przycisk **Wyloguj** w menu).

## Role

| Rola | Co może |
|---|---|
| **Właścicielka** | wszystko, w tym ceny/kody rabatowe, strony prawne, ustawienia, dziennik zdarzeń, cofanie realizacji i anulowanie voucherów, wycofanie produktu |
| **Obsługa** | zamówienia, wysyłka, realizacja i przedłużanie voucherów, klienci (podgląd), opinie, zgłoszenia, produkty (edycja, pliki, stan), raporty |

## Pulpit

Pokazuje sprzedaż (dziś / 7 dni / 30 dni) i **listę spraw wymagających uwagi** — każdy kafelek prowadzi do
właściwego widoku. Żółty kafelek = jest coś do zrobienia.

## Zamówienia

1. **Lista** — filtruj po statusie płatności, realizacji, numerze lub e-mailu. Kliknij numer, aby otworzyć zamówienie.
2. **Szczegóły** — pozycje, płatności (wszystkie próby), dokumenty, wysłane wiadomości i **notatki wewnętrzne**
   (klientka ich nie widzi).
3. **Wysyłka książki** (InPost): w „Wysyłka” wpisz numer przesyłki i kliknij **Oznacz jako wysłane** — klientka dostaje
   e-mail z linkiem do śledzenia. Po doręczeniu: **Oznacz jako dostarczone**.
4. **Odbiór w gabinecie**: gdy zamówienie jest gotowe, kliknij **Gotowe do odbioru** (klientka dostaje e-mail),
   po wydaniu — **Odebrane**.
5. **Wyślij ponownie dostęp** — dla zamówień z materiałami cyfrowymi, gdy klientka zgubiła e-mail.
6. **Anuluj zamówienie** — tylko dla zamówień czekających na płatność (zwalnia rezerwację książek i kodu rabatowego).
   Zamówień opłaconych nie anulujesz tutaj — zwrot pieniędzy robisz w panelu Stripe i odnotowujesz w notatce.

## Produkty

* **Dodaj produkt** → wybierz rodzaj (książka / e-book lub kurs PDF / audiobook / voucher), uzupełnij dane → **Zapisz szkic**.
* W edycji: nazwa, opisy, ceny, SEO, **zdjęcia** (PNG/JPEG/WebP do 5 MB).
* **Zmiana ceny wymaga powodu** — trafia do niezmiennej historii cen. Pole „Cena przed obniżką” wypełniaj tylko
  przy promocji: sklep sam pokaże ustawową informację o najniższej cenie z 30 dni.
* **Pliki płatnych materiałów** (e-book/kurs: PDF; audiobook: MP3 osobno dla każdego rozdziału): najpierw wpisz
  etykietę, potem wybierz plik. Aplikacja sprawdza zawartość pliku (nie nazwę) i odrzuca uszkodzone lub
  zabezpieczone hasłem PDF-y. Pliki nie są publiczne; PDF jest oznaczany danymi kupującej przy każdym pobraniu.
* **Treść czytnika** (e-book): wklej rozdziały jako JSON (przykład jest w polu). Dozwolone bloki: `p`, `h2`, `quote`,
  `list`, `exercise`.
* **Stan książki**: korekta ze zmianą (np. `5` lub `-2`) i uzasadnieniem; każda zmiana jest w rejestrze magazynu.
* **Opublikuj** — sprawdza kompletność (nazwa, cena, VAT, zdjęcie, dane rodzaju). **Wycofaj** (właścicielka) —
  produkt znika ze sklepu, ale pozostaje w zamówieniach.

## Vouchery

* **Wyszukiwanie** po kodzie, e-mailu kupującej, imieniu obdarowanej lub numerze zamówienia → **Otwórz**.
* **Zrealizuj voucher** — wpisz osobę realizującą wizytę; data zapisuje się automatycznie. Voucher zrealizowany,
  wygasły lub anulowany nie da się zrealizować.
* **Przedłuż** — wybierz nowy ostatni dzień ważności (ważny „włącznie”) i powód; PDF vouchera wygeneruje się ponownie.
* **Cofnij realizację / Anuluj** (właścicielka) — wymagają powodu.
* **Rejestr realizacji** — pełna historia zdarzeń. **Prośby o przedłużenie** — decyzja z wyborem nowej daty.

## Klienci, opinie, zgłoszenia

* **Klienci** — wyszukiwarka i podgląd historii. Każde otwarcie profilu jest zapisywane w dzienniku.
* **Opinie** — nowe opinie (tylko od osób, które kupiły produkt) czekają na decyzję. **Opublikuj** lub **Odrzuć**
  (opcjonalna notatka). Treść jest tekstem — nic nie jest interpretowane jako HTML.
* **Zgłoszenia** — odstąpienia, zwroty, reklamacje. Przyjmij do realizacji, a potem rozpatrz lub odrzuć **z uzasadnieniem**
  (klientka je zobaczy). Na reklamację odpowiedz w 14 dni.

## Kody rabatowe (właścicielka)

Kod procentowy (1–100%) lub kwotowy, minimalna wartość zamówienia, limit użyć. Użycie liczy się dopiero po opłaceniu
zamówienia. **Wyłącz** zatrzymuje kod bez usuwania historii.

## Strony i FAQ (właścicielka)

* **Strony**: regulamin, polityka prywatności, polityka cookies, dostawa i płatności, o autorce. Format tekstu: `## `
  nagłówek, `> ` cytat, `- ` punkt listy, pusta linia = nowy akapit. **Zapisz szkic**, a dopiero potem **Opublikuj**.
  Do czasu publikacji strona pokazuje „treść w przygotowaniu”. **Teksty prawne zweryfikuj z prawnikiem.**
* **FAQ** (centrum pomocy): kategoria, pytanie, odpowiedź, kolejność, opublikowane tak/nie.

## Raporty

Wybierz zakres (do 366 dni) i grupowanie (dni/miesiące). Zobaczysz sprzedaż brutto/netto/podatek, rozbicie na stawki VAT
i najlepsze produkty. **Pobierz CSV** — plik do Excela (separator `;`, UTF-8, komórki zabezpieczone przed formułami).

## Ustawienia (właścicielka)

Dane sprzedawcy na paragonach i fakturach, koszty i progi dostawy, adres e-mail dla alertów, dane kontaktowe i adres
rezerwacji wizyt, opóźnienie próśb o opinię. Zmiany działają od razu.

## Dziennik (właścicielka)

* **Zdarzenia** — kto i co zmienił (logowania, ceny, publikacje, realizacje voucherów, płatności…). Filtr po początku
  nazwy akcji, np. `voucher.`, `order.`, `payment.`.
* **Zgody cookies** — rejestr wyborów odwiedzających.

## Co robić, gdy…

| Sytuacja | Działanie |
|---|---|
| Klientka nie dostała e-maila | Zamówienie → sekcja „Wiadomości”: status i błąd. Dla materiałów cyfrowych użyj „Wyślij ponownie dostęp”. Sprawdź folder SPAM. |
| Płatność „wisi” | Zamówienie → Płatności. Jeśli Stripe pokazuje sukces, a zamówienie nie — sprawdź w Stripe → Webhooks i użyj „Resend”. |
| Pojawił się alert „Niezgodna kwota płatności” | Nie wydawaj towaru; sprawdź płatność w Stripe i skontaktuj się z klientką. |
| Konflikt magazynowy | Opłacono książkę, której zabrakło po wygaśnięciu rezerwacji: skontaktuj się z klientką (czekanie na dostawę lub zwrot). |
| Zapomniałaś hasła do panelu | Administrator techniczny uruchamia polecenie z `docs/wdrozenie-vps.md` pkt 5. |
| Podejrzenie włamania | Zmień hasła (panel, Stripe, poczta), sprawdź Dziennik → logowania, zgłoś administratorowi technicznemu. |

## Teksty prawne (regulamin, polityki)

Szkice stron `regulamin`, `polityka-prywatnosci`, `polityka-cookies`, `dostawa-i-platnosci`, `o-autorce` wgrywa polecenie
(z `apps/api`): `uv run --frozen --all-groups python -m sensoria.modules.content.legal_pages`. Strony powstają jako **szkice**,
nigdy nie nadpisują edycji. Uzupełnij pola `[UZUPEŁNIJ]` (NIP, e-mail, życiorys autorki) w Strony i FAQ, każ prawnikowi sprawdzić
treść i dopiero opublikuj.

# Lista kontrolna responsywności i dostępności ekranu

Użyj kopii tej listy przy każdym nowym ekranie. Zapisuj rzeczywiste wyniki; brak sprawdzenia oznacz jako **niesprawdzone**. Automat axe nie potwierdza pełnej zgodności z WCAG ani poprawności treści.

## Dane kontroli

- Nazwa ekranu / URL:
- Data:
- Osoba wykonująca:
- Środowisko / commit:
- Testowane szerokości: 360 px / 390 px / 768 px / 1024 px / 1280 px / inne:
- Wynik ogólny:
- Znalezione problemy:
- Wykonane poprawki:
- Pozostałe ograniczenia:

## Układ i responsywność

- [ ] Przy 360 px nie występuje poziome przewijanie strony; przy przepełnieniu zapisano winny element i poprawkę.
- [ ] Style są mobile-first; układ rozszerza się przez breakpointy [08] (`sm: 360px`, `md: 768px`, `lg: 1024px`, `xl: 1280px`).
- [ ] Sprawdzono reprezentatywne szerokości telefonu, tabletu i desktopu oraz zachowanie na granicach breakpointów.
- [ ] Aktywne obszary kontrolek mają co najmniej 44 × 44 px.
- [ ] Tabele na wąskim ekranie są prezentowane jako karty, a etykiety identyfikują wartości.
- [ ] Obrazy rezerwują miejsce przez jawne wymiary lub proporcje; sprawdzono przed i po załadowaniu.
- [ ] Długie słowa, adresy i treści nie wypychają kontenerów poza ekran.
- [ ] Dialogi, menu i inne treści otwierane mieszczą się na małym ekranie i przewijają wewnętrznie, gdy trzeba.

## Semantyka i treść

- [ ] Strona ma dokładnie jeden `h1`, hierarchia nagłówków jest logiczna i nie pomija poziomów.
- [ ] Strona ma dokładnie jeden semantyczny `main`.
- [ ] Obrazy informacyjne mają sensowny `alt`; dekoracyjne mają `alt=""`.
- [ ] Każde pole formularza ma powiązaną etykietę; błędy i podpowiedzi są powiązane z polem.
- [ ] Informacja nie jest przekazywana wyłącznie kolorem; tekst/status pozostaje widoczny.
- [ ] Kontrast wszystkich zestawień odpowiada progom i rolom tokenów [08].

## Klawiatura i interakcje

- [ ] Pierwszy Tab ujawnia link „Przejdź do treści”; aktywacja przenosi fokus do `main`.
- [ ] Focus jest widoczny, kolejność logiczna; nie użyto dodatniego `tabindex`.
- [ ] Linki, przyciski i stopka są dostępne z klawiatury.
- [ ] Menu mobilne obsługuje klawiaturę, Escape, focus trap i przywrócenie fokusu.
- [ ] Modal obsługuje klawiaturę, Escape, focus trap, przywrócenie fokusu i blokadę tła.
- [ ] Accordion obsługuje klawiaturę, a zamknięta treść nie jest osiągalna Tabem.
- [ ] Zmiana szerokości nie pozostawia focusu ani blokady tła w ukrytym menu/dialogu.

## Ruch, powiększenie i automaty

- [ ] `prefers-reduced-motion: reduce` wyłącza animacje dekoracyjne, przejścia i płynne przewijanie; funkcjonalny stan nadal jest czytelny.
- [ ] Przy powiększeniu przeglądarki do 200% nie ma utraty treści ani funkcjonalności; opisano, czy był to rzeczywisty zoom czy tylko symulacja.
- [ ] Wynik axe: strony i otwarte stany zapisano; wszystkie `critical`/`serious` rozwiązano.
- [ ] Wyniki `moderate`/`minor` i `incomplete` zapisano do przeglądu; `incomplete` oceniono ręcznie albo jawnie pozostawiono jako niesprawdzone.
- [ ] Ręcznie oceniono sens altów, etykiet, kontrastu, komunikatów i zachowania fokusu.

## Wyniki kontroli istniejącego layoutu i galerii [11]

Kontrole wypełniaj po ich wykonaniu. „Niesprawdzone” nie oznacza zaliczenia.

| Obszar / stan                                                               | Test                                                                                                | Wynik                                                                                                                                                                                                                                                                                                                                                                         |
| --------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Layout sklepu (`/`, `/sklep`, `/koszyk`, `/zamowienie`, `/konto`, `/pomoc`) | Axe WCAG 2.1 A/AA na 360/1280 px; szerokości i przepełnienie dokumentu 360/390/640/768/1024/1280 px | **Spełnione**: 0 naruszeń `critical`/`serious`; bez poziomego przepełnienia. `incomplete` koloru w stopce oceniono: `ink-muted` na najjaśniejszym końcu gradientu 7,82:1, `ink` 17,46:1.                                                                                                                                                                                      |
| `/dev/tokeny` — galeria, formularze i przykłady                             | Axe WCAG 2.1 A/AA na 360/1280 px; szerokości i przepełnienie dokumentu 360/390/640/768/1024/1280 px; cele dotykowe | **Spełnione**: 0 naruszeń `critical`/`serious`; bez poziomego przepełnienia i cele ≥44×44 px. Długi niełamliwy adres zawija się; placeholder obrazu rezerwuje proporcję 1:1 (brak prawdziwych obrazów do testu ładowania). `incomplete` oceniono ręcznie: `ink` na `surface-muted` 16,45:1, `ink` na `surface` 18,04:1; wskaźnik accordionu jest dekoracyjny, stan przekazuje `aria-expanded`. |
| Menu mobilne otwarte                                                        | Axe, Escape, focus trap, przywrócenie fokusu i zmiana szerokości                                    | **Spełnione** w Chromium: bez naruszeń blokujących; Tab/Shift+Tab pozostają w dialogu, Escape przywraca fokus, menu zamyka się od 768 px.                                                                                                                                                                                                                                     |
| Modal otwarty                                                               | Axe, focus trap, Escape, powrót fokusu i scroll lock                                                | **Spełnione** w Chromium: bez naruszeń blokujących; fokus zostaje w dialogu, Escape zamyka, fokus wraca do przycisku, przewijanie tła blokowane i przywracane.                                                                                                                                                                                                                |
| Accordion rozwinięty                                                        | Axe i klawiatura                                                                                    | **Spełnione** w Chromium: bez naruszeń blokujących; ArrowDown, Home, End i Space sprawdzone.                                                                                                                                                                                                                                                                                  |
| Reduced motion                                                              | Emulowana preferencja, style animacji/przewijania i czytelny loading                                | **Spełnione** w Chromium: `reduce` aktywne, animacja spinnera 0,01 ms, przewijanie `auto`, loading pozostaje czytelny.                                                                                                                                                                                                                                                        |
| Skip link                                                                   | Pierwszy Tab i aktywacja                                                                            | **Spełnione** w Chromium: pierwszy fokus ujawnia link, Enter przenosi fokus do `main`; nawigacja desktopowa i stopka osiągalne Tabem.                                                                                                                                                                                                                                         |
| Rzeczywisty zoom przeglądarki 200%                                          | Reflow, dostępność treści i funkcji                                                                 | **Niesprawdzone**: 640 px przetestowano tylko jako symulację węższego viewportu; rzeczywistego zoomu nie sprawdzono.                                                                                                                                                                                                                                                          |
| Test kontrolowanego naruszenia `critical`                                   | Axe wykrywa naruszenie, komenda kończy się kodem niezerowym                                         | **Spełnione**: kontrolowane `aria-checked` na `button` wykryto jako `aria-allowed-attr` (`critical`); Playwright zakończył się kodem 1. Fixture usunięto.                                                                                                                                                                                                                     |

Kontrole wykonano lokalnie w Chromium przez Playwright, nie w GitHub Actions. Próba sterowania oknem przez narzędzie UI zakończyła się błędem inicjalizacji. Szerokość 640 px jest symulacją, nie rzeczywistym zoomem. Wyniki axe `incomplete` dla kontrastu oceniono ręcznie na tokenach i najgorszym końcu gradientu.

## Zasada dla przyszłych ekranów 07 i 10

Indeks makiet wskazuje panel sklepu z zamówieniami (07) oraz historię zamówień (10). Nie są budowane w etapie [11]. Ich dane tabelaryczne na wąskim ekranie należy pokazywać jako listę kart; każda wartość ma mieć etykietę pola, a nie polegać wyłącznie na kolejności kolumn.

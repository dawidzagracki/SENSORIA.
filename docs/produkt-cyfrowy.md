# Strona produktu cyfrowego

Trasa `/sklep/[slug]` wybiera widok DIGITAL tylko na podstawie `kind` z `GET /products/{slug}`. E-book i kurs PDF rozróżnia pole `digital.label`; inne rodzaje nadal trafiają do właściwych istniejących tras. Produkt, wariant etykiety, kategorie, odbiorcy, obraz, opis i rekomendacje pochodzą z odpowiedzi API. Kwoty pozostają całkowitymi groszami do momentu formatowania.

## Ceny i historia obniżki

`price` to aktualna cena brutto, `compare_at_price` to przekreślona cena porównawcza, a `digital.lowest_price_before_discount` to odrębny wynik historii. Procent obniżki zaokrąglany jest do najbliższego całego procentu, połówki w górę; obliczenie wykorzystuje arytmetykę całkowitoliczbową `BigInt`.

Backend ustala początek aktualnego stanu obniżki z kolejnych snapshotów `price_history` mających tę samą parę `price` i `compare_at_price`; zmiana wyłącznie VAT nie rozpoczyna go ponownie. Następnie wywołuje `lowest_price_last_30_days` z `valid_from` pierwszego snapshotu tej serii. Zapytanie liczy `[moment obniżki − 30 dni, moment obniżki)`, włącznie z ceną obowiązującą na początku okna. Jeżeli historia nie zawiera wcześniejszego, odmiennego stanu, `discount_started_at` i najniższa cena są `null`; frontend jawnie pokazuje brak możliwości ustalenia. Nie podstawia `compare_at_price` ani obecnej ceny.

## Pola widoku i źródła

- Tytuł, podtytuł, opis, obraz z alt, przypisane kategorie, odbiorcy, cena, cena porównawcza, VAT, etykieta E-BOOK PDF/KURS PDF, format, liczba stron, wydanie, dostępność i powiązane produkty: szczegóły publicznego API katalogu.
- Rekomendacje API są dobierane według istniejącej wspólnej kategorii, nie relacji autora; interfejs nazywa je „Podobne materiały”. Pobierane są zbiorczo w szczegółach produktu.
- JSON-LD `Product` zawiera bieżącą cenę w PLN, dostępność, opis, obraz i publiczny adres produktu. Cena porównawcza i najniższa historyczna nie są ofertą. Nie ma fikcyjnych ocen ani recenzji.
- Informacja o zgodzie na natychmiastowe udostępnienie jest tekstem informacyjnym. Strona nie zapisuje zgody i nie wdraża odroczonego wydania.

## Integracje i brakujące dane

Model `ProductDigital` nie zawiera spisu treści, rozdziałów e-booka, opisu autora, materiałów autora, szczegółowych korzyści, zatwierdzonych FAQ ani liczby stron bezpiecznego fragmentu. Interfejs nie kopiuje tych informacji z makiety do wszystkich produktów i wskazuje brak konfiguracji. Wymagane są pola redakcyjne powiązane z konkretnym produktem.

Etapy [21] (bezpieczny podgląd), [24] (serwerowy koszyk i kontrola ceny), [41] (znakowanie plików) oraz [73] (opinie) nie są dostępne. Przycisk podglądu jest wyłączony, zakup zgłasza brak integracji, a publiczne oceny i cytaty są pominięte. Treści o płatności, dostawie, zgodności urządzeń, fakturach i zwrotach wymagają zatwierdzenia względem rzeczywistej oferty i regulaminu.

## Kontrole

Fixture przeglądarkowa sprawdza oba rodzaje DIGITAL, renderowanie SSR/JSON-LD, wyświetlanie obniżki i ceny z historii, brak historycznej noty bez obniżki, responsywność 360 px oraz jawne zachowanie bez koszyka i podglądu. To nie potwierdza rzeczywistego produktu z bazy ani integracji zakupowych.

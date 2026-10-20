# Strona produktu: voucher

Trasa `/sklep/[slug]` pobiera publiczne szczegóły przez `GET /products/{slug}`. Pokazuje widok voucherowy wyłącznie dla `kind=VOUCHER`; inne rodzaje kieruje do istniejącego `/produkt/{slug}`. Brak produktu (API 404) daje 404, a awaria API nie jest zamieniana na 404.

Wybór wariantu bazuje na istniejących `voucher.variants`: ID, rodzaj i cena w groszach. URL używa `variant=gabinet` dla `IN_PERSON` oraz `variant=online` dla `ONLINE`. Pierwszy wariant zwrócony przez API jest domyślny. Nieprawidłowy parametr jest usuwany przez przekierowanie serwerowe, z zachowaniem innych parametrów. Zmiana wyboru używa nawigacji Next.js i historii przeglądarki. VAT pochodzi z `vat_rate` produktu, a oznaczenie EXEMPT pozostaje oddzielone od RATE_0.

Odpowiedź szczegółów API została rozszerzona o `vat_rate`, `is_available` i ID wariantów. To pola odczytywane z istniejących modeli; nie dodano tabel ani migracji.

## Zakup i prezent

Moduł koszyka [24] oraz serwerowa kontrola ceny jeszcze nie istnieją. `lib/voucher-cart.ts` dokumentuje przyszły kontrakt przyjmujący wyłącznie ID produktu i wariantu oraz opcjonalne wskazanie prezentu — bez ceny klienta. Aktualny adapter kończy się jawnym błędem, nie zmienia licznika i nie przekierowuje. Nie należy traktować kliknięcia jako zakupu. Opcja prezentu jest widoczna, ale wyłączona do czasu integracji [50].

Treści płatności, PDF, umawiania i przedłużania odtworzono jako tekst makiety i oznaczono informacją, że te operacje nie są realizowane przez aplikację. Odpowiedzi o fakturach, zwrotach i warunkach po terminie nie zostały określone; UI mówi wprost, że wymagają zatwierdzenia.

## Dane strukturalne

JSON-LD `ProductGroup` zawiera wyłącznie nazwę, opis, istniejące obrazy, ID wariantów, ceny wariantów przeliczone dokładnie z groszy na zapis PLN oraz dostępność produktu z API. Linki wariantów wskazują `/sklep/{slug}?variant=...`. Nie ma SKU, ocen ani fikcyjnych właściwości wariantu.

Kontrole: `npm run lint`, `npm run format:check`, `npx tsc --noEmit`, `npm test`, `npm run build`; testy przeglądarkowe dla wariantu i responsywności uruchamiaj przez `npm run a11y`. Fixture w harnessie jest testowa i nie potwierdza połączenia z prawdziwym API.

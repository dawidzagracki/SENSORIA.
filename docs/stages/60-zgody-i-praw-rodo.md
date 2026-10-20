# Etap [60] — zgody i realizacja praw

Stan dokumentacji: implementacja lokalna, 19 października 2026. Jest to opis stanu technicznego, a nie opinia prawna ani deklaracja pełnej zgodności działalności z RODO.

## Zakres i interfejs

Dolna część `/konto/dane` została rozbudowana o trzy zgody, uruchomienie i status eksportu danych oraz dialog zamknięcia konta. Istniejąca górna część [59] pozostaje na tej samej stronie. Zgody są zapisywane natychmiast po przełączeniu; eksport i zamknięcie wymagają osobnych jawnych działań. Prywatne odpowiedzi mają `Cache-Control: private, no-store`, `Vary: Cookie, Authorization`, `Referrer-Policy: no-referrer` i `X-Robots-Tag`.

API pod prefiksem `/accounts/privacy` (w Compose publiczny prefiks `/api` jest usuwany przez Caddy):

- `GET /consents` i `PUT /consents/{type}` — odczyt/zmiana zgody sesyjnego konta; typy `new_materials`, `voucher_reminders`, `review_requests`.
- `POST /exports` — utworzenie zadania eksportu; `GET /exports/{id}` — stan tylko właścicielki; `POST /exports/{id}/download` — krótko ważny autoryzowany plik.
- `POST /account-closure` — wymaga sesji, CSRF, świeżego uwierzytelnienia i zgodnego aktualnego e-maila.

Własność wynika z sesji, nie z `customer_id` formularza. Zmiany używają CSRF projektu. Teksty zgód są utrwalane niezmiennie jako `ConsentTextVersion`; nowe wersje wymagają nowego wpisu. Wartości `source`, IP i stempel czasu wyznacza serwer. IP i e-mailowe podmioty gościnne są reprezentowane w śladzie zgód przez HMAC z kluczem aplikacji. `subject_digest` pozwala rozpoznać zgodę gościa po normalizacji, bez przechowywania jawnego e-maila w samym śladzie.

## Historia zgód i wysyłki

`CustomerConsent` jest append-only. Zmiana tworzy nowe zdarzenie; odczyt wyznacza ostatnie zdarzenie zgodnie z czasem DB i stabilnym identyfikatorem. Checkout zapisuje osobne zgody marketingowe na znormalizowany e-mail z tekstem, źródłem i czasem. Import do konta następuje dopiero po potwierdzeniu własności przez [56], zachowując pierwotne czasy i teksty. Powiązane gościnne zdarzenie nie jest kopiowane ponownie.

Wspólna funkcja `has_current_consent` jest fail-closed i używana przez przypomnienia voucherów przy kwalifikacji oraz kontrolę bezpośrednio przed próbą wysłania. Cofnięcie zgody blokuje oczekujące przypomnienie; wiadomości już przyjętej dostawcą nie można cofnąć. [63] nie ma w tym repozytorium kompletnego dostarczającego workera, dlatego rekord/intencja kolejki nie jest dowodem wysłania ani doręczenia. Inne potencjalne typy wiadomości nie mają tu pełnej integracji zgód.

## Eksport

Eksport działa jako trwałe zadanie obsługiwane przez scheduler procesu API, bez blokowania requestu. Wynik jest prywatnym ZIP-em z JSON, dostępny po ponownej autoryzacji i krótkotrwałym odnośniku. Job ma właściciela, status, próbę, czas oraz prywatny identyfikator pliku; retry nie tworzy drugiego joba dla tej samej aktywnej operacji. Sesje, hashe haseł, tokeny i sekrety są wykluczone. Dane osoby trzeciej z prezentu są pomijane/redagowane.

Repozytorium nie ma jeszcze pełnego modułu dokumentów [36] ani historii pobrań [40] we wszystkich potrzebnych relacjach. Eksport wymienia te kategorie w manifeście jako niedostępne zamiast sugerować ich kompletność. Nie wykonano niezależnego ręcznego otwarcia archiwum w UI; testy API sprawdzają zakres i prywatność.

## Zamknięcie konta

Operacja jest natychmiastowa i idempotentna po zatwierdzeniu: ustawia `deleted_at`, blokuje uwierzytelnienie, unieważnia sesje i tokeny logowania/resetu/akcji, czyści profile i adresy, anuluje prywatne joby/eksporty i zabezpiecza kolejkę kontową przed późnym wysłaniem. Zalogowana sesja bieżąca jest również unieważniona, cookie usuwane. HMAC suppression marker zapobiega ponownemu podpięciu po odtworzeniu backupu.

Zamówienia, snapshoty, vouchery i wymagane dokumenty nie są kaskadowo usuwane ani modyfikowane. Dostęp do biblioteki jest zamknięty wraz z kontem zgodnie z wymaganiem etapu; jest to decyzja produktu i pozostaje w napięciu z wcześniejszym komunikatem o bezterminowym dostępie, a nie wymóg samego RODO. Nie anulujemy aktywnych voucherów ani zobowiązań. Część czyszczenia prywatnych eksportów działa w tle. Brak automatycznego cyklu usuwania backupów oznacza, że nie można obiecać natychmiastowego usunięcia wszystkich kopii; przy odtworzeniu suppression marker musi pozostać poza odtwarzanym zakresem bazy lub być odtworzony z kontrolowanego rejestru.

## Mapa danych i retencji

| Kategoria | Po zamknięciu | Powód zachowania/usunięcia | Retencja i ograniczenia |
|---|---|---|---|
| Profil, login, telefon | Usunięcie/wyłączenie; konto nie może się uwierzytelnić | Koniec operacyjnego profilu | Usunięcie w transakcji zamknięcia; kopie DB podlegają cyklowi backupów |
| Sesje, reset/login-link, tokeny akcji | Unieważnione | Natychmiastowe odcięcie dostępu | Nieaktywne rekordy mogą pozostać do rutynowego sprzątania |
| Książka adresowa i profile rozliczeniowe | Usunięcie | Nie są potrzebne do dalszego świadczenia | Wraz z zamknięciem; wcześniejsze snapshoty zamówień odrębnie |
| Zamówienia, pozycje i snapshoty nabywcy | Zachowanie z ograniczeniem dostępu | Historia umowy/rachunkowość i obsługa zobowiązań | Zależnie od kategorii dokumentacji, przepisów i przedawnienia; nie jeden uniwersalny termin |
| Dokumenty sprzedaży i księgowe | Zachowanie bez przerabiania treści | Obowiązki podatkowe/rachunkowe | Zgodnie z właściwą kategorią; typowy termin podatkowy liczony od końca roku, w którym upłynął termin płatności podatku, z wyjątkami |
| Vouchery i zdarzenia realizacji | Zachowanie, bez aktywnego loginu | Niewykonane zobowiązanie i historia świadczenia | Ograniczony dostęp administracyjny; termin zależy od zobowiązania i roszczeń |
| Zgody kontowe/gościnne | Minimalny dowód; jawny e-mail usuwany/pseudonimizowany | Rozliczalność zgody/wycofania | Brak automatycznej retencji/purge w tej implementacji; okres wymaga zatwierdzenia i wdrożenia |
| Audit log | Zachowanie tylko zdarzeń bez treści osobowych/sekretów | Bezpieczeństwo i rozliczalność | Według odrębnej polityki retencji logów; nie zdefiniowano tu automatycznego purge |
| Przygotowane eksporty | Anulowanie dostępu i usunięcie przez worker | Minimalizacja kopii danych | Krótki TTL linku; cleanup cykliczny; kopie zapasowe podlegają retencji |
| Kolejka e-mail | Anulowanie zadań oczekujących konta | Zapobieżenie wysyłce po zamknięciu | Dostarczający worker [63] nie jest kompletny; trzeba respektować stan konta przed wysyłką |
| Przeglądanie/analityka | Brak powiązanej historii klientki ujawnionej do eksportu | W repozytorium nie znaleziono profilu historii przeglądania | Zewnętrzna analityka poza sprawdzonym zakresem |

Usunięcie oznacza usunięcie operacyjnych danych, anonimizacja uniemożliwia identyfikację w danym zbiorze, a pseudonimizacja zachowuje możliwość powiązania przez dodatkowy sekret/klucz. Zachowane zamówienia mogą nadal pośrednio identyfikować klientkę; nie nazywamy tego pełną anonimizacją.

Podstawy wymagają oceny dla każdej kategorii i procesu. Oficjalny tekst RODO art. 17 wymienia wyjątki od usunięcia m.in. obowiązek prawny i ustalenie/obronę roszczeń ([EUR-Lex](https://eur-lex.europa.eu/eli/reg/2016/679/ojv)). Informacja KAS opisuje typowe liczenie przedawnienia zobowiązania podatkowego od końca roku, w którym upłynął termin płatności podatku, z wyjątkami ([podatki.gov.pl](https://www.podatki.gov.pl/abc-podatkow/uprawnienia-i-obowiazki-podatnika/?altTemplate=ArticlePdf&download=True)). Konkretne okresy retencji musi zatwierdzić administrator danych z księgowością/prawnikiem.

## Wyniki kontroli

### Makieta

Obejrzałem pierwszą stronę dostarczonego PDF-a (render 100 DPI w `tmp/pdfs/stage60-mock-1.png`). Dolna część pokazuje kartę „Zgody” z trzema przełącznikami i kartę „Twoje dane, Twoja decyzja” z dwoma przyciskami oraz wewnętrznym panelem usunięcia. Makieta ma zaznaczone przykładowe zgody i tekst „30 dni”; implementacja poprawnie bierze stan z bazy (domyślnie brak zgody) i opis przypomnień z aktualnej polityki [49], która może mieć kilka progów. To są dane wzorcowe, nie stan produkcyjny.

Bez uwierzytelnionej sesji widok `/konto/dane` przekierowuje do `/konto?next=...`, więc nie było możliwe uczciwe porównanie położenia/typografii kart prywatności w renderze strony. Bezpośrednie porównanie wizualne tej części: **NIESPRAWDZONE**. Widoczny stan logowania i istniejąca rama sklepu działają.

### Kryteria

| Kryterium | Ocena | Dowód / ograniczenie |
|---|---|---|
| Historia zgód, teksty i domyślna odmowa | SPEŁNIONE | Test PostgreSQL sprawdza trzy stany początkowe, append-only udzielenie/cofnięcie i wersję treści. |
| Sesyjna autoryzacja, prywatne cache, CSRF i audyt bez treści osobowych | SPEŁNIONE | Test API sprawdza 401 bez sesji, `no-store`, brak e-maila/IP w historii i własność. |
| Import zgód gościa dopiero po potwierdzeniu | SPEŁNIONE | Integracja [56] wywołuje import po potwierdzeniu; chronologia zachowuje źródłowy czas i digest. |
| Cofnięcie blokuje kwalifikację przypomnienia | SPEŁNIONE | Wspólny fail-closed reader użyty w [49]. |
| Ponowne sprawdzenie zgody bezpośrednio przed dostawcą | NIESPRAWDZONE | Odpowiednia funkcja jest przygotowana, ale kompletnego workera/dostawcy [63] brak. |
| Eksport pełny, prywatny i ponawialny | NIESPEŁNIONE | Zadanie i prywatny ZIP istnieją, ale historia pobrań i dokumenty sprzedaży nie mają modeli/integracji; nie jest to pełny eksport wszystkich danych projektu. |
| Ochrona endpointu pobrania eksportu | SPEŁNIONE | Test API sprawdza, że inna sesja nie odczyta ani nie pobierze joba; endpoint wymaga sesji i stanu `ready` z nieprzekroczonym TTL. |
| Pełny pozytywny przepływ pobrania ZIP | NIESPRAWDZONE | Nie wykonano testu, który przygotowuje archiwum, pobiera je sesją właścicielki i sprawdza zawartość ZIP. |
| Zamknięcie konta, sesji i tokenów | SPEŁNIONE | Test potwierdza zgodność e-maila i natychmiastową odmowę po unieważnieniu sesji; kod unieważnia tokeny i blokuje logowanie. |
| Zachowanie dokumentów, zobowiązań i wyjaśnienie utraty dostępu | SPEŁNIONE | Zamówienia/vouchery nie są usuwane; interfejs i dokumentacja ujawniają utratę dostępu do plików jako decyzję produktu. |
| Retencja, minimalizacja i czyszczenie wszystkich kopii | NIESPEŁNIONE | Brak purge historii zgód/logów i automatycznego cyklu czyszczenia backupów; okresy wymagają zatwierdzenia. |
| Zgodność wizualna dolnej części z PDF-em | NIESPRAWDZONE | PDF został obejrzany, ale render po autoryzacji nie był dostępny. |
| Responsywność i dostępność tej części po zalogowaniu | NIESPRAWDZONE | Globalny axe przechodzi 40/41, a wadliwy test jest zielony po izolacji; ekran privacy nie był dostępny bez sesji i nie oceniono go na 360 px. |

- **Etap:** NIE MOŻNA POTWIERDZIĆ jako kompletnie zaliczony; pozostały pełny eksport, faktyczna ścieżka wysyłki, polityka/automatyczna retencja oraz walidacja wizualna dostępnego widoku.

- Backend: świeża migracja Alembic na dedykowanej bazie `sensoria_stage60_v2_test` zakończona sukcesem. `ruff check`, format check i mypy strict dla zmienionych pakietów — sukces.
- Backend PostgreSQL: 56 testów integracyjnych w obszarze prywatności, auth, login-linków, profilu, podpinania zakupów, przypomnień i koszyka — sukces.
- Frontend: lint, format check, TypeScript i produkcyjny build — sukces.
- Axe Playwright: 40/41 testów przeszło w całym przebiegu. Jeden istniejący test katalogu nie doczekał zmiany URL w równoległym przebiegu; po uruchomieniu go osobno z jednym workerem przeszedł (1/1). Wskazuje to na konflikt/niestabilność testu równoległego, nie na odtworzoną regresję. Axe oznaczył istniejące zestawienia kontrastu jako `incomplete`; nie są automatycznie przypisywane tej stronie.
- Przeglądarka: niezalogowane wejście na `/konto/dane` przekierowuje do `/konto?next=%2Fkonto%2Fdane`; potwierdzono ochronę strony i wygląd istniejącej strony logowania. Nie uzyskano bezpiecznej testowej sesji, więc nie sprawdzono po zalogowaniu dolnych kart ani ich wizualnego porównania z PDF-em.
- Nie sprawdzono: pełnego eksportu wszystkich modułów, rzeczywistej wysyłki przez [63], cleanup plików w osobnym workerze/po restarcie, równoległego PostgreSQL dla wszystkich operacji adresowych/zamykania, wszystkich efektów odtworzenia backupu, 360 px strony prywatności ani bezpośredniego porównania dolnej części z PDF-em w przeglądarce.

Ocena etapu: **NIE MOŻNA POTWIERDZIĆ** jako kompletnego. Główna logika i API są zaimplementowane i mają zielone testy, lecz pełny eksport, e-mail, retencja/purge, lifecycle backupów i kontrola wizualna po sesji pozostają zależnościami/kontrolami otwartymi.

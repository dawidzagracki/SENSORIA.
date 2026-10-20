# Etap [59] — Dane osobowe i adresy

## Zakres i wynik

Źródłem kryteriów jest opis etapu [59] przekazany w zadaniu oraz makieta `12-dane-i-zgody-desktop.pdf`. Zaimplementowano odczyt i edycję profilu, dwuetapową zmianę e-maila, książkę adresową dwóch typów, regułę adresu domyślnego oraz użycie zapisanych danych w istniejącym checkoutcie.

**Ocena:** NIE MOŻNA POTWIERDZIĆ pełnego zaliczenia. Podstawowe API, UI, migracja i ścieżki profilu przeszły kontrole, ale pełna dostawa wiadomości e-mail zależy od workera [63], a sekcje zgód/eksportu/usuwania konta należą do [60]. Kontrola automatycznych migracji w lokalnym Windowsowym uruchomieniu napotkała wcześniejszą rewizję katalogu [16], która próbuje zmienić `products` przy oczekujących zdarzeniach triggerów. Nie zmieniano wydanej migracji.

## Zmienione pliki

- `apps/api/alembic/versions/f59000000001_account_profile_addresses.py`
- `apps/api/src/sensoria/modules/accounts/models.py`
- `apps/api/src/sensoria/modules/accounts/auth.py`
- `apps/api/src/sensoria/modules/accounts/router.py`
- `apps/api/src/sensoria/modules/accounts/purchase_linking.py`
- `apps/api/src/sensoria/modules/accounts/address_fingerprint.py`
- `apps/api/src/sensoria/modules/accounts/profile.py`
- `apps/api/src/sensoria/modules/accounts/mail_jobs.py`
- `apps/api/tests/test_accounts_profile.py`
- `apps/api/tests/test_accounts_auth.py`
- `apps/api/tests/test_purchase_linking.py`
- `apps/api/tests/test_migrations.py`
- `apps/web/app/(shop)/konto/dane/page.tsx`
- `apps/web/app/(shop)/konto/potwierdz-email-zmiane/page.tsx`
- `apps/web/components/account/account-data-view.tsx`
- `apps/web/components/account/email-change-confirmation.tsx`
- `apps/web/components/account/account-data-view.test.tsx`
- `apps/web/components/checkout/checkout-page.tsx`

## API i zabezpieczenia

- `GET /api/accounts/profile` — dane profilu, adresy, oczekujący e-mail i skonfigurowany kontakt. Odpowiedź ma `private, no-store`, `noindex` i `Referrer-Policy: no-referrer`.
- `PUT /api/accounts/profile/personal` — imię, nazwisko i opcjonalny telefon; tożsamość pochodzi z sesji, zapis wymaga CSRF.
- `POST /api/accounts/profile/email-change` — rozpoczyna potwierdzaną zmianę e-maila.
- `POST /api/accounts/profile/email-change/confirm` — jednorazowo potwierdza nowy adres; działa też z innej przeglądarki, nie przełącza po cichu sesji innego konta.
- `GET /api/accounts/profile/addresses`, `POST /api/accounts/profile/addresses`, `PUT /api/accounts/profile/addresses/{id}`, `POST /api/accounts/profile/addresses/{id}/default`, `DELETE /api/accounts/profile/addresses/{id}` — operacje własne klientki, z CSRF dla mutacji.
- `GET /api/accounts/checkout-defaults` — bezcache'owe podpowiedzi checkoutu z sesji klientki.

Zmiana e-maila zapisuje `pending_email`; stary adres pozostaje loginem do potwierdzenia. Link jest kryptograficzny, jednorazowy, ważny 24 godziny, w bazie przechowuje się skrót tokenu. Zmiana wymaga niedawnego ponownego uwierzytelnienia (10 minut). Przy potwierdzeniu sprawdzana jest ponownie unikalność nowego adresu, bezpiecznie uzgadniane są kwalifikujące się zakupy gościnne [56], a aktywne tokeny i linki logowania są unieważniane. Sesja właściwego konta jest rotowana; potwierdzenie z nowego urządzenia unieważnia stare sesje. Zamówienia, faktury i snapshoty nie są przepisywane.

Trwały payload e-maila jest szyfrowany kluczem wyprowadzonym z sekretu serwera, a jawny token nie trafia do audit logu. To zapewnia przygotowany kontrakt dla kolejki, nie dowód wysyłki: dostarczenie wymaga aktywnego workera [63].

## Adresy

`customer_addresses` przechowuje adres zwykły lub zweryfikowany punkt paczkomatowy. Adres zwykły wymaga ulicy, numeru budynku, kodu i miasta. Paczkomat wymaga kodu zweryfikowanego przez istniejący serwis punktów [30]; klient nie może podać własnego opisu jako potwierdzenia lokalizacji. Pola drugiego typu są czyszczone przy zapisie.

Migracja zachowuje istniejące snapshoty: rekordy z kodem punktu są klasyfikowane jako paczkomat, a pierwszy rekord każdego klienta według `created_at, id` staje się domyślny. Nie importuje odbioru osobistego jako prywatnego adresu. W dalszych importach [56] wykrywanie duplikatów korzysta z kanonicznej tożsamości adresu, a istniejący wybór domyślny pozostaje zachowany.

Pierwszy adres jest domyślny. Dodanie, usunięcie i wybór domyślnego blokują rekord klienta w transakcji; usunięcie domyślnego wybiera najstarszy pozostały adres według `created_at, id`. Baza ma częściowy unikalny indeks dopuszczający najwyżej jeden domyślny adres. Istnienie jednego domyślnego przy niepustej książce zapewnia transakcyjna logika aplikacji. Po usunięciu ostatniego adresu książka jest pusta.

| Typ adresu | Wymagane | Opcjonalne | Walidacja | Użycie |
|---|---|---|---|---|
| Zwykły adres | ulica, numer budynku, kod pocztowy, miasto | numer lokalu, etykieta, kraj | walidacja pól i zgodność typu; nie przyjmuje kodu punktu | podpowiedź dla dostawy kurierem |
| Paczkomat | kod punktu | etykieta | kod sprawdzany przez źródło punktów [30]; brak pól adresu domowego | podpowiedź dla dostawy do punktu |

Checkout wczytuje te dane po zalogowaniu. Początkowe podpowiedzi wypełniają tylko pola, których klientka nie zmieniła w otwartym formularzu. Wybór punktu nadal przechodzi przez istniejący endpoint i serwerową walidację. Zapisane adresy nie modyfikują snapshotów zamówień.

## Interfejs i zapis

Strona `/konto/dane` używa wspólnego nagłówka, stopki i panelu konta. Dane osobowe mają roboczy stan formularza: pasek pojawia się tylko przy różnicy, „Anuluj” odtwarza zapisany stan, a „Zapisz dane” chowa go po potwierdzonym sukcesie. Operacje adresowe zapisują się osobno i są tak opisane; nie sugerują, że dolny pasek może je cofnąć. Przy niezapisanych danych jest ostrzeżenie dla nawigacji wewnętrznej i standardowy `beforeunload`.

Ekran potwierdzenia zmiany e-maila odczytuje sekret z fragmentu URL dopiero po otwarciu strony i wysyła POST wyłącznie po świadomym kliknięciu. GET, prefetch i render nie zużywają tokenu. Widok działa na innym urządzeniu; po potwierdzeniu informuje o przejściu do logowania.

Zrzuty wykonano na fikcyjnych danych. Porównanie z makietą potwierdza hierarchię nagłówka, panel po lewej, kartę danych, adresy, stan domyślny, przyciski i stopkę. Zauważona różnica przy 360 px — zbyt wąskie pola oraz wiersze adresu, bo układ przechodził na dwie kolumny już przy 360 px — została poprawiona przez przesunięcie układu do breakpointu tabletowego. Zrzut po poprawce pokazuje pojedynczą kolumnę bez przepełnienia.

W makiecie znajdują się także przełączniki zgód, eksport danych i usunięcie konta. Są poza zakresem [59] i zależą od [60], dlatego nie zbudowano ich jako pozornie działających przycisków. Pozycja „Zgody i prywatność” jest jawnie oznaczona jako niedostępna. Nie można więc uznać całego PDF-a za wiernie odtworzony.

## Wyniki kontroli

- Backend: pełny zestaw wcześniej wykonany na PostgreSQL — `254 passed, 1 skipped`; Ruff, format i mypy: zaliczone.
- Frontend: `npm test -- --run` — 86 testów w 21 plikach zaliczonych; lint, format, TypeScript i build zaliczone po poprawce responsywności.
- Widok w przeglądarce na fikcyjnych danych: desktop 1440 px i 360 px; brak poziomego przepełnienia. Zrzuty: `tmp/audit/stage59/desktop.png`, `tmp/audit/stage59/mobile-360.png`; makieta: `tmp/audit/stage59/reference-1.png`.
- Nowy test PostgreSQL dodany: równoległe dodawanie pierwszych dwóch adresów sprawdza, że dokładnie jeden pozostaje domyślny. Test używa oddzielnych sesji i połączeń. Wynik testów profilu i powiązania zakupów: `8 passed`.
- Jedno uruchomienie testu całego łańcucha migracji na pustej bazie testowej przerwało się na wcześniejszej rewizji katalogu `b16f0a9c7d31`, która kończyła się `cannot ALTER TABLE "products" because it has pending trigger events`. Rewizja wydana nie była zmieniana. Rewizja [59] została zastosowana i jest aktualnym head w dedykowanej bazie testowej wykorzystanej do testów API.
- `npm run a11y -- --workers=1`: 41 testów przeszło. Axe zgłosił raporty `incomplete` dla kontrastu w elementach całej istniejącej ramy sklepu; to wymaga osobnej ręcznej oceny. Pełny zestaw nie ma testu strony `/konto/dane`, więc jej kontrast sprawdzono wizualnie, a układ na 360 px przez kontrolę zrzutu i overflow.
- Rzeczywiste dostarczenie e-maila nie zostało potwierdzone, bo worker [63] nie jest częścią dostępnej implementacji.
- Testy frontendowe po poprawkach: `npm test -- --run` — 86 passed w 21 plikach; lint, format, TypeScript i `npm run build` zaliczone.

## Kryteria

| Kryterium | Status | Dowód / ograniczenie |
|---|---|---|
| Profil: imię, nazwisko i telefon | SPEŁNIONE | API, walidacja, test `test_profile_personal_data_and_saved_address_default_invariant` |
| Historyczne dane zamówień i dokumentów pozostają snapshotami | SPEŁNIONE | aktualizowany jest wyłącznie rekord `Customer`; brak zapisu do zamówień/dokumentów |
| Zmiana e-maila z potwierdzeniem | SPEŁNIONE | pending email, jednorazowy token 24 h, unikalność ponownie sprawdzana; testy zmiany w sesji i z innej przeglądarki |
| Zachowanie dostępu zakupów po zmianie e-maila | SPEŁNIONE | własność jest po `customer_id`, kwalifikujące się zakupy gościnne są uzgadniane przy potwierdzeniu |
| CRUD obu typów adresu i ochrona własności | SPEŁNIONE | endpointy sesyjne, walidacja typu, test cudzej pozycji i kształtu danych |
| Jeden adres domyślny | SPEŁNIONE | częściowy unique index i transakcyjne blokowanie rekordu klienta; test współbieżny dodano, ale lokalne ponowienie blokuje wcześniejsza migracja |
| Import adresów z zakupów i checkout | SPEŁNIONE | typ punktu rozpoznawany po snapshotcie, prywatne defaults API, istniejąca walidacja punktu |
| Robocze zmiany, anulowanie i ostrzeganie przed wyjściem | SPEŁNIONE | pasek zależy od różnicy stanu; adresy zapisują się osobno z jasnym komunikatem |
| Audit bez wartości danych osobowych | SPEŁNIONE | payload audytu zawiera nazwy zmienionych pól/typ operacji i id operacji, bez wartości formularza |
| Wizualne odwzorowanie części objętej [59] | SPEŁNIONE | porównane zrzuty desktop i 360 px; poprawiony mobilny układ |
| Sekcje zgód, eksportu i usuwania [60] | NIESPEŁNIONE | wyłączone z [59], zależność nie jest zaimplementowana; widok ich nie symuluje |
| Rzeczywiste wysłanie potwierdzenia e-mail | NIESPRAWDZONE | trwały zaszyfrowany job jest przygotowany, worker [63] niepotwierdzony |
| Automatyczna kontrola dostępności bez uwag | NIESPRAWDZONE | `npm run a11y` pierwsze uruchomienie kolidowało z buildem, kolejne uruchomienie jest potrzebne; raport `incomplete` wymaga ręcznej oceny kontrastu |

## Dlaczego te reguły

- E-mail wymaga potwierdzenia, bo staje się identyfikatorem logowania i musi należeć do klientki.
- Jeden adres domyślny wymaga indeksu w bazie i blokady transakcyjnej, bo równoległe żądania mogłyby inaczej utworzyć sprzeczny stan.
- Usunięcie adresu nie zmienia historii, bo zamówienia i dokumenty korzystają z utrwalonych snapshotów.
- Audit przechowuje sam fakt i zakres operacji, a nie wartości profilu, aby nie tworzyć dodatkowej kopii danych osobowych.

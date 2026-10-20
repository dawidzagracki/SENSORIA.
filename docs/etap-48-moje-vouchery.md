# Etap 48 — „Moje vouchery”

Stan wykonania: widok i kontrakty API są przygotowane, ale etap nie jest w pełni gotowy do odbioru, ponieważ repozytorium nie zawiera działającego uwierzytelniania konta ani zakończonych integracji [46]–[47].

## Co dostarcza ta zmiana

- Strona `/konto/vouchery` korzysta ze wspólnej ramy sklepu i pokazuje wszystkie vouchery przypisane do uwierzytelnionego klienta, ostrzeżenie o najbliższym terminie, kody z kopiowaniem, QR, działania zależne od stanu, PDF, prośby o przedłużenie i widok szczegółów.
- API `GET /accounts/vouchers` ustala właściciela wyłącznie z `request.state.customer_id`, bez przyjmowania emaila lub customer ID z żądania. Odpowiedź ma `private, no-store`, `noindex` i `Referrer-Policy: no-referrer`.
- `GET /accounts/vouchers/{id}/qr`, `GET /accounts/vouchers/{id}/pdf` i `POST /accounts/vouchers/{id}/extension-requests` ponownie sprawdzają przypisanie vouchera do sesji klientki. Prośba ma opcjonalną treść, blokadę rekordu, deduplikację otwartego zgłoszenia oraz limit trzech zgłoszeń na dobę egzekwowany blokadą PostgreSQL advisory per konto. Zgłoszenie nie zmienia terminu.
- QR jest generowany z konfiguracji `SITE_URL` i rzeczywistego kodu; nie jest publicznym plikiem ani uprawnieniem do pobrania PDF. Publiczny endpoint weryfikacyjny pozostaje odrębny.
- Przy braku konfiguracji publicznego kontaktu widok uczciwie informuje o braku, zamiast używać przykładowego numeru telefonu.

## Źródła danych i brakujące etapy

Dane kart pochodzą ze snapshotu wystawionego vouchera (`issue_snapshot`/wariant), rekordu vouchera, pozycji i zamówienia, produktu oraz zadania PDF. Stan `ACTIVE`/`EXPIRING_SOON`/`EXPIRED`/`REDEEMED`/`CANCELLED` i dni do terminu liczy backend przez centralną funkcję `effective_voucher_status` oraz lokalne daty `Europe/Warsaw`.

W repozytorium nie ma jeszcze zatwierdzonego modułu kont ani middleware sesji. Wymagany integracyjny punkt to zaufane `request.state.customer_id`; dopóki logowanie go nie zasila, endpointy odmawiają dostępu `401`. Nie wolno zastąpić tego sprawdzaniem emaila, kodu vouchera ani UUID podanego przez klienta. Podpinanie zakupów bez konta po potwierdzeniu emaila również nie istnieje.

Brakuje backendowej logiki [46] (historii decyzji/przedłużeń, wyliczanego stanu `EXTENDED`, konfiguracji progu 60 dni, panelowej decyzji) i [47] (rejestru realizacji z miejscem). Bieżący widok korzysta z dostępnych pól z etapu wystawiania: nie udaje, że zna lokalizację wizyty ani historię operacji. Formularz prośby jest zapisany jako `voucher_extension_requests`, lecz nie ma odbiorcy/obsługi administracyjnej [68] ani dostarczenia wiadomości. Wartości telefonu, czasu odpowiedzi i rezerwacji nie są skonfigurowane w obecnym seedzie. Generator PDF [45] także nie jest uruchomiony: endpoint bez gotowego prywatnego pliku zwraca stan przygotowywania/niedostępności; nie twierdzi, że dokument został wygenerowany.

`customer_name` jest `null`, bo brak modelu profilu. „Klientka od” opiera się na pierwszym opłaconym zamówieniu przypisanym do konta, nie na dacie rejestracji. W aktualnym uproszczonym modelu powiązanie `Cart.customer_id` z kontem nie ma tabeli kont ani mechanizmu bezpiecznego przejęcia zakupów.

## Migracja i konfiguracja

Nowa migracja `f48000000001_voucher_extension_requests` (po `aa4500000001`) dodaje trwałe zgłoszenia klientek, unikalne dla jednego otwartego zgłoszenia na voucher. Dodano `SITE_URL` jako konfigurację publicznego originu; w produkcji musi używać HTTPS. Dodano `qrcode` oraz `tzdata` do API i aktualizację `uv.lock`.

Ustawienie `vouchers.public.v1` może zawierać `contact_email`, `contact_phone`, `booking_url` i `booking_instructions`. Nie zostało dodane do seedu, bo projekt nie ma zatwierdzonych danych kontaktowych. Jego edycja wymaga istniejącego mechanizmu administracyjnego, którego brak.

## Wizualne porównanie i rozbieżności

Plik `docs/11-moje-vouchery-desktop.pdf` nie znajduje się w repozytorium, więc dokładne porównanie renderu z makietą jest **niesprawdzone**. Strona używa istniejących tokenów i odtwarza opisany układ kart biletowych. Wymaganie ma pierwszeństwo nad rysunkiem: voucher wygasający zachowuje dodatkowo przycisk prośby o przedłużenie. Karta zrealizowana jest przygaszona; nie pokazuje fikcyjnego miejsca wizyty, bo rejestr [47] nie zapisuje go.

Nie wykonano rzeczywistego testu przeglądarkowego z zalogowanym kontem, pobraniem PDF ani przesłaniem zgłoszenia do operacyjnego procesu. Testy komponentu używają fixture, a testy API sprawdzają przede wszystkim odmowę bez zaufanej sesji. Nie jest to dowód działania pełnego przepływu.

## Kontrole

Kontrole punktowe po zmianach:
- backend Ruff lint — zaliczony;
- backend Ruff format check — zaliczony;
- mypy strict dla accounts/vouchers/config — zaliczony;
- testy backendowe endpointów/stanów/konfiguracji — 24 passed;
- frontend TypeScript — zaliczony;
- frontend ESLint — 0 błędów, 1 ostrzeżenie `@next/next/no-img-element` dla QR jako SVG;
- frontend Prettier — zaliczony;
- testy Vitest komponentu — 5 passed;
- build Next.js — zakończony poprawnie; trasa `/konto/vouchery` została wykryta jako dynamiczna;
- Playwright/axe — 39 passed; narzędzie wypisało `incomplete` dla kontrastu na istniejących elementach wspólnej strony/stopki oraz prosi o ocenę ręczną; nie jest to pełna ręczna ocena WCAG;
- test przeglądarkowy Playwright z przechwyconym, fikcyjnym API — desktop 1440 px i telefon 360 px: po 3 karty, bez poziomego przepełnienia; zrzuty `tmp/audit/stage48/desktop.png` i `tmp/audit/stage48/mobile-360.png`. To dowód układu na fixture, nie danych/autoryzacji produkcyjnej;
- pełna paczka backend pytest bez `test_migrations.py` — 102 passed, 1 skipped, 75 errors z powodu braku wymaganego `TEST_DATABASE_URL`; zatem testy integracyjne wymagające PostgreSQL są zablokowane, a nie zaliczone;
- migracji na bazie PostgreSQL, rzeczywistej sesji, działającego generatora PDF i bezpośredniego porównania z brakującą makietą nie uznaje się za sprawdzone.

Etap pozostaje częściowo zablokowany do integracji z prawdziwym uwierzytelnianiem, [46]–[47], procesem PDF, konfiguracją kontaktu i panelem [68].

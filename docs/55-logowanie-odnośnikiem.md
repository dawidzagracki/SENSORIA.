# Etap 55 — logowanie odnośnikiem

## Przepływ

1. Formularz logowania wysyła wyłącznie e-mail i bezpieczny lokalny `return_to` do `POST /api/auth/login-link` (bez hasła). Endpoint zwraca ten sam komunikat i strukturę dla istniejącego i nieistniejącego konta. Nie tworzy kont.
2. Dla istniejącego konta transakcja blokuje konto, unieważnia poprzednie linki i oczekujące zlecenia, a następnie zapisuje nowy `login_links` oraz zaszyfrowany intent `auth_email_jobs`. Jawny token jest losowy (`secrets.token_urlsafe(32)`), a w `login_links` zapisuje się wyłącznie SHA-256. Payload kolejki jest szyfrowany AES-GCM kluczem wyprowadzonym z `SECRET_KEY`, nie zawiera tokenu w postaci jawnej w bazie.
3. Worker kolejki powinien tuż przed wysłaniem wywołać `login_link_job_is_current`; helper odrzuca zlecenie, gdy link wygasł, zużyto go lub unieważniono. Link ma 15 minut od utworzenia. Opóźniony dostawca nie przedłuża tokenu — niewysłana/już przeterminowana wiadomość jest do anulowania, a klientka prosi o nową.
4. Wiadomość kieruje do `/konto/link-logowania/{token}`. Dedykowana dynamiczna strona potwierdzenia odczytuje token do pamięci i natychmiast zastępuje widoczny adres `/konto/link-logowania`. Strona jest no-store/no-referrer i nie ma zewnętrznych zasobów ani automatycznego POST. Access logi Uvicorn są wyłączone, a Caddy nie zapisuje access logów.
5. GET/HEAD `GET /api/auth/login-link/{token}` tylko sprawdza ważność (HEAD jest niezmieniający); nie loguje, nie zużywa tokenu i nie ujawnia konta.
6. Świadome kliknięcie „Zaloguj mnie” wykonuje chroniony CSRF-owo `POST /api/auth/login-link/{token}`. Blokada konta i wiersza linku, jednorazowe `used_at`, `last_login_at` i utworzenie/rotacja sesji [54] są w jednej transakcji. Druga równoległa próba przegrywa. Jeśli w przeglądarce jest inne aktywne konto, link nie jest zużywany.
7. API zwraca wyłącznie zweryfikowany lokalny cel. Sekret sesji trafia do cookie HttpOnly, Secure w produkcji, SameSite=Lax i Path=/api; nie trafia do localStorage.

## Ograniczenia i logi

Ustawienia `.env` (zakresy walidowane przez Pydantic): przy limicie e-mail 4 pierwsze 3 prośby w oknie są przyjmowane, a czwarta uruchamia cooldown; limit IP wynosi 20 na 3600 s; cooldown 900 s; limit błędnych wykorzystań wynosi 20 na IP/token. Wartości można zmienić bez wdrożenia. Limiter używa istniejącej tabeli PostgreSQL `auth_attempts` oraz blokad transakcyjnych/advisory, więc współdziała między procesami. Rate limit zwraca 429 i Retry-After, lecz ten sam komunikat niezależnie od istnienia konta. Adresy kluczy są HMAC-owane. Odpowiedzi dostają asynchroniczny minimalny czas i jitter, co ogranicza prosty pomiar czasu; nie stanowi matematycznej gwarancji stałego czasu.

Każda nowa prośba zaakceptowana dla konta unieważnia poprzedni niewykorzystany link; ograniczona prośba nie unieważnia działającego. Weryfikacja skrótu tokenu używa `hmac.compare_digest`. Posiadanie linku potwierdza kontrolę skrzynki, więc użycie linku ustawia `email_verified_at`; nie uruchamia podpinania zakupów gościa [56]. Ta metoda nadal zależy od bezpieczeństwa skrzynki i ochrony linku; nie jest bezwarunkowo bezpieczniejsza od innych metod.

W produkcyjnym i developerskim poleceniu Uvicorn wyłączono access log, ponieważ token jest wymagany w ścieżce API. Caddy nie ma reguły access-log. Nie logujemy tokenu, URL-a ani pełnego IP; audit zawiera tylko identyfikatory konta/linku oraz HMAC e-mail/IP i przyczynę odrzucenia. Wdrożenie innych proxy/telemetrii musi zachować maskowanie ścieżek `/api/auth/login-link/*`. Zlecenia anulowane, wysłane i wygasłe tracą zaszyfrowany payload; istniejący scheduler czyszczenia wykonuje ograniczone partie co interwał koszyka (domyślnie godzinę), a ponowienie dla konta usuwa payload poprzedniego zlecenia natychmiast. Wysłany, ale wciąż aktywny link nie jest czyszczony do czasu jego wygaśnięcia, bo skaner/późne kliknięcie nadal może go wykorzystać.

## Integracje i pozostały zakres

W repozytorium nie ma workerów [63] ani edytowalnego systemu szablonów [62]. Implementacja zapisuje trwałe, zaszyfrowane zlecenie i dostarcza helper budowania linku oraz minimalną treść tekstową; nie wysyła e-maili i nie deklaruje ich zakolejkowania przez zewnętrzny transport ani dostarczenia. Worker [63] musi ustawiać `sent_at` dopiero po wyniku dostawcy i sprawdzać aktualność zlecenia bezpośrednio przed przekazaniem. Wysyłka ma nieunikniony stan niepewny, jeśli dostawca przyjmie wiadomość, a proces padnie przed zapisem wyniku.

Makieta `09-logowanie-desktop.pdf` nie znajduje się w `docs/`; porównanie bezpośrednie nie zostało wykonane. Istniejący ekran zachowuje kolumny, kartę, separator i CTA; strona potwierdzenia jest nowym widokiem w tym samym stylu. Reset hasła i rejestracja pozostają bez zmian.

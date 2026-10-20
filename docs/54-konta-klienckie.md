# Etap 54 — konto klientki

## Stan i zależności

API konta, sesje, limity prób i formularze zostały dodane do `accounts`. W projekcie nie ma dostawcy wiadomości ani workera [63]. Reset hasła i potwierdzenie e-maila zapisują więc trwałe, szyfrowane zlecenia w `auth_email_jobs`; ich stan `pending` oznacza tylko gotowe zlecenie, nie wysłanie. Włączenie workera [63] i szablonów [62] jest wymagane do rzeczywistego dostarczenia wiadomości. Pomocnik `mail_jobs.py` odszyfrowuje zlecenie w zaufanym workerze i buduje odnośnik z `SITE_URL`. Token jest w fragmencie URL (`#token=...`), dzięki czemu przeglądarka nie wysyła go w żądaniu strony ani nagłówku Referer; formularz pobiera fragment do pamięci i usuwa go z paska adresu.

Logowanie odnośnikiem [55], podpinanie zakupów gościa [56], zarządzanie kontami admina [64] i interfejs konta pozostają osobnymi etapami. Rejestracja nie podpina wcześniejszych zakupów. Makieta `09-logowanie-desktop.pdf` nie jest dostępna w repozytorium, więc bezpośrednie porównanie wizualne jest niesprawdzone.

## Trasy

API (zewnętrznie przez `/api`):

| Metoda i ścieżka | Zastosowanie |
|---|---|
| `GET /accounts/csrf` | wydanie double-submit CSRF tokenu, bez cache |
| `POST /accounts/register` | utworzenie konta i sesji; zlecenie weryfikacji |
| `POST /accounts/login` | logowanie i rotacja sesji bieżącej przeglądarki |
| `GET /accounts/session` | odczyt własnej sesji |
| `POST /accounts/logout` | unieważnienie sesji i usunięcie cookie |
| `POST /accounts/password/change` | zmiana hasła po weryfikacji bieżącego |
| `POST /accounts/password-reset/request` | jednakowa odpowiedź dla znanego i nieznanego adresu |
| `POST /accounts/password-reset/confirm` | jednorazowe ustawienie hasła tokenem |
| `POST /accounts/email/verify` | jednorazowe potwierdzenie e-maila |
| `POST /accounts/email/verification-resend` | ponowienie weryfikacji z limitem |

Widoki: `/konto`, `/konto/odzyskaj-haslo`, `/konto/ustaw-haslo`, `/konto/potwierdz-email`.

## Zabezpieczenia

- E-mail jest normalizowany przez trim i zapis lowercase; kropki i `+tag` pozostają bez zmian. Ograniczenie UNIQUE w PostgreSQL rozstrzyga wyścig rejestracji. Migracja dodaje nowe tabele, nie scala istniejących klientów.
- Hasła hashuje `argon2-cffi` Argon2id: 19 MiB, 2 iteracje, 1 lane, 32 bajty hash i 16 bajtów soli. Sprawdzane jest `check_needs_rehash`. Limit wejścia: 1024 znaki i maksymalnie 4096 bajtów UTF-8, bez trimowania. Wymagane jest 10 znaków; niewielka lokalna lista blokuje popularne hasła, bez zewnętrznego lookupu.
- Nieznane konto korzysta z kontrolnego hasha Argon2id i identycznej weryfikacji, a błędne logowanie zwraca ten sam komunikat. Próby są trwale liczone w PostgreSQL po keyed-hash znormalizowanego e-maila i adresu IP. Okno wynosi 15 minut, limit e-maila 10, limit IP 50, blokada 15 minut. Kolejne żądania w czasie blokady nie przedłużają blokady. IP z `X-Forwarded-For` jest przyjmowane tylko za proxy w `TRUSTED_PROXY_CIDRS`.
- Sesja to losowy sekret 256-bitowy; baza przechowuje HMAC, nie sekret. Cookie jest HttpOnly, SameSite=Lax, host-only, Path `/api`; Secure jest włączone w production i wyłączone wyłącznie w development. Zwykła sesja: 12 godzin bezczynności / 7 dni maksymalnie. „Zapamiętaj mnie”: 14 dni bezczynności / 30 dni maksymalnie. Aktywność przesuwa limit bezczynności, nigdy limit absolutny. Wylogowanie unieważnia wpis po stronie serwera. Logowanie obraca sesję tej samej przeglądarki bez wylogowania innych urządzeń. Zmiana hasła unieważnia pozostałe sesje i rotuje bieżącą; reset unieważnia wszystkie.
- Każdy POST wymaga zgodnego Origin oraz double-submit `X-CSRF-Token`; dla uwierzytelnionej sesji token jest dodatkowo związany hashem zapisanym w sesji. `SameSite` jest tylko dodatkową ochroną.
- Tokeny resetu i weryfikacji mają odrębne cele; losowy sekret jest przechowywany jako HMAC, jest jednorazowy, reset wygasa po 1 godzinie, weryfikacja po 24 godzinach. `SELECT FOR UPDATE` obejmuje sprawdzenie i zużycie. GET strony nie konsumuje tokenu.
- Dane wysyłki wiadomości są szyfrowane AES-GCM w outboxie, klucz wyprowadzany z `SECRET_KEY` z separacją domeny. To pozwala workerowi [63] uzyskać sekretny token, bez trzymania go jawnie w bazie lub logach.

## Zastrzeżenie operacyjne

Do czasu wdrożenia [63] nie można zrealizować resetu ani potwierdzenia e-maila end-to-end: powstaje zlecenie, ale klientka nie otrzymuje wiadomości. Weryfikacja e-maila nie blokuje korzystania z konta; ma natomiast być warunkiem integracji zakupów gościa w [56]. Potwierdzenie adresu nie oznacza zgody marketingowej.

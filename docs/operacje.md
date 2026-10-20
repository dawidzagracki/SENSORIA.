# Operacje: kopie zapasowe, monitoring, dzienniki — etapy [86], [87], [88]

## Kopie zapasowe [86]

`scripts/backup.sh` robi **jedną zaszyfrowaną paczkę**: zrzut PostgreSQL (`pg_dump -Fc`) + archiwum prywatnych
plików (wolumen `uploads_data`: pliki cyfrowe, PDF-y voucherów, dokumenty). Paczka jest szyfrowana AES-256
(`openssl enc -pbkdf2`, 200 000 iteracji), ma sumę SHA-256 i trafia na Dysk Google przez `rclone`.

| Parametr | Domyślnie |
|---|---|
| lokalnie | `./backups`, 7 dni |
| Dysk Google | `RCLONE_REMOTE`, 30 dni (starsze są usuwane) |
| harmonogram | cron 03:30 (patrz `docs/wdrozenie-vps.md`) |
| monitorowanie | `BACKUP_PING_URL` — ping po udanej kopii; monitor typu „dead man's switch” alarmuje, gdy ping nie przyjdzie |

### Odtwarzanie — procedura przetestowana

1. **Test bez ryzyka** (zalecane co kwartał): `scripts/restore.sh <plik.tar.enc>` — sprawdza sumę,
   odszyfrowuje, odtwarza do bazy `…_restore_check`, wypisuje wersję migracji i liczby zamówień/produktów,
   po czym usuwa bazę kontrolną. Plik z Dysku Google: `scripts/restore.sh gdrive:sensoria-backups/<plik>.tar.enc`.
2. **Odtworzenie produkcji** po awarii: `CONFIRM_RESTORE=yes scripts/restore.sh <plik> --apply`.
   Skrypt zatrzymuje API i web, podmienia bazę i pliki, uruchamia usługi. Następnie sprawdź
   `/api/health/deep` i zamówienia z ostatnich godzin — kopia nie zawiera zamówień nowszych niż ona sama
   (Stripe pamięta płatności; zrzut zdarzeń można odtworzyć w panelu Stripe → Webhooks → „Resend”).
3. **Utrata hasła do kopii = utrata kopii.** Trzymaj je w menedżerze haseł, osobno od serwera.

### Co robić po odtworzeniu na nowym serwerze

Zainstaluj stos wg `docs/wdrozenie-vps.md` (pkt 2–4 **bez** seedu), skopiuj `.env` (z tym samym `SECRET_KEY`!), uruchom
`restore.sh --apply`.

## Monitoring [87]

| Co | Jak |
|---|---|
| Strona działa | `scripts/uptime-check.sh` (cron) albo zewnętrzny monitor na `/` |
| Stan aplikacji | `GET /api/health/deep`: baza, zaległa kolejka maili (>30 min), wiadomości w statusie `failed`, zawieszone PDF-y voucherów, czas ostatniego zdarzenia płatności. Zwraca **503**, gdy coś wymaga uwagi |
| Nieudane płatności | e-mail do właścicielki (`ops.alerts.v1`): płatność nieudana/wygasła, niezgodna kwota, konflikt magazynowy, niewysłana wiadomość; plus e-mail do klientki z linkiem „Zapłać ponownie” |
| Zgłoszenia klientek | alert o każdej reklamacji / odstąpieniu |
| Panel | pulpit pokazuje liczniki: zamówienia do wysyłki, prośby o przedłużenie, niski stan, konflikty magazynowe, niewysłane maile |

Alerty są idempotentne (jeden na zdarzenie) i **nie wysyłają się**, gdy nie skonfigurowano `ops.alerts.v1` —
wtedy zostaje ślad w logach (`sensoria.ops.alerts`).

## Dzienniki zdarzeń [88]

* **`audit_log`** — nieusuwalny dziennik: logowania administratorek, zmiany zamówień, realizacja/anulowanie/
  przedłużenie voucherów, zmiany cen (pełna historia w `price_history`), publikacje produktów i stron, moderacja,
  odczyt danych klientki, korekty magazynu, potwierdzenia płatności. Podgląd: panel → **Dziennik** (właścicielka),
  filtr po początku nazwy akcji (`order.`, `voucher.`, `payment.`…).
* **Rejestr voucherów** (`voucher_events`) — realizacje, cofnięcia, anulowania, przedłużenia z datą i osobą;
  panel → Vouchery → „Rejestr realizacji”.
* **Historia cen** — `price_history` (niemodyfikowalna, chroniona triggerem).
* **Rejestr zgód** — zgody RODO/marketingowe (`customer_consents`) i zgody na cookies (`cookie_consents`).
* **Wiadomości** — każda wysłana wiadomość jest w `mail_outbox` ze statusem, liczbą prób i błędem; widoczne
  w szczegółach zamówienia.
* **Logi aplikacji** — `docker compose logs api` (tekstowe, bez sekretów, haseł i parametrów SQL).

Dane osobowe w `audit_log` są ograniczone do identyfikatorów; adresy e-mail nie są w nim zapisywane.

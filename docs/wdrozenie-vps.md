# Wdrożenie produkcyjne na VPS — etap [89]

Ten dokument prowadzi od pustego serwera do działającego sklepu. Kroki wymagające Twoich danych
(domena, klucze Stripe, poczta) są oznaczone **[TWOJE DANE]**. Aplikacja nie zawiera żadnych
domyślnych haseł ani kluczy.

## 1. Co jest potrzebne

| Element | Wymaganie |
|---|---|
| Serwer (VPS) | Linux (Debian 12 / Ubuntu 22.04+), min. 2 vCPU, 4 GB RAM, 40 GB dysku |
| Domena | rekord **A** (i opcjonalnie AAAA) wskazujący na adres VPS **[TWOJE DANE]** |
| Porty | 80 i 443 otwarte (Caddy sam uzyskuje certyfikat Let's Encrypt); SSH tylko z Twojego IP |
| Stripe | konto + klucze (najpierw testowe) **[TWOJE DANE]** |
| Poczta | konto u dostawcy SMTP (Postmark / SES / Resend) i uwierzytelniona domena **[TWOJE DANE]** |
| Backup | konto Google Drive + `rclone` **[TWOJE DANE]** |

## 2. Przygotowanie serwera

```bash
# jako root, jednorazowo
apt update && apt install -y ca-certificates curl git ufw openssl
curl -fsSL https://get.docker.com | sh
ufw default deny incoming && ufw allow OpenSSH && ufw allow 80,443/tcp && ufw allow 443/udp && ufw enable
adduser --disabled-password sensoria && usermod -aG docker sensoria
```

Zaloguj się jako `sensoria` i pobierz kod:

```bash
git clone git@github.com:dawidzagracki/SENSORIA.git /opt/sensoria && cd /opt/sensoria
```

## 3. Konfiguracja `.env`

```bash
cp .env.example .env && chmod 600 .env
```

Uzupełnij **wyłącznie na serwerze** (plik `.env` nie trafia do gita):

| Zmienna | Wartość |
|---|---|
| `DOMAIN` | np. `sensoria.shop` |
| `SITE_URL` | `https://sensoria.shop` (bez ukośnika na końcu) |
| `NEXT_PUBLIC_API_URL` | `https://sensoria.shop/api` |
| `POSTGRES_PASSWORD` | losowe hasło: `openssl rand -base64 32` |
| `SECRET_KEY` | losowy klucz ≥ 32 znaki: `openssl rand -hex 32` |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | z panelu Stripe |
| `SMTP_*`, `MAIL_FROM` | dane dostawcy poczty |
| `BACKUP_PASSPHRASE_FILE` | np. `/opt/sensoria-secrets/backup.pass` (patrz pkt 8) |

`SECRET_KEY` podpisuje tokeny dostępu do zamówień — **nie zmieniaj go po uruchomieniu**, bo
linki z wcześniejszych e-maili przestaną działać.

## 4. Pierwsze uruchomienie

```bash
docker compose -f docker-compose.yml up --build -d
docker compose -f docker-compose.yml exec api alembic upgrade head
docker compose -f docker-compose.yml exec api python -m sensoria.seed
docker compose -f docker-compose.yml exec api python -m sensoria.modules.catalog.seed   # tylko dane demonstracyjne — pomiń na produkcji
docker compose -f docker-compose.yml ps        # wszystkie usługi: healthy / running
curl -fsS https://sensoria.shop/api/health/deep
```

Migracje **nie** uruchamiają się automatycznie. Nigdy nie wykonuj `alembic downgrade` na produkcji.

## 5. Konto właścicielki panelu

```bash
docker compose -f docker-compose.yml exec api \
  python -m sensoria.modules.admin.cli --email ty@twojadomena.pl --name "Imię" --role owner
# program zapyta o hasło (min. 12 znaków); dla obsługi użyj --role staff
```

Panel jest pod `https://sensoria.shop/admin/logowanie`. Po 5 błędnych logowaniach konto blokuje się na
15 minut. Hasło zmienisz ponownym uruchomieniem polecenia z tym samym adresem e-mail.

## 6. Dane sprzedawcy i ustawienia, bez których nic się nie wystawi

Zaloguj się do panelu → **Ustawienia** (tylko właścicielka). Aplikacja nie zgaduje wartości biznesowych:

| Sekcja | Do czego | Skutek braku |
|---|---|---|
| Dane sprzedawcy | nagłówek paragonów i faktur | płatność działa, ale dokument czeka do uzupełnienia danych |
| Dostawa: koszty i progi | koszt paczkomatu/kuriera, próg darmowej dostawy, VAT dostawy | koszyk z książką nie policzy dostawy (fail-closed) |
| E-mail do alertów | nieudane płatności, reklamacje, konflikty magazynowe | alerty tylko w logach |
| Kontakt i rezerwacja | dane w koncie klientki i centrum pomocy | brak danych kontaktowych na stronach |
| Opinie | po ilu dniach prosić o opinię (domyślnie 7) | — |

## 7. Stripe

1. W panelu Stripe dodaj endpoint webhooka: `https://sensoria.shop/api/payments/webhooks/stripe`.
2. Zaznacz zdarzenia: `checkout.session.completed`, `checkout.session.async_payment_succeeded`,
   `checkout.session.async_payment_failed`, `checkout.session.expired`.
3. Skopiuj „Signing secret” do `STRIPE_WEBHOOK_SECRET`, zrestartuj API:
   `docker compose -f docker-compose.yml up -d api`.
4. Włącz metody płatności BLIK i karty (w tym Google Pay / Apple Pay) w ustawieniach Stripe.
5. Przetestuj kluczami testowymi (karta `4242 4242 4242 4242`), potem podmień na klucze produkcyjne.

Aplikacja weryfikuje podpis i znacznik czasu każdego webhooka, a to samo zdarzenie przetwarza tylko raz.

## 8. Kopie zapasowe na Dysk Google

```bash
sudo mkdir -p /opt/sensoria-secrets && sudo chown sensoria: /opt/sensoria-secrets && chmod 700 /opt/sensoria-secrets
openssl rand -base64 48 > /opt/sensoria-secrets/backup.pass && chmod 600 /opt/sensoria-secrets/backup.pass
```

**Zapisz hasło kopii poza serwerem** (menedżer haseł) — bez niego kopii nie odtworzysz.
Skonfiguruj `rclone config` (typ `drive`, nazwa `gdrive`), ustaw w `.env`
`RCLONE_REMOTE=gdrive:sensoria-backups`, a potem:

```bash
scripts/backup.sh                       # test ręczny
scripts/restore.sh backups/sensoria-<data>.tar.enc   # test odtworzenia do bazy kontrolnej
( crontab -l; echo "30 3 * * * /opt/sensoria/scripts/backup.sh >> /var/log/sensoria-backup.log 2>&1" ) | crontab -
```

Przetestuj odtworzenie **przed** uruchomieniem sprzedaży i potem co kwartał. Pełna procedura: `docs/operacje.md`.

## 9. Monitoring

* W zewnętrznym monitorze (np. UptimeRobot) dodaj `https://sensoria.shop/api/health/deep` —
  odpowiada 503, gdy kolejka maili stoi, są niewysłane wiadomości albo zawieszone PDF-y vouchera.
* Opcjonalnie: `*/5 * * * * /opt/sensoria/scripts/uptime-check.sh` z `ALERT_WEBHOOK`.
* Alerty o nieudanych płatnościach, niezgodnych kwotach, konfliktach magazynowych i niewysłanych mailach
  przychodzą e-mailem na adres z `ops.alerts.v1`.

## 10. Aktualizacje i wycofanie

```bash
cd /opt/sensoria && scripts/deploy.sh      # kopia → git merge --ff-only → build → migracje → restart → kontrola
```

Wycofanie kodu: `git checkout <poprzedni-tag> && docker compose -f docker-compose.yml up -d --build`.
Zmiany schematu bazy są tylko „w przód” — jeśli migracja zawiodła, odtwórz bazę z kopii
(`scripts/restore.sh <plik> --apply` z `CONFIRM_RESTORE=yes`).

## 11. Lista kontrolna przed otwarciem sklepu

- [ ] `https://domena` działa z certyfikatem, `http://` przekierowuje na HTTPS
- [ ] `/api/health/deep` zwraca `ok`
- [ ] konto właścicielki założone, logowanie do panelu działa
- [ ] Stripe: płatność testowa BLIK/karta przechodzi, zamówienie zmienia status na „Opłacone”
- [ ] e-mail: wiadomość potwierdzająca doszła, SPF/DKIM/DMARC „pass” (nagłówki w Gmailu → „Pokaż oryginał”)
- [ ] `company.seller.v1` uzupełnione, paragon/faktura generuje się
- [ ] regulamin, polityka prywatności i cookies opublikowane w panelu (po weryfikacji prawnej)
- [ ] pierwsza kopia zapasowa wykonana **i odtworzona testowo**
- [ ] produkty dodane, pliki cyfrowe wgrane, rozdziały e-booków uzupełnione
- [ ] dane demonstracyjne (seed katalogu) usunięte lub niewgrane

# Etap [49] — przypomnienia o terminie vouchera

## Stan integracji

Repozytorium zawiera trwały model kwalifikacji i cykli przypomnień, walidację ustawień,
ograniczony przebieg, codzienny scheduler i punkty integracji dla zgód oraz kolejki. Nie
zawiera jednak etapu [60] (źródło zgody „Przypomnienia o voucherach”) ani [62]/[63]
(szablonów, outboxa i workera poczty). Zgody `marketing` i `digital` z checkoutu nie są
używane jako zamiennik. Do czasu podłączenia tych modułów system działa fail-closed:
nie zleca wiadomości, statusuje powód blokady i nie zapisuje `sent_at`.

`VoucherReminderConsentReader` ma odczytać aktualną zgodę konkretnej odbiorczyni; wartość
`None` oznacza, że zgody nie da się zweryfikować i blokuje wysyłkę. `VoucherReminderQueue`
ma zapisać wiadomość do trwałego outboxa w tej samej transakcji co status `queued`. Worker
przed wysyłką wywołuje `revalidate_reminder_before_send`, a po przyjęciu przez dostawcę
`mark_reminder_provider_accepted`. Samo kolejkowanie nie ustawia `sent_at`; dostarczenie
do skrzynki jest raportowane osobno i tylko gdy dostawca je potwierdza.

## Ustawienia i harmonogram

Klucz `vouchers.reminders.v1` w `app_settings` ma niepoufne wartości domyślne:

```json
{"threshold_days":[30,7],"local_time":"09:00","timezone":"Europe/Warsaw","max_messages_per_run":200}
```

Seed dopisuje ustawienie wyłącznie, gdy go brakuje; operator może edytować JSON w
`app_settings`. W obecnym repozytorium nie ma interfejsu administracyjnego ustawień ani
autoryzowanego API edycji — jest to zależność od przyszłego panelu. Progi muszą być dodatnie,
unikalne i malejące; czas ma format `HH:MM`, strefa jest `Europe/Warsaw`, limit wynosi
1–5000. Weekend nie jest pomijany. Scheduler wyznacza następną lokalną godzinę przy każdym
przebiegu, a następnie konwertuje ją do UTC; podczas nieistniejącego czasu DST przesuwa
uruchomienie do pierwszej prawidłowej minuty, a przy niejednoznaczności wybiera pierwsze
wystąpienie. W standardowej konfiguracji 09:00 nie wpada w lukę DST.

W Compose scheduler działa jako zadanie lifespan API. Jest bezpieczny przy wielu workerach
dzięki ograniczonej partii, blokadom PostgreSQL, unikalności cyklu oraz ponownej kontroli
pod blokadą vouchera. Pojedynczy przebieg można też uruchomić ręcznie z `apps/api`:

```powershell
uv run --frozen --all-groups python -m sensoria.modules.vouchers.reminders_cli
```

Przebieg ręczny stosuje bieżące ustawienia DB i tę samą deduplikację. Nie wysyła maili.

## Progi, nadrabianie i idempotencja

Próg jest liczony z różnicy lokalnych dat `valid_until` i `now` w Europe/Warsaw, tak samo jak
centralna reguła [46]. Voucher musi nadal być ważny według dokładnego `valid_until`, mieć
trwały status `active` i brak `redeemed_at`. `EXPIRING_SOON` i ważne przedłużone vouchery
pozostają kwalifikowane.

Po pominiętym dniu wybierany jest najbardziej aktualny próg: przy 30 dniach lub mniej etap
30, a przy 7 dniach lub mniej etap 7. Jeśli etap 7 jest aktualny, nieaktualny etap 30
zostaje oznaczony `skipped`; wcześniejsze przypomnienie nie jest wysyłane razem z nowszym.
Liczba dni w treści jest liczona ponownie w chwili kolejki.

Unikalny klucz to `(voucher_id, valid_until_snapshot, threshold_days)`. Snapshot terminu
identyfikuje cykl ważności, więc przedłużenie dopuszcza nowe progi, a stare zlecenie jest
anulowane przez kontrolę workera. Unikalność jest egzekwowana w PostgreSQL. Zlecenie kolejki
i rekord przypomnienia powinny być zapisywane atomowo przez adapter [63]. Blokada voucheru
serializuje równoległe przebiegi. Limit ogranicza liczbę sprawdzanych rekordów i przez to
również maksymalną liczbę nowych wpisów kolejki w jednym przebiegu; kolejność jest
deterministyczna po `valid_until`, potem UUID.

## Odbiorca, treść i audyt

Odbiorca pochodzi z `orders.email` powiązanego z pozycją i voucherem; jest normalizowany do
małych liter. Integracja zgód musi potwierdzić zgodę właśnie tego adresu. `recipient_email`
vouchera sam w sobie nie stanowi dowodu zgody obdarowanej osoby. Obecnie zakupy gościnne nie
mają osobnego, wiarygodnego źródła tej zgody, więc są blokowane.

Zmienne szablonu powstają z snapshotu vouchera, aktualnego terminu oraz `SITE_URL`, nigdy z
nagłówka Host. Link prowadzi do `/konto/vouchery`; bezpieczna ścieżka dostępu gościa nie jest
jeszcze dostępna. Layout HTML/tekstowy musi dostarczyć [62]. Ton treści informuje o usłudze,
kodzie, aktualnym terminie, lokalnej liczbie dni i możliwości kontaktu w sprawie
przedłużenia; nie obiecuje automatycznej decyzji.

`voucher_reminder_runs` i powiązane wpisy `audit_log` przechowują konfigurację przebiegu,
liczniki, limit i zaległości bez pełnych kodów ani adresów. `queued`, `sent`, `delivered`,
`skipped`, `cancelled`, `blocked` i `failed` są odrębnymi rezultatami. Awaria po przyjęciu
wiadomości przez zewnętrznego dostawcę, ale przed potwierdzeniem lokalnym, wymaga uzgodnienia
po stabilnym ID dostawcy; bez takiej możliwości istnieje ryzyko niepewnego wyniku, którego
nie można obiecać jako bezwzględnie bezduplikatowego.

## Odbiór

Do weryfikacji przed uznaniem E2E za gotowe pozostaje podłączenie odrębnej zgody [60],
transakcyjnej kolejki/outboxa i workera [62]/[63], edytora ustawień, rzeczywistej lokalizacji
gościa oraz testu z lokalnym odbiornikiem poczty. Testy adapterów nie potwierdzają
dostarczenia wiadomości.

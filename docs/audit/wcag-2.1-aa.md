# Audyt dostępności WCAG 2.1 AA — etap [84]

Zakres: sklep, konto, czytnik, odtwarzacz, panel administracyjny. Data: 2026-10-20.

## Co sprawdzono automatycznie

Przeglądarkowe testy Playwright + axe-core (reguły `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`) uruchomione na **pełnym stosie**
(Caddy → build produkcyjny Next.js z CSP → API → PostgreSQL; dane z prawdziwych zamówień):

* `apps/web/a11y-stack-tests/stack.spec.ts` — 21 scenariuszy: strona główna, katalog, produkt, centrum pomocy, regulamin,
  polityka prywatności i cookies, „o autorce”, dostawa i płatności, odstąpienie, zwroty i reklamacje, koszyk, 404,
  potwierdzenie zamówienia, czytnik, weryfikacja vouchera, formularz opinii, logowanie do panelu, pulpit i 11 widoków panelu,
  szczegóły zamówienia, baner cookies.
* Dla każdego ekranu: dokładnie jeden `main#main-content` i jeden `h1`, brak poziomego przewijania przy **360, 768 i 1280 px**,
  **brak naruszeń `critical` i `serious`** (bramka `a11y-gate.ts`).
* `apps/web/a11y-tests/*` — istniejące 41 testów na fixture’owym API (katalog, produkty, koszyk, checkout, menu, redukcja ruchu).

Uruchomienie (wymaga działającego stosu i danych testowych):

```bash
docker run --rm --network <sieć_compose> -v "$PWD/apps/web":/app -v pw_node_modules:/app/node_modules -w /app \
  -e STACK_URL=http://caddy:8080 -e STACK_STATE='{"order_id":…,"token":…,"entitlement_id":…,"voucher_code":…,"admin_password":…}' \
  mcr.microsoft.com/playwright:v1.64.1-noble npx playwright test -c playwright.stack.config.ts
```

## Rozwiązania zastosowane w nowych ekranach

| Wymaganie | Realizacja |
|---|---|
| 1.3.1 / 4.1.2 struktura i nazwy | nagłówki w kolejności, `aria-label` na nawigacjach i regionach, `role="tablist"`/`aria-selected` w panelu, tabele z `caption` (sr-only) i `scope="col"` |
| 1.4.1 kolor nie jedynym nośnikiem | statusy mają tekst („Opłacone”, „Aktywny”), gwiazdki mają tekst „Ocena 4 z 5”, ukończone rozdziały mają „(przeczytany)” |
| 2.1.1 klawiatura | czytnik, odtwarzacz, wybór oceny (radio), accordion FAQ, menu i dialog cookies w pełni obsługiwane klawiaturą; widoczny fokus na wszystkich kontrolkach |
| 2.4.3 kolejność fokusu | po zmianie rozdziału fokus trafia na nagłówek rozdziału; dialog cookies używa natywnego `<dialog>` |
| 2.5.5 / 2.5.8 obszar dotyku | kontrolki w nowych ekranach mają minimum 44 px (tokeny `min-h-touch`, `min-w-touch`); istniejący test sprawdza to dla checkboxów i radio |
| 3.3.1 / 3.3.3 błędy formularzy | komunikaty powiązane z polami (`aria-describedby`), `role="alert"`, treść błędu po polsku z instrukcją naprawy |
| 4.1.3 komunikaty stanu | `role="status"` / `aria-live` dla ładowania, potwierdzeń płatności i wyników wyszukiwania w pomocy |
| 1.4.4 zmiana rozmiaru tekstu | czytnik ma własną skalę 80–200%; strona nie blokuje powiększania (`viewport`) |
| 2.3.3 / ruch | brak animacji dekoracyjnych w nowych ekranach; spinner przycisku ma `motion-reduce:animate-none` |

## Czego automat nie rozstrzyga — lista kontrolna do przejścia ręcznie

Wykonaj przed otwarciem sprzedaży (patrz też `docs/lista-kontrolna-ekranu.md`):

- [ ] **Kontrast tekstu** na tle gradientów (odtwarzacz: tekst jasny na ciemnym gradiencie; panel: stany ostrzeżeń) — axe zgłasza „incomplete”
- [ ] **Czytnik ekranu** (VoiceOver/NVDA): przejście zakupu → potwierdzenie → czytnik → odtwarzacz; czy komunikaty stanu są zrozumiałe
- [ ] **Powiększenie do 200%** i zoom tekstu — brak utraty treści na koszyku, checkoucie, czytniku, panelu zamówień
- [ ] **Sens etykiet i alternatyw** dla obrazów produktów dodawanych w panelu (pole „alt” ustawiane na nazwę produktu — warto uzupełnić opisem)
- [ ] **Tylko klawiatura**: dodanie produktu do koszyka, checkout, logowanie do panelu, realizacja vouchera
- [ ] **Treści prawne i FAQ** — czy język jest zrozumiały (3.1.5), czy skróty są objaśnione

## Znane odstępstwa

* Gradientowe tło odtwarzacza (`from-ink to-accent-action/70`): kontrast tekstu jest wystarczający na górze i w środku, ale
  przy najjaśniejszym fragmencie dołu wymaga potwierdzenia ręcznego. Do czasu weryfikacji traktuj jako ryzyko.
* Panel administracyjny nie był testowany z czytnikiem ekranu — zakres: automat + klawiatura.

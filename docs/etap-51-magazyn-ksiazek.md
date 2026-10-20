# Etap [51] — magazyn książek

## Model danych

- `product_book.stock_quantity` to fizyczny stan w egzemplarzach i musi być równy sumie `stock_movements.change` dla produktu.
- `stock_reservations.quantity` to czasowo zarezerwowane sztuki. Rezerwacja nie tworzy ruchu i nie zmniejsza fizycznego stanu.
- Dostępność = fizyczny stan − suma niewygasłych rezerwacji zamówień `pending_payment`.
- Waga jest zapisana w gramach (`weight_grams`), wymiary w milimetrach: długość (`length_mm`), szerokość (`width_mm`), wysokość/grubość (`height_mm`). Są to wymiary pojedynczej książki, nie zapakowanej paczki.
- Wymiary i masa istniejących rekordów pozostają `NULL`; migracja nie zgaduje danych. Checkout książki wymaga kompletu tych czterech wartości.

## Rejestr i cykl zamówienia

Migracja `f51000000001_stock_ledger` zapisuje dotychczasowy dodatni stan jako jeden ruch otwarcia `correction` z kluczem `opening:{product_id}`. Historia sprzed migracji nie istniała, więc nie można jej odtworzyć. Ruchy są append-only. PostgreSQL trigger atomowo aktualizuje agregat oraz odrzuca bezpośrednią zmianę/utworzenie `stock_quantity` poza ruchem.

Checkout blokuje szczegóły książki, sprawdza fizyczny stan pomniejszony o aktywne rezerwacje i zapisuje rezerwację z zamówieniem. Rezerwacja wygasa po 24 godzinach (zgodnie z dostępnym domyślnym okresem z [34]); w repozytorium nie ma obecnie edytowalnego ustawienia [34], więc operacyjna konfiguracja terminu pozostaje zależnością. Zadanie `expire_stock_reservations` zwalnia hold i oznacza nieopłacone zamówienie jako `expired`; nie dopisuje ruchu fizycznego.

Po potwierdzeniu płatności zaufany caller ma wywołać `record_paid_order_inventory` w tej samej transakcji co zmianę płatności. Każda pozycja ma klucz `purchase:{order_item_id}`. Aktywna rezerwacja jest konsumowana wraz z jednym ujemnym ruchem `purchase`. Przy późnym potwierdzeniu płatności po wygaśnięciu usługa próbuje zabezpieczyć stan dostępny; gdy nie ma sztuk, zapisuje `stock_fulfillment_conflicts`, nie tworzy ujemnego stanu i nie ukrywa konfliktu.

## Korekty, zwroty i alerty

`append_stock_movement` wymaga unikalnego klucza operacji. Korekta ręczna wymaga administratora i uzasadnienia w serwisie, ale nie ma endpointu, ponieważ uwierzytelnianie administracyjne i panel [67] nie istnieją. Dodatni ruch `return` można dopisać dopiero po potwierdzonym fizycznym przyjęciu zaufanego procesu zwrotów; repozytorium nie ma modelu/obsługi zwrotów, więc nie ma publicznej operacji przyjęcia zwrotu.

Przy spadku `stock_quantity` z wartości co najmniej progu do wartości poniżej `low_stock_threshold` tworzony jest `low_stock_alerts` w tej samej transakcji. Zdarzenie jest trwałym zamiarem powiadomienia, nie potwierdzeniem doręczenia. Worker powiadomień administracyjnych nie istnieje.

## Zadania i kontrole

Zadanie istniejącego `cleanup_scheduler` uruchamia `expire_stock_reservations` cyklicznie i używa blokad zamówień `SKIP LOCKED`; operacje produktu blokują książki w deterministycznym porządku UUID. Ruch, agregat i audit log są w transakcji caller-a.

Testy katalogu, koszyka i magazynu uruchamia się przez `uv run --frozen --all-groups pytest` z `apps/api`, po ustawieniu `TEST_DATABASE_URL` wskazującego dedykowany PostgreSQL 16 o nazwie kończącej się `_test`. Nie uruchamiaj migracji ani testów na bazie aplikacji.

## Integracje poza zakresem / brakujące

- [33] w tym checkoutcie jest tylko szkieletem; transakcyjne wywołanie `record_paid_order_inventory` nie jest podłączone do rzeczywistego webhooka.
- [34] ma istniejący scheduler wygaśnięcia w orders, ale brak pełnej obsługi płatności, anulowania administracyjnego i edytowalnego terminu.
- Zwroty, admin auth, panel [67] i dostarczanie powiadomień nie istnieją. Nie udostępniono niezabezpieczonych endpointów zastępczych.
- [52] może użyć `OrderItem.shipping_snapshot` do masy i wymiarów pojedynczej książki; suma masy to `weight_grams × quantity`. Wymiary paczki wymagają osobnej reguły pakowania. Nie skonfigurowano progów wagowych ani nie zmieniono cennika dostawy.

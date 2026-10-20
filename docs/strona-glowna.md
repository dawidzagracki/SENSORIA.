# Strona główna

Trasa `/` korzysta z `apps/web/app/(shop)/page.tsx`, a sklepowa rama z etapu [10] pozostaje w nadrzędnym layoucie. Strona jest dynamiczna i pobiera dane przez serwerowy `API_URL` bez utrwalania wyników między żądaniami.

## Treści edytowalne

API udostępnia wyłącznie walidowany zestaw `homepage.content.v1` przez `GET /catalog/public/homepage`. Endpoint zwraca treści nadtytułu, hasła (w trzech częściach dla wyróżnienia kursywą), akapitu, CTA, czterech obietnic i opcjonalne identyfikatory redakcyjnie wybranych produktów. Nie udostępnia całej tabeli `app_settings`. Przy braku wpisu zwraca bezpieczne wartości domyślne zdefiniowane razem z modelem; `uv run --frozen --all-groups python -m sensoria.seed` zapisuje je idempotentnie i nie nadpisuje późniejszej edycji.

Identyfikatory produktów są opcjonalne. Strona weryfikuje, czy wskazany produkt nadal jest zwrócony jako publiczny produkt właściwego rodzaju; jeśli nie, wybiera pierwszy opublikowany produkt tego rodzaju z sortowania `recommended`. Kurs wybiera spośród `DIGITAL` tylko po etykiecie `COURSE_PDF`. Gdy nie ma produktu danego rodzaju, karta nie jest zastępowana fikcyjną ofertą. CTA do vouchera przechodzi wtedy do katalogu z filtrem `kind=VOUCHER`.

Treści obietnic pochodzą z konfiguracji redakcyjnej. Samej obecności tych haseł nie należy traktować jako potwierdzenia działających płatności, wysyłki plików ani procesu dostawy; te integracje są poza zakresem etapu [22].

## Pobieranie i koszyk

Serwer wykonuje zbiorcze zapytania listy API: osobno dla typów potrzebnych w kompozycji i jedno dla polecanych kart. Nie odpytuje API po szczegóły każdej karty. API zwraca wyłącznie opublikowane produkty, ich aktualne slugi, ceny, obrazy i dostępne metryki. Obrazy nie mają wpisanych na stałe danych produktów; pierwszy obraz produktu voucherowego jest jedynym oznaczonym priorytetowo, jeśli API zwróci obraz.

Karty używają wspólnego `ProductCard`. Ponieważ integracja koszyka [24] nie istnieje, kliknięcie „Do koszyka” w sekcji polecanych pokazuje informację o niedostępnej integracji i nie udaje dodania. Wspólny nagłówek nadal używa serwerowego adaptera koszyka z etapu [10].

## SEO

Strona publikuje współdzielone `Organization` i `WebSite` JSON-LD, ze stabilnymi identyfikatorami i publicznym originem `SITE_URL`. Repozytorium nie zawiera logo w `apps/web/public`, więc schemat nie wskazuje fikcyjnego obrazu. Nie dodano `SearchAction`, ponieważ wyszukiwarka nie ma osobnej strony wyników.

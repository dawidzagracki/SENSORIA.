"use client";

import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState, useTransition } from "react";
import {
  Alert,
  Breadcrumbs,
  Button,
  Modal,
  ProductCard,
  Radio,
  Select,
  TextField,
} from "@/components/ui";
import { NoResults } from "@/components/catalog/no-results";
import {
  catalogPriceBands,
  countActiveCatalogFilters,
  updateCatalogParams,
} from "@/lib/catalog-query";
import type {
  CatalogListItem,
  CatalogListResponse,
} from "@/types/catalog-list";
import type { SearchPresentationSettings } from "@/types/search-presentation";

const sortOptions = [
  ["recommended", "Polecane"],
  ["price_asc", "Cena: od najniższej"],
  ["price_desc", "Cena: od najwyższej"],
  ["newest", "Najnowsze"],
  ["bestselling", "Bestsellery"],
] as const;
function resultLabel(count: number): string {
  const lastTwo = count % 100;
  const last = count % 10;
  if (count === 1) return "1 produkt";
  if (lastTwo >= 12 && lastTwo <= 14) return `${count} produktów`;
  return `${count} ${last >= 2 && last <= 4 ? "produkty" : "produktów"}`;
}

function categoryLabel(label: string): string {
  const normalized = label.toLocaleLowerCase("pl-PL");
  if (normalized.includes("voucher")) return "Vouchery na wizyty";
  if (normalized.includes("książ") || normalized.includes("ksiaz"))
    return "Książki papierowe";
  if (normalized.includes("audio")) return "Audiobooki";
  if (normalized.includes("kurs")) return "Kursy PDF";
  return label;
}
function countLabel(count: number): string {
  return count.toLocaleString("pl-PL");
}

function productType(
  product: CatalogListItem,
): "VOUCHER" | "KSIĄŻKA" | "AUDIOBOOK" | "KURS PDF" | "E-BOOK PDF" {
  if (product.kind === "VOUCHER") return "VOUCHER";
  if (product.kind === "BOOK") return "KSIĄŻKA";
  if (product.kind === "AUDIOBOOK") return "AUDIOBOOK";
  return product.digital_label === "COURSE_PDF" ? "KURS PDF" : "E-BOOK PDF";
}

function metric(product: CatalogListItem): string {
  if (
    product.digital?.page_count !== null &&
    product.digital?.page_count !== undefined
  )
    return `${product.digital.file_format.toUpperCase()} · ${product.digital.page_count} stron`;
  if (product.digital) return product.digital.file_format.toUpperCase();
  if (product.audiobook?.duration_seconds) {
    const minutes = Math.floor(product.audiobook.duration_seconds / 60);
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    return hours ? `${hours} godz. ${remainingMinutes} min` : `${minutes} min`;
  }
  if (product.voucher)
    return `Ważny ${product.voucher.validity_months} ${product.voucher.validity_months === 1 ? "miesiąc" : "miesięcy"}`;
  if (product.book?.isbn) return `ISBN ${product.book.isbn}`;
  return product.kind === "BOOK"
    ? "Książka papierowa"
    : product.kind === "VOUCHER"
      ? "Voucher na wizytę"
      : "Materiał cyfrowy";
}

function SkeletonCards() {
  return (
    <div
      aria-label="Ładowanie produktów"
      className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3"
      role="status"
    >
      {Array.from({ length: 6 }, (_, index) => (
        <div
          className="overflow-hidden rounded-card border border-border bg-surface"
          key={index}
        >
          <div className="aspect-product-image animate-pulse bg-surface-muted" />
          <div className="space-y-4 p-4">
            <div className="h-6 animate-pulse rounded-pill bg-surface-muted" />
            <div className="h-12 animate-pulse rounded-pill bg-surface-muted" />
            <div className="h-10 animate-pulse rounded-pill bg-surface-muted" />
          </div>
        </div>
      ))}
    </div>
  );
}

type CatalogViewProps = {
  data: CatalogListResponse;
  allCategoriesTotal: number;
  globalTotal: number;
  loadError?: string;
  searchPresentation: SearchPresentationSettings | null;
};

export function CatalogView({
  data,
  allCategoriesTotal,
  globalTotal,
  loadError,
  searchPresentation,
}: CatalogViewProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const params = useMemo(
    () => new URLSearchParams(searchParams.toString()),
    [searchParams],
  );
  const [isPending, startTransition] = useTransition();
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);
  const [listView, setListView] = useState(false);
  const [searchText, setSearchText] = useState(params.get("q") ?? "");
  const [cartNotice, setCartNotice] = useState(false);
  const activeFilters = countActiveCatalogFilters(params);
  const query = (params.get("q") ?? "").trim();
  const showNoResults =
    !loadError &&
    !isPending &&
    data.total === 0 &&
    (Boolean(query) || activeFilters > 0);

  useEffect(() => setSearchText(searchParams.get("q") ?? ""), [searchParams]); // Keep the draft aligned after Back/Forward.

  function navigate(
    changes: Parameters<typeof updateCatalogParams>[1],
    clear = false,
  ) {
    const href = updateCatalogParams(params, changes, clear);
    // A filtered/search result can be much shorter than the catalog. Let Next
    // return to the top so its heading is not left clipped at the old scroll offset.
    startTransition(() => router.push(href));
  }

  function choosePrice(value: string) {
    const band = catalogPriceBands.find((item) => item.value === value);
    if (!band) {
      navigate({ price_min: null, price_max: null });
      return;
    }
    navigate({ price_min: band.min, price_max: band.max });
  }

  function renderFilters(suffix: string) {
    return (
      <div className="space-y-6">
        <fieldset>
          <legend className="uppercase-label mb-2">Kategorie</legend>
          <div className="space-y-1">
            <Radio
              checked={!params.has("category")}
              label={
                <span className="flex w-full justify-between gap-2">
                  <span>Wszystkie</span>
                  <span className="text-caption">
                    {countLabel(allCategoriesTotal)}
                  </span>
                </span>
              }
              name={`category-${suffix}`}
              onChange={() => navigate({ category: null })}
            />
            {data.facets.categories.map((option) => (
              <Radio
                checked={params.get("category") === option.value}
                key={option.value}
                label={
                  <span className="flex w-full justify-between gap-2">
                    <span>{categoryLabel(option.label)}</span>
                    <span className="text-caption text-ink-muted">
                      {countLabel(option.count)}
                    </span>
                  </span>
                }
                name={`category-${suffix}`}
                onChange={() => navigate({ category: option.value })}
              />
            ))}
          </div>
        </fieldset>
        <fieldset>
          <legend className="uppercase-label mb-2">Dla kogo</legend>
          <div className="space-y-1">
            <Radio
              checked={!params.has("audience")}
              label="Wszyscy"
              name={`audience-${suffix}`}
              onChange={() => navigate({ audience: null })}
            />
            {data.facets.audiences.map((option) => (
              <Radio
                checked={params.get("audience") === option.value}
                key={option.value}
                label={
                  <span className="flex w-full justify-between gap-2">
                    <span>{option.label}</span>
                    <span className="text-caption text-ink-muted">
                      {option.count.toLocaleString("pl-PL")}
                    </span>
                  </span>
                }
                name={`audience-${suffix}`}
                onChange={() => navigate({ audience: option.value })}
              />
            ))}
          </div>
        </fieldset>
        <fieldset>
          <legend className="uppercase-label mb-2">Cena</legend>
          <div className="space-y-1">
            <Radio
              checked={!params.has("price_min") && !params.has("price_max")}
              label="Każda cena"
              name={`price-${suffix}`}
              onChange={() => navigate({ price_min: null, price_max: null })}
            />
            {catalogPriceBands.map((band) => {
              const option = data.facets.prices.find(
                (item) => item.value === band.value,
              );
              const checked =
                params.get("price_min") === band.min &&
                params.get("price_max") === band.max;
              return (
                <Radio
                  checked={checked}
                  key={band.value}
                  label={
                    <span className="flex w-full justify-between gap-2">
                      <span>{band.label}</span>
                      <span className="text-caption text-ink-muted">
                        {(option?.count ?? 0).toLocaleString("pl-PL")}
                      </span>
                    </span>
                  }
                  name={`price-${suffix}`}
                  onChange={() => choosePrice(band.value)}
                />
              );
            })}
          </div>
        </fieldset>
        <fieldset>
          <legend className="uppercase-label mb-2">Dostawa</legend>
          <div className="space-y-1">
            <Radio
              checked={!params.has("delivery")}
              label="Każdy sposób"
              name={`delivery-${suffix}`}
              onChange={() => navigate({ delivery: null })}
            />
            {data.facets.deliveries.map((option) => (
              <Radio
                checked={params.get("delivery") === option.value}
                key={option.value}
                label={
                  <span className="flex w-full justify-between gap-2">
                    <span>
                      {option.value === "digital"
                        ? "Od razu na mailu"
                        : "Paczkomat InPost"}
                    </span>
                    <span className="text-caption text-ink-muted">
                      {option.count.toLocaleString("pl-PL")}
                    </span>
                  </span>
                }
                name={`delivery-${suffix}`}
                onChange={() => navigate({ delivery: option.value })}
              />
            ))}
          </div>
        </fieldset>
        <Button
          className="w-full"
          onClick={() => navigate({}, true)}
          variant="text"
        >
          Wyczyść filtry
        </Button>
      </div>
    );
  }

  const pages = Array.from(
    { length: data.total_pages },
    (_, index) => index + 1,
  );
  const currentSort =
    params.get("sort") ?? (params.has("q") ? "" : "recommended");
  const products = data.items;
  const selectedKind = params.get("kind");
  const currentCatalogLabel = query
    ? "Wyniki wyszukiwania"
    : selectedKind === "VOUCHER"
      ? "Vouchery"
      : selectedKind === "BOOK"
        ? "Książki papierowe"
        : selectedKind === "AUDIOBOOK"
          ? "Audiobooki"
          : selectedKind === "DIGITAL"
            ? "Materiały cyfrowe"
            : params.has("category")
              ? categoryLabel(
                  data.facets.categories.find(
                    (category) => category.value === params.get("category"),
                  )?.label ?? "Materiały",
                )
              : "Wszystkie produkty";

  return (
    <main className="page-shell min-h-screen" id="main-content" tabIndex={-1}>
      <Breadcrumbs
        items={[{ href: "/", label: "Sklep" }, { label: currentCatalogLabel }]}
      />
      {showNoResults ? (
        <NoResults
          draft={searchText}
          hasFilters={activeFilters > 0}
          emptyCollectionLabel={
            !query && params.get("kind") === "VOUCHER" ? "voucherów" : null
          }
          onChooseQuery={(value) => {
            setSearchText(value);
            navigate({ q: value });
          }}
          onClearFilters={() => navigate({}, true)}
          onDraftChange={setSearchText}
          onSearch={() => navigate({ q: searchText || null })}
          query={query}
          settings={searchPresentation}
          suggestions={data.suggestions}
        />
      ) : (
        <>
          <section
            aria-labelledby="catalog-title"
            className="my-6 grid gap-6 rounded-card bg-surface-muted p-6 lg:grid-cols-2 lg:items-center lg:p-8"
          >
            <div className="min-w-0">
              <p className="uppercase-label text-accent-action">Sklep</p>
              <h1
                className="mt-3 max-w-content font-display text-title font-bold text-ink"
                id="catalog-title"
              >
                Materiały, które{" "}
                <em className="font-decorative font-normal text-accent-action">
                  zabierasz ze sobą
                </em>
              </h1>
              <p className="mt-4 max-w-content text-body-small text-ink-muted">
                Vouchery na wizyty, książki, audiobooki i kursy przygotowane
                przez zespół pracujący z dziećmi, młodzieżą i dorosłymi od 1999
                roku.
              </p>
            </div>
            <dl className="grid grid-cols-1 gap-4 text-center md:grid-cols-3 md:w-full">
              <div>
                <dt className="font-interface text-subtitle font-bold text-accent-action">
                  {loadError ? "—" : globalTotal.toLocaleString("pl-PL")}
                </dt>
                <dd className="text-caption text-ink-muted">
                  materiałów w sklepie
                </dd>
              </div>
              <div>
                <dt className="font-interface text-subtitle font-bold text-accent-action">
                  27 lat
                </dt>
                <dd className="text-caption text-ink-muted">
                  praktyki w gabinecie
                </dd>
              </div>
              <div>
                <dt className="font-interface text-subtitle font-bold text-accent-action">
                  15 s
                </dt>
                <dd className="text-caption text-ink-muted">
                  od płatności do pliku
                </dd>
              </div>
            </dl>
          </section>

          <div className="grid gap-6 lg:grid-cols-4">
            <aside
              aria-label="Filtry katalogu"
              className="hidden lg:col-span-1 lg:block"
            >
              {loadError ? null : renderFilters("desktop")}
            </aside>
            <section
              aria-label="Produkty"
              aria-busy={isPending}
              className="min-w-0 lg:col-span-3"
            >
              <div className="mb-4 flex flex-wrap items-end justify-between gap-4 border-b border-border pb-4">
                <div className="flex min-w-0 flex-1 flex-wrap items-end gap-3">
                  <Button
                    className="lg:hidden"
                    disabled={Boolean(loadError)}
                    onClick={() => setMobileFiltersOpen(true)}
                    variant="secondary"
                  >
                    Filtry{activeFilters ? ` (${activeFilters})` : ""}
                  </Button>
                  <form
                    className="w-full flex-1 md:max-w-wide"
                    onSubmit={(event) => {
                      event.preventDefault();
                      navigate({ q: searchText || null });
                    }}
                  >
                    <TextField
                      aria-label="Szukaj w katalogu"
                      label="Szukaj"
                      maxLength={160}
                      name="q"
                      onChange={(event) => setSearchText(event.target.value)}
                      placeholder="Wpisz nazwę lub temat"
                      value={searchText}
                    />
                  </form>
                  <p
                    aria-live="polite"
                    className="pb-2 text-body-small font-bold text-ink"
                  >
                    {loadError ? "Wyniki niedostępne" : resultLabel(data.total)}
                  </p>
                </div>
                <div className="flex flex-wrap items-end gap-2">
                  <Select
                    className="min-w-48"
                    label="Sortuj"
                    onChange={(event) =>
                      navigate({ sort: event.target.value || null })
                    }
                    value={currentSort}
                  >
                    <option value="">Trafność</option>
                    {sortOptions.map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </Select>
                  <div
                    aria-label="Widok produktów"
                    className="flex gap-1"
                    role="group"
                  >
                    <Button
                      aria-pressed={!listView}
                      onClick={() => setListView(false)}
                      size="sm"
                      variant={listView ? "secondary" : "primary"}
                    >
                      Siatka
                    </Button>
                    <Button
                      aria-pressed={listView}
                      onClick={() => setListView(true)}
                      size="sm"
                      variant={listView ? "primary" : "secondary"}
                    >
                      Lista
                    </Button>
                  </div>
                </div>
              </div>
              {loadError ? (
                <Alert title="Nie udało się pobrać katalogu" variant="error">
                  {loadError}
                  <div className="mt-3">
                    <Button
                      onClick={() => router.refresh()}
                      variant="secondary"
                    >
                      Spróbuj ponownie
                    </Button>
                  </div>
                </Alert>
              ) : null}
              {isPending ? (
                <div
                  aria-live="polite"
                  className="mb-4 text-caption text-ink-muted"
                  role="status"
                >
                  Aktualizuję wyniki…
                </div>
              ) : null}
              {isPending ? (
                <SkeletonCards />
              ) : loadError ? null : data.total > 0 && products.length === 0 ? (
                <Alert title="Ta strona nie zawiera produktów" variant="info">
                  Katalog zawiera {resultLabel(data.total)}, ale strona{" "}
                  {data.page} jest poza zakresem.
                  <div className="mt-3">
                    <Button
                      onClick={() => navigate({ page: "1" })}
                      variant="secondary"
                    >
                      Przejdź do pierwszej strony
                    </Button>
                  </div>
                </Alert>
              ) : products.length ? (
                <div
                  className={
                    listView
                      ? "grid grid-cols-1 gap-4"
                      : "grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3"
                  }
                >
                  {products.map((product) => (
                    <ProductCard
                      description={product.short_description ?? ""}
                      href={`/produkt/${encodeURIComponent(product.slug)}`}
                      image={
                        product.image ? (
                          <Image
                            alt=""
                            className="object-cover"
                            fill
                            sizes="(min-width: 1280px) 25vw, (min-width: 768px) 40vw, 90vw"
                            src={product.image.url}
                            unoptimized
                          />
                        ) : (
                          <span className="flex h-full items-center justify-center p-4 text-caption text-ink-muted">
                            Brak zdjęcia
                          </span>
                        )
                      }
                      imageAlt={product.image?.alt ?? "Brak zdjęcia produktu"}
                      key={product.id}
                      metric={metric(product)}
                      onAddToCart={() => setCartNotice(true)}
                      previousPriceInGrosze={
                        product.compare_at_price ?? undefined
                      }
                      lowestPriceInGrosze={
                        product.compare_at_price
                          ? (product.lowest_price_before_discount ?? null)
                          : undefined
                      }
                      priceInGrosze={product.price}
                      title={product.name}
                      type={productType(product)}
                    />
                  ))}
                </div>
              ) : (
                <p className="rounded-card border border-border bg-surface-muted p-6 text-body-small text-ink">
                  Nie znaleziono produktów spełniających wybrane warunki.
                </p>
              )}
              {cartNotice ? (
                <Alert title="Koszyk" variant="info">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <span>
                      Dodawanie produktów nie jest jeszcze dostępne. Ta
                      integracja powstanie w etapie koszyka.
                    </span>
                    <Button
                      onClick={() => setCartNotice(false)}
                      size="sm"
                      variant="secondary"
                    >
                      Zamknij
                    </Button>
                  </div>
                </Alert>
              ) : null}
              {data.total_pages > 1 && !loadError ? (
                <nav
                  aria-label="Stronicowanie produktów"
                  className="mt-8 flex flex-wrap justify-center gap-2"
                >
                  {pages.map((page) => (
                    <Button
                      aria-current={page === data.page ? "page" : undefined}
                      key={page}
                      onClick={() => navigate({ page: String(page) })}
                      size="sm"
                      variant={page === data.page ? "primary" : "secondary"}
                    >
                      {page}
                    </Button>
                  ))}
                  {data.page < data.total_pages ? (
                    <Button
                      aria-label="Następna strona"
                      onClick={() => navigate({ page: String(data.page + 1) })}
                      size="sm"
                      variant="secondary"
                    >
                      →
                    </Button>
                  ) : null}
                </nav>
              ) : null}
            </section>
          </div>
        </>
      )}
      <Modal
        onOpenChange={setMobileFiltersOpen}
        open={mobileFiltersOpen}
        title="Filtry katalogu"
      >
        <div className="max-h-screen overflow-y-auto pr-2">
          {loadError ? (
            <p className="text-body-small">
              Filtry będą dostępne po przywróceniu połączenia z katalogiem.
            </p>
          ) : (
            renderFilters("mobile")
          )}
        </div>
        <div className="mt-4">
          <Button
            className="w-full"
            onClick={() => setMobileFiltersOpen(false)}
            variant="primary"
          >
            Pokaż {resultLabel(data.total)}
          </Button>
        </div>
      </Modal>
    </main>
  );
}

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
  Select,
} from "@/components/ui";
import { NoResults } from "@/components/catalog/no-results";
import { CartToast, useAddToCart } from "@/components/products/use-add-to-cart";
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

function FilterGroup({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <fieldset>
      <legend className="uppercase-label mb-3 text-ink-muted">{title}</legend>
      <div className="flex flex-wrap gap-2">{children}</div>
    </fieldset>
  );
}

function Chip({
  label,
  count,
  pressed,
  onClick,
}: {
  label: string;
  count?: string;
  pressed: boolean;
  onClick: () => void;
}) {
  return (
    <button
      aria-pressed={pressed}
      className={`inline-flex min-h-touch items-center gap-2 rounded-pill border px-4 py-2 font-interface text-caption font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action focus-visible:ring-offset-2 focus-visible:ring-offset-surface ${
        pressed
          ? "border-accent-action bg-accent-action text-surface"
          : "border-border bg-surface text-ink hover:border-accent hover:bg-surface-muted"
      }`}
      onClick={onClick}
      type="button"
    >
      <span>{label}</span>
      {count ? (
        <span
          className={`rounded-pill px-2 text-label ${pressed ? "bg-surface text-accent-action" : "bg-surface-muted text-ink-muted"}`}
        >
          {count}
        </span>
      ) : null}
    </button>
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
  const { add, busyId, notice, dismiss } = useAddToCart();
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
    const priceChecked = (band: (typeof catalogPriceBands)[number]) =>
      params.get("price_min") === band.min &&
      params.get("price_max") === band.max;
    const noPrice = !params.has("price_min") && !params.has("price_max");
    return (
      <div className="space-y-7">
        <FilterGroup title="Kategorie">
          <Chip
            count={countLabel(allCategoriesTotal)}
            label="Wszystkie"
            onClick={() => navigate({ category: null })}
            pressed={!params.has("category")}
          />
          {data.facets.categories.map((option) => (
            <Chip
              count={countLabel(option.count)}
              key={option.value}
              label={categoryLabel(option.label)}
              onClick={() => navigate({ category: option.value })}
              pressed={params.get("category") === option.value}
            />
          ))}
        </FilterGroup>
        {data.facets.audiences.length ? (
          <FilterGroup title="Dla kogo">
            <Chip
              label="Wszyscy"
              onClick={() => navigate({ audience: null })}
              pressed={!params.has("audience")}
            />
            {data.facets.audiences.map((option) => (
              <Chip
                count={option.count.toLocaleString("pl-PL")}
                key={option.value}
                label={option.label}
                onClick={() => navigate({ audience: option.value })}
                pressed={params.get("audience") === option.value}
              />
            ))}
          </FilterGroup>
        ) : null}
        <FilterGroup title="Cena">
          <Chip
            label="Każda cena"
            onClick={() => navigate({ price_min: null, price_max: null })}
            pressed={noPrice}
          />
          {catalogPriceBands.map((band) => {
            const option = data.facets.prices.find(
              (item) => item.value === band.value,
            );
            return (
              <Chip
                count={(option?.count ?? 0).toLocaleString("pl-PL")}
                key={band.value}
                label={band.label}
                onClick={() => choosePrice(band.value)}
                pressed={priceChecked(band)}
              />
            );
          })}
        </FilterGroup>
        <FilterGroup title="Dostawa">
          <Chip
            label="Każdy sposób"
            onClick={() => navigate({ delivery: null })}
            pressed={!params.has("delivery")}
          />
          {data.facets.deliveries.map((option) => (
            <Chip
              count={option.count.toLocaleString("pl-PL")}
              key={option.value}
              label={
                option.value === "digital"
                  ? "Od razu na mailu"
                  : "Paczkomat InPost"
              }
              onClick={() => navigate({ delivery: option.value })}
              pressed={params.get("delivery") === option.value}
            />
          ))}
        </FilterGroup>
        {activeFilters > 0 ? (
          <Button
            className="w-full"
            onClick={() => navigate({}, true)}
            size="sm"
            variant="secondary"
          >
            Wyczyść filtry ({activeFilters})
          </Button>
        ) : null}
        <span className="sr-only">{suffix}</span>
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
            className="my-6 grid gap-6 rounded-card bg-surface-muted p-6 md:p-8 lg:grid-cols-[3fr_2fr] lg:items-center lg:p-10"
          >
            <div className="min-w-0">
              <p className="uppercase-label text-accent-action">Sklep</p>
              <h1
                className="mt-3 max-w-content font-display text-title font-extrabold tracking-tight text-ink md:text-display"
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
            <dl className="grid grid-cols-3 gap-4 text-center">
              <div>
                <dt className="font-display text-subtitle font-extrabold text-accent-action md:text-title">
                  {loadError ? "—" : globalTotal.toLocaleString("pl-PL")}
                </dt>
                <dd className="text-caption text-ink-muted">
                  materiałów w sklepie
                </dd>
              </div>
              <div>
                <dt className="font-display text-subtitle font-extrabold text-accent-action md:text-title">
                  27 lat
                </dt>
                <dd className="text-caption text-ink-muted">
                  praktyki w gabinecie
                </dd>
              </div>
              <div>
                <dt className="font-display text-subtitle font-extrabold text-accent-action md:text-title">
                  15 s
                </dt>
                <dd className="text-caption text-ink-muted">
                  od płatności do pliku
                </dd>
              </div>
            </dl>
          </section>

          <div className="grid gap-8 lg:grid-cols-[280px_1fr]">
            <aside aria-label="Filtry katalogu" className="hidden lg:block">
              <div className="sticky top-24 rounded-card border border-border bg-surface p-6 shadow-subtle">
                {loadError ? null : renderFilters("desktop")}
              </div>
            </aside>
            <section
              aria-label="Produkty"
              aria-busy={isPending}
              className="min-w-0"
            >
              <form
                className="mb-4"
                onSubmit={(event) => {
                  event.preventDefault();
                  navigate({ q: searchText || null });
                }}
                role="search"
              >
                <label className="sr-only" htmlFor="catalog-search">
                  Szukaj w katalogu
                </label>
                <div className="relative">
                  <svg
                    aria-hidden="true"
                    className="pointer-events-none absolute left-5 top-1/2 h-5 w-5 -translate-y-1/2 text-ink-muted"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <path
                      d="M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM21 21l-4.3-4.3"
                      stroke="currentColor"
                      strokeLinecap="round"
                      strokeWidth="1.8"
                    />
                  </svg>
                  <input
                    className="min-h-control-lg w-full rounded-pill border border-border bg-surface py-3 pl-14 pr-32 text-body text-ink shadow-subtle placeholder:text-ink-muted focus-visible:border-accent-action focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
                    id="catalog-search"
                    maxLength={160}
                    name="q"
                    onChange={(event) => setSearchText(event.target.value)}
                    placeholder="Szukaj w sklepie"
                    type="search"
                    value={searchText}
                  />
                  <button
                    className="absolute right-2 top-1/2 min-h-touch -translate-y-1/2 rounded-pill bg-accent-action px-5 font-interface text-button font-semibold text-surface hover:bg-accent hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action focus-visible:ring-offset-2"
                    type="submit"
                  >
                    Szukaj
                  </button>
                </div>
              </form>
              <div className="mb-6 flex flex-wrap items-center justify-between gap-3 border-b border-border pb-4">
                <div className="flex flex-wrap items-center gap-3">
                  <Button
                    className="lg:hidden"
                    disabled={Boolean(loadError)}
                    onClick={() => setMobileFiltersOpen(true)}
                    size="sm"
                    variant="secondary"
                  >
                    Filtry{activeFilters ? ` (${activeFilters})` : ""}
                  </Button>
                  <p
                    aria-live="polite"
                    className="text-body-small font-semibold text-ink"
                  >
                    {loadError ? "Wyniki niedostępne" : resultLabel(data.total)}
                  </p>
                  {activeFilters > 0 || query ? (
                    <button
                      className="min-h-touch rounded-pill px-3 text-caption font-semibold text-accent-action underline underline-offset-4 hover:text-ink"
                      onClick={() => navigate({}, true)}
                      type="button"
                    >
                      Wyczyść wszystko
                    </button>
                  ) : null}
                </div>
                <div className="flex flex-wrap items-center gap-3">
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
                    className="hidden gap-1 self-end md:flex"
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
                      : "grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3"
                  }
                >
                  {products.map((product) => (
                    <ProductCard
                      description={product.short_description ?? ""}
                      href={`/sklep/${encodeURIComponent(product.slug)}`}
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
                      actionHref={
                        product.kind === "VOUCHER"
                          ? `/sklep/${encodeURIComponent(product.slug)}`
                          : undefined
                      }
                      actionLabel={
                        product.kind === "VOUCHER"
                          ? "Wybierz wariant"
                          : "Do koszyka"
                      }
                      addLoading={busyId === product.id}
                      onAddToCart={() => void add(product.id, product.name)}
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
              <CartToast notice={notice} onDismiss={dismiss} />
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

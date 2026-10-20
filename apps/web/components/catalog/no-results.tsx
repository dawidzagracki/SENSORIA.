"use client";

import Image from "next/image";
import { Button, ProductCard, TextField } from "@/components/ui";
import type {
  CatalogListItem,
  CatalogListResponse,
} from "@/types/catalog-list";
import type { SearchPresentationSettings } from "@/types/search-presentation";

type NoResultsProps = {
  query: string;
  draft: string;
  hasFilters: boolean;
  emptyCollectionLabel: string | null;
  settings: SearchPresentationSettings | null;
  suggestions: CatalogListResponse["suggestions"];
  onDraftChange: (value: string) => void;
  onSearch: () => void;
  onChooseQuery: (value: string) => void;
  onClearFilters: () => void;
};

function productType(
  product: CatalogListItem,
): "VOUCHER" | "KSIĄŻKA" | "AUDIOBOOK" | "KURS PDF" | "E-BOOK PDF" {
  if (product.kind === "VOUCHER") return "VOUCHER";
  if (product.kind === "BOOK") return "KSIĄŻKA";
  if (product.kind === "AUDIOBOOK") return "AUDIOBOOK";
  return product.digital_label === "COURSE_PDF" ? "KURS PDF" : "E-BOOK PDF";
}

function metric(product: CatalogListItem): string {
  if (product.digital?.page_count != null)
    return `${product.digital.file_format.toUpperCase()} · ${product.digital.page_count} stron`;
  if (product.audiobook?.duration_seconds) {
    const minutes = Math.floor(product.audiobook.duration_seconds / 60);
    const hours = Math.floor(minutes / 60);
    return hours ? `${hours} godz. ${minutes % 60} min` : `${minutes} min`;
  }
  if (product.voucher)
    return `Ważny ${product.voucher.validity_months} ${product.voucher.validity_months === 1 ? "miesiąc" : "miesięcy"}`;
  return product.kind === "BOOK" ? "Książka papierowa" : "Materiał cyfrowy";
}

export function NoResults({
  query,
  draft,
  hasFilters,
  emptyCollectionLabel,
  settings,
  suggestions,
  onDraftChange,
  onSearch,
  onChooseQuery,
  onClearFilters,
}: NoResultsProps) {
  const related = suggestions?.related_products.slice(0, 3) ?? [];
  const filterOnly = !query;

  return (
    <section
      aria-labelledby="no-results-title"
      className="overflow-hidden rounded-card border border-border bg-surface"
    >
      <div className="bg-surface-muted px-4 py-8 sm:px-8 md:px-12 md:py-12">
        <p className="uppercase-label text-accent-action">
          {emptyCollectionLabel
            ? "VOUCHERY NA WIZYTY"
            : filterOnly
              ? "FILTRY"
              : "WYSZUKIWANIE"}
        </p>
        <h1
          className="mt-3 max-w-content break-words font-display text-title font-bold text-ink"
          id="no-results-title"
        >
          {filterOnly ? (
            emptyCollectionLabel ? (
              `Nie ma teraz dostępnych ${emptyCollectionLabel}`
            ) : (
              "Brak produktów spełniających wybrane filtry"
            )
          ) : (
            <>
              Brak wyników dla{" "}
              <em className="break-words font-decorative font-normal text-accent-action">
                „{query}”
              </em>
            </>
          )}
        </h1>
        {filterOnly ? (
          <p className="mt-3 max-w-content text-body-small text-ink-muted">
            {emptyCollectionLabel
              ? "W tej chwili w katalogu nie ma opublikowanych voucherów. Sprawdź ponownie później albo skontaktuj się z nami, jeśli szukasz konkretnej oferty."
              : "Zmień wybrane zawężenia albo wyszukaj temat bez tych filtrów."}
          </p>
        ) : null}
        <form
          className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-end"
          onSubmit={(event) => {
            event.preventDefault();
            onSearch();
          }}
        >
          <TextField
            className="min-w-0 flex-1"
            label="Szukaj w katalogu"
            maxLength={160}
            name="q"
            onChange={(event) => onDraftChange(event.target.value)}
            value={draft}
          />
          <Button className="shrink-0" type="submit" variant="primary">
            Szukaj
          </Button>
        </form>
        {settings && !emptyCollectionLabel ? (
          <div className="mt-5 flex flex-wrap items-center gap-2">
            <span className="mr-1 text-body-small font-bold text-ink">
              Spróbuj:
            </span>
            {settings.suggested_queries.map((term) => (
              <Button
                className="rounded-pill border-border"
                key={term}
                onClick={() => onChooseQuery(term)}
                size="sm"
                variant="secondary"
              >
                {term}
              </Button>
            ))}
          </div>
        ) : null}
        {suggestions?.popular_queries.length && !emptyCollectionLabel ? (
          <p className="mt-4 text-caption text-ink-muted">
            Popularne wyszukiwania: {suggestions.popular_queries.join(" · ")}
          </p>
        ) : null}
        {hasFilters ? (
          <div className="mt-5">
            <Button onClick={onClearFilters} variant="secondary">
              Wyczyść filtry
            </Button>
          </div>
        ) : null}
      </div>

      {settings && !emptyCollectionLabel ? (
        <div className="mx-4 my-6 rounded-card bg-surface-muted p-4 sm:mx-8 sm:p-6">
          <h2 className="font-interface text-subtitle font-bold text-ink">
            {filterOnly
              ? "Nie znaleźliśmy produktów z tym zestawem filtrów"
              : "Nie mamy jeszcze materiału na ten temat"}
          </h2>
          <p className="mt-2 max-w-content text-body-small text-ink-muted">
            {filterOnly
              ? "Możesz zmienić filtry lub skontaktować się z nami — podpowiemy, czego szukać."
              : "Jeśli szukasz czegoś konkretnego, napisz — jeśli to obszar, w którym pracujemy, podpowiemy, co wybrać zamiast tego, albo umówimy Cię na konsultację."}
          </p>
          <div className="mt-4 flex flex-wrap gap-3">
            {settings.contact_email ? (
              <a
                className="inline-flex min-h-touch items-center rounded-pill bg-accent-action px-4 py-3 font-interface text-label font-bold text-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action focus-visible:ring-offset-2"
                href={`mailto:${settings.contact_email}`}
              >
                Napisz do nas
              </a>
            ) : null}
            {settings.contact_phone ? (
              <a
                className="inline-flex min-h-touch items-center rounded-pill border border-accent-action px-4 py-3 font-interface text-label font-bold text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action focus-visible:ring-offset-2"
                href={`tel:${settings.contact_phone.replace(/[^+0-9]/g, "")}`}
              >
                Zadzwoń
              </a>
            ) : null}
          </div>
          {!settings.contact_email && !settings.contact_phone ? (
            <p className="mt-3 text-caption text-ink-muted">
              Dane kontaktowe nie są obecnie skonfigurowane.
            </p>
          ) : null}
        </div>
      ) : null}

      {related.length ? (
        <div className="px-4 pb-8 sm:px-8 md:px-12">
          <h2 className="mb-4 font-interface text-subtitle font-bold text-ink">
            Materiały o zbliżonej tematyce
          </h2>
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
            {related.map((product) => (
              <ProductCard
                actionHref={`/produkt/${encodeURIComponent(product.slug)}`}
                actionLabel="Zobacz"
                description={product.short_description ?? ""}
                href={`/produkt/${encodeURIComponent(product.slug)}`}
                image={
                  product.image ? (
                    <Image
                      alt=""
                      className="object-cover"
                      fill
                      sizes="(min-width: 1024px) 30vw, 90vw"
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
                previousPriceInGrosze={product.compare_at_price ?? undefined}
                priceInGrosze={product.price}
                title={product.name}
                type={productType(product)}
              />
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}

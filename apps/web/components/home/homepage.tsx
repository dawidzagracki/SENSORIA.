import Image from "next/image";
import Link from "next/link";
import { Alert, Badge, Price } from "@/components/ui";
import { formatMoney } from "@/lib/format-money";
import {
  productMetric,
  productTypeLabel,
  type HomepageFeaturedProducts,
} from "@/lib/homepage-products";
import type { CatalogListItem } from "@/types/catalog-list";
import type { HomepageContent } from "@/types/homepage";
import { RecommendedProducts } from "./recommended-products";

type HomepageProps = {
  content: HomepageContent;
  featured: HomepageFeaturedProducts;
  recommendations: CatalogListItem[];
  catalogUnavailable: boolean;
  recommendationsUnavailable: boolean;
};

function BenefitIcon({
  name,
}: {
  name: HomepageContent["benefits"][number]["icon"];
}) {
  const paths: Record<typeof name, string> = {
    payment: "M3 7h18v11H3z M3 10h18 M7 15h3",
    email: "M3 5h18v14H3z M3 6l9 7 9-7",
    parcel: "M4 8l8-4 8 4v9l-8 4-8-4z M4 8l8 4 8-4 M12 12v9",
    voucher: "M5 5h14v14H5z M8 9h.01 M16 9h.01 M8 15h8",
  };
  return (
    <svg aria-hidden="true" className="h-6 w-6" fill="none" viewBox="0 0 24 24">
      <path
        d={paths[name]}
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.7"
      />
    </svg>
  );
}

function ProductArtwork({ product }: { product: CatalogListItem }) {
  if (product.image) {
    return (
      <Image
        alt=""
        className="object-cover"
        fill
        sizes="(min-width: 1024px) 28vw, (min-width: 640px) 45vw, 90vw"
        src={product.image.url}
        unoptimized
      />
    );
  }

  if (product.kind === "VOUCHER") {
    return (
      <div className="absolute inset-4 flex flex-col justify-between rounded-card border border-border bg-surface p-4 text-ink shadow-subtle sm:inset-6 sm:p-6">
        <span className="uppercase-label text-accent-action">
          VOUCHER NA WIZYTĘ
        </span>
        <span className="max-w-content font-interface text-subtitle font-bold">
          {product.name}
        </span>
        <span className="flex items-end justify-between gap-4">
          <span className="font-interface text-caption font-bold tracking-caps text-accent-action">
            PODGLĄD
          </span>
          <svg
            aria-hidden="true"
            className="h-12 w-12 shrink-0 text-accent-action"
            fill="currentColor"
            viewBox="0 0 36 36"
          >
            <path d="M1 1h10v10H1zM4 4v4h4V4zM14 1h10v10H14zM17 4v4h4V4zM25 1h10v10H25zM28 4v4h4V4zM1 14h10v10H1zM4 17v4h4v-4zM14 14h4v4h-4zM21 14h3v3h-3zM27 14h8v4h-8zM15 21h5v4h-5zM23 20h4v4h-4zM30 20h5v5h-5zM1 27h10v8H1zM4 29v4h4v-4zM14 28h4v7h-4zM21 27h5v4h-5zM29 28h6v7h-6z" />
          </svg>
        </span>
      </div>
    );
  }

  if (product.kind === "AUDIOBOOK") {
    return (
      <div
        aria-hidden="true"
        className="absolute inset-0 flex items-center justify-center bg-surface-muted p-6"
      >
        <div className="flex h-2/3 w-2/3 items-center justify-center gap-2 rounded-card border border-border bg-surface p-6 text-accent-action shadow-subtle">
          {[
            "h-4",
            "h-8",
            "h-12",
            "h-16",
            "h-10",
            "h-14",
            "h-6",
            "h-12",
            "h-8",
          ].map((height, index) => (
            <span
              aria-hidden="true"
              className={`w-2 rounded-pill bg-current ${height}`}
              key={`${height}-${index}`}
            />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div
      aria-hidden="true"
      className="absolute inset-0 flex items-center justify-center bg-surface-muted p-6"
    >
      <div className="relative flex h-2/3 w-2/3 items-center justify-center rounded-card border border-border bg-surface p-6 shadow-subtle">
        <div className="w-full space-y-3 text-accent">
          <span className="block h-2 rounded-pill bg-current" />
          <span className="block h-2 w-3/4 rounded-pill bg-current" />
          <span className="block h-2 w-5/6 rounded-pill bg-current" />
          <span className="block h-2 w-2/3 rounded-pill bg-current" />
        </div>
      </div>
    </div>
  );
}

function HeroProductCard({
  product,
  slot,
  priority = false,
}: {
  product: CatalogListItem;
  slot: "voucher" | "audiobook" | "course";
  priority?: boolean;
}) {
  const position = {
    voucher: "lg:absolute lg:left-30 lg:top-1/4 lg:z-20 lg:w-5/12 lg:-rotate-2",
    audiobook: "lg:absolute lg:right-0 lg:top-16 lg:z-10 lg:w-1/3 lg:rotate-2",
    course:
      "lg:absolute lg:right-0 lg:top-1/2 lg:z-30 lg:w-1/3 lg:-translate-x-16 lg:-translate-y-12 lg:-rotate-1",
  }[slot];
  const type = productTypeLabel(product);

  return (
    <Link
      aria-label={`${type}: ${product.name}, ${formatMoney(product.price)}`}
      className={`group min-w-0 rounded-card border border-border bg-surface p-3 shadow-subtle transition-transform hover:-translate-y-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action focus-visible:ring-offset-2 focus-visible:ring-offset-surface sm:p-4 ${position}`}
      href={`/sklep/${encodeURIComponent(product.slug)}`}
    >
      <div
        className={`relative ${product.kind === "VOUCHER" ? "aspect-ticket-preview" : "aspect-product-image"} overflow-hidden rounded-card bg-surface-muted`}
      >
        {product.image ? (
          <Image
            alt=""
            className="object-cover"
            fill
            priority={priority}
            sizes="(min-width: 1024px) 34vw, (min-width: 640px) 44vw, 90vw"
            src={product.image.url}
            unoptimized
          />
        ) : (
          <ProductArtwork product={product} />
        )}
        <div className="absolute left-3 top-3">
          <Badge label={type} />
        </div>
      </div>
      <div className="min-w-0 space-y-2 p-1 pt-3">
        <h2 className="line-clamp-2 font-interface text-label font-bold text-ink">
          {product.name}
        </h2>
        {/* No reduced-price claim without the Omnibus 30-day price, which this feed lacks. */}
        <Price
          amountInGrosze={product.price}
          lowestPriceInGrosze={null}
          previousAmountInGrosze={product.compare_at_price ?? undefined}
        />
        <p className="break-words text-caption text-ink-muted">
          {productMetric(product)}
        </p>
      </div>
    </Link>
  );
}

const featuredCategories = [
  {
    slot: "voucher",
    label: "VOUCHER NA WIZYTĘ",
    title: "Wybierz wizytę dla siebie",
    href: "/sklep?kind=VOUCHER",
    detail: "Sprawdź dostępne vouchery",
  },
  {
    slot: "audiobook",
    label: "AUDIOBOOKI",
    title: "Posłuchaj materiałów Sensoria",
    href: "/sklep?kind=AUDIOBOOK",
    detail: "Przejdź do audiobooków",
  },
  {
    slot: "course",
    label: "KURSY PDF",
    title: "Materiały do pracy w domu",
    href: "/sklep?category=kursy-pdf",
    detail: "Zobacz kursy PDF",
  },
] as const;

function HeroCategoryCard({
  category,
}: {
  category: (typeof featuredCategories)[number];
}) {
  const artwork =
    category.slot === "voucher" ? (
      <div className="mx-auto flex h-24 w-4/5 items-center justify-between gap-3 rounded-card border border-border bg-surface-muted p-3 sm:h-28 sm:p-4">
        <div className="min-w-0">
          <span className="uppercase-label text-accent-action">WZÓR</span>
          <span className="mt-2 block font-interface text-label font-bold text-ink sm:text-caption">
            Voucher na wizytę
          </span>
        </div>
        <span
          aria-hidden="true"
          className="grid h-12 w-12 shrink-0 grid-cols-4 gap-0.5 rounded-md bg-surface p-1 sm:h-14 sm:w-14"
        >
          {Array.from({ length: 16 }, (_, index) => (
            <span
              className={index % 3 === 0 ? "bg-accent-action" : "bg-ink"}
              key={index}
            />
          ))}
        </span>
      </div>
    ) : category.slot === "audiobook" ? (
      <div className="flex h-16 items-center justify-center gap-1 rounded-card bg-surface-muted p-4 text-accent-action sm:h-20 sm:gap-2">
        {["h-6", "h-10", "h-14", "h-8", "h-16", "h-10", "h-6"].map(
          (height, index) => (
            <span
              aria-hidden="true"
              className={`w-1.5 rounded-pill bg-current sm:w-2 ${height}`}
              key={`${height}-${index}`}
            />
          ),
        )}
      </div>
    ) : (
      <div className="flex h-24 items-center justify-center rounded-card bg-surface-muted p-4">
        <div className="w-4/5 space-y-2 rounded-card border border-border bg-surface p-4">
          <span className="block h-2 rounded-pill bg-accent" />
          <span className="block h-2 w-3/4 rounded-pill bg-accent" />
          <span className="block h-2 w-5/6 rounded-pill bg-accent" />
          <span className="block h-2 w-2/3 rounded-pill bg-accent" />
        </div>
      </div>
    );

  const position = {
    voucher: "lg:absolute lg:left-30 lg:top-1/4 lg:z-20 lg:w-5/12 lg:-rotate-2",
    audiobook: "lg:absolute lg:right-0 lg:top-16 lg:z-10 lg:w-1/3 lg:rotate-2",
    course:
      "lg:absolute lg:right-0 lg:top-1/2 lg:z-30 lg:w-1/3 lg:-translate-x-16 lg:-translate-y-12 lg:-rotate-1",
  }[category.slot];

  return (
    <Link
      aria-label={`${category.label}: ${category.title}`}
      className={`group min-w-0 rounded-card border border-border bg-surface p-3 shadow-subtle transition-transform hover:-translate-y-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action focus-visible:ring-offset-2 focus-visible:ring-offset-surface sm:p-4 ${position}`}
      href={category.href}
    >
      <span className="uppercase-label text-accent-action">
        {category.label}
      </span>
      <span className="mt-2 block line-clamp-2 font-interface text-label font-bold text-ink sm:text-caption">
        {category.title}
      </span>
      <span className="mt-3 block">{artwork}</span>
      <span className="mt-3 block font-interface text-label font-bold text-ink-muted underline decoration-accent-action underline-offset-4">
        {category.detail}
      </span>
    </Link>
  );
}

export function Homepage({
  content,
  featured,
  recommendations,
  catalogUnavailable,
  recommendationsUnavailable,
}: HomepageProps) {
  const voucherHref = featured.voucher
    ? `/sklep/${encodeURIComponent(featured.voucher.slug)}`
    : "/sklep?kind=VOUCHER";

  return (
    <main className="page-shell min-h-screen" id="main-content" tabIndex={-1}>
      <section
        aria-labelledby="home-title"
        className="grid gap-8 py-8 md:gap-12 lg:grid-cols-[3fr_5fr] lg:items-start lg:py-12"
      >
        <div className="min-w-0">
          <p className="uppercase-label mb-6 flex items-center gap-3 text-accent-action">
            <span aria-hidden="true" className="h-px w-6 bg-current" />
            {content.eyebrow}
          </p>
          <h1
            className="max-w-content font-display text-title font-bold leading-tight text-ink md:text-display xl:text-home"
            id="home-title"
          >
            {content.headline.before_emphasis}{" "}
            <em className="font-decorative font-normal text-accent-action">
              {content.headline.emphasis}
            </em>{" "}
            {content.headline.after_emphasis}
          </h1>
          <p className="mt-6 max-w-content text-body text-ink-muted">
            {content.paragraph}
          </p>
          <div className="mt-6 flex flex-wrap gap-3 lg:mt-12">
            <Link
              className="inline-flex min-h-control-lg items-center justify-center rounded-pill border border-accent-action bg-accent-action px-6 py-4 font-interface text-body-small font-bold text-surface transition-colors hover:border-accent hover:bg-accent hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
              href={content.catalog_button_target}
            >
              {content.catalog_button_label}
            </Link>
            <Link
              className="inline-flex min-h-control-lg items-center justify-center rounded-pill border border-accent-action bg-surface px-6 py-4 font-interface text-body-small font-bold text-ink transition-colors hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
              href={voucherHref}
            >
              {content.voucher_button_label}
            </Link>
          </div>
          <ul
            aria-label="Obietnice sklepu"
            className="mt-6 flex flex-wrap gap-3 lg:mt-8"
          >
            {content.benefits.map((benefit) => (
              <li
                className="flex min-h-touch items-center gap-3 rounded-pill border border-border bg-surface-muted px-3 py-2 font-interface text-caption font-bold text-ink"
                key={benefit.icon}
              >
                <span className="text-accent-action">
                  <BenefitIcon name={benefit.icon} />
                </span>
                <span>{benefit.text}</span>
              </li>
            ))}
          </ul>
          <p
            aria-hidden="true"
            className="mt-8 flex items-center gap-3 font-interface text-caption font-bold tracking-caps text-ink-muted"
          >
            <span className="h-px w-12 bg-accent" /> PRZEWIŃ, ŻEBY ZOBACZYĆ
            SKLEP
          </p>
        </div>

        <div
          aria-label="Polecane rodzaje materiałów"
          className="relative min-w-0 lg:aspect-square lg:w-hero lg:max-w-none lg:overflow-hidden"
          role="group"
        >
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 hidden items-center justify-center lg:flex"
          >
            <div className="aspect-square w-full scale-125 rounded-pill border border-accent/40" />
            <div className="absolute aspect-square w-5/6 scale-125 rounded-pill border border-dashed border-accent/40" />
            <div className="absolute aspect-square w-2/3 scale-125 rounded-pill border border-accent/40" />
          </div>
          {catalogUnavailable ? (
            <Alert title="Nie można pobrać produktów" variant="error">
              Spróbuj ponownie później. Linki i ceny nie są zastępowane
              przykładowymi danymi.
            </Alert>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:block lg:aspect-square">
              {featuredCategories.map((category) => {
                const product = featured[category.slot];
                return product ? (
                  <HeroProductCard
                    key={category.slot}
                    product={product}
                    priority={
                      category.slot === "voucher" && Boolean(product.image)
                    }
                    slot={category.slot}
                  />
                ) : (
                  <HeroCategoryCard category={category} key={category.slot} />
                );
              })}
            </div>
          )}
        </div>
      </section>

      <section
        aria-labelledby="recommended-title"
        className="border-t border-border py-8 md:py-12"
      >
        <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="uppercase-label text-accent-action">
              WYBRANE DLA CIEBIE
            </p>
            <h2
              className="mt-2 font-interface text-title font-bold text-ink"
              id="recommended-title"
            >
              Polecane materiały
            </h2>
          </div>
          <Link
            className="inline-flex min-h-touch items-center rounded-pill px-4 font-interface text-caption font-bold text-ink underline decoration-accent-action underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
            href="/sklep"
          >
            Zobacz cały katalog
          </Link>
        </div>
        {recommendationsUnavailable ? (
          <Alert title="Katalog jest chwilowo niedostępny" variant="error">
            Nie można teraz pobrać polecanych produktów.
          </Alert>
        ) : recommendations.length ? (
          <RecommendedProducts products={recommendations} />
        ) : (
          <p className="rounded-card border border-border bg-surface-muted p-6 text-body-small text-ink-muted">
            Brak opublikowanych produktów do polecenia.
          </p>
        )}
      </section>
    </main>
  );
}

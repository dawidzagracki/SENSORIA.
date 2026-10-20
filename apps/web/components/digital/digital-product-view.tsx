import { Accordion } from "@/components/ui";
import { CatalogRelatedProducts } from "@/components/products/catalog-related-products";
import {
  ProductBreadcrumbs,
  ProductCover,
  ProductHeading,
  productTypeLabel,
} from "@/components/products/product-detail-shared";
import { ProductPurchaseActions } from "@/components/products/product-purchase-actions";
import { PdfSamplePreview } from "@/components/products/pdf-sample-preview";
import type { CatalogProductDetail } from "@/types/catalog";

type Props = { product: CatalogProductDetail };

function discountPercent(price: number, compareAtPrice: number): number {
  const discount = BigInt(compareAtPrice - price) * 100n;
  const denominator = BigInt(compareAtPrice);
  return Number((discount * 2n + denominator) / (denominator * 2n));
}

function DigitalCover({ product }: Props) {
  return (
    <div className="space-y-4">
      <ProductCover product={product} label={productTypeLabel(product)} />
      {product.digital?.sample_available && product.digital.sample_pages ? (
        <PdfSamplePreview
          pages={product.digital.sample_pages}
          slug={product.slug}
        />
      ) : null}
      <ul className="flex flex-wrap justify-center gap-3 text-caption text-ink-muted">
        {product.digital?.page_count ? (
          <li className="min-h-touch rounded-pill border border-border px-3 py-3">
            {product.digital.file_format} · {product.digital.page_count} stron
          </li>
        ) : null}
        {product.digital?.edition ? (
          <li className="min-h-touch rounded-pill border border-border px-3 py-3">
            Wydanie {product.digital.edition}
          </li>
        ) : null}
      </ul>
    </div>
  );
}

function faqItems(product: CatalogProductDetail) {
  return [
    {
      id: "delivery",
      title: "Kiedy dostanę plik?",
      content: (
        <p>
          Informacja o wydaniu pliku wymaga potwierdzenia w konfiguracji
          zamówienia. Nota o zgodzie na wcześniejsze udostępnienie znajduje się
          przed przyciskami zakupu.
        </p>
      ),
    },
    {
      id: "reader",
      title: "Czy mogę czytać na czytniku?",
      content: (
        <p>
          Format pliku: {product.digital?.file_format ?? "niepodany"}. Zgodność
          z konkretnymi urządzeniami nie została określona.
        </p>
      ),
    },
    {
      id: "invoice",
      title: "Czy dostanę fakturę?",
      content: <p>Informacja o fakturach nie została zatwierdzona.</p>,
    },
    {
      id: "return",
      title: "Czy mogę zwrócić e-booka?",
      content: <p>Zasady zwrotu wymagają zatwierdzonej treści regulaminu.</p>,
    },
  ];
}

export function DigitalProductView({ product }: Props) {
  const digital = product.digital;
  const isDiscounted =
    product.compare_at_price !== null &&
    product.compare_at_price > product.price;
  return (
    <main
      className="page-shell space-y-8 pb-28 md:space-y-12 lg:pb-0"
      id="main-content"
      tabIndex={-1}
    >
      <ProductBreadcrumbs product={product} categoryLabel="Materiały cyfrowe" />
      <article className="grid min-w-0 gap-8 lg:grid-cols-2 lg:gap-12">
        <DigitalCover product={product} />
        <section
          aria-labelledby="digital-title"
          className="min-w-0 space-y-5 lg:sticky lg:top-24 lg:self-start"
        >
          <ProductHeading product={product} label={productTypeLabel(product)} />
          {product.audience_tags.length > 0 ? (
            <div aria-label="Dla kogo" className="flex flex-wrap gap-2">
              {product.audience_tags.map((tag) => (
                <span
                  className="rounded-pill border border-border px-3 py-2 text-caption text-ink-muted"
                  key={tag}
                >
                  {tag}
                </span>
              ))}
            </div>
          ) : null}
          {digital?.edition ? (
            <p className="text-body-small text-ink-muted">
              Wydanie {digital.edition}
            </p>
          ) : null}
          <p className="rounded-card border border-border bg-surface-muted p-4 text-body-small text-ink">
            Kupując treść cyfrową, potwierdzasz przy płatności zgodę na jej
            udostępnienie przed upływem terminu odstąpienia od umowy — co
            oznacza utratę prawa do odstąpienia. Bez tej zgody plik wyślemy po
            14 dniach.
            <span className="mt-2 block text-caption text-ink-muted">
              To informacja o wymaganym kroku zamówienia. Ta strona nie zapisuje
              zgody ani nie uruchamia odroczonego wydania pliku.
            </span>
          </p>
          <section aria-label="Dane oferty" className="space-y-4">
            {isDiscounted && product.compare_at_price !== null ? (
              <p className="inline-flex rounded-pill bg-accent-action px-3 py-2 text-label font-bold text-on-accent">
                −{discountPercent(product.price, product.compare_at_price)}%
              </p>
            ) : null}
            <ProductPurchaseActions
              available={product.is_available}
              compareAtPrice={isDiscounted ? product.compare_at_price : null}
              lowestPriceBeforeDiscount={
                product.lowest_price_before_discount ??
                product.digital?.lowest_price_before_discount ??
                null
              }
              mobileLabel="Kup i pobierz"
              price={product.price}
              productId={product.id}
              primaryLabel="Kup i pobierz teraz"
              vatRate={product.vat_rate}
            />
          </section>
          <ul className="space-y-3 border-t border-border pt-4 text-body-small text-ink-muted">
            <li>
              Zakup, płatność i wydawanie plików nie są jeszcze podłączone.
            </li>
            <li>
              Plik cyfrowy nie jest udostępniany przed potwierdzeniem płatności.
            </li>
            <li>Znakowanie pliku wymaga osobnego etapu [41].</li>
          </ul>
        </section>
      </article>

      <section
        aria-labelledby="digital-contents-title"
        className="-mx-4 space-y-4 bg-surface-muted px-4 py-8 md:-mx-4 md:px-4 xl:-mx-12 xl:px-12"
      >
        <p className="text-label font-bold uppercase tracking-caps text-accent-action">
          Spis treści
        </p>
        <h2
          className="font-display text-subtitle font-bold text-ink"
          id="digital-contents-title"
        >
          Co znajdziesz w środku
        </h2>
        <p className="text-body-small text-ink-muted">
          Spis treści nie jest jeszcze dostępny w danych tego produktu.
        </p>
      </section>

      {product.audience_tags.length > 0 ? (
        <section aria-labelledby="digital-audience-title" className="space-y-4">
          <p className="text-label font-bold uppercase tracking-caps text-accent-action">
            Dla kogo
          </p>
          <h2
            className="font-display text-subtitle font-bold text-ink"
            id="digital-audience-title"
          >
            Komu ten materiał pomoże
          </h2>
          <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {product.audience_tags.map((tag) => (
              <li
                className="rounded-card border border-border bg-surface p-4 text-body-small text-ink"
                key={tag}
              >
                {tag}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section
        aria-labelledby="digital-author-title"
        className="-mx-4 space-y-4 bg-surface-muted px-4 py-8 md:-mx-4 md:px-4 xl:-mx-12 xl:px-12"
      >
        <p className="text-label font-bold uppercase tracking-caps text-accent-action">
          O autorce
        </p>
        <h2
          className="font-display text-subtitle font-bold text-ink"
          id="digital-author-title"
        >
          Informacje o autorce
        </h2>
        <p className="text-body-small text-ink-muted">
          Informacje o autorce nie zostały powiązane z tym produktem w danych
          API.
        </p>
      </section>

      <CatalogRelatedProducts
        currentId={product.id}
        products={product.related_products}
      />

      <section
        aria-labelledby="digital-faq-title"
        className="mx-auto w-full max-w-content space-y-5"
      >
        <p className="text-label font-bold uppercase tracking-caps text-accent-action">
          Pytania
        </p>
        <h2
          className="font-display text-subtitle font-bold text-ink"
          id="digital-faq-title"
        >
          Zanim kupisz
        </h2>
        <Accordion
          defaultExpandedIds={["delivery"]}
          items={faqItems(product)}
          mode="single"
        />
      </section>
      <p className="text-caption text-ink-muted">
        Dane o fragmentach, spisie treści, autorce i warunkach produktu wymagają
        uzupełnienia w zatwierdzonych treściach redakcyjnych.
      </p>
    </main>
  );
}

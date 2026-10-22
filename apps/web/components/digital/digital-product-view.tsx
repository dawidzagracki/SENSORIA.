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
import {
  AuthorBlurb,
  DigitalConsentNotice,
  TrustList,
  digitalFaq,
  digitalTrust,
} from "@/components/products/product-info";
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
  return digitalFaq(
    product.digital?.label === "COURSE_PDF" ? "course" : "ebook",
  );
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
          <DigitalConsentNotice />
          <section aria-label="Dane oferty" className="space-y-4">
            {isDiscounted && product.compare_at_price !== null ? (
              <p className="inline-flex rounded-pill bg-accent-action px-3 py-2 text-label font-bold text-surface">
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
          <TrustList items={digitalTrust} />
        </section>
      </article>

      {product.audience_tags.length > 0 ? (
        <section aria-labelledby="digital-audience-title" className="space-y-4">
          <p className="uppercase-label text-accent-action">Dla kogo</p>
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

      <AuthorBlurb />

      <CatalogRelatedProducts
        currentId={product.id}
        products={product.related_products}
      />

      <section
        aria-labelledby="digital-faq-title"
        className="mx-auto w-full max-w-content space-y-5"
      >
        <p className="uppercase-label text-accent-action">Pytania</p>
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
    </main>
  );
}

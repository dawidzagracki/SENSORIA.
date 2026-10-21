import { ProductPurchaseActions } from "@/components/products/product-purchase-actions";
import { CatalogRelatedProducts } from "@/components/products/catalog-related-products";
import {
  ProductBreadcrumbs,
  ProductCover,
  ProductHeading,
} from "@/components/products/product-detail-shared";
import { AuthorBlurb } from "@/components/products/product-info";
import { getBookAvailability } from "@/lib/catalog-product";
import type { CatalogProductDetail } from "@/types/catalog";

export function BookProductView({
  product,
}: {
  product: CatalogProductDetail;
}) {
  const book = product.book;
  if (!book) throw new Error("Produkt BOOK nie zawiera danych magazynowych.");
  const availability = getBookAvailability(book.available_quantity);
  const canBuy = availability.available && product.is_available;
  const dimensions = [book.length_mm, book.width_mm, book.height_mm];
  const hasDimensions = dimensions.every((dimension) => dimension !== null);

  return (
    <main
      className="page-shell space-y-8 pb-28 md:space-y-12 lg:pb-0"
      id="main-content"
      tabIndex={-1}
    >
      <ProductBreadcrumbs product={product} categoryLabel="Książki papierowe" />
      <article className="grid min-w-0 gap-8 lg:grid-cols-2 lg:gap-12">
        <div className="space-y-4">
          <ProductCover product={product} label="KSIĄŻKA" />
          <dl className="grid grid-cols-2 gap-3 text-body-small text-ink-muted">
            {book.binding ? (
              <div className="rounded-card border border-border p-3">
                <dt className="text-caption">Oprawa</dt>
                <dd className="break-words font-bold text-ink">
                  {book.binding}
                </dd>
              </div>
            ) : null}
            {hasDimensions ? (
              <div className="rounded-card border border-border p-3">
                <dt className="text-caption">Wymiary (dł. × szer. × wys.)</dt>
                <dd className="font-bold text-ink">
                  {dimensions.join(" × ")} mm
                </dd>
              </div>
            ) : null}
            {book.weight_grams ? (
              <div className="rounded-card border border-border p-3">
                <dt className="text-caption">Waga</dt>
                <dd className="font-bold text-ink">{book.weight_grams} g</dd>
              </div>
            ) : null}
            {book.isbn ? (
              <div className="min-w-0 rounded-card border border-border p-3">
                <dt className="text-caption">ISBN</dt>
                <dd className="break-all font-bold text-ink">{book.isbn}</dd>
              </div>
            ) : null}
          </dl>
        </div>
        <section
          aria-label="Informacje o książce i zakup"
          className="min-w-0 space-y-5 lg:sticky lg:top-24 lg:self-start"
        >
          <ProductHeading product={product} label="KSIĄŻKA" />
          {availability.message ? (
            <p
              className={
                "inline-flex rounded-pill px-3 py-2 text-label font-bold " +
                (availability.state === "unavailable"
                  ? "bg-danger text-on-danger"
                  : "bg-warning text-on-warning")
              }
              role={availability.state === "unavailable" ? "status" : undefined}
            >
              {availability.message}
            </p>
          ) : null}
          <section
            aria-label="Dostawa książki"
            className="space-y-2 border-y border-border py-4 text-body-small text-ink-muted"
          >
            {book.shipping_business_days && book.shipping_method ? (
              <>
                <p>Wysyłka w {book.shipping_business_days} dni robocze.</p>
                <p>{book.shipping_method}</p>
              </>
            ) : (
              <p>
                Wysyłamy InPostem (Paczkomat lub kurier) albo wydajemy w
                gabinecie w Olsztynie. Koszt zobaczysz w koszyku.
              </p>
            )}
          </section>
          <p className="rounded-card border border-border bg-surface-muted p-4 text-body-small text-ink">
            Masz 14 dni na odstąpienie od umowy.{" "}
            <a
              className="underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
              href="/pomoc/zwroty-i-reklamacje"
            >
              Informacje o zwrotach
            </a>
            .
          </p>
          <ProductPurchaseActions
            available={canBuy}
            compareAtPrice={product.compare_at_price}
            lowestPriceBeforeDiscount={
              product.lowest_price_before_discount ?? null
            }
            disabledReason={
              book.available_quantity === 0
                ? "Nie można teraz kupić tej książki, ponieważ nie ma jej na stanie."
                : !canBuy
                  ? "Zakup jest obecnie niedostępny."
                  : undefined
            }
            mobileLabel="Kup książkę"
            price={product.price}
            productId={product.id}
            primaryLabel="Kup książkę"
            vatRate={product.vat_rate}
          />
        </section>
      </article>
      {product.audience_tags.length > 0 ? (
        <section aria-labelledby="book-audience-title" className="space-y-4">
          <h2
            className="font-display text-subtitle font-bold text-ink"
            id="book-audience-title"
          >
            Dla kogo
          </h2>
          <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {product.audience_tags.map((audience) => (
              <li
                className="rounded-card border border-border bg-surface p-4 text-body-small text-ink"
                key={audience}
              >
                {audience}
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
    </main>
  );
}

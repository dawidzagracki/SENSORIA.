"use client";

import Image from "next/image";
import { CartToast, useAddToCart } from "./use-add-to-cart";
import { ProductCard, type ProductType } from "@/components/ui";
import type { CatalogRelatedProduct } from "@/types/catalog";

type Props = { currentId: string; products: CatalogRelatedProduct[] };

function productType(product: CatalogRelatedProduct): ProductType {
  if (product.kind === "VOUCHER") return "VOUCHER";
  if (product.kind === "BOOK") return "KSIĄŻKA";
  if (product.kind === "AUDIOBOOK") return "AUDIOBOOK";
  return product.digital_label === "COURSE_PDF" ? "KURS PDF" : "E-BOOK PDF";
}

export function CatalogRelatedProducts({ currentId, products }: Props) {
  const { add, busyId, notice, dismiss } = useAddToCart();
  const recommendations = products
    .filter(
      (product, index, all) =>
        product.id !== currentId &&
        all.findIndex((candidate) => candidate.id === product.id) === index,
    )
    .slice(0, 3);

  if (recommendations.length === 0) return null;

  return (
    <section
      aria-labelledby="catalog-related-title"
      className="-mx-4 space-y-5 bg-surface-muted px-4 py-8 md:-mx-4 md:px-4 xl:-mx-12 xl:px-12"
    >
      <div>
        <p className="uppercase-label text-accent-action">Zobacz też</p>
        <h2
          className="mt-2 font-display text-subtitle font-bold text-ink"
          id="catalog-related-title"
        >
          Podobne materiały
        </h2>
      </div>
      <div className="grid min-w-0 grid-cols-1 gap-4 md:grid-cols-3">
        {recommendations.map((product) => (
          <ProductCard
            description={
              product.short_description ??
              "Opis produktu nie został udostępniony."
            }
            href={`/sklep/${encodeURIComponent(product.slug)}`}
            image={
              product.image ? (
                <Image
                  alt={product.image.alt}
                  className="object-cover"
                  fill
                  sizes="(min-width: 1280px) 25vw, (min-width: 768px) 50vw, 100vw"
                  src={product.image.url}
                  unoptimized
                />
              ) : null
            }
            imageAlt={product.image?.alt ?? "Okładka produktu niedostępna"}
            key={product.id}
            metric={
              product.digital?.page_count
                ? `${product.digital.file_format} · ${product.digital.page_count} stron`
                : (product.digital?.file_format ?? "Szczegóły produktu")
            }
            actionHref={
              product.kind === "VOUCHER"
                ? `/sklep/${encodeURIComponent(product.slug)}`
                : undefined
            }
            actionLabel={
              product.kind === "VOUCHER" ? "Wybierz wariant" : "Do koszyka"
            }
            addLoading={busyId === product.id}
            onAddToCart={() => void add(product.id, product.name)}
            previousPriceInGrosze={product.compare_at_price ?? undefined}
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
      <CartToast notice={notice} onDismiss={dismiss} />
    </section>
  );
}

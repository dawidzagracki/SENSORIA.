"use client";

import Image from "next/image";
import { CartToast, useAddToCart } from "@/components/products/use-add-to-cart";
import { ProductCard } from "@/components/ui";
import { productMetric, productTypeLabel } from "@/lib/homepage-products";
import type { CatalogListItem } from "@/types/catalog-list";

export function RecommendedProducts({
  products,
}: {
  products: CatalogListItem[];
}) {
  const { add, busyId, notice, dismiss } = useAddToCart();
  return (
    <>
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
        {products.map((product) => {
          const href = `/sklep/${encodeURIComponent(product.slug)}`;
          const needsVariant = product.kind === "VOUCHER";
          return (
            <ProductCard
              actionHref={needsVariant ? href : undefined}
              actionLabel={needsVariant ? "Wybierz wariant" : "Do koszyka"}
              addLoading={busyId === product.id}
              description={product.short_description ?? ""}
              href={href}
              image={
                product.image ? (
                  <Image
                    alt=""
                    className="object-cover"
                    fill
                    sizes="(min-width: 1280px) 22vw, (min-width: 768px) 45vw, 90vw"
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
              lowestPriceInGrosze={
                product.compare_at_price
                  ? (product.lowest_price_before_discount ?? null)
                  : undefined
              }
              metric={productMetric(product)}
              onAddToCart={() => void add(product.id, product.name)}
              previousPriceInGrosze={product.compare_at_price ?? undefined}
              priceInGrosze={product.price}
              title={product.name}
              type={productTypeLabel(product)}
            />
          );
        })}
      </div>
      <CartToast notice={notice} onDismiss={dismiss} />
    </>
  );
}

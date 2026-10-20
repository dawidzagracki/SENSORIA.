"use client";

import Image from "next/image";
import { useState } from "react";
import { Alert, Button, ProductCard } from "@/components/ui";
import { productMetric, productTypeLabel } from "@/lib/homepage-products";
import type { CatalogListItem } from "@/types/catalog-list";

export function RecommendedProducts({
  products,
}: {
  products: CatalogListItem[];
}) {
  const [notice, setNotice] = useState(false);
  return (
    <>
      {notice ? (
        <div className="mb-6">
          <Alert title="Dodawanie do koszyka" variant="info">
            Ta funkcja będzie dostępna po wdrożeniu integracji koszyka.
            <Button
              className="ml-3"
              onClick={() => setNotice(false)}
              size="sm"
              variant="secondary"
            >
              Zamknij
            </Button>
          </Alert>
        </div>
      ) : null}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
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
                  sizes="(min-width: 1024px) 30vw, (min-width: 768px) 45vw, 90vw"
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
            metric={productMetric(product)}
            onAddToCart={() => setNotice(true)}
            previousPriceInGrosze={product.compare_at_price ?? undefined}
            lowestPriceInGrosze={
              product.compare_at_price
                ? (product.lowest_price_before_discount ?? null)
                : undefined
            }
            priceInGrosze={product.price}
            title={product.name}
            type={productTypeLabel(product)}
          />
        ))}
      </div>
    </>
  );
}

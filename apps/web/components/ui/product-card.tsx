import Link from "next/link";
import type { ReactNode } from "react";
import { productTypeTokens } from "../../tailwind.config";
import { Badge, type ProductBadgeLabel } from "./badge";
import { Button } from "./button";
import { Price } from "./price";

export type ProductType = ProductBadgeLabel;

export type ProductCardProps = {
  actionHref?: string;
  actionLabel?: string;
  description: string;
  href?: string;
  image: ReactNode;
  imageAlt: string;
  isBestseller?: boolean;
  metric: string;
  onAddToCart?: () => void;
  addLoading?: boolean;
  previousPriceInGrosze?: number;
  lowestPriceInGrosze?: number | null;
  priceInGrosze: number;
  title: string;
  type: ProductType;
};

export function ProductCard({
  actionHref,
  actionLabel = "Do koszyka",
  description,
  href,
  image,
  imageAlt,
  isBestseller = false,
  metric,
  onAddToCart,
  addLoading = false,
  previousPriceInGrosze,
  lowestPriceInGrosze,
  priceInGrosze,
  title,
  type,
}: ProductCardProps) {
  if (!productTypeTokens.some((token) => token.label === type)) {
    throw new Error(`Brak tokenu dla typu produktu: ${type}`);
  }

  return (
    <article className="group flex h-full flex-col overflow-hidden rounded-card border border-border bg-surface shadow-subtle transition duration-200 hover:-translate-y-1 hover:shadow-overlay motion-reduce:hover:translate-y-0">
      <div
        aria-label={imageAlt}
        className="relative aspect-product-image overflow-hidden bg-surface-muted [&_img]:transition-transform [&_img]:duration-300 group-hover:[&_img]:scale-105 motion-reduce:group-hover:[&_img]:scale-100"
        role="img"
      >
        {image}
        <div className="absolute inset-x-4 top-4 flex flex-wrap items-start gap-2">
          <Badge label={type} />
          {isBestseller ? <Badge label="BESTSELLER" /> : null}
        </div>
      </div>
      <div className="flex flex-1 flex-col p-5">
        <h3 className="font-display text-card-title font-extrabold text-ink">
          {href ? (
            <Link
              className="inline-flex min-h-touch items-center focus-visible:rounded-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
              href={href}
            >
              {title}
            </Link>
          ) : (
            title
          )}
        </h3>
        <p className="mt-2 text-body-small text-ink-muted">{description}</p>
        <div className="mt-auto pt-4">
          <div className="mb-4 border-t border-border pt-4">
            <Price
              amountInGrosze={priceInGrosze}
              previousAmountInGrosze={previousPriceInGrosze}
              lowestPriceInGrosze={lowestPriceInGrosze}
            />
            <p className="mt-2 text-caption text-ink-muted">{metric}</p>
          </div>
          {actionHref ? (
            <Link
              className="inline-flex min-h-control-md w-full items-center justify-center rounded-pill border border-accent-action bg-surface px-4 py-3 font-interface text-button font-semibold text-accent-action focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action focus-visible:ring-offset-2 hover:bg-surface-muted"
              href={actionHref}
            >
              {actionLabel}
            </Link>
          ) : (
            <Button
              className="w-full"
              loading={addLoading}
              onClick={onAddToCart}
              variant="secondary"
            >
              {actionLabel}
            </Button>
          )}
        </div>
      </div>
    </article>
  );
}

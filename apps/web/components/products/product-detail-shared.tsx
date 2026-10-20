import Image from "next/image";
import {
  Badge,
  Breadcrumbs,
  type BreadcrumbItem,
  type ProductType,
} from "@/components/ui";
import { categoryPath } from "@/lib/catalog-urls";
import type { CatalogProductDetail } from "@/types/catalog";

export function productTypeLabel(product: CatalogProductDetail): ProductType {
  if (product.kind === "BOOK") return "KSIĄŻKA";
  if (product.kind === "AUDIOBOOK") return "AUDIOBOOK";
  if (product.kind === "VOUCHER") return "VOUCHER";
  return product.digital?.label === "COURSE_PDF" ? "KURS PDF" : "E-BOOK PDF";
}

export function ProductBreadcrumbs({
  product,
  categoryLabel,
}: {
  product: CatalogProductDetail;
  categoryLabel: string;
}) {
  const category = product.categories[0];
  const items: BreadcrumbItem[] = [{ label: "Sklep", href: "/sklep" }];
  if (category?.parent_name && category.parent_slug) {
    items.push({
      label: category.parent_name,
      href: categoryPath(category.parent_slug),
    });
  }
  if (category) {
    items.push({ label: category.name, href: categoryPath(category.slug) });
  } else {
    items.push({ label: categoryLabel });
  }
  items.push({ label: product.name });
  return <Breadcrumbs items={items as [BreadcrumbItem, ...BreadcrumbItem[]]} />;
}

export function ProductCover({
  product,
  label,
}: {
  product: CatalogProductDetail;
  label: ProductType;
}) {
  const image = product.images[0];
  return (
    <figure className="rounded-card bg-surface-muted p-4 shadow-subtle md:p-6">
      <div className="relative mx-auto aspect-ebook-cover w-full max-w-content overflow-hidden rounded-card bg-surface">
        {image ? (
          <Image
            alt={image.alt}
            className="object-contain"
            fill
            priority
            sizes="(min-width: 1024px) 38vw, 100vw"
            src={image.url}
            unoptimized
          />
        ) : (
          <div className="flex h-full items-center justify-center p-4 text-center text-body-small text-ink-muted">
            Okładka nie została udostępniona.
          </div>
        )}
        <div className="absolute left-3 top-3">
          <Badge label={label} />
        </div>
      </div>
    </figure>
  );
}

export function ProductHeading({
  product,
  label,
}: {
  product: CatalogProductDetail;
  label: ProductType;
}) {
  const taxonomyLabel =
    product.categories[0]?.parent_name ?? product.categories[0]?.name;
  return (
    <header className="min-w-0 space-y-4">
      {taxonomyLabel ? (
        <p className="text-label font-bold uppercase tracking-caps text-accent-action">
          {taxonomyLabel}
        </p>
      ) : null}
      <Badge label={label} />
      <h1 className="break-words font-display text-title font-bold text-ink">
        {product.name}
      </h1>
      {product.short_description ? (
        <p className="font-decorative text-emphasis italic text-accent-action">
          {product.short_description}
        </p>
      ) : null}
      {product.description ? (
        <p className="break-words text-body text-ink-muted">
          {product.description}
        </p>
      ) : null}
    </header>
  );
}

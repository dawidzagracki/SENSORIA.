import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Badge, Breadcrumbs, Price } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { getPublicProduct } from "@/lib/catalog-api";
import {
  categoryPath,
  productPath,
  publicUrl,
  safePublicImageUrl,
} from "@/lib/catalog-urls";
import {
  productBreadcrumbJsonLd,
  productJsonLd,
  serializeJsonLd,
} from "@/lib/json-ld";
import type { ProductBadgeLabel } from "@/components/ui";
import type { PublicProduct } from "@/types/catalog";

export const dynamic = "force-dynamic";

type ProductPageProps = { params: Promise<{ slug: string }> };

function labelForProduct(
  kind: "VOUCHER" | "BOOK" | "AUDIOBOOK" | "DIGITAL",
  digitalLabel: "COURSE_PDF" | "EBOOK_PDF" | null,
): ProductBadgeLabel {
  if (kind === "VOUCHER") return "VOUCHER";
  if (kind === "BOOK") return "KSIĄŻKA";
  if (kind === "AUDIOBOOK") return "AUDIOBOOK";
  return digitalLabel === "COURSE_PDF" ? "KURS PDF" : "E-BOOK PDF";
}

export async function generateMetadata({
  params,
}: ProductPageProps): Promise<Metadata> {
  const { slug } = await params;
  try {
    const product = await getPublicProduct(slug);
    const canonical = publicUrl(productPath(product.slug));
    const image = product.og_image
      ? safePublicImageUrl(product.og_image)
      : undefined;
    return {
      title: { absolute: product.meta_title },
      description: product.meta_description,
      alternates: { canonical },
      openGraph: {
        type: "website",
        url: canonical,
        title: product.meta_title,
        description: product.meta_description,
        ...(image ? { images: [{ url: image }] } : {}),
      },
    };
  } catch (error: unknown) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }
}

export default async function ProductPage({ params }: ProductPageProps) {
  const { slug } = await params;
  let product: PublicProduct;
  try {
    product = await getPublicProduct(slug);
  } catch (error: unknown) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }

  const preferredCategory = [...product.categories].sort((left, right) =>
    left.slug.localeCompare(right.slug, "pl"),
  )[0];
  const breadcrumbItems = [
    { label: "Sklep", href: "/sklep" },
    ...(preferredCategory?.parent_slug && preferredCategory.parent_name
      ? [
          {
            label: preferredCategory.parent_name,
            href: categoryPath(preferredCategory.parent_slug),
          },
        ]
      : []),
    ...(preferredCategory
      ? [
          {
            label: preferredCategory.name,
            href: categoryPath(preferredCategory.slug),
          },
        ]
      : []),
    { label: product.name },
  ] as [
    { label: string; href?: string },
    ...{ label: string; href?: string }[],
  ];
  const structuredData = [
    productJsonLd(product),
    productBreadcrumbJsonLd(product),
  ];
  const image = product.images[0];
  const productImageUrl = image ? safePublicImageUrl(image.url) : undefined;

  return (
    <main className="page-shell space-y-6" id="main-content" tabIndex={-1}>
      <Breadcrumbs items={breadcrumbItems} />
      <article className="grid min-w-0 gap-6 rounded-card border border-border bg-surface p-4 shadow-card md:grid-cols-2 md:p-8">
        {image && productImageUrl ? (
          <div className="relative aspect-product-image overflow-hidden rounded-card bg-surface-muted">
            <Image
              src={productImageUrl}
              alt={image.alt}
              fill
              sizes="(min-width: 768px) 50vw, 100vw"
              className="object-cover"
              unoptimized
            />
          </div>
        ) : null}
        <div className="min-w-0 space-y-4">
          <Badge label={labelForProduct(product.kind, product.digital_label)} />
          <h1 className="font-display text-title font-bold text-ink">
            {product.name}
          </h1>
          <p className="text-body text-ink-muted">
            {product.short_description ??
              product.description ??
              product.meta_description}
          </p>
          <div className="border-t border-border pt-4">
            {product.offers.length > 1 ? (
              <ul className="space-y-4" aria-label="Dostępne warianty ceny">
                {product.offers.map((offer, index) => (
                  <li
                    key={`${offer.name ?? "offer"}-${index}`}
                    className="flex flex-wrap justify-between gap-3"
                  >
                    <span>
                      {offer.name === "ONLINE"
                        ? "Wizyta online"
                        : "Wizyta stacjonarna"}
                    </span>
                    <Price
                      amountInGrosze={offer.price}
                      vatRate={product.vat_rate ?? undefined}
                    />
                  </li>
                ))}
              </ul>
            ) : product.price !== null ? (
              <Price
                amountInGrosze={product.price}
                previousAmountInGrosze={product.compare_at_price ?? undefined}
                lowestPriceInGrosze={null}
                vatRate={product.vat_rate ?? undefined}
              />
            ) : null}
          </div>
          <p role="status" className="text-body text-ink">
            {product.is_available
              ? "Produkt dostępny"
              : "Produkt chwilowo niedostępny"}
          </p>
          {product.categories.length > 0 ? (
            <ul
              className="flex flex-wrap gap-3"
              aria-label="Kategorie produktu"
            >
              {product.categories.map((category) => (
                <li key={category.slug}>
                  <Link
                    className="underline"
                    href={categoryPath(category.slug)}
                  >
                    {category.name}
                  </Link>
                </li>
              ))}
            </ul>
          ) : null}
          {product.audience_tags.length > 0 ? (
            <p>
              Dla: <span>{product.audience_tags.join(", ")}</span>
            </p>
          ) : null}
        </div>
      </article>
      {product.description ? (
        <section
          aria-labelledby="product-description-title"
          className="max-w-content space-y-3"
        >
          <h2
            id="product-description-title"
            className="font-interface text-subtitle font-bold"
          >
            Opis produktu
          </h2>
          <p className="whitespace-pre-line">{product.description}</p>
        </section>
      ) : null}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: serializeJsonLd(structuredData) }}
      />
    </main>
  );
}

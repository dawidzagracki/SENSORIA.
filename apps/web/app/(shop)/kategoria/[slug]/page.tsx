import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ApiError } from "@/lib/api";
import { getPublicCategory } from "@/lib/catalog-api";
import {
  categoryPath,
  productPath,
  publicUrl,
  safePublicImageUrl,
} from "@/lib/catalog-urls";
import { categoryBreadcrumbJsonLd, serializeJsonLd } from "@/lib/json-ld";
import {
  Price,
  type ProductBadgeLabel,
  Badge,
  Breadcrumbs,
} from "@/components/ui";
import type { PublicCategoryPage, PublicProduct } from "@/types/catalog";

export const dynamic = "force-dynamic";

type CategoryPageProps = { params: Promise<{ slug: string }> };

function productBadge(product: PublicProduct): ProductBadgeLabel {
  if (product.kind === "VOUCHER") return "VOUCHER";
  if (product.kind === "BOOK") return "KSIĄŻKA";
  if (product.kind === "AUDIOBOOK") return "AUDIOBOOK";
  return product.digital_label === "COURSE_PDF" ? "KURS PDF" : "E-BOOK PDF";
}

async function loadCategory(slug: string): Promise<PublicCategoryPage> {
  try {
    return await getPublicCategory(slug);
  } catch (error: unknown) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }
}

export async function generateMetadata({
  params,
}: CategoryPageProps): Promise<Metadata> {
  const { slug } = await params;
  const category = await loadCategory(slug);
  const canonical = publicUrl(categoryPath(category.slug));
  const source = category.og_image ?? process.env.SITE_OG_IMAGE;
  const image = source ? safePublicImageUrl(source) : undefined;
  return {
    title: { absolute: category.meta_title },
    description: category.meta_description,
    alternates: { canonical },
    openGraph: {
      type: "website",
      url: canonical,
      title: category.meta_title,
      description: category.meta_description,
      ...(image ? { images: [{ url: image }] } : {}),
    },
  };
}

export default async function CategoryPage({ params }: CategoryPageProps) {
  const { slug } = await params;
  const category = await loadCategory(slug);
  const structuredData = categoryBreadcrumbJsonLd(
    category.name,
    category.slug,
    category.parent_name,
    category.parent_slug,
  );
  const breadcrumbItems = [
    { label: "Sklep", href: "/sklep" },
    ...(category.parent_slug && category.parent_name
      ? [
          {
            label: category.parent_name,
            href: categoryPath(category.parent_slug),
          },
        ]
      : []),
    { label: category.name },
  ] as [
    { label: string; href?: string },
    ...{ label: string; href?: string }[],
  ];

  return (
    <main className="page-shell space-y-6" id="main-content" tabIndex={-1}>
      <Breadcrumbs items={breadcrumbItems} />
      <header className="space-y-3">
        <h1 className="font-display text-title font-bold text-ink">
          {category.name}
        </h1>
        <p className="max-w-content text-ink-muted">
          {category.description ?? category.meta_description}
        </p>
        <p>{category.published_product_count} opublikowanych produktów</p>
      </header>
      {category.products.length ? (
        <ul className="grid min-w-0 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {category.products.map((product) => {
            const imageUrl = product.images[0]
              ? safePublicImageUrl(product.images[0].url)
              : undefined;
            return (
              <li
                key={product.id}
                className="min-w-0 rounded-card border border-border bg-surface p-4 shadow-card"
              >
                <article className="space-y-4">
                  <Badge label={productBadge(product)} />
                  <h2 className="font-interface text-subtitle font-bold">
                    <Link
                      className="underline"
                      href={productPath(product.slug)}
                    >
                      {product.name}
                    </Link>
                  </h2>
                  <p className="break-words text-ink-muted">
                    {product.short_description ?? product.meta_description}
                  </p>
                  {product.images[0] && imageUrl ? (
                    <Image
                      src={imageUrl}
                      alt={product.images[0].alt}
                      width={320}
                      height={320}
                      unoptimized
                      sizes="(min-width: 1024px) 30vw, (min-width: 360px) 50vw, 100vw"
                      className="aspect-product-image w-full rounded-card object-cover"
                    />
                  ) : null}
                  <div className="space-y-2">
                    {product.offers.map((offer, index) => (
                      <Price
                        key={`${offer.name ?? "price"}-${index}`}
                        amountInGrosze={offer.price}
                        previousAmountInGrosze={
                          product.offers.length === 1
                            ? (product.compare_at_price ?? undefined)
                            : undefined
                        }
                        vatRate={product.vat_rate ?? undefined}
                      />
                    ))}
                  </div>
                  <p className="text-caption">
                    {product.is_available ? "Dostępny" : "Chwilowo niedostępny"}
                  </p>
                </article>
              </li>
            );
          })}
        </ul>
      ) : (
        <p>W tej kategorii nie ma obecnie opublikowanych produktów.</p>
      )}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: serializeJsonLd(structuredData) }}
      />
    </main>
  );
}

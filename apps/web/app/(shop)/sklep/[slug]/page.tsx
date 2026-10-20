import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";
import { ApiError } from "@/lib/api";
import { getCatalogProductDetail } from "@/lib/catalog-api";
import {
  publicUrl,
  safePublicImageUrl,
  voucherProductPath,
} from "@/lib/catalog-urls";
import { serializeJsonLd } from "@/lib/serialize-json-ld";
import { VoucherProductView } from "@/components/voucher/voucher-product-view";
import type { CatalogProductDetail, VoucherVariantKind } from "@/types/catalog";
import { DigitalProductView } from "@/components/digital/digital-product-view";
import { BookProductView } from "@/components/products/book-product-view";
import { AudiobookProductView } from "@/components/products/audiobook-product-view";

export const dynamic = "force-dynamic";

type PageProps = {
  params: Promise<{ slug: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

const variantKeys: Record<VoucherVariantKind, string> = {
  IN_PERSON: "gabinet",
  ONLINE: "online",
};

function safeJsonPrice(grosze: number): string {
  if (!Number.isSafeInteger(grosze) || grosze < 0) {
    throw new RangeError("Cena w JSON-LD musi być całkowitą liczbą groszy.");
  }
  return `${Math.floor(grosze / 100)}.${String(grosze % 100).padStart(2, "0")}`;
}

function buildVoucherJsonLd(product: CatalogProductDetail) {
  const description =
    product.description ??
    product.short_description ??
    product.meta_description;
  const image = product.images
    .map(({ url }) => safePublicImageUrl(url))
    .filter((url): url is string => url !== undefined);
  const variants = product.voucher?.variants ?? [];
  return {
    "@context": "https://schema.org",
    "@type": "ProductGroup",
    productGroupID: product.id,
    name: product.name,
    description,
    image,
    url: publicUrl(voucherProductPath(product.slug)),
    hasVariant: variants.map((variant) => ({
      "@type": "Product",
      identifier: variant.id,
      name: `${product.name} — ${variant.kind === "IN_PERSON" ? "w gabinecie" : "online"}`,
      image,
      offers: {
        "@type": "Offer",
        price: safeJsonPrice(variant.price),
        priceCurrency: "PLN",
        availability: product.is_available
          ? "https://schema.org/InStock"
          : "https://schema.org/OutOfStock",
        url: publicUrl(
          voucherProductPath(product.slug, variantKeys[variant.kind]),
        ),
      },
    })),
  };
}

function buildProductJsonLd(
  product: CatalogProductDetail,
  availability: "InStock" | "OutOfStock",
) {
  const image = product.images
    .map(({ url }) => safePublicImageUrl(url))
    .filter((url): url is string => url !== undefined);
  const description =
    product.description ??
    product.short_description ??
    product.meta_description;
  return {
    "@context": "https://schema.org",
    "@type": "Product",
    name: product.name,
    description,
    image,
    url: publicUrl(voucherProductPath(product.slug)),
    offers: {
      "@type": "Offer",
      price: safeJsonPrice(product.price),
      priceCurrency: "PLN",
      availability: `https://schema.org/${availability}`,
      url: publicUrl(voucherProductPath(product.slug)),
    },
  };
}

function preserveOtherParams(
  searchParams: Record<string, string | string[] | undefined>,
): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(searchParams)) {
    if (key === "variant" || value === undefined) continue;
    for (const item of Array.isArray(value) ? value : [value]) {
      params.append(key, item);
    }
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

async function readProduct(slug: string): Promise<CatalogProductDetail> {
  try {
    return await getCatalogProductDetail(slug);
  } catch (error: unknown) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }
}

export async function generateMetadata({
  params,
}: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const product = await readProduct(slug);
  if (!isSupportedProductKind(product))
    redirect(`/produkt/${encodeURIComponent(slug)}`);
  const canonical = publicUrl(voucherProductPath(product.slug));
  const image = product.images[0]
    ? safePublicImageUrl(product.images[0].url)
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
}

function isSupportedProductKind(product: CatalogProductDetail): boolean {
  return ["VOUCHER", "DIGITAL", "BOOK", "AUDIOBOOK"].includes(product.kind);
}

export default async function VoucherPage({ params, searchParams }: PageProps) {
  const [{ slug }, query] = await Promise.all([params, searchParams]);
  const product = await readProduct(slug);
  if (!isSupportedProductKind(product))
    redirect(`/produkt/${encodeURIComponent(slug)}`);

  if (
    product.kind === "DIGITAL" ||
    product.kind === "BOOK" ||
    product.kind === "AUDIOBOOK"
  ) {
    const available =
      product.kind === "BOOK"
        ? (product.book?.available_quantity ?? 0) > 0 && product.is_available
        : product.is_available;
    const structuredData = buildProductJsonLd(
      product,
      available ? "InStock" : "OutOfStock",
    );
    const view =
      product.kind === "DIGITAL" ? (
        <DigitalProductView product={product} />
      ) : product.kind === "BOOK" ? (
        <BookProductView product={product} />
      ) : (
        <AudiobookProductView product={product} />
      );
    return (
      <>
        {view}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: serializeJsonLd(structuredData) }}
        />
      </>
    );
  }

  const variants = product.voucher?.variants ?? [];
  const requestedVariant = query.variant;
  const validVariant =
    typeof requestedVariant === "string" &&
    variants.some((variant) => variantKeys[variant.kind] === requestedVariant);
  if (requestedVariant !== undefined && !validVariant) {
    redirect(
      `${voucherProductPath(product.slug)}${preserveOtherParams(query)}`,
    );
  }
  const initialVariantKey = validVariant
    ? (requestedVariant as string)
    : variants[0]
      ? variantKeys[variants[0].kind]
      : "";
  const structuredData = buildVoucherJsonLd(product);
  const safeImages = product.images
    .map((image) => ({ ...image, url: safePublicImageUrl(image.url) }))
    .filter((image): image is typeof image & { url: string } =>
      Boolean(image.url),
    );
  const safeProduct = { ...product, images: safeImages };

  return (
    <>
      <VoucherProductView
        product={safeProduct}
        initialVariantKey={initialVariantKey}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: serializeJsonLd(structuredData) }}
      />
    </>
  );
}

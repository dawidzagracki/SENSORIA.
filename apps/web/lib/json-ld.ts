import "server-only";
import type { PublicProduct } from "@/types/catalog";
import { serializeJsonLd } from "@/lib/serialize-json-ld";
import {
  categoryPath,
  productPath,
  publicUrl,
  safePublicImageUrl,
} from "@/lib/catalog-urls";

export { serializeJsonLd };

function schemaPrice(grosze: number): string {
  if (!Number.isSafeInteger(grosze) || grosze < 0) {
    throw new RangeError(
      "Cena Schema.org musi być bezpieczną liczbą całkowitych groszy.",
    );
  }
  return `${Math.floor(grosze / 100)}.${String(grosze % 100).padStart(2, "0")}`;
}

const vatLabels = {
  RATE_23: "23%",
  RATE_8: "8%",
  RATE_5: "5%",
  RATE_0: "0%",
  EXEMPT: "zw. z VAT",
} as const;

export function productJsonLd(product: PublicProduct) {
  const selectedCategory = [...product.categories].sort((left, right) =>
    left.slug.localeCompare(right.slug, "pl"),
  )[0];
  const offers = product.offers.map((offer) => ({
    "@type": "Offer",
    price: schemaPrice(offer.price),
    priceCurrency: "PLN",
    availability: product.is_available
      ? "https://schema.org/InStock"
      : "https://schema.org/OutOfStock",
    url: publicUrl(productPath(product.slug)),
  }));
  const data: Record<string, unknown> = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: product.name,
    description: product.meta_description,
    image: product.images
      .map((image) => safePublicImageUrl(image.url))
      .filter((image): image is string => image !== undefined),
    url: publicUrl(productPath(product.slug)),
    offers,
  };
  if (product.vat_rate) {
    data.additionalProperty = {
      "@type": "PropertyValue",
      name: "Stawka VAT",
      value: vatLabels[product.vat_rate],
    };
  }
  if (selectedCategory) data.category = selectedCategory.name;
  return data;
}

export function productBreadcrumbJsonLd(product: PublicProduct) {
  const selected = [...product.categories].sort((left, right) =>
    left.slug.localeCompare(right.slug, "pl"),
  )[0];
  const list = [
    { name: "Strona główna", item: publicUrl("/") },
    ...(selected?.parent_name && selected.parent_slug
      ? [
          {
            name: selected.parent_name,
            item: publicUrl(categoryPath(selected.parent_slug)),
          },
          { name: selected.name, item: publicUrl(categoryPath(selected.slug)) },
        ]
      : selected
        ? [
            {
              name: selected.name,
              item: publicUrl(categoryPath(selected.slug)),
            },
          ]
        : []),
    { name: product.name, item: publicUrl(productPath(product.slug)) },
  ];
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: list.map((item, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: item.name,
      item: item.item,
    })),
  };
}

export function categoryBreadcrumbJsonLd(
  name: string,
  slug: string,
  parentName?: string | null,
  parentSlug?: string | null,
) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      {
        "@type": "ListItem",
        position: 1,
        name: "Strona główna",
        item: publicUrl("/"),
      },
      ...(parentName && parentSlug
        ? [
            {
              "@type": "ListItem",
              position: 2,
              name: parentName,
              item: publicUrl(categoryPath(parentSlug)),
            },
            {
              "@type": "ListItem",
              position: 3,
              name,
              item: publicUrl(categoryPath(slug)),
            },
          ]
        : [
            {
              "@type": "ListItem",
              position: 2,
              name,
              item: publicUrl(categoryPath(slug)),
            },
          ]),
    ],
  };
}

export function organizationJsonLd() {
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    "@id": publicUrl("/#organization"),
    name: "Sensoria Terapia — Anna Parakiewicz",
    url: publicUrl("/"),
  };
}

export function websiteJsonLd() {
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "@id": publicUrl("/#website"),
    url: publicUrl("/"),
    name: "Sensoria Terapia — Anna Parakiewicz",
    publisher: { "@id": publicUrl("/#organization") },
    inLanguage: "pl-PL",
  };
}

export function productSchemaPriceForTest(grosze: number): string {
  return schemaPrice(grosze);
}

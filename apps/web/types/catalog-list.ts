import { ApiError } from "@/lib/api";
import type { DigitalLabel, ProductKind, PublicImage } from "@/types/catalog";

export type CatalogFacetOption = {
  value: string;
  label: string;
  count: number;
};
export type CatalogListItem = {
  id: string;
  slug: string;
  name: string;
  kind: ProductKind;
  digital_label: DigitalLabel | null;
  short_description: string | null;
  price: number;
  compare_at_price: number | null;
  lowest_price_before_discount?: number | null;
  discount_started_at?: string | null;
  image: PublicImage | null;
  book: {
    weight_grams: number | null;
    length_mm: number | null;
    width_mm: number | null;
    height_mm: number | null;
    isbn: string | null;
  } | null;
  audiobook: {
    duration_seconds: number | null;
    narrator: string | null;
    chapters: Array<{
      title: string;
      length_seconds: number;
      position: number;
    }>;
  } | null;
  digital: {
    page_count: number | null;
    file_format: string;
    edition: string | null;
    label: DigitalLabel;
    lowest_price_before_discount?: number | null;
    discount_started_at?: string | null;
  } | null;
  voucher: {
    validity_months: number;
    service_name: string;
    variants: Array<{ kind: string; price: number }>;
  } | null;
};
export type CatalogListResponse = {
  items: CatalogListItem[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
  facets: {
    categories: CatalogFacetOption[];
    kinds: CatalogFacetOption[];
    audiences: CatalogFacetOption[];
    deliveries: CatalogFacetOption[];
    prices: CatalogFacetOption[];
  };
  suggestions: {
    popular_queries: string[];
    related_products: CatalogListItem[];
  } | null;
};

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function safeInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value);
}
function safeMoney(value: unknown): value is number {
  return safeInteger(value) && value >= 0;
}
function nullableInteger(value: unknown): boolean {
  return value === null || safeInteger(value);
}
function nullableString(value: unknown): boolean {
  return value === null || typeof value === "string";
}
function isDigitalLabel(value: unknown): value is DigitalLabel {
  return value === "COURSE_PDF" || value === "EBOOK_PDF";
}
function isKind(value: unknown): value is ProductKind {
  return (
    value === "VOUCHER" ||
    value === "BOOK" ||
    value === "AUDIOBOOK" ||
    value === "DIGITAL"
  );
}

function validBook(value: unknown): boolean {
  return (
    value === null ||
    (record(value) &&
      nullableInteger(value.weight_grams) &&
      nullableInteger(value.length_mm) &&
      nullableInteger(value.width_mm) &&
      nullableInteger(value.height_mm) &&
      nullableString(value.isbn))
  );
}
function validAudiobook(value: unknown): boolean {
  return (
    value === null ||
    (record(value) &&
      nullableInteger(value.duration_seconds) &&
      nullableString(value.narrator) &&
      Array.isArray(value.chapters) &&
      value.chapters.every(
        (chapter) =>
          record(chapter) &&
          typeof chapter.title === "string" &&
          safeInteger(chapter.length_seconds) &&
          chapter.length_seconds >= 0 &&
          safeInteger(chapter.position) &&
          chapter.position >= 0,
      ))
  );
}
function validDigital(value: unknown): boolean {
  return (
    value === null ||
    (record(value) &&
      nullableInteger(value.page_count) &&
      typeof value.file_format === "string" &&
      nullableString(value.edition) &&
      (value.lowest_price_before_discount === undefined ||
        nullableInteger(value.lowest_price_before_discount)) &&
      (value.discount_started_at === undefined ||
        nullableString(value.discount_started_at)) &&
      isDigitalLabel(value.label))
  );
}
function validVoucher(value: unknown): boolean {
  return (
    value === null ||
    (record(value) &&
      safeInteger(value.validity_months) &&
      value.validity_months > 0 &&
      typeof value.service_name === "string" &&
      Array.isArray(value.variants) &&
      value.variants.every(
        (variant) =>
          record(variant) &&
          typeof variant.kind === "string" &&
          safeMoney(variant.price),
      ))
  );
}
function validKindDetails(value: Record<string, unknown>): boolean {
  if (value.kind === "BOOK")
    return (
      record(value.book) &&
      value.audiobook === null &&
      value.digital === null &&
      value.voucher === null &&
      value.digital_label === null
    );
  if (value.kind === "AUDIOBOOK")
    return (
      record(value.audiobook) &&
      value.book === null &&
      value.digital === null &&
      value.voucher === null &&
      value.digital_label === null
    );
  if (value.kind === "VOUCHER")
    return (
      record(value.voucher) &&
      value.book === null &&
      value.audiobook === null &&
      value.digital === null &&
      value.digital_label === null
    );
  return (
    record(value.digital) &&
    value.digital_label === value.digital.label &&
    value.book === null &&
    value.audiobook === null &&
    value.voucher === null
  );
}

function parseItem(value: unknown): CatalogListItem {
  if (
    !record(value) ||
    typeof value.id !== "string" ||
    typeof value.slug !== "string" ||
    typeof value.name !== "string" ||
    !isKind(value.kind) ||
    !(value.digital_label === null || isDigitalLabel(value.digital_label)) ||
    !nullableString(value.short_description) ||
    !safeMoney(value.price) ||
    !(value.compare_at_price === null || safeMoney(value.compare_at_price)) ||
    !(
      value.image === null ||
      (record(value.image) &&
        typeof value.image.url === "string" &&
        typeof value.image.alt === "string")
    ) ||
    !validBook(value.book) ||
    !validAudiobook(value.audiobook) ||
    !validDigital(value.digital) ||
    !validVoucher(value.voucher) ||
    !validKindDetails(value)
  ) {
    throw new ApiError(
      "INVALID_RESPONSE",
      "Serwer zwrócił nieprawidłowe dane katalogu.",
    );
  }
  return value as unknown as CatalogListItem;
}
function parseFacet(value: unknown): CatalogFacetOption[] {
  if (
    !Array.isArray(value) ||
    !value.every(
      (item) =>
        record(item) &&
        typeof item.value === "string" &&
        typeof item.label === "string" &&
        safeInteger(item.count) &&
        item.count >= 0,
    )
  ) {
    throw new ApiError(
      "INVALID_RESPONSE",
      "Serwer zwrócił nieprawidłowe liczniki filtrów.",
    );
  }
  return value as CatalogFacetOption[];
}
function parseSuggestions(value: unknown): CatalogListResponse["suggestions"] {
  if (value === null || value === undefined) return null;
  if (
    !record(value) ||
    !Array.isArray(value.popular_queries) ||
    !value.popular_queries.every((query) => typeof query === "string") ||
    !Array.isArray(value.related_products)
  ) {
    throw new ApiError(
      "INVALID_RESPONSE",
      "Serwer zwrócił nieprawidłowe podpowiedzi katalogu.",
    );
  }
  return {
    popular_queries: value.popular_queries,
    related_products: value.related_products.map(parseItem),
  };
}
export function parseCatalogList(value: unknown): CatalogListResponse {
  if (
    !record(value) ||
    !Array.isArray(value.items) ||
    !record(value.facets) ||
    !["total", "page", "per_page", "total_pages"].every(
      (key) => safeInteger(value[key]) && (value[key] as number) >= 0,
    )
  ) {
    throw new ApiError(
      "INVALID_RESPONSE",
      "Serwer zwrócił nieprawidłową listę katalogu.",
    );
  }
  if (
    (value.page as number) < 1 ||
    (value.per_page as number) < 1 ||
    (value.per_page as number) > 48
  ) {
    throw new ApiError(
      "INVALID_RESPONSE",
      "Serwer zwrócił nieprawidłowe parametry stronicowania.",
    );
  }
  const facets = value.facets;
  return {
    items: value.items.map(parseItem),
    total: value.total as number,
    page: value.page as number,
    per_page: value.per_page as number,
    total_pages: value.total_pages as number,
    facets: {
      categories: parseFacet(facets.categories),
      kinds: parseFacet(facets.kinds),
      audiences: parseFacet(facets.audiences),
      deliveries: parseFacet(facets.deliveries),
      prices: parseFacet(facets.prices),
    },
    suggestions: parseSuggestions(value.suggestions),
  };
}

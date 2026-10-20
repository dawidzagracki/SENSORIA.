import { ApiError } from "@/lib/api";

export type VatRate = "RATE_23" | "RATE_8" | "RATE_5" | "RATE_0" | "EXEMPT";
export type ProductKind = "VOUCHER" | "BOOK" | "AUDIOBOOK" | "DIGITAL";
export type DigitalLabel = "COURSE_PDF" | "EBOOK_PDF";

export type PublicImage = { url: string; alt: string };
export type PublicOffer = { name: string | null; price: number };
export type PublicCategoryRef = {
  name: string;
  slug: string;
  parent_name: string | null;
  parent_slug: string | null;
};

export type PublicProduct = {
  id: string;
  kind: ProductKind;
  digital_label: DigitalLabel | null;
  name: string;
  slug: string;
  short_description: string | null;
  description: string | null;
  price: number | null;
  compare_at_price: number | null;
  vat_rate: VatRate | null;
  is_available: boolean;
  images: PublicImage[];
  offers: PublicOffer[];
  categories: PublicCategoryRef[];
  audience_tags: string[];
  meta_title: string;
  meta_description: string;
  og_image: string | null;
  created_at: string;
  updated_at: string;
  published_at: string;
};

export type VoucherVariantKind = "IN_PERSON" | "ONLINE";
export type CatalogVoucherVariant = {
  id: string;
  kind: VoucherVariantKind;
  price: number;
};
export type CatalogVoucherDetails = {
  validity_months: number;
  service_name: string;
  variants: CatalogVoucherVariant[];
};
export type CatalogDigitalDetails = {
  page_count: number | null;
  file_format: string;
  edition: string | null;
  label: DigitalLabel;
  lowest_price_before_discount: number | null;
  discount_started_at: string | null;
  sample_available: boolean;
  sample_pages: number | null;
};
export type CatalogBookDetails = {
  stock_quantity: number;
  available_quantity: number;
  weight_grams: number | null;
  length_mm: number | null;
  width_mm: number | null;
  height_mm: number | null;
  isbn: string | null;
  binding: string | null;
  shipping_business_days: number | null;
  shipping_method: string | null;
};
export type CatalogAudiobookChapter = {
  title: string;
  length_seconds: number;
  position: number;
};
export type CatalogAudiobookDetails = {
  duration_seconds: number | null;
  narrator: string | null;
  file_format: string | null;
  chapters: CatalogAudiobookChapter[];
  sample_available: boolean;
  sample_duration_seconds: number | null;
};
export type CatalogRelatedProduct = {
  id: string;
  slug: string;
  name: string;
  kind: ProductKind;
  digital_label: DigitalLabel | null;
  short_description: string | null;
  price: number;
  compare_at_price: number | null;
  image: PublicImage | null;
  digital: Pick<
    CatalogDigitalDetails,
    "page_count" | "file_format" | "label"
  > | null;
};
export type CatalogProductDetail = {
  id: string;
  slug: string;
  name: string;
  kind: ProductKind;
  digital_label: DigitalLabel | null;
  vat_rate: VatRate | null;
  is_available: boolean;
  short_description: string | null;
  description: string | null;
  price: number;
  compare_at_price: number | null;
  image: PublicImage | null;
  images: PublicImage[];
  categories: PublicCategoryRef[];
  audience_tags: string[];
  digital: CatalogDigitalDetails | null;
  book: CatalogBookDetails | null;
  audiobook: CatalogAudiobookDetails | null;
  meta_title: string;
  meta_description: string;
  voucher: CatalogVoucherDetails | null;
  related_products: CatalogRelatedProduct[];
  published_at: string;
};

export type PublicCategory = {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  parent_slug: string | null;
  parent_name: string | null;
  position: number;
  published_product_count: number;
  meta_title: string;
  meta_description: string;
  og_image: string | null;
  created_at: string;
  updated_at: string;
};

export type PublicCategoryPage = PublicCategory & { products: PublicProduct[] };
export type PublicSitemap = {
  entries: Array<{
    kind: "product" | "category";
    slug: string;
    last_modified: string;
  }>;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isSafeMoney(value: unknown): value is number | null {
  return (
    value === null || (typeof value === "number" && Number.isSafeInteger(value))
  );
}

export function parsePublicProduct(value: unknown): PublicProduct {
  if (
    !isRecord(value) ||
    typeof value.id !== "string" ||
    typeof value.name !== "string" ||
    typeof value.slug !== "string" ||
    typeof value.meta_title !== "string" ||
    typeof value.meta_description !== "string" ||
    typeof value.is_available !== "boolean" ||
    !isSafeMoney(value.price) ||
    !isSafeMoney(value.compare_at_price) ||
    !Array.isArray(value.images) ||
    !Array.isArray(value.offers) ||
    !Array.isArray(value.categories) ||
    !Array.isArray(value.audience_tags)
  ) {
    throw new ApiError(
      "INVALID_RESPONSE",
      "Serwer zwrócił nieprawidłowe dane produktu.",
    );
  }
  for (const offer of value.offers) {
    if (
      !isRecord(offer) ||
      typeof offer.price !== "number" ||
      !Number.isSafeInteger(offer.price)
    ) {
      throw new ApiError(
        "INVALID_RESPONSE",
        "Serwer zwrócił nieprawidłową cenę produktu.",
      );
    }
  }
  return value as unknown as PublicProduct;
}

export function parseCatalogProductDetail(
  value: unknown,
): CatalogProductDetail {
  const validMoney = (amount: unknown): amount is number | null =>
    amount === null ||
    (typeof amount === "number" && Number.isSafeInteger(amount) && amount >= 0);
  const validKinds = ["VOUCHER", "BOOK", "AUDIOBOOK", "DIGITAL"];
  const validVat = ["RATE_23", "RATE_8", "RATE_5", "RATE_0", "EXEMPT"];
  if (
    !isRecord(value) ||
    typeof value.id !== "string" ||
    typeof value.slug !== "string" ||
    typeof value.name !== "string" ||
    !validKinds.includes(String(value.kind)) ||
    !(value.vat_rate === null || validVat.includes(String(value.vat_rate))) ||
    typeof value.is_available !== "boolean" ||
    !validMoney(value.price) ||
    !validMoney(value.compare_at_price) ||
    !(
      value.short_description === null ||
      typeof value.short_description === "string"
    ) ||
    !(value.description === null || typeof value.description === "string") ||
    typeof value.meta_title !== "string" ||
    typeof value.meta_description !== "string" ||
    !Array.isArray(value.images) ||
    !Array.isArray(value.categories) ||
    !Array.isArray(value.audience_tags) ||
    !Array.isArray(value.related_products) ||
    (value.kind === "BOOK" && value.book === null) ||
    (value.kind === "AUDIOBOOK" && value.audiobook === null) ||
    typeof value.published_at !== "string"
  ) {
    throw new ApiError(
      "INVALID_RESPONSE",
      "Serwer zwrócił nieprawidłowe dane produktu.",
    );
  }
  if (value.voucher !== null) {
    if (
      !isRecord(value.voucher) ||
      !Number.isSafeInteger(value.voucher.validity_months) ||
      Number(value.voucher.validity_months) < 1 ||
      typeof value.voucher.service_name !== "string" ||
      !Array.isArray(value.voucher.variants) ||
      value.voucher.variants.some(
        (variant) =>
          !isRecord(variant) ||
          typeof variant.id !== "string" ||
          (variant.kind !== "IN_PERSON" && variant.kind !== "ONLINE") ||
          !validMoney(variant.price) ||
          variant.price === null,
      )
    ) {
      throw new ApiError(
        "INVALID_RESPONSE",
        "Serwer zwrócił nieprawidłowe warianty produktu.",
      );
    }
  }
  if (value.book !== null) {
    const book = value.book;
    if (
      !isRecord(book) ||
      !Number.isSafeInteger(book.stock_quantity) ||
      Number(book.stock_quantity) < 0 ||
      !Number.isSafeInteger(book.available_quantity) ||
      Number(book.available_quantity) < 0 ||
      Number(book.available_quantity) > Number(book.stock_quantity) ||
      !nullableSafeInteger(book.weight_grams) ||
      !nullableSafeInteger(book.length_mm) ||
      !nullableSafeInteger(book.width_mm) ||
      !nullableSafeInteger(book.height_mm) ||
      !nullableString(book.isbn) ||
      !nullableString(book.binding) ||
      !nullableSafeInteger(book.shipping_business_days) ||
      !nullableString(book.shipping_method)
    ) {
      throw new ApiError(
        "INVALID_RESPONSE",
        "Serwer zwrócił nieprawidłowe dane książki.",
      );
    }
  }
  if (value.audiobook !== null) {
    const audiobook = value.audiobook;
    if (
      !isRecord(audiobook) ||
      !nullableSafeInteger(audiobook.duration_seconds) ||
      !nullableString(audiobook.narrator) ||
      !nullableString(audiobook.file_format) ||
      typeof audiobook.sample_available !== "boolean" ||
      !nullableSafeInteger(audiobook.sample_duration_seconds) ||
      (audiobook.sample_duration_seconds !== null &&
        Number(audiobook.sample_duration_seconds) <= 0) ||
      (audiobook.sample_available &&
        audiobook.sample_duration_seconds === null) ||
      !Array.isArray(audiobook.chapters) ||
      audiobook.chapters.some(
        (chapter) =>
          !isRecord(chapter) ||
          typeof chapter.title !== "string" ||
          !Number.isSafeInteger(chapter.length_seconds) ||
          Number(chapter.length_seconds) <= 0 ||
          !Number.isSafeInteger(chapter.position) ||
          Number(chapter.position) < 0,
      )
    ) {
      throw new ApiError(
        "INVALID_RESPONSE",
        "Serwer zwrócił nieprawidłowe dane audiobooka.",
      );
    }
  }
  if (value.digital !== null) {
    if (
      !isRecord(value.digital) ||
      !validMoney(value.digital.page_count) ||
      typeof value.digital.file_format !== "string" ||
      !(
        value.digital.edition === null ||
        typeof value.digital.edition === "string"
      ) ||
      (value.digital.label !== "COURSE_PDF" &&
        value.digital.label !== "EBOOK_PDF") ||
      !validMoney(value.digital.lowest_price_before_discount) ||
      typeof value.digital.sample_available !== "boolean" ||
      !nullableSafeInteger(value.digital.sample_pages) ||
      (value.digital.sample_pages !== null &&
        Number(value.digital.sample_pages) <= 0) ||
      (value.digital.sample_available && value.digital.sample_pages === null) ||
      !(
        value.digital.discount_started_at === null ||
        typeof value.digital.discount_started_at === "string"
      )
    ) {
      throw new ApiError(
        "INVALID_RESPONSE",
        "Serwer zwrócił nieprawidłowe dane produktu cyfrowego.",
      );
    }
  }
  return value as unknown as CatalogProductDetail;
}

function nullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function nullableSafeInteger(value: unknown): value is number | null {
  return (
    value === null || (typeof value === "number" && Number.isSafeInteger(value))
  );
}

export function parsePublicCategory(value: unknown): PublicCategoryPage {
  if (
    !isRecord(value) ||
    typeof value.id !== "string" ||
    typeof value.name !== "string" ||
    typeof value.slug !== "string" ||
    typeof value.meta_title !== "string" ||
    typeof value.meta_description !== "string" ||
    typeof value.published_product_count !== "number" ||
    !Array.isArray(value.products)
  ) {
    throw new ApiError(
      "INVALID_RESPONSE",
      "Serwer zwrócił nieprawidłowe dane kategorii.",
    );
  }
  return {
    ...(value as unknown as PublicCategory),
    products: value.products.map(parsePublicProduct),
  };
}

export function parsePublicSitemap(value: unknown): PublicSitemap {
  if (!isRecord(value) || !Array.isArray(value.entries)) {
    throw new ApiError(
      "INVALID_RESPONSE",
      "Serwer zwrócił nieprawidłową mapę witryny.",
    );
  }
  const entries: PublicSitemap["entries"] = value.entries.map((entry) => {
    if (
      !isRecord(entry) ||
      (entry.kind !== "product" && entry.kind !== "category") ||
      typeof entry.slug !== "string" ||
      typeof entry.last_modified !== "string"
    ) {
      throw new ApiError(
        "INVALID_RESPONSE",
        "Serwer zwrócił nieprawidłowy wpis mapy witryny.",
      );
    }
    const kind: "product" | "category" =
      entry.kind === "product" ? "product" : "category";
    return {
      kind,
      slug: entry.slug,
      last_modified: entry.last_modified,
    };
  });
  return { entries };
}

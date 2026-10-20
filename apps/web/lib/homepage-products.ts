import type { CatalogListItem } from "@/types/catalog-list";
import type { HomepageContent } from "@/types/homepage";

export type HomepageFeaturedProducts = {
  voucher: CatalogListItem | null;
  audiobook: CatalogListItem | null;
  course: CatalogListItem | null;
};

function choose(
  products: CatalogListItem[],
  preferredId: string | null,
  isExpected: (product: CatalogListItem) => boolean,
): CatalogListItem | null {
  const eligible = products.filter(isExpected);
  return (
    eligible.find((product) => product.id === preferredId) ??
    eligible[0] ??
    null
  );
}

export function selectHomepageFeaturedProducts(
  voucherProducts: CatalogListItem[],
  audiobookProducts: CatalogListItem[],
  digitalProducts: CatalogListItem[],
  settings: HomepageContent,
): HomepageFeaturedProducts {
  return {
    voucher: choose(
      voucherProducts,
      settings.product_selection.voucher_id,
      (product) => product.kind === "VOUCHER",
    ),
    audiobook: choose(
      audiobookProducts,
      settings.product_selection.audiobook_id,
      (product) => product.kind === "AUDIOBOOK",
    ),
    course: choose(
      digitalProducts,
      settings.product_selection.course_id,
      (product) =>
        product.kind === "DIGITAL" && product.digital_label === "COURSE_PDF",
    ),
  };
}

export function productTypeLabel(
  product: CatalogListItem,
): "VOUCHER" | "KSIĄŻKA" | "AUDIOBOOK" | "KURS PDF" | "E-BOOK PDF" {
  if (product.kind === "VOUCHER") return "VOUCHER";
  if (product.kind === "BOOK") return "KSIĄŻKA";
  if (product.kind === "AUDIOBOOK") return "AUDIOBOOK";
  return product.digital_label === "COURSE_PDF" ? "KURS PDF" : "E-BOOK PDF";
}

export function productMetric(product: CatalogListItem): string {
  if (product.voucher) {
    const months = product.voucher.validity_months;
    const monthLabel = months === 1 ? "miesiąc" : "miesięcy";
    return `Ważny ${months} ${monthLabel}`;
  }
  if (product.audiobook?.duration_seconds) {
    const minutes = Math.floor(product.audiobook.duration_seconds / 60);
    const hours = Math.floor(minutes / 60);
    const rest = minutes % 60;
    return hours ? `${hours} godz. ${rest} min` : `${minutes} min`;
  }
  if (product.digital?.page_count) {
    return `${product.digital.file_format.toUpperCase()} · ${product.digital.page_count} stron`;
  }
  if (product.book?.isbn) return `ISBN ${product.book.isbn}`;
  return product.short_description ?? "Materiał Sensoria";
}

import { describe, expect, it } from "vitest";
import { selectHomepageFeaturedProducts } from "./homepage-products";
import type { CatalogListItem } from "../types/catalog-list";
import type { HomepageContent } from "../types/homepage";

const settings = {
  product_selection: {
    voucher_id: "voucher",
    audiobook_id: null,
    course_id: "ebook",
  },
} as HomepageContent;

function item(
  id: string,
  kind: CatalogListItem["kind"],
  digitalLabel: CatalogListItem["digital_label"] = null,
): CatalogListItem {
  return {
    id,
    slug: id,
    name: id,
    kind,
    digital_label: digitalLabel,
    short_description: null,
    price: 1000,
    compare_at_price: null,
    image: null,
    book: null,
    audiobook: null,
    digital: digitalLabel
      ? {
          page_count: 8,
          file_format: "PDF",
          edition: null,
          label: digitalLabel,
        }
      : null,
    voucher: null,
  };
}

describe("homepage featured product selection", () => {
  it("uses valid editorial IDs and deterministic type fallbacks", () => {
    const result = selectHomepageFeaturedProducts(
      [item("voucher", "VOUCHER")],
      [item("audio", "AUDIOBOOK")],
      [
        item("ebook", "DIGITAL", "EBOOK_PDF"),
        item("course", "DIGITAL", "COURSE_PDF"),
      ],
      settings,
    );
    expect(result.voucher?.id).toBe("voucher");
    expect(result.audiobook?.id).toBe("audio");
    expect(result.course?.id).toBe("course");
  });

  it("falls back when a selected product is no longer published or no longer matches its slot", () => {
    const result = selectHomepageFeaturedProducts(
      [item("replacement", "VOUCHER")],
      [],
      [item("ebook", "DIGITAL", "EBOOK_PDF")],
      settings,
    );
    expect(result.voucher?.id).toBe("replacement");
    expect(result.audiobook).toBeNull();
    expect(result.course).toBeNull();
  });
});

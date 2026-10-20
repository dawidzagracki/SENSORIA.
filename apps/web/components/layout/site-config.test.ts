import { describe, expect, it } from "vitest";
import { normalizeCatalogParams } from "@/lib/catalog-query";
import { productCategoryLinks } from "./site-config";

describe("product category navigation", () => {
  it("uses catalog filters understood by the store route", () => {
    expect(
      productCategoryLinks.map(({ href }) => {
        const url = new URL(href, "http://localhost");
        const params = normalizeCatalogParams(
          Object.fromEntries(url.searchParams.entries()),
        );
        return Object.fromEntries(params.entries());
      }),
    ).toEqual([
      { kind: "VOUCHER" },
      { kind: "BOOK" },
      { kind: "AUDIOBOOK" },
      { category: "kursy-pdf" },
    ]);
  });
});

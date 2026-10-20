import { describe, expect, it } from "vitest";
import {
  apiCatalogUrl,
  catalogPriceBands,
  countActiveCatalogFilters,
  normalizeCatalogParams,
  updateCatalogParams,
} from "./catalog-query";

describe("catalog query state", () => {
  it("normalizes defaults while retaining every supported URL parameter", () => {
    expect(
      normalizeCatalogParams({
        page: "1",
        per_page: "12",
        sort: "recommended",
        q: "  terapia  ",
        category: "kursy-pdf",
      }).toString(),
    ).toBe("category=kursy-pdf&q=terapia");
  });

  it("preserves other filters and resets pagination when filters or sorting change", () => {
    const current = new URLSearchParams(
      "category=vouchery&page=3&q=terapia&sort=price_asc",
    );
    expect(updateCatalogParams(current, { audience: "rodzice" })).toBe(
      "/sklep?category=vouchery\u0026q=terapia\u0026sort=price_asc\u0026audience=rodzice",
    );
    expect(updateCatalogParams(current, { page: "2" })).toContain("page=2");
  });

  it("clears catalog filters but keeps search, sort, and page size", () => {
    const current = new URLSearchParams(
      "category=x&kind=BOOK&price_max=5000&q=terapia&sort=newest&per_page=24&page=3",
    );
    expect(updateCatalogParams(current, {}, true)).toBe(
      "/sklep?q=terapia\u0026sort=newest\u0026per_page=24",
    );
  });

  it("uses API page defaults and only counts non-default filters", () => {
    expect(apiCatalogUrl(new URLSearchParams("q=terapia"))).toBe(
      "/products?q=terapia\u0026page=1\u0026per_page=12",
    );
    expect(
      countActiveCatalogFilters(
        new URLSearchParams(
          "category=x&price_min=0&q=terapia&page=2&sort=newest",
        ),
      ),
    ).toBe(2);
  });

  it("maps makieta price labels to disjoint gross-grosz ranges", () => {
    expect(catalogPriceBands.map(({ min, max }) => [min, max])).toEqual([
      ["0", "5000"],
      ["5001", "15000"],
      ["15001", null],
    ]);
  });
});

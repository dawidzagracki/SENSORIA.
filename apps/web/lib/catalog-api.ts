import "server-only";
import { cache } from "react";
import { ApiError, requestJson } from "@/lib/api";
import { getServerApiUrl } from "@/lib/server-api-url";
import {
  parsePublicCategory,
  parseCatalogProductDetail,
  parsePublicProduct,
  parsePublicSitemap,
  type PublicCategoryPage,
  type CatalogProductDetail,
  type PublicProduct,
  type PublicSitemap,
} from "@/types/catalog";

async function readCatalog(path: string): Promise<unknown> {
  const apiUrl = getServerApiUrl();
  if (!apiUrl) {
    throw new ApiError(
      "API_NOT_CONFIGURED",
      "Serwer API nie jest skonfigurowany.",
    );
  }
  return requestJson(apiUrl, path, { cache: "no-store" });
}

export const getPublicProduct = cache(
  async (slug: string): Promise<PublicProduct> =>
    parsePublicProduct(
      await readCatalog(`/catalog/public/products/${encodeURIComponent(slug)}`),
    ),
);

export const getCatalogProductDetail = cache(
  async (slug: string): Promise<CatalogProductDetail> =>
    parseCatalogProductDetail(
      await readCatalog(`/products/${encodeURIComponent(slug)}`),
    ),
);

export const getPublicCategory = cache(
  async (slug: string): Promise<PublicCategoryPage> =>
    parsePublicCategory(
      await readCatalog(
        `/catalog/public/categories/${encodeURIComponent(slug)}`,
      ),
    ),
);

export async function getPublicSitemapData(): Promise<PublicSitemap> {
  return parsePublicSitemap(await readCatalog("/catalog/public/sitemap"));
}

import "server-only";
import { ApiError, requestJson } from "@/lib/api";
import { getServerApiUrl } from "@/lib/server-api-url";
import { apiCatalogUrl } from "@/lib/catalog-query";
import {
  parseCatalogList,
  type CatalogListResponse,
} from "@/types/catalog-list";

export async function getCatalogList(
  params: URLSearchParams,
  options: { recordSearch?: boolean } = {},
): Promise<CatalogListResponse> {
  const apiUrl = getServerApiUrl();
  if (!apiUrl)
    throw new ApiError(
      "API_NOT_CONFIGURED",
      "Serwer API nie jest skonfigurowany.",
    );
  const apiParams = new URLSearchParams(apiCatalogUrl(params).split("?")[1]);
  if (options.recordSearch === false) apiParams.set("record_search", "false");
  return parseCatalogList(
    await requestJson(apiUrl, `/products?${apiParams.toString()}`, {
      cache: "no-store",
    }),
  );
}

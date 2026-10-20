import "server-only";
import { ApiError, requestJson } from "@/lib/api";
import { getServerApiUrl } from "@/lib/server-api-url";
import {
  parseSearchPresentationSettings,
  type SearchPresentationSettings,
} from "@/types/search-presentation";

export async function getSearchPresentation(): Promise<SearchPresentationSettings> {
  const apiUrl = getServerApiUrl();
  if (!apiUrl) {
    throw new ApiError(
      "API_NOT_CONFIGURED",
      "Serwer API nie jest skonfigurowany.",
    );
  }
  return parseSearchPresentationSettings(
    await requestJson(apiUrl, "/catalog/public/search-presentation", {
      cache: "no-store",
    }),
  );
}

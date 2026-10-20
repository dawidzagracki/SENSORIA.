import "server-only";

import { ApiError, requestJson } from "@/lib/api";
import { getServerApiUrl } from "@/lib/server-api-url";
import type { HomepageContent } from "@/types/homepage";
import { parseHomepageContent } from "@/types/homepage";

export async function getHomepageContent(): Promise<HomepageContent> {
  const apiUrl = getServerApiUrl();
  if (!apiUrl) {
    throw new ApiError(
      "API_NOT_CONFIGURED",
      "Serwer API nie jest skonfigurowany.",
    );
  }
  return parseHomepageContent(
    await requestJson(apiUrl, "/catalog/public/homepage", {
      cache: "no-store",
    }),
  );
}

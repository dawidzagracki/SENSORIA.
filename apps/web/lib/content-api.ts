import "server-only";
import { requestJson } from "@/lib/api";
import { getServerApiUrl } from "@/lib/server-api-url";
import type { ContentBlock } from "@/components/library/library-types";

export type ContentPageData = {
  slug: string;
  title: string;
  summary: string | null;
  blocks: ContentBlock[];
  updated_at: string;
};

/** Returns null when the page is unpublished or the API is unavailable. */
export async function getContentPage(
  slug: string,
): Promise<ContentPageData | null> {
  const apiUrl = getServerApiUrl();
  if (!apiUrl) return null;
  try {
    const body = (await requestJson(
      apiUrl,
      `/pages/${encodeURIComponent(slug)}`,
      { cache: "no-store" },
    )) as ContentPageData;
    return Array.isArray(body.blocks) && typeof body.title === "string"
      ? body
      : null;
  } catch {
    return null;
  }
}

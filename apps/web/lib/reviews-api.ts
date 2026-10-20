import "server-only";
import { requestJson } from "@/lib/api";
import { getServerApiUrl } from "@/lib/server-api-url";
import type { PublicReviews } from "@/lib/reviews-shared";

export { aggregateRatingJsonLd } from "@/lib/reviews-shared";
export type { PublicReviews } from "@/lib/reviews-shared";

/** Reviews are optional page furniture: any failure simply hides the section. */
export async function getProductReviews(
  slug: string,
): Promise<PublicReviews | null> {
  const apiUrl = getServerApiUrl();
  if (!apiUrl) return null;
  try {
    const body = (await requestJson(
      apiUrl,
      `/reviews/products/${encodeURIComponent(slug)}?page_size=10`,
      { cache: "no-store" },
    )) as PublicReviews;
    if (
      !body ||
      typeof body.total !== "number" ||
      !Array.isArray(body.items) ||
      typeof body.summary !== "object" ||
      body.summary === null ||
      typeof body.summary.count !== "number" ||
      typeof body.summary.distribution !== "object"
    )
      return null;
    return body;
  } catch {
    return null;
  }
}

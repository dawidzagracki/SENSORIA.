import "server-only";
import { requestJson } from "@/lib/api";
import { getServerApiUrl } from "@/lib/server-api-url";

export type PublicReviews = {
  summary: {
    count: number;
    average: number | null;
    distribution: Record<string, number>;
  };
  total: number;
  items: Array<{
    id: string;
    author: string;
    rating: number;
    title: string | null;
    body: string;
    created_at: string;
    verified_purchase: boolean;
  }>;
};

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
    if (!body || typeof body.total !== "number" || !Array.isArray(body.items))
      return null;
    return body;
  } catch {
    return null;
  }
}

/** Only real, approved reviews may feed structured data. */
export function aggregateRatingJsonLd(reviews: PublicReviews | null) {
  if (!reviews || reviews.summary.count < 1 || reviews.summary.average === null)
    return null;
  return {
    "@type": "AggregateRating",
    ratingValue: reviews.summary.average.toFixed(1),
    reviewCount: reviews.summary.count,
    bestRating: "5",
    worstRating: "1",
  };
}

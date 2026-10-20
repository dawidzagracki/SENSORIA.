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

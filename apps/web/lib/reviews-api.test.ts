import { describe, expect, it } from "vitest";

import {
  aggregateRatingJsonLd,
  type PublicReviews,
} from "@/lib/reviews-shared";

const reviews = (count: number, average: number | null): PublicReviews => ({
  summary: { count, average, distribution: { "5": count } },
  total: count,
  items: [],
});

describe("aggregateRatingJsonLd", () => {
  it("emits structured data only for real approved reviews", () => {
    expect(aggregateRatingJsonLd(null)).toBeNull();
    expect(aggregateRatingJsonLd(reviews(0, null))).toBeNull();
    expect(aggregateRatingJsonLd(reviews(3, 4.667))).toMatchObject({
      "@type": "AggregateRating",
      ratingValue: "4.7",
      reviewCount: 3,
    });
  });
});

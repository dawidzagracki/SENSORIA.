import type { Metadata } from "next";
import { ReviewForm } from "@/components/reviews/review-form";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Dodaj opinię | SENSORIA",
  robots: { index: false, follow: false, noarchive: true },
  referrer: "no-referrer",
};

export default async function NewReviewPage({
  searchParams,
}: {
  searchParams: Promise<{ order?: string; item?: string; token?: string }>;
}) {
  const { order, item, token } = await searchParams;
  return (
    <ReviewForm
      orderId={typeof order === "string" ? order : null}
      itemId={typeof item === "string" ? item : null}
      token={typeof token === "string" ? token : null}
    />
  );
}

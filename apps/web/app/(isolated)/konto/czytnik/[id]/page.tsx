import type { Metadata } from "next";
import { ReaderView } from "@/components/library/reader-view";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Czytnik | SENSORIA",
  robots: { index: false, follow: false, noarchive: true },
  referrer: "no-referrer",
};

export default async function ReaderPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ order_token?: string }>;
}) {
  const { id } = await params;
  const { order_token: token } = await searchParams;
  return (
    <ReaderView
      entitlementId={id}
      orderToken={typeof token === "string" ? token : null}
    />
  );
}

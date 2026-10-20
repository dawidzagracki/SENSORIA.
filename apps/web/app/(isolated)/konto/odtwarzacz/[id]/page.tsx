import type { Metadata } from "next";
import { PlayerView } from "@/components/library/player-view";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Odtwarzacz | SENSORIA",
  robots: { index: false, follow: false, noarchive: true },
  referrer: "no-referrer",
};

export default async function PlayerPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ order_token?: string }>;
}) {
  const { id } = await params;
  const { order_token: token } = await searchParams;
  return (
    <PlayerView
      entitlementId={id}
      orderToken={typeof token === "string" ? token : null}
    />
  );
}

import type { Metadata } from "next";
import { ConfirmationView } from "@/components/order/confirmation-view";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Potwierdzenie zamówienia | SENSORIA",
  robots: { index: false, follow: false, noarchive: true },
  referrer: "no-referrer",
};

export default async function ConfirmationPage({
  searchParams,
}: {
  searchParams: Promise<{ order?: string; token?: string }>;
}) {
  const { order, token } = await searchParams;
  return (
    <ConfirmationView
      orderId={typeof order === "string" ? order : null}
      token={typeof token === "string" ? token : null}
    />
  );
}

import type { Metadata } from "next";
import { AdminOrderDetail } from "@/components/admin/orders";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Zamówienie | Panel SENSORIA",
  robots: { index: false, follow: false, noarchive: true },
  referrer: "no-referrer",
};

export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <AdminOrderDetail id={id} />;
}

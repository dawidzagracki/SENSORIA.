import type { Metadata } from "next";
import { AdminOrders } from "@/components/admin/orders";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Zamówienia | Panel SENSORIA",
  robots: { index: false, follow: false, noarchive: true },
  referrer: "no-referrer",
};

export default function Page() {
  return <AdminOrders />;
}

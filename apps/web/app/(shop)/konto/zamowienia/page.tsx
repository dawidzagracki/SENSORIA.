import type { Metadata } from "next";
import { MyOrdersView } from "@/components/account/my-orders-view";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Zamówienia | SENSORIA",
  robots: { index: false, follow: false, noarchive: true },
};

export default function OrdersPage() {
  return <MyOrdersView />;
}

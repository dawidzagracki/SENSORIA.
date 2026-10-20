import type { Metadata } from "next";
import { AdminProductNew } from "@/components/admin/products";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Nowy produkt | Panel SENSORIA",
  robots: { index: false, follow: false, noarchive: true },
  referrer: "no-referrer",
};

export default function Page() {
  return <AdminProductNew />;
}

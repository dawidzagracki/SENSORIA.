import type { Metadata } from "next";
import { AdminProducts } from "@/components/admin/products";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Produkty | Panel SENSORIA",
  robots: { index: false, follow: false, noarchive: true },
  referrer: "no-referrer",
};

export default function Page() {
  return <AdminProducts />;
}

import type { Metadata } from "next";
import { AdminVouchers } from "@/components/admin/vouchers";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Vouchery | Panel SENSORIA",
  robots: { index: false, follow: false, noarchive: true },
  referrer: "no-referrer",
};

export default function Page() {
  return <AdminVouchers />;
}

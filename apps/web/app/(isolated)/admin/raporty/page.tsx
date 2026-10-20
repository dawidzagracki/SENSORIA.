import type { Metadata } from "next";
import { AdminReports } from "@/components/admin/content";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Raporty | Panel SENSORIA",
  robots: { index: false, follow: false, noarchive: true },
  referrer: "no-referrer",
};

export default function Page() {
  return <AdminReports />;
}

import type { Metadata } from "next";
import { AdminDashboard } from "@/components/admin/dashboard";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Panel | Panel SENSORIA",
  robots: { index: false, follow: false, noarchive: true },
  referrer: "no-referrer",
};

export default function Page() {
  return <AdminDashboard />;
}

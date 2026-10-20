import type { Metadata } from "next";
import { AdminSettings } from "@/components/admin/settings";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Ustawienia | Panel SENSORIA",
  robots: { index: false, follow: false, noarchive: true },
  referrer: "no-referrer",
};

export default function Page() {
  return <AdminSettings />;
}

import type { Metadata } from "next";
import { AdminContent } from "@/components/admin/content";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Strony i FAQ | Panel SENSORIA",
  robots: { index: false, follow: false, noarchive: true },
  referrer: "no-referrer",
};

export default function Page() {
  return <AdminContent />;
}

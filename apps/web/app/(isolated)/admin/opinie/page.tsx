import type { Metadata } from "next";
import { AdminReviews } from "@/components/admin/simple-lists";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Opinie | Panel SENSORIA",
  robots: { index: false, follow: false, noarchive: true },
  referrer: "no-referrer",
};

export default function Page() {
  return <AdminReviews />;
}

import type { Metadata } from "next";
import { MyVouchersView } from "@/components/account/my-vouchers-view";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Moje vouchery | SENSORIA",
  robots: { index: false, follow: false, noarchive: true },
};

export default function MyVouchersPage() {
  return <MyVouchersView />;
}

import type { Metadata } from "next";
import { AccountDataView } from "@/components/account/account-data-view";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Dane i adresy | SENSORIA",
  robots: { index: false, follow: false, noarchive: true },
};

export default function AccountDataPage() {
  return <AccountDataView />;
}

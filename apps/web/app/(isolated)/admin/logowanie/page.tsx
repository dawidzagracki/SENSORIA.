import type { Metadata } from "next";
import { AdminLoginForm } from "@/components/admin/login-form";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Logowanie do panelu | Panel SENSORIA",
  robots: { index: false, follow: false, noarchive: true },
  referrer: "no-referrer",
};

export default function Page() {
  return <AdminLoginForm />;
}

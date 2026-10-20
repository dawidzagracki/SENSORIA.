import type { Metadata } from "next";
import { EmailChangeConfirmation } from "@/components/account/email-change-confirmation";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Potwierdź e-mail | SENSORIA",
  robots: { index: false, follow: false, noarchive: true },
  referrer: "no-referrer",
};

export default function ConfirmEmailChangePage() {
  return <EmailChangeConfirmation />;
}

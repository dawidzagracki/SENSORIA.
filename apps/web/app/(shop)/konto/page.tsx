import type { Metadata } from "next";
import {
  AccountAuthPanel,
  AccountBenefits,
} from "@/components/account/auth-panel";
import { safeReturnPath } from "@/lib/safe-return";

export const metadata: Metadata = {
  title: "Logowanie i konto | SENSORIA",
  robots: { index: false, follow: false },
};
export const dynamic = "force-dynamic";

export default async function AccountPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>;
}) {
  const params = await searchParams;
  return (
    <main
      id="main-content"
      className="relative overflow-hidden bg-surface px-4 py-12 sm:py-16"
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-96 bg-gradient-to-br from-surface-muted via-surface to-surface"
      />
      <div className="relative mx-auto grid max-w-page-shell items-start gap-10 lg:grid-cols-[1fr_0.95fr] lg:gap-16">
        <AccountBenefits />
        <AccountAuthPanel nextPath={safeReturnPath(params.next)} />
      </div>
    </main>
  );
}

import type { Metadata } from "next";
import { AccountRecoveryForm } from "@/components/account/auth-panel";

export const metadata: Metadata = {
  title: "Potwierdzenie adresu | SENSORIA",
  referrer: "no-referrer",
  robots: { index: false, follow: false },
};
export const dynamic = "force-dynamic";

export default async function TokenPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  return (
    <main
      id="main-content"
      className="min-h-[60vh] bg-gradient-to-br from-surface-muted via-surface to-surface px-4 py-12 sm:py-20"
    >
      <div className="mx-auto grid max-w-page-shell justify-items-center gap-8">
        <div className="text-center">
          <p className="uppercase-label text-accent-action">Twoje konto</p>
          <h1 className="mt-3 font-display text-subtitle text-ink">
            Potwierdzenie adresu
          </h1>
        </div>
        <AccountRecoveryForm initialToken={token} mode="verify" />
      </div>
    </main>
  );
}

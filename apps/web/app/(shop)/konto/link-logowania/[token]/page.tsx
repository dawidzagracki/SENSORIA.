import type { Metadata } from "next";
import { LoginLinkConfirmation } from "@/components/account/login-link-confirmation";

export const metadata: Metadata = {
  title: "Potwierdź logowanie | SENSORIA",
  referrer: "no-referrer",
  robots: { index: false, follow: false },
};
export const dynamic = "force-dynamic";

export default async function LoginLinkTokenPage({
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
          <p className="text-label font-bold tracking-wide text-accent-action">
            TWOJE KONTO
          </p>
          <h1 className="mt-3 font-display text-subtitle text-ink">
            Potwierdź logowanie
          </h1>
        </div>
        <LoginLinkConfirmation initialToken={token} />
      </div>
    </main>
  );
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function AccountLink() {
  const pathname = usePathname();
  const isAccountPage = pathname === "/konto" || pathname.startsWith("/konto/");

  return (
    <Link
      aria-current={isAccountPage ? "page" : undefined}
      className="inline-flex min-h-touch items-center justify-center rounded-pill border border-accent-action px-4 py-2 font-interface text-label font-bold text-ink transition-colors hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
      href="/konto"
    >
      Zaloguj się
    </Link>
  );
}

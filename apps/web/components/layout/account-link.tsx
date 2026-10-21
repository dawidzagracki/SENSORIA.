"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

export const ACCOUNT_SESSION_EVENT = "sensoria:account-session";
const API = process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") || "/api";

/** Shows "Moje konto" for a signed-in customer and "Zaloguj się" otherwise. */
export function AccountLink() {
  const pathname = usePathname();
  const [firstName, setFirstName] = useState<string | null>(null);
  const isAccountPage = pathname === "/konto" || pathname.startsWith("/konto/");

  useEffect(() => {
    let active = true;
    function load() {
      void fetch(`${API}/accounts/session`, {
        credentials: "include",
        cache: "no-store",
      })
        .then(async (response) => {
          if (!response.ok) return null;
          const body = (await response.json()) as {
            customer?: { first_name?: string };
          };
          return body.customer?.first_name ?? "";
        })
        .catch(() => null)
        .then((value) => {
          if (active) setFirstName(value);
        });
    }
    load();
    window.addEventListener(ACCOUNT_SESSION_EVENT, load);
    return () => {
      active = false;
      window.removeEventListener(ACCOUNT_SESSION_EVENT, load);
    };
  }, [pathname]);

  return (
    <Link
      aria-current={isAccountPage ? "page" : undefined}
      className="hidden min-h-touch items-center justify-center rounded-pill border border-accent-action px-4 py-2 font-interface text-button font-semibold text-accent-action transition-colors hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action focus-visible:ring-offset-2 focus-visible:ring-offset-surface sm:inline-flex"
      href="/konto"
    >
      {firstName === null ? "Zaloguj się" : "Moje konto"}
    </Link>
  );
}

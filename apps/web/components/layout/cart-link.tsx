"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { formatCartAccessibleName, useCartCount } from "./cart-count-provider";

export function CartLink() {
  const { count } = useCartCount();
  const pathname = usePathname();
  const accessibleName = formatCartAccessibleName(count);

  return (
    <Link
      aria-label={accessibleName}
      aria-current={pathname === "/koszyk" ? "page" : undefined}
      className="inline-flex min-h-touch items-center justify-center gap-2 rounded-pill border border-accent-action px-4 py-2 font-interface text-label font-bold text-ink transition-colors hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
      href="/koszyk"
    >
      <span>Koszyk</span>
      {count !== null ? (
        <span
          aria-hidden="true"
          className="rounded-pill bg-accent-action px-2 py-1 text-surface"
        >
          {count}
        </span>
      ) : null}
    </Link>
  );
}

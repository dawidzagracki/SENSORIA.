"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import type { RefObject } from "react";
import { primaryNavigationLinks } from "./site-config";

function isCurrentLink(href: string, pathname: string, query: string) {
  const [targetPath, targetQuery = ""] = href.split("?");
  if (pathname !== targetPath) return false;
  const target = new URLSearchParams(targetQuery);
  const current = new URLSearchParams(query);
  for (const [key, value] of target.entries()) {
    if (current.get(key) !== value) return false;
  }
  return true;
}

export function MainNavigation({
  className = "",
  onNavigate,
  navRef,
}: {
  className?: string;
  onNavigate?: () => void;
  navRef?: RefObject<HTMLElement | null>;
}) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const query = searchParams.toString();

  return (
    <nav aria-label="Nawigacja główna" className={className} ref={navRef}>
      <ul className="flex flex-col gap-2 lg:flex-row lg:items-center lg:gap-4">
        {primaryNavigationLinks.map((item) => {
          const current = isCurrentLink(item.href, pathname, query);
          return (
            <li key={item.href}>
              <Link
                aria-current={current ? "page" : undefined}
                className={`flex min-h-touch items-center rounded-card border-b-2 px-3 py-2 font-interface text-label text-ink transition-colors hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action focus-visible:ring-offset-2 focus-visible:ring-offset-surface ${current ? "border-accent-action font-bold" : "border-transparent"}`}
                href={item.href}
                onClick={onNavigate}
              >
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

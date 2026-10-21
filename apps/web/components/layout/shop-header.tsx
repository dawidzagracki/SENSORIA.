"use client";

import Link from "next/link";
import { useRef } from "react";
import { BrandLogo } from "./brand-logo";
import { CartLink } from "./cart-link";
import { AccountLink } from "./account-link";
import { MainNavigation } from "./main-navigation";
import { MobileMenu } from "./mobile-menu";

export function ShopHeader() {
  const desktopNavigationRef = useRef<HTMLElement>(null);

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-surface/95 backdrop-blur">
      <div className="mx-auto flex max-w-page-shell flex-wrap items-center justify-between gap-3 px-4 py-3 sm:py-4">
        <Link
          aria-label="Sensoria — strona główna"
          className="inline-flex min-h-touch items-center rounded-card text-[26px] leading-none text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
          href="/"
        >
          <BrandLogo />
        </Link>
        <MainNavigation
          className="hidden lg:block"
          navRef={desktopNavigationRef}
        />
        <div className="flex items-center gap-2">
          <AccountLink />
          <CartLink />
          <MobileMenu desktopNavigationRef={desktopNavigationRef} />
        </div>
      </div>
    </header>
  );
}

"use client";

import Link from "next/link";
import { BrandLogo } from "@/components/layout/brand-logo";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import {
  adminJson,
  clearSession,
  loadAdminSession,
  type AdminIdentity,
} from "@/lib/admin-api";
import { ClientApiError } from "@/lib/client-api";

const NAV: Array<{ href: string; label: string; owner?: boolean }> = [
  { href: "/admin", label: "Pulpit" },
  { href: "/admin/zamowienia", label: "Zamówienia" },
  { href: "/admin/produkty", label: "Produkty" },
  { href: "/admin/vouchery", label: "Vouchery" },
  { href: "/admin/klienci", label: "Klienci" },
  { href: "/admin/opinie", label: "Opinie" },
  { href: "/admin/zgloszenia", label: "Zgłoszenia" },
  { href: "/admin/rabaty", label: "Kody rabatowe", owner: true },
  { href: "/admin/strony", label: "Strony i FAQ", owner: true },
  { href: "/admin/raporty", label: "Raporty" },
  { href: "/admin/ustawienia", label: "Ustawienia", owner: true },
  { href: "/admin/dziennik", label: "Dziennik", owner: true },
];

export function AdminShell({
  title,
  children,
}: {
  title: string;
  children: (admin: AdminIdentity) => ReactNode;
}) {
  const pathname = usePathname();
  const [admin, setAdmin] = useState<AdminIdentity | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    loadAdminSession()
      .then(setAdmin)
      .catch((caught: unknown) => {
        if (caught instanceof ClientApiError && caught.status === 401) {
          window.location.assign("/admin/logowanie");
          return;
        }
        setError("Nie udało się połączyć z serwerem.");
      });
  }, []);

  async function logout() {
    try {
      await adminJson("/auth/logout", { method: "POST" });
    } finally {
      clearSession();
      window.location.assign("/admin/logowanie");
    }
  }

  if (error)
    return (
      <main id="main-content" className="p-8">
        <p role="alert">{error}</p>
      </main>
    );
  if (!admin)
    return (
      <main id="main-content" className="p-8">
        <p role="status" aria-busy="true">
          Wczytujemy panel…
        </p>
      </main>
    );
  const items = NAV.filter((item) => !item.owner || admin.role === "owner");
  return (
    <div className="min-h-screen bg-surface-muted text-ink lg:grid lg:grid-cols-[15rem_minmax(0,1fr)]">
      <aside className="border-b border-border bg-surface p-4 lg:min-h-screen lg:border-b-0 lg:border-r">
        <p className="font-display text-emphasis">
          <BrandLogo />
          <span className="ml-2 text-caption font-bold text-ink-muted">
            panel
          </span>
        </p>
        <nav aria-label="Panel administracyjny" className="mt-4">
          <ul className="flex flex-wrap gap-1 lg:block lg:space-y-1">
            {items.map((item) => {
              const active =
                item.href === "/admin"
                  ? pathname === "/admin"
                  : pathname.startsWith(item.href);
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={`flex min-h-touch items-center rounded-control px-3 text-body-small focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action ${
                      active
                        ? "bg-ink font-bold text-surface"
                        : "hover:bg-surface-muted"
                    }`}
                  >
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
        <div className="mt-6 border-t border-border pt-4 text-caption text-ink-muted">
          <p>
            {admin.display_name} ·{" "}
            {admin.role === "owner" ? "właścicielka" : "obsługa"}
          </p>
          <button
            type="button"
            onClick={logout}
            className="mt-2 min-h-touch text-accent-action underline"
          >
            Wyloguj
          </button>
        </div>
      </aside>
      <main
        id="main-content"
        tabIndex={-1}
        className="min-w-0 p-4 focus:outline-none md:p-8"
      >
        <h1 className="font-display text-title text-ink">{title}</h1>
        <div className="mt-6">{children(admin)}</div>
      </main>
    </div>
  );
}

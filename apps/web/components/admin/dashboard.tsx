"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AdminShell } from "@/components/admin/admin-shell";
import { Card, ErrorBox, Loading } from "@/components/admin/ui";
import { adminJson, errorText } from "@/lib/admin-api";
import { money } from "@/lib/client-api";

type Dashboard = {
  sales: Record<
    "today" | "last_7_days" | "last_30_days",
    { orders: number; revenue_grosz: number }
  >;
  attention: Record<string, number>;
  vouchers: { active: number; expiring_in_30_days: number };
};

const ATTENTION: Array<[string, string, string]> = [
  [
    "orders_awaiting_shipment",
    "Zamówienia do wysyłki",
    "/admin/zamowienia?status=paid&fulfillment=awaiting_fulfillment",
  ],
  [
    "orders_pending_payment",
    "Oczekują na płatność",
    "/admin/zamowienia?status=pending_payment",
  ],
  [
    "voucher_extension_requests",
    "Prośby o przedłużenie vouchera",
    "/admin/vouchery?tab=requests",
  ],
  ["low_stock_books", "Książki z niskim stanem", "/admin/produkty?kind=BOOK"],
  ["stock_conflicts", "Konflikty magazynowe", "/admin/zamowienia?status=paid"],
  ["failed_mails", "Niewysłane wiadomości", "/admin/dziennik"],
];

function Dash() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    adminJson<Dashboard>("/dashboard")
      .then(setData)
      .catch((e: unknown) =>
        setError(errorText(e, "Nie udało się wczytać pulpitu.")),
      );
  }, []);
  if (error) return <ErrorBox message={error} />;
  if (!data) return <Loading />;
  return (
    <div className="space-y-6">
      <section aria-labelledby="sales" className="grid gap-4 md:grid-cols-3">
        <h2 id="sales" className="sr-only">
          Sprzedaż
        </h2>
        {(
          [
            ["today", "Dzisiaj"],
            ["last_7_days", "Ostatnie 7 dni"],
            ["last_30_days", "Ostatnie 30 dni"],
          ] as const
        ).map(([key, label]) => (
          <Card key={key}>
            <p className="text-caption font-bold tracking-wide text-ink-muted">
              {label.toUpperCase()}
            </p>
            <p className="mt-2 font-display text-title">
              {money(data.sales[key].revenue_grosz)}
            </p>
            <p className="text-body-small text-ink-muted">
              {data.sales[key].orders} opłaconych zamówień
            </p>
          </Card>
        ))}
      </section>
      <Card title="Wymaga uwagi">
        <ul className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {ATTENTION.map(([key, label, href]) => {
            const value = data.attention[key] ?? 0;
            return (
              <li key={key}>
                <Link
                  href={href}
                  className={`flex min-h-touch items-center justify-between gap-3 rounded-control border px-4 py-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action ${
                    value > 0
                      ? "border-warning bg-warning text-on-warning"
                      : "border-border"
                  }`}
                >
                  <span>{label}</span>
                  <strong>{value}</strong>
                </Link>
              </li>
            );
          })}
        </ul>
      </Card>
      <Card title="Vouchery">
        <p>
          Aktywnych: <strong>{data.vouchers.active}</strong> · wygasa w ciągu 30
          dni: <strong>{data.vouchers.expiring_in_30_days}</strong>
        </p>
      </Card>
    </div>
  );
}

export function AdminDashboard() {
  return <AdminShell title="Pulpit">{() => <Dash />}</AdminShell>;
}

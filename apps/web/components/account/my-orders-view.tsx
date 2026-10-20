"use client";

import Link from "next/link";
import Image from "next/image";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { ShipmentTracking } from "@/components/account/shipment-tracking";
import { ReorderButton } from "@/components/account/reorder-button";
import type { CustomerShipment } from "@/lib/shipment-presentation";

type Item = {
  id: string;
  product_id: string;
  name: string;
  kind: string;
  quantity: number;
  unit_price_grosz: number;
  line_total_grosz: number;
  vat_rate: string;
  variant: string | null;
  cover_url: string | null;
  cover_alt: string | null;
};
type Order = {
  id: string;
  number: string;
  created_at: string;
  status: string;
  buyer_email: string;
  fulfillment_status: string;
  amount_due_grosz: number;
  paid_amount_grosz: number | null;
  calculation: Record<string, unknown>;
  invoice: Record<string, unknown>;
  shipping: Record<string, unknown> | null;
  delivery_point: Record<string, string> | null;
  items: Item[];
  shipment: CustomerShipment | null;
  documents: Array<{
    id: string;
    type: string;
    number: string;
    date: string;
    amount_grosz: number;
    currency: string;
    status: string;
  }>;
};
type History = {
  customer_name: string;
  contact_email: string | null;
  contact_phone: string | null;
  first_purchase_at: string | null;
  total_count: number;
  counts: Record<string, number>;
  page: number;
  page_size: number;
  items: Order[];
};
type Filter = "all" | "in_progress" | "completed" | "invoices";
const API = process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") || "/api";
const filters: { id: Filter; label: string }[] = [
  { id: "all", label: "Wszystkie" },
  { id: "in_progress", label: "W realizacji" },
  { id: "completed", label: "Zakończone" },
  { id: "invoices", label: "Faktury" },
];
const money = (grosz: number) =>
  `${Math.floor(grosz / 100)},${String(grosz % 100).padStart(2, "0")} zł`;
const fullDate = (value: string) =>
  new Intl.DateTimeFormat("pl-PL", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "Europe/Warsaw",
  }).format(new Date(value));
const monthYear = (value: string | null) =>
  value
    ? new Intl.DateTimeFormat("pl-PL", {
        month: "long",
        year: "numeric",
        timeZone: "Europe/Warsaw",
      }).format(new Date(value))
    : "bez dotychczasowych zakupów";
const fulfillmentLabel: Record<string, string> = {
  awaiting_fulfillment: "W REALIZACJI",
  shipped: "WYSYŁKA W TOKU",
  delivered: "DOSTARCZONE",
  ready_for_pickup: "GOTOWE DO ODBIORU",
  picked_up: "ODEBRANE",
  cancelled: "ANULOWANE",
};
function statusLabel(order: Order) {
  return order.status === "paid"
    ? "OPŁACONE"
    : order.status === "pending_payment"
      ? "OCZEKUJE NA PŁATNOŚĆ"
      : order.status === "expired"
        ? "WYGASŁE"
        : "ANULOWANE";
}
function ImagePlaceholder({ item }: { item: Item }) {
  return item.cover_url ? (
    <Image
      alt={item.cover_alt || item.name}
      className="aspect-ebook-cover w-11 shrink-0 rounded-control object-cover sm:w-12"
      height={60}
      width={48}
      src={item.cover_url}
    />
  ) : (
    <div
      aria-hidden="true"
      className="aspect-ebook-cover w-11 shrink-0 rounded-control bg-gradient-to-br from-surface-muted to-accent/50 sm:w-12"
    />
  );
}

export function MyOrdersView() {
  const [filter, setFilter] = useState<Filter>("all");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<History | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [expanded, setExpanded] = useState<string | null>(null);
  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(
        `${API}/accounts/orders?filter=${filter}&page=${page}&page_size=10`,
        {
          credentials: "include",
          cache: "no-store",
          headers: { Accept: "application/json" },
        },
      );
      if (response.status === 401) {
        window.location.assign(
          `/konto?next=${encodeURIComponent("/konto/zamowienia")}`,
        );
        return;
      }
      if (!response.ok)
        throw new Error(
          response.status === 403
            ? "Nie masz dostępu do tej historii."
            : "Nie udało się pobrać historii zamówień.",
        );
      setData((await response.json()) as History);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Nie udało się pobrać historii zamówień.",
      );
    } finally {
      setLoading(false);
    }
  }, [filter, page]);
  useEffect(() => {
    void load();
  }, [load, retry]);

  const orders = data?.items ?? [];

  return (
    <main id="main-content" className="min-h-[60vh] bg-surface text-ink">
      <section className="relative overflow-hidden px-4 pb-7 pt-8 sm:px-8 sm:pb-9 sm:pt-10">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 top-0 h-52 bg-gradient-to-r from-surface via-surface-muted to-accent/10"
        />
        <div className="relative mx-auto max-w-page-shell">
          <p className="text-label font-bold tracking-caps text-accent-action">
            TWOJE KONTO
          </p>
          <h1 className="mt-3 font-display text-title font-bold md:text-display">
            Zamówienia
          </h1>
        </div>
      </section>
      <div className="mx-auto grid max-w-page-shell gap-7 px-4 pb-14 sm:px-8 lg:grid-cols-[17rem_minmax(0,1fr)] lg:gap-8">
        <aside className="space-y-4">
          <section className="flex items-center gap-3 rounded-card bg-surface-muted p-4">
            <span
              aria-hidden="true"
              className="grid size-12 shrink-0 place-items-center rounded-full bg-accent-action font-bold text-surface"
            >
              {data?.customer_name
                .split(/\s+/)
                .map((part) => part[0])
                .slice(0, 2)
                .join("")
                .toUpperCase() || "S"}
            </span>
            <div className="min-w-0">
              <p className="break-words font-semibold">
                {data?.customer_name ?? "Twoje konto"}
              </p>
              <p className="text-caption text-ink-muted">
                Klientka od {monthYear(data?.first_purchase_at ?? null)}
              </p>
            </div>
          </section>
          <nav
            aria-label="Nawigacja konta"
            className="rounded-card border border-border bg-surface p-2"
          >
            <ul className="space-y-1">
              <li>
                <span
                  aria-disabled="true"
                  className="flex min-h-touch items-center rounded-control px-3 text-body-small text-ink-muted"
                >
                  Moja biblioteka
                </span>
              </li>
              <li>
                <Link
                  href="/konto/vouchery"
                  className="flex min-h-touch items-center rounded-control px-3 text-body-small text-ink-muted hover:bg-surface-muted"
                >
                  Moje vouchery
                </Link>
              </li>
              <li>
                <Link
                  aria-current="page"
                  href="/konto/zamowienia"
                  className="flex min-h-touch items-center rounded-control bg-ink px-3 font-semibold text-body-small text-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
                >
                  Zamówienia
                </Link>
              </li>
              <li>
                <span
                  aria-disabled="true"
                  className="flex min-h-touch items-center rounded-control px-3 text-body-small text-ink-muted"
                >
                  Dane i adresy
                </span>
              </li>
              <li>
                <span
                  aria-disabled="true"
                  className="flex min-h-touch items-center rounded-control px-3 text-body-small text-ink-muted"
                >
                  Zgody i prywatność
                </span>
              </li>
            </ul>
          </nav>
          <section className="rounded-card border border-border bg-surface p-4 text-body-small">
            <h2 className="font-semibold">Potrzebujesz pomocy?</h2>
            {data?.contact_email ? (
              <a
                className="mt-2 block break-all text-accent-action underline"
                href={`mailto:${data.contact_email}`}
              >
                {data.contact_email}
              </a>
            ) : (
              <p className="mt-2 text-ink-muted">
                Dane kontaktowe obsługi nie są skonfigurowane.
              </p>
            )}
            {data?.contact_phone ? (
              <a
                className="mt-1 block break-all text-accent-action underline"
                href={`tel:${data.contact_phone}`}
              >
                {data.contact_phone}
              </a>
            ) : null}
            <p className="mt-2 text-ink-muted">
              Informacja o czasie odpowiedzi nie jest skonfigurowana.
            </p>
          </section>
        </aside>
        <section className="min-w-0" aria-label="Historia zamówień">
          <div
            className="mb-5 flex flex-wrap gap-2"
            role="group"
            aria-label="Filtr zamówień"
          >
            {filters.map((entry) => (
              <button
                key={entry.id}
                type="button"
                aria-pressed={filter === entry.id}
                onClick={() => {
                  setFilter(entry.id);
                  setPage(1);
                }}
                className={`min-h-touch rounded-pill border px-4 text-body-small font-semibold focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${filter === entry.id ? "border-ink bg-ink text-surface" : "border-border bg-surface text-ink hover:bg-surface-muted"}`}
              >
                {entry.label}
                {entry.id !== "invoices"
                  ? ` ${data?.counts[entry.id] ?? ""}`
                  : ""}
              </button>
            ))}
          </div>
          {loading ? (
            <p
              aria-live="polite"
              className="rounded-card border border-border bg-surface p-8 text-center"
            >
              Ładuję historię zamówień…
            </p>
          ) : null}
          {error ? (
            <div
              role="alert"
              className="rounded-card border border-border bg-surface p-6"
            >
              <h2 className="font-semibold">Nie udało się pobrać danych</h2>
              <p className="mt-2 text-body-small text-ink-muted">{error}</p>
              <Button
                className="mt-4"
                onClick={() => setRetry((value) => value + 1)}
                variant="secondary"
              >
                Spróbuj ponownie
              </Button>
            </div>
          ) : null}
          {!loading && !error && filter === "invoices" ? (
            <div className="rounded-card border border-border bg-surface p-8">
              <h2 className="font-display text-subtitle font-bold">
                Dokumenty sprzedaży
              </h2>
              <p className="mt-2 text-body-small text-ink-muted">
                Moduł dokumentów [36] nie jest dostępny w tej wersji, dlatego
                nie pokazujemy fikcyjnych dokumentów ani przycisków pobrania.
              </p>
            </div>
          ) : null}
          {!loading &&
          !error &&
          filter !== "invoices" &&
          orders.length === 0 ? (
            <div className="rounded-card border border-border bg-surface p-8 text-center">
              <h2 className="font-display text-subtitle font-bold">
                {filter === "all"
                  ? "Nie masz jeszcze zamówień"
                  : "Brak zamówień w tym widoku"}
              </h2>
              <p className="mt-2 text-body-small text-ink-muted">
                Historia zamówień pojawi się tutaj po zakupie.
              </p>
              <Link
                className="mt-5 inline-flex min-h-touch items-center rounded-pill bg-accent-action px-5 font-semibold text-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-ink"
                href="/sklep"
              >
                Przejdź do sklepu
              </Link>
            </div>
          ) : null}
          <div className="space-y-4">
            {orders.map((order) => (
              <article
                key={order.id}
                className="overflow-hidden rounded-card border border-border bg-surface"
              >
                <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-gradient-to-r from-surface to-surface-muted/60 px-4 py-4 sm:px-6">
                  <p>
                    <strong>{order.number}</strong>
                    <span className="text-ink-muted">
                      {" "}
                      · {fullDate(order.created_at)}
                    </span>
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <span className="rounded-pill bg-success px-3 py-1 text-label font-bold text-on-success">
                      {statusLabel(order)}
                    </span>
                    <span className="rounded-pill border border-border px-3 py-1 text-label font-bold">
                      {fulfillmentLabel[order.fulfillment_status] ??
                        order.fulfillment_status}
                    </span>
                  </div>
                </header>
                <div className="px-4 sm:px-6">
                  {order.items.map((item) => (
                    <div
                      key={item.id}
                      className="flex min-w-0 items-center gap-3 border-b border-border py-4 sm:gap-4"
                    >
                      <ImagePlaceholder item={item} />
                      <div className="min-w-0 flex-1">
                        <h2 className="break-words font-semibold">
                          {item.name}
                        </h2>
                        <p className="mt-1 text-body-small text-ink-muted">
                          {item.kind === "DIGITAL"
                            ? "Materiał cyfrowy"
                            : item.kind === "AUDIOBOOK"
                              ? "Audiobook"
                              : item.kind === "BOOK"
                                ? `Książka · ${item.quantity} szt.`
                                : "Voucher"}
                          {item.variant ? ` · ${item.variant}` : ""}
                        </p>
                      </div>
                      <p className="shrink-0 text-right text-body-small font-semibold">
                        {money(item.line_total_grosz)}
                      </p>
                    </div>
                  ))}
                  {order.shipment && order.shipment.items.length > 0 ? (
                    <div className="my-4">
                      <ShipmentTracking
                        shipment={order.shipment}
                        variant="order"
                      />
                    </div>
                  ) : null}
                </div>
                <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-4 py-4 sm:px-6">
                  <p className="text-body-small text-ink-muted">
                    {order.paid_amount_grosz !== null ? (
                      <>
                        Zapłacono{" "}
                        <strong className="ml-1 text-body text-ink">
                          {money(order.paid_amount_grosz)}
                        </strong>
                      </>
                    ) : (
                      <>
                        Do zapłaty{" "}
                        <strong className="ml-1 text-body text-ink">
                          {money(order.amount_due_grosz)}
                        </strong>
                      </>
                    )}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {order.status === "paid" && order.items.length > 0 ? (
                      <ReorderButton
                        endpoint={`/cart/reorder/orders/${encodeURIComponent(order.id)}`}
                        label="Zamów ponownie"
                      />
                    ) : null}
                    <button
                      onClick={() =>
                        setExpanded(expanded === order.id ? null : order.id)
                      }
                      aria-expanded={expanded === order.id}
                      className="inline-flex min-h-touch items-center rounded-pill border border-border px-4 text-body-small font-semibold focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
                    >
                      Szczegóły
                    </button>
                    {order.documents.map((document) => (
                      <a
                        key={document.id}
                        href={`${API}/accounts/orders/${order.id}/documents/${document.id}`}
                        className="inline-flex min-h-touch items-center rounded-pill border border-border px-4 text-body-small font-semibold"
                      >
                        Pobierz {document.type}
                      </a>
                    ))}
                  </div>
                </footer>
                {expanded === order.id ? (
                  <section
                    className="border-t border-border bg-surface-muted/40 p-4 sm:p-6"
                    aria-label={`Szczegóły ${order.number}`}
                  >
                    <h3 className="font-semibold">Rozliczenie zamówienia</h3>
                    <dl className="mt-3 grid gap-2 text-body-small sm:grid-cols-2">
                      <div className="flex justify-between gap-3">
                        <dt>Produkty brutto</dt>
                        <dd>
                          {money(
                            Number(order.calculation.products_gross_grosz ?? 0),
                          )}
                        </dd>
                      </div>
                      <div className="flex justify-between gap-3">
                        <dt>Rabat</dt>
                        <dd>
                          {money(Number(order.calculation.discount_grosz ?? 0))}
                        </dd>
                      </div>
                      <div className="flex justify-between gap-3">
                        <dt>Dostawa</dt>
                        <dd>
                          {money(
                            Number(
                              (
                                order.calculation.delivery as
                                  Record<string, number> | undefined
                              )?.gross_grosz ?? 0,
                            ),
                          )}
                        </dd>
                      </div>
                      <div className="flex justify-between gap-3 font-semibold">
                        <dt>Razem</dt>
                        <dd>{money(order.amount_due_grosz)}</dd>
                      </div>
                    </dl>
                    <h4 className="mt-4 font-semibold">
                      Podsumowanie VAT zapisane przy zakupie
                    </h4>
                    <ul className="mt-2 space-y-1 text-body-small">
                      {(
                        order.calculation.vat_groups as
                          | Array<{
                              vat_label: string;
                              net_grosz: number;
                              tax_grosz: number;
                              gross_grosz: number;
                            }>
                          | undefined
                      )?.map((group) => (
                        <li
                          key={group.vat_label}
                          className="flex flex-wrap justify-between gap-x-4"
                        >
                          <span>
                            VAT {group.vat_label}: netto{" "}
                            {money(group.net_grosz)}, podatek{" "}
                            {money(group.tax_grosz)}
                          </span>
                          <span>brutto {money(group.gross_grosz)}</span>
                        </li>
                      ))}
                    </ul>
                    {order.shipping ? (
                      <div className="mt-4">
                        <h4 className="font-semibold">Dane dostawy</h4>
                        <p className="mt-1 break-words text-body-small text-ink-muted">
                          {String(order.shipping.method ?? "—")}
                          {order.delivery_point?.code
                            ? ` · ${order.delivery_point.code}`
                            : ""}
                        </p>
                      </div>
                    ) : null}
                    <div className="mt-4">
                      <h4 className="font-semibold">Dane nabywcy</h4>
                      <p className="mt-1 break-words text-body-small text-ink-muted">
                        {String(order.invoice.kind ?? "Osoba prywatna")} ·{" "}
                        {String(
                          (
                            order.invoice.buyer_snapshot as
                              Record<string, string> | undefined
                          )?.first_name ?? "",
                        )}{" "}
                        {String(
                          (
                            order.invoice.buyer_snapshot as
                              Record<string, string> | undefined
                          )?.last_name ?? "",
                        )}{" "}
                        · {order.buyer_email}
                      </p>
                    </div>
                  </section>
                ) : null}
              </article>
            ))}
          </div>
          {data &&
          data.total_count > data.page_size &&
          filter !== "invoices" ? (
            <nav
              aria-label="Stronicowanie historii"
              className="mt-5 flex items-center justify-between"
            >
              <Button
                disabled={page <= 1}
                onClick={() => setPage((value) => Math.max(1, value - 1))}
                variant="secondary"
              >
                Poprzednia
              </Button>
              <span aria-live="polite" className="text-body-small">
                Strona {page} · {data.total_count} zamówień
              </span>
              <Button
                disabled={page * data.page_size >= data.total_count}
                onClick={() => setPage((value) => value + 1)}
                variant="secondary"
              >
                Następna
              </Button>
            </nav>
          ) : null}
        </section>
      </div>
    </main>
  );
}

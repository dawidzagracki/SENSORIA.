"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { DownloadButton } from "@/components/library/download-button";
import type {
  EntitlementDetail,
  LibraryItem,
} from "@/components/library/library-types";
import {
  API,
  apiJson,
  ClientApiError,
  formatDate,
  money,
} from "@/lib/client-api";

type OrderStatus = {
  order_id: string;
  public_number: string | null;
  status: "pending_payment" | "paid" | "cancelled" | "expired";
  payment_status: string | null;
  payment_method: string;
  amount_due_grosz: number;
  email_masked: string;
  created_at: string;
  requires_shipping: boolean;
  delivery_method: string | null;
  items: Array<{
    name: string | null;
    quantity: number;
    unit_price_grosz: number;
    is_voucher: boolean;
  }>;
  can_retry_payment: boolean;
};
type VoucherRow = {
  id: string;
  code: string;
  service_name: string | null;
  status: string;
  valid_until: string;
  pdf_ready: boolean;
  is_gift: boolean;
};
type DocumentRow = { id: string; kind: string; number: string };

const POLL_MS = 3000;
const POLL_LIMIT = 20;
const deliveryLabel: Record<string, string> = {
  parcel_locker: "Paczkomat InPost",
  courier: "Kurier",
  pickup_in_person: "Odbiór w gabinecie",
};

export function ConfirmationView({
  orderId,
  token,
}: {
  orderId: string | null;
  token: string | null;
}) {
  const [order, setOrder] = useState<OrderStatus | null>(null);
  const [error, setError] = useState("");
  const [library, setLibrary] = useState<LibraryItem[]>([]);
  const [files, setFiles] = useState<
    Record<string, EntitlementDetail["files"]>
  >({});
  const [vouchers, setVouchers] = useState<VoucherRow[]>([]);
  const [documents, setDocuments] = useState<DocumentRow[]>([]);
  const [retrying, setRetrying] = useState(false);
  const polls = useRef(0);

  const query = token ? `?token=${encodeURIComponent(token)}` : "";
  const tokenParam = token ? `?order_token=${encodeURIComponent(token)}` : "";
  const orderToken = token ? token : null;

  const load = useCallback(async () => {
    if (!orderId || !token) return;
    try {
      const status = await apiJson<OrderStatus>(
        `/payments/orders/${orderId}${query}`,
      );
      setOrder(status);
      if (status.status === "paid") {
        const [lib, vch, docs] = await Promise.all([
          apiJson<{ items: LibraryItem[] }>(
            `/library/orders/${orderId}?order_token=${encodeURIComponent(token)}`,
          ),
          apiJson<{ items: VoucherRow[] }>(
            `/vouchers/orders/${orderId}?order_token=${encodeURIComponent(token)}`,
          ),
          apiJson<{ items: DocumentRow[] }>(
            `/documents/orders/${orderId}${tokenParam}`,
          ),
        ]);
        setLibrary(lib.items);
        setVouchers(vch.items);
        setDocuments(docs.items);
        const detail: Record<string, EntitlementDetail["files"]> = {};
        for (const item of lib.items) {
          const info = await apiJson<EntitlementDetail>(
            `/library/entitlements/${item.id}${tokenParam}`,
          );
          detail[item.id] = info.files;
        }
        setFiles(detail);
      }
    } catch (caught) {
      setError(
        caught instanceof ClientApiError && caught.status === 404
          ? "Nie znaleziono zamówienia. Użyj linku z wiadomości e-mail."
          : "Nie udało się wczytać zamówienia. Odśwież stronę.",
      );
    }
  }, [orderId, token, query, tokenParam]);

  useEffect(() => {
    void load();
  }, [load]);

  // Right after the hosted payment page the webhook may still be in flight.
  useEffect(() => {
    if (!order || order.status !== "pending_payment") return;
    if (order.payment_status !== "pending" || polls.current >= POLL_LIMIT)
      return;
    const timer = window.setTimeout(() => {
      polls.current += 1;
      void load();
    }, POLL_MS);
    return () => window.clearTimeout(timer);
  }, [order, load]);

  async function retryPayment() {
    if (!orderId || !token) return;
    setRetrying(true);
    setError("");
    try {
      const session = await apiJson<{ payment_url: string }>(
        `/payments/orders/${orderId}/session?token=${encodeURIComponent(token)}`,
        { method: "POST" },
      );
      window.location.assign(session.payment_url);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Nie udało się uruchomić płatności.",
      );
      setRetrying(false);
    }
  }

  if (!orderId || !token) {
    return (
      <Shell title="Nie znaleziono zamówienia">
        <Alert variant="warning">
          Otwórz tę stronę z linku w wiadomości e-mail albo z konta klientki.
        </Alert>
      </Shell>
    );
  }
  if (error && !order) {
    return (
      <Shell title="Zamówienie">
        <Alert variant="error">{error}</Alert>
      </Shell>
    );
  }
  if (!order) {
    return (
      <Shell title="Zamówienie">
        <p role="status" aria-busy="true">
          Wczytujemy zamówienie…
        </p>
      </Shell>
    );
  }

  const awaiting =
    order.status === "pending_payment" && order.payment_status === "pending";
  const title =
    order.status === "paid"
      ? "Dziękujemy! Zamówienie opłacone"
      : awaiting
        ? "Potwierdzamy płatność…"
        : order.status === "pending_payment"
          ? "Zamówienie czeka na płatność"
          : "Zamówienie nieaktywne";

  return (
    <Shell title={title}>
      <p className="text-body text-ink-muted">
        Zamówienie <strong>{order.public_number}</strong> z{" "}
        {formatDate(order.created_at)} · potwierdzenia wysyłamy na{" "}
        {order.email_masked}
      </p>
      {error ? (
        <div className="mt-4">
          <Alert variant="error">{error}</Alert>
        </div>
      ) : null}

      {awaiting ? (
        <div className="mt-6">
          <Alert variant="info">
            Czekamy na potwierdzenie od operatora płatności. To zwykle trwa
            kilka sekund — ta strona odświeży się sama.
          </Alert>
        </div>
      ) : null}
      {order.status === "pending_payment" && !awaiting ? (
        <div className="mt-6 space-y-4">
          <Alert variant="warning" title="Płatność nie została zakończona">
            {order.payment_status === "failed"
              ? "Płatność nie powiodła się, a środki nie zostały pobrane."
              : "Nie otrzymaliśmy jeszcze płatności."}{" "}
            Zamówienie jest zarezerwowane przez ograniczony czas.
          </Alert>
          {order.can_retry_payment ? (
            <Button loading={retrying} onClick={retryPayment} size="lg">
              Zapłać ponownie
            </Button>
          ) : null}
        </div>
      ) : null}
      {order.status === "expired" || order.status === "cancelled" ? (
        <div className="mt-6">
          <Alert variant="error">
            To zamówienie wygasło lub zostało anulowane. Jeśli płatność została
            pobrana, napisz do nas — wyjaśnimy sprawę.
          </Alert>
          <Link
            href="/sklep"
            className="mt-4 inline-flex min-h-touch items-center text-accent-action underline"
          >
            Wróć do sklepu
          </Link>
        </div>
      ) : null}

      <section
        aria-labelledby="summary"
        className="mt-8 rounded-card border border-border bg-surface p-5"
      >
        <h2 id="summary" className="font-display text-subtitle text-ink">
          Podsumowanie
        </h2>
        <ul className="mt-4 divide-y divide-border">
          {order.items.map((item, index) => (
            <li
              key={`${item.name}-${index}`}
              className="flex justify-between gap-4 py-3"
            >
              <span>
                {item.name ?? "Produkt"} × {item.quantity}
              </span>
              <span>{money(item.unit_price_grosz * item.quantity)}</span>
            </li>
          ))}
        </ul>
        <p className="mt-4 flex justify-between font-bold">
          <span>Do zapłaty</span>
          <span>{money(order.amount_due_grosz)}</span>
        </p>
        {order.requires_shipping ? (
          <p className="mt-3 text-caption text-ink-muted">
            Dostawa: {deliveryLabel[order.delivery_method ?? ""] ?? "wysyłka"}.
            {order.delivery_method === "pickup_in_person"
              ? " Powiadomimy Cię e-mailem, gdy zamówienie będzie gotowe do odbioru."
              : " Powiadomimy Cię e-mailem, gdy paczka zostanie nadana."}
          </p>
        ) : null}
      </section>

      {order.status === "paid" && library.length > 0 ? (
        <section aria-labelledby="library" className="mt-8">
          <h2 id="library" className="font-display text-subtitle text-ink">
            Twoje materiały
          </h2>
          <ul className="mt-4 space-y-4">
            {library.map((item) => (
              <li
                key={item.id}
                className="rounded-card border border-border bg-surface p-5"
              >
                <p className="font-bold text-ink">{item.title}</p>
                <div className="mt-3 flex flex-wrap gap-3">
                  {item.kind === "audiobook" ? (
                    <Link
                      href={`/konto/odtwarzacz/${item.id}${tokenParam}`}
                      className="inline-flex min-h-touch items-center rounded-pill bg-accent-action px-5 text-label font-bold text-surface"
                    >
                      Słuchaj
                    </Link>
                  ) : (
                    <Link
                      href={`/konto/czytnik/${item.id}${tokenParam}`}
                      className="inline-flex min-h-touch items-center rounded-pill bg-accent-action px-5 text-label font-bold text-surface"
                    >
                      Czytaj w przeglądarce
                    </Link>
                  )}
                  {(files[item.id] ?? [])
                    .filter((f) => f.kind === "pdf")
                    .map((file) => (
                      <DownloadButton
                        key={file.id}
                        entitlementId={item.id}
                        fileId={file.id}
                        orderToken={orderToken}
                        label={`Pobierz ${file.label} (PDF)`}
                      />
                    ))}
                </div>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-caption text-ink-muted">
            Każdy plik PDF jest oznaczony Twoimi danymi. Link do pobrania działa
            ograniczoną liczbę razy i można go w każdej chwili odnowić.
          </p>
        </section>
      ) : null}

      {order.status === "paid" && vouchers.length > 0 ? (
        <section aria-labelledby="vouchers" className="mt-8">
          <h2 id="vouchers" className="font-display text-subtitle text-ink">
            Vouchery
          </h2>
          <ul className="mt-4 space-y-4">
            {vouchers.map((voucher) => (
              <li
                key={voucher.id}
                className="rounded-card border border-border bg-surface p-5"
              >
                <p className="font-bold text-ink">{voucher.service_name}</p>
                {voucher.is_gift ? (
                  <p className="mt-1 text-body-small text-ink-muted">
                    Voucher w prezencie — wyślemy go obdarowanej osobie w
                    wybranym dniu.
                  </p>
                ) : (
                  <>
                    <p className="mt-2 font-display text-emphasis tracking-wider">
                      {voucher.code}
                    </p>
                    <p className="text-body-small text-ink-muted">
                      Ważny do {formatDate(voucher.valid_until)}
                    </p>
                    {voucher.pdf_ready ? (
                      <a
                        className="mt-3 inline-flex min-h-touch items-center text-accent-action underline"
                        href={`${API}/vouchers/${voucher.id}/pdf${tokenParam}`}
                      >
                        Pobierz voucher (PDF)
                      </a>
                    ) : (
                      <p
                        className="mt-3 text-caption text-ink-muted"
                        role="status"
                      >
                        PDF vouchera jest przygotowywany — dostaniesz go także
                        e-mailem.
                      </p>
                    )}
                  </>
                )}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {order.status === "paid" ? (
        <section aria-labelledby="documents" className="mt-8">
          <h2 id="documents" className="font-display text-subtitle text-ink">
            Dokumenty
          </h2>
          {documents.length ? (
            <ul className="mt-4 space-y-2">
              {documents.map((doc) => (
                <li key={doc.id}>
                  <a
                    className="inline-flex min-h-touch items-center text-accent-action underline"
                    href={`${API}/documents/${doc.id}/pdf${tokenParam}`}
                  >
                    {doc.kind === "invoice" ? "Faktura" : "Paragon"}{" "}
                    {doc.number} (PDF)
                  </a>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-body-small text-ink-muted">
              Dokument sprzedaży pojawi się tutaj, gdy zostanie wystawiony.
            </p>
          )}
        </section>
      ) : null}

      <p className="mt-10 text-body-small text-ink-muted">
        Masz pytanie do zamówienia?{" "}
        <Link
          className="text-accent-action underline"
          href={`/pomoc/zwroty-i-reklamacje?order=${orderId}&token=${encodeURIComponent(token)}`}
        >
          Zgłoś reklamację lub zwrot
        </Link>{" "}
        albo zajrzyj do{" "}
        <Link className="text-accent-action underline" href="/pomoc">
          centrum pomocy
        </Link>
        .
      </p>
    </Shell>
  );
}

function Shell({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <main
      id="main-content"
      tabIndex={-1}
      className="mx-auto w-full max-w-wide min-w-0 px-4 py-10 focus:outline-none sm:py-14"
    >
      <h1 className="font-display text-title text-ink">{title}</h1>
      <div className="mt-3">{children}</div>
    </main>
  );
}

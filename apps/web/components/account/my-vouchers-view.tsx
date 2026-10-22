"use client";

import Link from "next/link";
import Image from "next/image";
import type { FormEvent } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { PurchaseLinkingNotice } from "@/components/account/purchase-linking-notice";
import { ReorderButton } from "@/components/account/reorder-button";

type VoucherStatus =
  | "active"
  | "expiring_soon"
  | "expired"
  | "redeemed"
  | "cancelled"
  | "extended";

type VoucherRequest = {
  created_at: string;
  status: "pending" | "approved" | "rejected";
  message: string;
};

type Voucher = {
  id: string;
  code: string;
  status: VoucherStatus;
  name: string;
  variant: string;
  issued_at: string;
  valid_until: string;
  days_until_expiry: number;
  redeemed_at: string | null;
  redeemed_by: string | null;
  place: string | null;
  purchase_date: string;
  pdf_status: "ready" | "preparing" | "failed" | "missing";
  qr_path: string;
  product_path: string | null;
  variant_id?: string | null;
  request_pending: boolean;
  requests: VoucherRequest[];
};

type ResponseData = {
  customer_name: string | null;
  first_purchase_at: string | null;
  items: Voucher[];
  total_count: number;
  usable_count: number;
  purchase_history_notice?: boolean;
  contact_email: string | null;
  contact_phone: string | null;
  booking_url: string | null;
  booking_instructions: string | null;
};

type ActionModal = "transfer" | "details" | "booking" | null;
const API_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") || "/api";

function formatDate(value: string, options: Intl.DateTimeFormatOptions = {}) {
  return new Intl.DateTimeFormat("pl-PL", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "Europe/Warsaw",
    ...options,
  }).format(new Date(value));
}

function monthYear(value: string | null) {
  if (!value) return "bez dotychczasowych zakupów";
  // "21 października 2026" → "października 2026" (genitive, as "od …" requires).
  return new Intl.DateTimeFormat("pl-PL", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "Europe/Warsaw",
  })
    .format(new Date(value))
    .replace(/^\d+\s/, "");
}

function initials(name: string | null) {
  const parts = name?.trim().split(/\s+/).filter(Boolean) ?? [];
  return parts.length
    ? parts
        .slice(0, 2)
        .map((part) => part[0])
        .join("")
        .toUpperCase()
    : "S";
}

function statusLabel(status: VoucherStatus) {
  const labels: Record<VoucherStatus, string> = {
    active: "Aktywny",
    expiring_soon: "Wygasa wkrótce",
    extended: "Przedłużony",
    expired: "Wygasły",
    redeemed: "Zrealizowany",
    cancelled: "Anulowany",
  };
  return labels[status];
}

function expiryWarningDays(vouchers: Voucher[]) {
  return vouchers
    .filter((voucher) => voucher.status === "expiring_soon")
    .map((voucher) => voucher.days_until_expiry)
    .filter((days) => days >= 0)
    .sort((a, b) => a - b)[0];
}

function warningCopy(days: number) {
  if (days === 0) return "jeden z Twoich voucherów wygasa dzisiaj";
  if (days === 1) return "jeden z Twoich voucherów wygasa jutro";
  return `jeden z Twoich voucherów wygasa za ${days} dni`;
}

function apiPath(path: string) {
  return API_URL ? `${API_URL}${path}` : path;
}

function AccountNavigation({ voucherCount }: { voucherCount: number }) {
  return (
    <nav
      aria-label="Nawigacja konta"
      className="rounded-card border border-border bg-surface p-5 shadow-card"
    >
      <ul className="space-y-2">
        <li>
          <span
            aria-disabled="true"
            className="flex min-h-touch items-center justify-between rounded-control px-3 text-body text-ink-muted"
          >
            <span>Moja biblioteka</span>
          </span>
        </li>
        <li>
          <Link
            aria-current="page"
            className="flex min-h-touch items-center justify-between rounded-control border border-accent/30 bg-accent/10 px-3 font-semibold text-body text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
            href="/konto/vouchery"
          >
            <span>Moje vouchery</span>
            <span
              aria-label={`${voucherCount} aktywne vouchery`}
              className="rounded-full bg-accent-action px-2 py-1 text-caption text-surface"
            >
              {voucherCount}
            </span>
          </Link>
        </li>
        {["Zamówienia", "Dane i adresy", "Zgody i prywatność"].map((label) => (
          <li key={label}>
            <span
              aria-disabled="true"
              className="flex min-h-touch items-center rounded-control px-3 text-body text-ink-muted"
            >
              {label}
            </span>
          </li>
        ))}
      </ul>
    </nav>
  );
}

export function MyVouchersView() {
  const [data, setData] = useState<ResponseData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [activeVoucher, setActiveVoucher] = useState<Voucher | null>(null);
  const [modal, setModal] = useState<ActionModal>(null);
  const [extensionMessage, setExtensionMessage] = useState("");
  const [extensionBusy, setExtensionBusy] = useState(false);
  const [extensionMessageStatus, setExtensionMessageStatus] = useState<
    string | null
  >(null);
  const [extensionError, setExtensionError] = useState<string | null>(null);
  const [copyStatus, setCopyStatus] = useState<Record<string, string>>({});
  const [pdfStatus, setPdfStatus] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(apiPath("/accounts/vouchers"), {
        cache: "no-store",
        credentials: "include",
        headers: { Accept: "application/json" },
      });
      if (response.status === 401)
        throw new ApiError(
          "AUTHENTICATION_REQUIRED",
          "Zaloguj się, aby zobaczyć swoje vouchery.",
          401,
        );
      if (!response.ok)
        throw new ApiError(
          "HTTP_ERROR",
          "Nie udało się pobrać voucherów.",
          response.status,
        );
      const result = (await response.json()) as ResponseData;
      setData(result);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Nie udało się pobrać voucherów.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  const nearestWarning = useMemo(
    () => expiryWarningDays(data?.items ?? []),
    [data?.items],
  );
  const displayName = data?.customer_name ?? "Twoje konto";

  async function copyCode(voucher: Voucher) {
    try {
      if (!navigator.clipboard?.writeText)
        throw new Error("Clipboard API niedostępne");
      await navigator.clipboard.writeText(voucher.code);
      setCopyStatus((current) => ({
        ...current,
        [voucher.id]: "Kod skopiowany",
      }));
    } catch {
      setCopyStatus((current) => ({
        ...current,
        [voucher.id]: "Skopiuj kod ręcznie, zaznaczając jego tekst.",
      }));
    }
  }

  async function submitExtension(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeVoucher || extensionBusy) return;
    setExtensionBusy(true);
    setExtensionError(null);
    setExtensionMessageStatus(null);
    try {
      const response = await fetch(
        apiPath(`/accounts/vouchers/${activeVoucher.id}/extension-requests`),
        {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
          },
          body: JSON.stringify({ message: extensionMessage }),
        },
      );
      if (response.status === 429) {
        const retryAfter = Number(response.headers.get("Retry-After"));
        const retryAt =
          Number.isFinite(retryAfter) && retryAfter > 0
            ? new Date(Date.now() + retryAfter * 1000)
            : null;
        throw new Error(
          retryAt
            ? `Wysłano już kilka próśb. Spróbuj ponownie ${formatDate(retryAt.toISOString(), { hour: "2-digit", minute: "2-digit" })}.`
            : "Wysłano już kilka próśb. Spróbuj ponownie później.",
        );
      }
      if (!response.ok)
        throw new Error(
          "Nie udało się wysłać prośby. Treść formularza została zachowana.",
        );
      setExtensionMessageStatus(
        "Prośba wysłana i czeka na rozpatrzenie. Termin ważności nie zmienił się.",
      );
      setExtensionMessage("");
      setRefreshKey((current) => current + 1);
    } catch (cause) {
      setExtensionError(
        cause instanceof Error ? cause.message : "Nie udało się wysłać prośby.",
      );
    } finally {
      setExtensionBusy(false);
    }
  }

  async function refreshPdf(voucher: Voucher) {
    setPdfStatus((current) => ({
      ...current,
      [voucher.id]: "Sprawdzam stan dokumentu…",
    }));
    setRefreshKey((current) => current + 1);
    window.setTimeout(
      () =>
        setPdfStatus((current) => ({
          ...current,
          [voucher.id]:
            "Jeśli dokument nadal się przygotowuje, spróbuj ponownie za chwilę.",
        })),
      500,
    );
  }

  function openModal(next: ActionModal, voucher: Voucher) {
    setActiveVoucher(voucher);
    setModal(next);
    setExtensionError(null);
    setExtensionMessageStatus(null);
  }

  function voucherActions(voucher: Voucher) {
    const pdfReady = voucher.pdf_status === "ready";
    const download = pdfReady
      ? apiPath(`/accounts/vouchers/${voucher.id}/pdf`)
      : undefined;
    const downloadButton = (
      <a
        aria-disabled={!download}
        className={`inline-flex min-h-touch items-center justify-center rounded-control border border-border px-4 text-center text-body font-semibold ${download ? "text-ink hover:bg-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent" : "cursor-not-allowed text-ink-muted"}`}
        href={download}
        onClick={(event) => {
          if (!download) {
            event.preventDefault();
            if (voucher.pdf_status === "preparing") void refreshPdf(voucher);
          }
        }}
      >
        {pdfReady
          ? "Pobierz PDF"
          : voucher.pdf_status === "preparing"
            ? "Odśwież stan PDF"
            : "PDF niedostępny"}
      </a>
    );
    if (voucher.status === "redeemed" || voucher.status === "cancelled") {
      return (
        <div className="flex flex-wrap gap-2">
          <Button
            onClick={() => openModal("details", voucher)}
            variant="secondary"
          >
            Zobacz szczegóły
          </Button>
          {voucher.status === "redeemed" && voucher.product_path ? (
            <ReorderButton
              endpoint={`/cart/reorder/vouchers/${encodeURIComponent(voucher.id)}`}
              label="Kup ponownie"
            />
          ) : null}
        </div>
      );
    }
    if (voucher.status === "expired") {
      return (
        <div className="flex flex-wrap gap-2">
          <Button
            disabled={voucher.request_pending}
            onClick={() => openModal("details", voucher)}
            variant="secondary"
          >
            {voucher.request_pending
              ? "Prośba oczekuje"
              : "Poproś o przedłużenie"}
          </Button>
          <Button onClick={() => openModal("details", voucher)} variant="text">
            Szczegóły
          </Button>
        </div>
      );
    }
    return (
      <div className="flex flex-wrap gap-2">
        {downloadButton}
        <Button
          onClick={() => openModal("booking", voucher)}
          variant="secondary"
        >
          Umów wizytę
        </Button>
        <Button onClick={() => openModal("transfer", voucher)} variant="text">
          Przekaż komuś
        </Button>
        {voucher.status === "expiring_soon" ? (
          <Button
            disabled={voucher.request_pending}
            onClick={() => openModal("details", voucher)}
            variant="primary"
          >
            {voucher.request_pending
              ? "Prośba oczekuje"
              : "Poproś o przedłużenie"}
          </Button>
        ) : null}
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-surface-muted text-ink">
      <section className="bg-gradient-to-br from-surface-muted to-surface px-4 py-10 md:px-8 md:py-14">
        <div className="mx-auto max-w-page-shell">
          <p className="text-caption font-bold tracking-wide text-accent-action">
            TWOJE KONTO
          </p>
          <h1 className="mt-2 font-display text-title font-bold md:text-display">
            Moje vouchery
          </h1>
          <p className="mt-3 max-w-prose text-body text-ink-muted">
            Twoje kody, terminy i informacje o realizacji w jednym miejscu.
          </p>
          <div className="mt-4">
            <PurchaseLinkingNotice />
          </div>
        </div>
      </section>
      <div className="mx-auto grid max-w-page-shell gap-8 px-4 py-8 md:px-8 lg:grid-cols-[17rem_minmax(0,1fr)] lg:py-12">
        <aside className="space-y-4">
          <section
            aria-label="Profil klientki"
            className="flex items-center gap-3 rounded-card border border-border bg-surface p-5 shadow-card"
          >
            <div
              aria-hidden="true"
              className="flex size-12 shrink-0 items-center justify-center rounded-full bg-accent/10 font-bold text-accent-action"
            >
              {initials(data?.customer_name ?? null)}
            </div>
            <div className="min-w-0">
              <p className="break-words font-semibold">{displayName}</p>
              <p className="text-caption text-ink-muted">
                Klientka od {monthYear(data?.first_purchase_at ?? null)}
              </p>
            </div>
          </section>
          <AccountNavigation voucherCount={data?.usable_count ?? 0} />
          <section className="rounded-card border border-border bg-surface p-5">
            <h2 className="font-semibold">Potrzebujesz pomocy?</h2>
            {data?.contact_email ? (
              <a
                className="mt-2 block break-all text-body text-accent-action underline"
                href={`mailto:${data.contact_email}`}
              >
                {data.contact_email}
              </a>
            ) : (
              <p className="mt-2 text-body text-ink-muted">
                Napisz do nas przez formularz w centrum pomocy.
              </p>
            )}
            {data?.contact_phone ? (
              <a
                className="mt-1 block text-body text-accent-action underline"
                href={`tel:${data.contact_phone}`}
              >
                {data.contact_phone}
              </a>
            ) : null}
            <a
              className="mt-3 inline-block text-body-small font-semibold text-accent-action underline"
              href="/pomoc"
            >
              Centrum pomocy
            </a>
          </section>
        </aside>
        <section aria-label="Lista voucherów" className="min-w-0">
          {data?.purchase_history_notice ? (
            <p
              className="mb-4 rounded-control border border-border bg-surface p-4 text-body-small text-ink-muted"
              role="status"
            >
              Po potwierdzeniu adresu e-mail zobaczysz tutaj swoje wcześniejsze
              zakupy.
            </p>
          ) : null}
          {loading ? (
            <p
              aria-live="polite"
              className="rounded-card border border-border bg-surface p-8 text-center"
            >
              Ładuję Twoje vouchery…
            </p>
          ) : null}
          {error ? (
            <div
              className="rounded-card border border-border bg-surface p-6"
              role="alert"
            >
              <h2 className="font-semibold">
                Nie udało się otworzyć listy voucherów
              </h2>
              <p className="mt-2 text-body text-ink-muted">{error}</p>
              {error.includes("Zaloguj się") ? (
                <p className="mt-4 text-caption text-ink-muted">
                  Logowanie klientki nie jest jeszcze dostępne w tej wersji
                  sklepu.
                </p>
              ) : (
                <Button
                  className="mt-4"
                  onClick={() => setRefreshKey((current) => current + 1)}
                  variant="secondary"
                >
                  Spróbuj ponownie
                </Button>
              )}
            </div>
          ) : null}
          {!loading && !error && data?.items.length === 0 ? (
            <div className="rounded-card border border-border bg-surface p-8 text-center">
              <h2 className="font-display text-subtitle font-bold">
                Nie masz jeszcze voucherów
              </h2>
              <p className="mt-2 text-body text-ink-muted">
                Kup voucher na wizytę, aby jego kod i termin były dostępne
                tutaj.
              </p>
              <Link
                className="mt-5 inline-flex min-h-touch items-center rounded-pill bg-accent-action px-5 font-semibold text-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                href="/sklep?typ=voucher"
              >
                Zobacz vouchery
              </Link>
            </div>
          ) : null}
          {!loading && !error && data && data.items.length > 0 ? (
            <>
              {nearestWarning !== undefined ? (
                <div
                  className="mb-6 rounded-card border border-accent/30 bg-accent/10 p-4 md:p-5"
                  role="status"
                >
                  <p className="font-semibold">
                    {warningCopy(nearestWarning)}. Jeśli nie zdążysz umówić
                    wizyty, napisz do nas — wspólnie omówimy możliwości. Nic nie
                    przepada bez rozmowy. Sama prośba nie zmienia terminu.
                  </p>
                </div>
              ) : null}
              <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
                <div>
                  <h2 className="font-display text-subtitle font-bold">
                    Twoje vouchery
                  </h2>
                  <p className="mt-1 text-caption text-ink-muted">
                    {data.total_count}{" "}
                    {data.total_count === 1
                      ? "voucher"
                      : data.total_count >= 2 && data.total_count <= 4
                        ? "vouchery"
                        : "voucherów"}{" "}
                    w historii
                  </p>
                </div>
                <p className="text-caption text-ink-muted">
                  Licznik aktywnych i dostępnych: {data.usable_count}
                </p>
              </div>
              <div className="grid gap-5 xl:grid-cols-2">
                {data.items.map((voucher) => {
                  const isHistorical =
                    voucher.status === "redeemed" ||
                    voucher.status === "expired" ||
                    voucher.status === "cancelled";
                  return (
                    <article
                      className={`relative min-w-0 overflow-hidden rounded-card border border-accent/20 p-5 shadow-card ${isHistorical ? "bg-surface" : "bg-gradient-to-br from-surface-muted to-surface"}`}
                      key={voucher.id}
                    >
                      <div
                        aria-hidden="true"
                        className="pointer-events-none absolute -right-10 -top-12 size-36 rounded-full border border-accent/10"
                      />
                      <div className="relative flex min-w-0 items-start gap-4">
                        <div className="flex size-20 shrink-0 items-center justify-center rounded-control border border-border bg-white p-2">
                          <Image
                            alt={`Kod QR vouchera ${voucher.code}`}
                            className={`size-full object-contain ${isHistorical ? "opacity-60 grayscale" : ""}`}
                            height={96}
                            unoptimized
                            src={voucher.qr_path}
                            width={96}
                          />
                        </div>
                        <div className="min-w-0 flex-1">
                          <span className="inline-flex rounded-full border border-accent/20 bg-surface px-3 py-1 text-caption font-semibold">
                            {statusLabel(voucher.status)}
                          </span>
                          <h3 className="mt-3 break-words font-display text-subtitle font-bold">
                            {voucher.name}
                          </h3>
                          <p className="mt-1 text-caption text-ink-muted">
                            {voucher.variant}
                          </p>
                          <div className="mt-2 flex flex-wrap items-center gap-2">
                            <code className="break-all rounded-control bg-surface px-2 py-1 font-mono text-body font-bold tracking-wide">
                              {voucher.code}
                            </code>
                            <Button
                              aria-label={`Kopiuj kod ${voucher.code}`}
                              onClick={() => void copyCode(voucher)}
                              size="sm"
                              variant="text"
                            >
                              Kopiuj kod
                            </Button>
                          </div>
                          <p
                            aria-live="polite"
                            className="min-h-5 text-caption text-ink-muted"
                          >
                            {copyStatus[voucher.id] ?? ""}
                          </p>
                        </div>
                      </div>
                      <div className="relative my-4 border-t border-dashed border-accent/30" />
                      <dl className="relative grid gap-3 sm:grid-cols-2">
                        <div>
                          <dt className="text-caption text-ink-muted">
                            {voucher.status === "redeemed"
                              ? "Ważny do (termin historyczny)"
                              : "Termin ważności"}
                          </dt>
                          <dd className="mt-1 break-words font-semibold">
                            {formatDate(voucher.valid_until)}
                          </dd>
                        </div>
                        <div>
                          <dt className="text-caption text-ink-muted">
                            Miejsce świadczenia
                          </dt>
                          <dd className="mt-1 break-words font-semibold">
                            {voucher.status === "redeemed"
                              ? "Miejsce wizyty nie jest zapisywane w obecnym rejestrze"
                              : (voucher.place ??
                                "Szczegóły dostępne w dokumencie")}
                          </dd>
                        </div>
                        {voucher.status === "redeemed" ? (
                          <div className="sm:col-span-2">
                            <dt className="text-caption text-ink-muted">
                              Data realizacji
                            </dt>
                            <dd className="mt-1 break-words font-semibold">
                              {voucher.redeemed_at
                                ? formatDate(voucher.redeemed_at)
                                : "Brak zapisanej daty"}
                              {voucher.redeemed_by
                                ? ` · odnotował(a): ${voucher.redeemed_by}`
                                : " · konto realizujące nie jest zapisane"}{" "}
                              · miejsce realizacji nie jest zapisywane w obecnym
                              rejestrze
                            </dd>
                          </div>
                        ) : null}
                        {voucher.status === "expiring_soon" ? (
                          <div className="sm:col-span-2">
                            <dt className="text-caption text-ink-muted">
                              Pozostało według kalendarza
                            </dt>
                            <dd className="mt-1 font-semibold">
                              {voucher.days_until_expiry === 0
                                ? "Wygasa dzisiaj"
                                : voucher.days_until_expiry === 1
                                  ? "Wygasa jutro"
                                  : `Wygasa za ${voucher.days_until_expiry} dni`}
                            </dd>
                          </div>
                        ) : null}
                        {voucher.request_pending ? (
                          <div className="sm:col-span-2">
                            <dt className="text-caption text-ink-muted">
                              Prośba o przedłużenie
                            </dt>
                            <dd className="mt-1 font-semibold">
                              Oczekuje na rozpatrzenie
                            </dd>
                          </div>
                        ) : null}
                      </dl>
                      {pdfStatus[voucher.id] ? (
                        <p
                          aria-live="polite"
                          className="relative mt-3 text-caption text-ink-muted"
                        >
                          {pdfStatus[voucher.id]}
                        </p>
                      ) : null}
                      <div className="relative mt-5">
                        {voucherActions(voucher)}
                      </div>
                    </article>
                  );
                })}
              </div>
              <p className="mt-6 rounded-card border border-border bg-surface p-4 text-caption text-ink-muted">
                Vouchery pozostają w historii konta. Aktualny stan i termin są
                sprawdzane przez system przy każdej operacji.
              </p>
            </>
          ) : null}
        </section>
      </div>
      <Modal
        onOpenChange={(open) => {
          if (!open) setModal(null);
        }}
        open={modal !== null}
        title={
          modal === "transfer"
            ? "Przekaż voucher"
            : modal === "booking"
              ? "Umów wizytę"
              : modal === "details"
                ? "Szczegóły vouchera"
                : ""
        }
      >
        {activeVoucher && modal === "transfer" ? (
          <div className="space-y-4">
            <p>
              Voucher nie jest przypisany do osoby, która z niego skorzysta.
              Możesz przekazać jej plik PDF. To nie zmienia właścicielki konta
              ani historii zakupu.
            </p>
            {activeVoucher.pdf_status === "ready" ? (
              <a
                className="inline-flex min-h-touch items-center rounded-control bg-accent-action px-4 font-semibold text-surface"
                href={apiPath(`/accounts/vouchers/${activeVoucher.id}/pdf`)}
              >
                Pobierz PDF do przekazania
              </a>
            ) : (
              <p className="text-caption text-ink-muted">
                Dokument nie jest jeszcze dostępny.
              </p>
            )}
          </div>
        ) : null}
        {activeVoucher && modal === "booking" ? (
          <div className="space-y-4">
            <p>
              {data?.booking_instructions ??
                "Skontaktuj się z nami, aby ustalić dostępny termin. Otwarcie tego okna nie rezerwuje wizyty ani nie realizuje vouchera."}
            </p>
            {data?.booking_url ? (
              <a
                className="inline-flex min-h-touch items-center rounded-control bg-accent-action px-4 font-semibold text-white"
                href={data.booking_url}
                rel="noreferrer"
              >
                Otwórz kontakt / rezerwację
              </a>
            ) : data?.contact_email ? (
              <a
                className="inline-flex min-h-touch items-center rounded-control bg-accent-action px-4 font-semibold text-white"
                href={`mailto:${data.contact_email}`}
              >
                Napisz do nas
              </a>
            ) : (
              <a
                className="inline-flex min-h-touch items-center rounded-control bg-accent-action px-4 font-semibold text-white"
                href="/pomoc"
              >
                Centrum pomocy
              </a>
            )}
          </div>
        ) : null}
        {activeVoucher && modal === "details" ? (
          <div className="space-y-4">
            <dl className="grid gap-3">
              <div>
                <dt className="text-caption text-ink-muted">Kod</dt>
                <dd className="font-mono font-semibold">
                  {activeVoucher.code}
                </dd>
              </div>
              <div>
                <dt className="text-caption text-ink-muted">Stan</dt>
                <dd>{statusLabel(activeVoucher.status)}</dd>
              </div>
              <div>
                <dt className="text-caption text-ink-muted">Zakupiono</dt>
                <dd>{formatDate(activeVoucher.purchase_date)}</dd>
              </div>
              <div>
                <dt className="text-caption text-ink-muted">Termin</dt>
                <dd>{formatDate(activeVoucher.valid_until)}</dd>
              </div>
            </dl>
            {activeVoucher.status === "expired" ||
            activeVoucher.status === "expiring_soon" ? (
              activeVoucher.request_pending ? (
                <p role="status">
                  Prośba oczekuje na rozpatrzenie. Termin nie został zmieniony.
                </p>
              ) : (
                <form
                  className="space-y-3"
                  onSubmit={(event) => void submitExtension(event)}
                >
                  <label className="block" htmlFor="extension-message">
                    <span className="mb-1 block font-semibold">
                      Uzasadnienie (opcjonalne)
                    </span>
                    <textarea
                      className="min-h-24 w-full rounded-control border border-border bg-surface px-3 py-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
                      id="extension-message"
                      maxLength={2000}
                      onChange={(event) =>
                        setExtensionMessage(event.target.value)
                      }
                      value={extensionMessage}
                    />
                  </label>
                  {extensionError ? (
                    <p className="text-caption text-on-danger" role="alert">
                      {extensionError}
                    </p>
                  ) : null}
                  {extensionMessageStatus ? (
                    <p className="text-caption text-success" role="status">
                      {extensionMessageStatus}
                    </p>
                  ) : null}
                  <Button
                    disabled={extensionBusy}
                    loading={extensionBusy}
                    type="submit"
                    variant="primary"
                  >
                    Wyślij prośbę
                  </Button>
                </form>
              )
            ) : activeVoucher.requests.length ? (
              <div>
                <h3 className="font-semibold">Historia próśb</h3>
                <ul className="mt-2 space-y-2">
                  {activeVoucher.requests.map((request) => (
                    <li
                      className="rounded-control bg-surface-muted p-3"
                      key={request.created_at}
                    >
                      <p>
                        {formatDate(request.created_at)} ·{" "}
                        {request.status === "pending"
                          ? "oczekuje"
                          : request.status === "approved"
                            ? "rozpatrzona pozytywnie"
                            : "odrzucona"}
                      </p>
                      {request.message ? (
                        <p className="mt-1 break-words">{request.message}</p>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : null}
      </Modal>
    </main>
  );
}

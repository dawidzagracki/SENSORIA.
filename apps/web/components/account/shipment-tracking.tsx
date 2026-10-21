"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import {
  type CustomerShipment,
  formatShipmentAddress,
  formatShipmentDate,
  presentShipmentStatus,
} from "@/lib/shipment-presentation";
import { Button } from "@/components/ui/button";

type Props = {
  shipment: CustomerShipment;
  variant: "library" | "order";
};

function ShipmentDate({
  value,
  label,
}: {
  value: string | null;
  label: string;
}) {
  const [relative, setRelative] = useState<string | null>(null);
  useEffect(() => {
    if (!value) return;
    const timeZone =
      Intl.DateTimeFormat().resolvedOptions().timeZone || "Europe/Warsaw";
    setRelative(formatShipmentDate(value, new Date(), timeZone));
  }, [value]);
  if (!value) return null;
  return (
    <time
      dateTime={value}
      title={new Intl.DateTimeFormat("pl-PL", {
        dateStyle: "full",
        timeZone: "Europe/Warsaw",
      }).format(new Date(value))}
    >
      {label}{" "}
      {relative ??
        new Intl.DateTimeFormat("pl-PL", {
          day: "numeric",
          month: "long",
          year: "numeric",
          timeZone: "Europe/Warsaw",
        }).format(new Date(value))}
    </time>
  );
}

function CopyTrackingNumber({ number }: { number: string }) {
  const [message, setMessage] = useState("");
  async function copyNumber() {
    try {
      if (!navigator.clipboard?.writeText)
        throw new Error("clipboard unavailable");
      await navigator.clipboard.writeText(number);
      setMessage("Numer przesyłki skopiowany.");
    } catch {
      setMessage(
        "Nie udało się skopiować. Zaznacz numer i skopiuj go ręcznie.",
      );
    }
  }
  return (
    <div className="flex min-w-0 flex-wrap items-center gap-2">
      <span className="break-all font-interface text-body-small font-bold text-ink">
        {number}
      </span>
      <Button
        type="button"
        variant="text"
        size="sm"
        onClick={copyNumber}
        aria-label="Skopiuj numer przesyłki"
      >
        Kopiuj numer
      </Button>
      <span className="sr-only" role="status" aria-live="polite">
        {message}
      </span>
      {message && (
        <span className="w-full text-caption text-ink-muted" aria-hidden="true">
          {message}
        </span>
      )}
    </div>
  );
}

function TrackingLink({ href }: { href: string | null }) {
  if (!href) return null;
  return (
    <a
      className="inline-flex min-h-touch items-center justify-center rounded-pill border border-accent-action px-5 font-interface text-caption font-bold text-accent-action underline-offset-4 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-action"
      href={href}
      target="_blank"
      rel="noopener noreferrer"
    >
      Śledź przesyłkę
      <span className="sr-only"> (otwiera się w nowej karcie)</span>
    </a>
  );
}

export function ShipmentTracking({ shipment, variant }: Props) {
  const status = presentShipmentStatus(shipment);
  const address = formatShipmentAddress(shipment);
  const shippedDate = shipment.shipped_at ? (
    <ShipmentDate value={shipment.shipped_at} label="Nadana" />
  ) : null;

  if (variant === "library") {
    return (
      <section
        aria-label="Książki z zamówienia"
        className="rounded-card border border-border bg-surface p-4 sm:p-5"
      >
        <ul className="space-y-4">
          {shipment.items.map((item) => (
            <li
              key={`${shipment.order_id}-${item.product_id}`}
              className="grid min-w-0 grid-cols-[4.5rem_minmax(0,1fr)] gap-4 sm:grid-cols-[5rem_minmax(0,1fr)]"
            >
              <div className="relative aspect-ebook-cover overflow-hidden rounded-control bg-surface-muted">
                {item.cover_url ? (
                  <Image
                    src={item.cover_url}
                    alt={item.cover_alt || item.name}
                    fill
                    sizes="80px"
                    className="object-cover"
                  />
                ) : (
                  <span className="flex h-full items-center justify-center px-2 text-center text-caption text-ink-muted">
                    Książka
                  </span>
                )}
              </div>
              <div className="min-w-0 space-y-2">
                <h3 className="break-words font-display text-subtitle font-bold text-ink">
                  {item.name}
                </h3>
                <p className="break-words text-body-small text-ink-muted">
                  Książka papierowa · {item.quantity} szt. ·{" "}
                  <span className="font-bold text-ink">{status.label}</span>
                </p>
                {address && (
                  <p className="break-words text-caption text-ink-muted">
                    {address}
                  </p>
                )}
                {shipment.tracking_number && (
                  <CopyTrackingNumber number={shipment.tracking_number} />
                )}
                {shipment.tracking_link_status === "unconfigured" &&
                  shipment.shipment_status !== null && (
                    <p className="text-caption text-ink-muted">
                      Link śledzenia jest chwilowo niedostępny.
                    </p>
                  )}
                <TrackingLink href={shipment.tracking_url} />
                {shippedDate && (
                  <p className="text-caption text-ink-muted">{shippedDate}</p>
                )}
              </div>
            </li>
          ))}
        </ul>
      </section>
    );
  }

  if (variant === "order") {
    return (
      <section
        aria-label="Informacje o przesyłce"
        className="grid min-w-0 gap-3 rounded-card bg-surface-muted p-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-center"
      >
        <div className="flex min-w-0 items-start gap-3">
          <span
            aria-hidden="true"
            className="grid size-10 shrink-0 place-items-center rounded-control border border-border bg-surface text-accent-action"
          >
            <svg
              viewBox="0 0 24 24"
              className="size-5"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 1 1 16 0Z" />
              <circle cx="12" cy="10" r="2.5" />
            </svg>
          </span>
          <div className="min-w-0 space-y-1">
            <p className="break-words font-display text-body-small font-bold text-ink">
              <span>{status.label}</span>
              {address ? ` · ${address}` : null}
            </p>
            {shipment.tracking_number ? (
              <div className="flex min-w-0 flex-wrap items-center gap-x-1 text-caption text-ink-muted">
                <span>Numer przesyłki</span>
                <CopyTrackingNumber number={shipment.tracking_number} />
                {shippedDate ? <> · {shippedDate}</> : null}
              </div>
            ) : (
              <p className="break-words text-caption text-ink-muted">
                {status.description}
              </p>
            )}
          </div>
        </div>
        <TrackingLink href={shipment.tracking_url} />
      </section>
    );
  }

  return (
    <section
      aria-label="Informacje o przesyłce"
      className="grid min-w-0 gap-4 rounded-card border border-border bg-surface-muted p-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:p-5"
    >
      <div className="min-w-0 space-y-2">
        <p className="font-interface uppercase-label text-accent-action">
          {status.label}
        </p>
        {address && (
          <p className="break-words font-display text-body font-bold text-ink">
            {address}
          </p>
        )}
        <p className="text-caption text-ink-muted">{status.description}</p>
        <div className="space-y-1">
          {shipment.tracking_number && (
            <CopyTrackingNumber number={shipment.tracking_number} />
          )}
          {shippedDate && (
            <p className="text-caption text-ink-muted">{shippedDate}</p>
          )}
          {shipment.delivered_at && (
            <p className="text-caption text-ink-muted">
              <ShipmentDate value={shipment.delivered_at} label="Dostarczona" />
            </p>
          )}
          {shipment.pickup_ready_at && (
            <p className="text-caption text-ink-muted">
              <ShipmentDate
                value={shipment.pickup_ready_at}
                label="Gotowa do odbioru od"
              />
            </p>
          )}
          {shipment.picked_up_at && (
            <p className="text-caption text-ink-muted">
              <ShipmentDate value={shipment.picked_up_at} label="Odebrana" />
            </p>
          )}
          {shipment.tracking_link_status === "unconfigured" &&
            shipment.shipment_status !== null && (
              <p className="text-caption text-ink-muted">
                Link śledzenia jest chwilowo niedostępny.
              </p>
            )}
        </div>
      </div>
      <TrackingLink href={shipment.tracking_url} />
    </section>
  );
}

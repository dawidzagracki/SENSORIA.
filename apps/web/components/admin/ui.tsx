"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { Alert } from "@/components/ui/alert";

export function Card({
  title,
  children,
  actions,
}: {
  title?: string;
  children: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <section className="rounded-card border border-border bg-surface p-5">
      {title || actions ? (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          {title ? (
            <h2 className="font-display text-emphasis text-ink">{title}</h2>
          ) : (
            <span />
          )}
          {actions}
        </div>
      ) : null}
      {children}
    </section>
  );
}

export function ErrorBox({ message }: { message: string }) {
  return message ? <Alert variant="error">{message}</Alert> : null;
}

export function Loading({ label = "Wczytujemy…" }: { label?: string }) {
  return (
    <p role="status" aria-busy="true" className="text-ink-muted">
      {label}
    </p>
  );
}

export function Pager({
  page,
  total,
  pageSize,
  onPage,
}: {
  page: number;
  total: number;
  pageSize: number;
  onPage: (page: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <nav
      aria-label="Stronicowanie"
      className="mt-4 flex items-center gap-3 text-body-small"
    >
      <button
        type="button"
        className="min-h-touch rounded-pill border border-border px-4 disabled:opacity-40"
        disabled={page <= 1}
        onClick={() => onPage(page - 1)}
      >
        ← Poprzednia
      </button>
      <span>
        Strona {page} z {pages} · {total} pozycji
      </span>
      <button
        type="button"
        className="min-h-touch rounded-pill border border-border px-4 disabled:opacity-40"
        disabled={page >= pages}
        onClick={() => onPage(page + 1)}
      >
        Następna →
      </button>
    </nav>
  );
}

export function Table({
  caption,
  head,
  children,
}: {
  caption: string;
  head: string[];
  children: ReactNode;
}) {
  const root = useRef<HTMLDivElement>(null);
  // On narrow screens rows become cards; each cell is labelled by its column heading.
  useEffect(() => {
    root.current?.querySelectorAll("tbody tr").forEach((row) => {
      row.querySelectorAll("td").forEach((cell, index) => {
        if (head[index]) cell.setAttribute("data-label", head[index]);
      });
    });
  });
  return (
    <div className="responsive-table overflow-x-auto" ref={root}>
      <table className="w-full min-w-[40rem] border-collapse text-left text-body-small">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-border text-caption uppercase tracking-wide text-ink-muted">
            {head.map((label) => (
              <th key={label} scope="col" className="px-3 py-2 font-bold">
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">{children}</tbody>
      </table>
    </div>
  );
}

export const inputClass =
  "min-h-touch w-full rounded-control border border-border bg-surface px-3 text-body focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action";

export function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
}) {
  return (
    <label className="block text-label text-ink">
      {label}
      <span className="mt-1 block">{children}</span>
      {hint ? (
        <span className="mt-1 block text-caption text-ink-muted">{hint}</span>
      ) : null}
    </label>
  );
}

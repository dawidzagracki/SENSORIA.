"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { DownloadButton } from "@/components/library/download-button";
import type {
  EntitlementDetail,
  LibraryItem,
} from "@/components/library/library-types";
import { apiJson, ClientApiError, formatDate } from "@/lib/client-api";

type Loaded = {
  item: LibraryItem;
  files: EntitlementDetail["files"];
};

export function LibraryView() {
  const [rows, setRows] = useState<Loaded[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const list = await apiJson<{ items: LibraryItem[] }>("/library/mine");
        const loaded: Loaded[] = [];
        for (const item of list.items) {
          const detail = await apiJson<EntitlementDetail>(
            `/library/entitlements/${item.id}`,
          );
          loaded.push({ item, files: detail.files });
        }
        if (!cancelled) setRows(loaded);
      } catch (caught) {
        if (cancelled) return;
        if (caught instanceof ClientApiError && caught.status === 401) {
          window.location.assign(
            `/konto?next=${encodeURIComponent("/konto/biblioteka")}`,
          );
          return;
        }
        setError("Nie udało się wczytać biblioteki. Spróbuj ponownie.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main
      id="main-content"
      tabIndex={-1}
      className="mx-auto w-full max-w-page-shell min-w-0 px-4 py-10 focus:outline-none sm:py-14"
    >
      <p className="text-caption font-bold tracking-wide text-accent-action">
        TWOJE KONTO
      </p>
      <h1 className="mt-2 font-display text-title text-ink">Moja biblioteka</h1>
      <p className="mt-3 max-w-content text-body text-ink-muted">
        E-booki, kursy i audiobooki, które kupiłaś. Czytasz i słuchasz w
        przeglądarce, a pliki PDF możesz pobrać.
      </p>
      <nav
        aria-label="Konto"
        className="mt-6 flex flex-wrap gap-4 text-body-small"
      >
        <Link
          className="min-h-touch py-3 text-accent-action underline"
          href="/konto/zamowienia"
        >
          Zamówienia
        </Link>
        <Link
          className="min-h-touch py-3 text-accent-action underline"
          href="/konto/vouchery"
        >
          Vouchery
        </Link>
        <Link
          className="min-h-touch py-3 text-accent-action underline"
          href="/konto/dane"
        >
          Dane i zgody
        </Link>
      </nav>
      {error ? (
        <div className="mt-6">
          <Alert variant="error">{error}</Alert>
        </div>
      ) : null}
      {!rows && !error ? (
        <p className="mt-8" role="status" aria-busy="true">
          Wczytujemy bibliotekę…
        </p>
      ) : null}
      {rows && rows.length === 0 ? (
        <section className="mt-8 rounded-card border border-border bg-surface-muted p-8">
          <h2 className="font-display text-subtitle text-ink">
            Biblioteka jest jeszcze pusta
          </h2>
          <p className="mt-2 text-body text-ink-muted">
            Po zakupie materiałów cyfrowych pojawią się tutaj od razu po
            opłaceniu zamówienia.
          </p>
          <Link
            className="mt-4 inline-flex min-h-touch items-center rounded-pill bg-accent-action px-6 text-label font-bold text-surface"
            href="/sklep"
          >
            Przejdź do sklepu
          </Link>
        </section>
      ) : null}
      {rows && rows.length > 0 ? (
        <ul className="mt-8 grid gap-5 sm:grid-cols-2">
          {rows.map(({ item, files }) => {
            const percent =
              item.chapters_total > 0
                ? Math.round(
                    (item.chapters_completed / item.chapters_total) * 100,
                  )
                : 0;
            return (
              <li
                key={item.id}
                className="flex flex-col rounded-card border border-border bg-surface p-5"
              >
                <p className="text-caption font-bold tracking-wide text-accent-action">
                  {item.kind === "audiobook" ? "AUDIOBOOK" : "E-BOOK / KURS"}
                </p>
                <h2 className="mt-1 font-display text-emphasis text-ink">
                  {item.title}
                </h2>
                <p className="mt-1 text-caption text-ink-muted">
                  Zakup {formatDate(item.granted_at)} · {item.order_number}
                </p>
                {item.chapters_total > 0 ? (
                  <div className="mt-4">
                    <div
                      role="progressbar"
                      aria-label={`Postęp: ${item.chapters_completed} z ${item.chapters_total} rozdziałów`}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-valuenow={percent}
                      className="h-2 rounded-pill bg-surface-muted"
                    >
                      <div
                        className="h-2 rounded-pill bg-accent-action"
                        style={{ width: `${percent}%` }}
                      />
                    </div>
                    <p className="mt-1 text-caption text-ink-muted">
                      Przeczytane rozdziały: {item.chapters_completed} z{" "}
                      {item.chapters_total}
                    </p>
                  </div>
                ) : null}
                <div className="mt-5 flex flex-wrap gap-3">
                  <Link
                    className="inline-flex min-h-touch items-center rounded-pill bg-accent-action px-5 text-label font-bold text-surface"
                    href={
                      item.kind === "audiobook"
                        ? `/konto/odtwarzacz/${item.id}`
                        : `/konto/czytnik/${item.id}`
                    }
                  >
                    {item.kind === "audiobook" ? "Słuchaj" : "Czytaj"}
                  </Link>
                  {files
                    .filter((file) => file.kind === "pdf")
                    .map((file) => (
                      <DownloadButton
                        key={file.id}
                        entitlementId={item.id}
                        fileId={file.id}
                        label="Pobierz PDF"
                      />
                    ))}
                </div>
              </li>
            );
          })}
        </ul>
      ) : null}
    </main>
  );
}

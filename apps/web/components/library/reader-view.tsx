"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { ContentBlocks } from "@/components/library/content-blocks";
import { DownloadButton } from "@/components/library/download-button";
import {
  tokenQuery,
  type ChapterContent,
  type EntitlementDetail,
} from "@/components/library/library-types";
import { apiJson, ClientApiError } from "@/lib/client-api";

const SCALES = [80, 90, 100, 115, 130, 150, 175, 200];

export function ReaderView({
  entitlementId,
  orderToken,
}: {
  entitlementId: string;
  orderToken: string | null;
}) {
  const q = tokenQuery(orderToken);
  const [detail, setDetail] = useState<EntitlementDetail | null>(null);
  const [chapter, setChapter] = useState<ChapterContent | null>(null);
  const [position, setPosition] = useState(0);
  const [scale, setScale] = useState(100);
  const [completed, setCompleted] = useState<number[]>([]);
  const [error, setError] = useState("");
  const heading = useRef<HTMLHeadingElement>(null);
  const initialised = useRef(false);

  const save = useCallback(
    async (body: Record<string, unknown>) => {
      try {
        await apiJson(`/library/entitlements/${entitlementId}/progress${q}`, {
          method: "PUT",
          json: body,
        });
      } catch {
        /* progress is a convenience; reading must never break because of it */
      }
    },
    [entitlementId, q],
  );

  useEffect(() => {
    (async () => {
      try {
        const info = await apiJson<EntitlementDetail>(
          `/library/entitlements/${entitlementId}${q}`,
        );
        setDetail(info);
        setPosition(
          Math.min(
            info.progress.position,
            Math.max(0, info.reader_chapters.length - 1),
          ),
        );
        setScale(info.progress.font_scale);
        setCompleted(info.progress.completed);
        initialised.current = true;
      } catch (caught) {
        if (
          caught instanceof ClientApiError &&
          caught.status === 401 &&
          !orderToken
        ) {
          window.location.assign(
            `/konto?next=${encodeURIComponent(`/konto/czytnik/${entitlementId}`)}`,
          );
          return;
        }
        setError(
          caught instanceof Error
            ? caught.message
            : "Nie udało się otworzyć materiału.",
        );
      }
    })();
  }, [entitlementId, q, orderToken]);

  useEffect(() => {
    if (!detail || !initialised.current || detail.reader_chapters.length === 0)
      return;
    let cancelled = false;
    (async () => {
      try {
        const content = await apiJson<ChapterContent>(
          `/library/entitlements/${entitlementId}/chapters/${position}${q}`,
        );
        if (cancelled) return;
        setChapter(content);
        heading.current?.focus();
        void save({ position });
      } catch (caught) {
        if (!cancelled)
          setError(
            caught instanceof Error
              ? caught.message
              : "Nie udało się wczytać rozdziału.",
          );
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [detail, position, entitlementId, q, save]);

  function go(next: number) {
    if (!detail) return;
    if (next > position && !completed.includes(position)) {
      setCompleted((value) => [...value, position].sort((a, b) => a - b));
      void save({ position: next, completed_position: position });
    }
    setPosition(Math.max(0, Math.min(next, detail.reader_chapters.length - 1)));
  }

  function finish() {
    if (completed.includes(position)) return;
    setCompleted((value) => [...value, position].sort((a, b) => a - b));
    void save({ position, completed_position: position });
  }

  function changeScale(delta: number) {
    const index = SCALES.indexOf(scale);
    const next =
      SCALES[Math.max(0, Math.min(SCALES.length - 1, index + delta))] ?? scale;
    setScale(next);
    void save({ position, font_scale: next });
  }

  if (error)
    return (
      <Shell>
        <Alert variant="error">{error}</Alert>
        <Link
          className="mt-4 inline-block text-accent-action underline"
          href="/konto/biblioteka"
        >
          Wróć do biblioteki
        </Link>
      </Shell>
    );
  if (!detail)
    return (
      <Shell>
        <p role="status" aria-busy="true">
          Otwieramy materiał…
        </p>
      </Shell>
    );
  if (detail.reader_chapters.length === 0)
    return (
      <Shell>
        <h1 className="font-display text-title text-ink">{detail.title}</h1>
        <p className="mt-3 text-body text-ink-muted">
          Wersja do czytania w przeglądarce nie jest jeszcze dostępna dla tego
          materiału. Możesz pobrać plik PDF.
        </p>
        <div className="mt-4 flex gap-3">
          {detail.files
            .filter((f) => f.kind === "pdf")
            .map((file) => (
              <DownloadButton
                key={file.id}
                entitlementId={entitlementId}
                fileId={file.id}
                orderToken={orderToken}
                label="Pobierz PDF"
              />
            ))}
        </div>
      </Shell>
    );

  const total = detail.reader_chapters.length;
  const percent = Math.round((completed.length / total) * 100);
  const isPdf = detail.reader_mode === "pdf";
  const pdfFiles = detail.files.filter((f) => f.kind === "pdf");
  const pageUrl = (page: number) =>
    `/api/library/entitlements/${entitlementId}/pages/${page}${q}`;
  const currentMeta = detail.reader_chapters[position];
  const pagesRead = detail.total_pages
    ? Math.round((completed.length / total) * detail.total_pages)
    : null;

  return (
    <div className="flex min-h-screen flex-col-reverse bg-surface text-ink lg:grid lg:grid-cols-[19rem_minmax(0,1fr)]">
      <aside
        aria-label="Spis treści"
        className="border-t border-border p-5 lg:min-h-screen lg:border-b-0 lg:border-r lg:border-t-0"
      >
        <p className="font-display text-emphasis">{detail.title}</p>
        {detail.author ? (
          <p className="text-body-small text-ink-muted">{detail.author}</p>
        ) : null}
        <div
          role="progressbar"
          aria-label="Postęp czytania"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percent}
          className="mt-5 h-2 rounded-pill bg-surface-muted"
        >
          <div
            className="h-2 rounded-pill bg-accent-action"
            style={{ width: `${percent}%` }}
          />
        </div>
        <p className="mt-2 text-caption font-bold text-ink-muted">
          Ukończono {percent}% · zostało {100 - percent}%
        </p>
        <p className="text-caption text-ink-muted">
          {pagesRead !== null && detail.total_pages
            ? `Przeczytane ${pagesRead} z ${detail.total_pages} stron · `
            : ""}
          rozdziały: {completed.length} z {total}
        </p>
        {pdfFiles.length ? (
          <div className="mt-4 space-y-2">
            {pdfFiles.map((file) => (
              <DownloadButton
                key={file.id}
                entitlementId={entitlementId}
                fileId={file.id}
                orderToken={orderToken}
                label="Pobierz PDF"
              />
            ))}
          </div>
        ) : null}
        <h2 className="mt-6 text-caption font-bold tracking-wide text-ink-muted">
          SPIS TREŚCI
        </h2>
        <ol className="mt-2 space-y-1">
          {detail.reader_chapters.map((item) => (
            <li key={item.position}>
              <button
                type="button"
                onClick={() => go(item.position)}
                aria-current={item.position === position ? "true" : undefined}
                className={`flex min-h-touch w-full items-center gap-3 rounded-control px-3 py-2 text-left font-body text-body-small focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action ${
                  item.position === position
                    ? "bg-ink text-surface"
                    : "hover:bg-surface-muted"
                }`}
              >
                <span
                  aria-hidden="true"
                  className="w-6 shrink-0 text-caption font-bold"
                >
                  {completed.includes(item.position)
                    ? "✓"
                    : String(item.position + 1).padStart(2, "0")}
                </span>
                <span>
                  {item.title}
                  {completed.includes(item.position) ? (
                    <span className="sr-only"> (przeczytany)</span>
                  ) : null}
                </span>
              </button>
            </li>
          ))}
        </ol>
        <Link
          href="/konto/biblioteka"
          className="mt-6 inline-flex min-h-touch items-center text-accent-action underline"
        >
          ← Wróć do biblioteki
        </Link>
      </aside>
      <main
        id="main-content"
        tabIndex={-1}
        className="min-w-0 focus:outline-none"
      >
        <div className="flex items-center justify-between gap-4 border-b border-border px-5 py-3">
          <div className="flex min-w-0 items-center gap-3">
            <Link
              className="inline-flex min-h-touch items-center text-body-small font-semibold text-accent-action underline lg:hidden"
              href="/konto/biblioteka"
            >
              ← Biblioteka
            </Link>
            <p className="min-w-0 text-body-small font-bold">
              Rozdział {position + 1} z {total} · {currentMeta?.title}
            </p>
          </div>
          <div
            role="group"
            aria-label="Rozmiar tekstu"
            className={`flex gap-2 ${isPdf ? "hidden" : ""}`}
          >
            <button
              type="button"
              aria-label="Zmniejsz tekst"
              disabled={scale === SCALES[0]}
              onClick={() => changeScale(-1)}
              className="min-h-touch min-w-touch rounded-pill border border-border disabled:opacity-40"
            >
              −
            </button>
            <button
              type="button"
              aria-label="Powiększ tekst"
              disabled={scale === SCALES[SCALES.length - 1]}
              onClick={() => changeScale(1)}
              className="min-h-touch min-w-touch rounded-pill border border-border disabled:opacity-40"
            >
              +
            </button>
          </div>
        </div>
        <article
          className={`mx-auto px-5 py-10 ${isPdf ? "max-w-4xl" : "max-w-content"}`}
          style={isPdf ? undefined : { fontSize: `${scale}%` }}
        >
          <p className="text-caption font-bold tracking-wide text-accent-action">
            ROZDZIAŁ {position + 1}
          </p>
          <h1
            ref={heading}
            tabIndex={-1}
            className="mt-2 font-display text-title text-ink focus:outline-none"
          >
            {chapter?.title ?? currentMeta?.title}
          </h1>
          {chapter ? (
            <ContentBlocks
              blocks={chapter.blocks}
              pageUrl={isPdf ? pageUrl : undefined}
            />
          ) : (
            <p role="status" aria-busy="true" className="mt-6">
              Wczytujemy rozdział…
            </p>
          )}
          <nav
            aria-label="Rozdziały"
            className="mt-12 flex justify-between gap-4 border-t border-border pt-6"
          >
            <button
              type="button"
              onClick={() => go(position - 1)}
              disabled={position === 0}
              className="min-h-touch rounded-pill border border-ink px-5 font-interface text-label font-bold disabled:opacity-40"
            >
              ← Poprzedni rozdział
            </button>
            {position >= total - 1 ? (
              <button
                type="button"
                onClick={finish}
                disabled={completed.includes(position)}
                className="min-h-touch rounded-pill bg-accent-action px-5 font-interface text-label font-bold text-surface disabled:opacity-60"
              >
                {completed.includes(position)
                  ? "Ukończono ✓"
                  : "Zakończ i oznacz jako ukończony"}
              </button>
            ) : (
              <button
                type="button"
                onClick={() => go(position + 1)}
                className="min-h-touch rounded-pill bg-accent-action px-5 font-interface text-label font-bold text-surface"
              >
                Następny rozdział →
              </button>
            )}
          </nav>
          {chapter ? (
            <p className="mt-8 text-center text-body-small text-ink-muted">
              {chapter.footer}
            </p>
          ) : null}
        </article>
      </main>
    </div>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main
      id="main-content"
      tabIndex={-1}
      className="mx-auto w-full max-w-content px-4 py-14 focus:outline-none"
    >
      {children}
    </main>
  );
}

import Link from "next/link";
import { ContentBlocks } from "@/components/library/content-blocks";
import type { ContentPageData } from "@/lib/content-api";

const date = (value: string) =>
  new Intl.DateTimeFormat("pl-PL", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "Europe/Warsaw",
  }).format(new Date(value));

/** Published information page, or an honest placeholder while the text is being prepared. */
export function ContentPageView({
  page,
  fallbackTitle,
}: {
  page: ContentPageData | null;
  fallbackTitle: string;
}) {
  return (
    <main
      id="main-content"
      tabIndex={-1}
      className="mx-auto w-full max-w-content min-w-0 px-4 py-10 focus:outline-none sm:py-14"
    >
      <h1 className="font-display text-title text-ink">
        {page?.title ?? fallbackTitle}
      </h1>
      {page ? (
        <>
          {page.summary ? (
            <p className="mt-3 text-body text-ink-muted">{page.summary}</p>
          ) : null}
          <div className="mt-6">
            <ContentBlocks blocks={page.blocks} />
          </div>
          <p className="mt-10 text-caption text-ink-muted">
            Ostatnia aktualizacja: {date(page.updated_at)}
          </p>
        </>
      ) : (
        <>
          <p className="mt-4 text-body text-ink-muted">
            Ta treść jest w przygotowaniu. W razie pytań skorzystaj z centrum
            pomocy.
          </p>
          <Link
            className="mt-4 inline-flex min-h-touch items-center text-accent-action underline"
            href="/pomoc"
          >
            Centrum pomocy
          </Link>
        </>
      )}
    </main>
  );
}

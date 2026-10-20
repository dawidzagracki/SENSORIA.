import Link from "next/link";

export default function NotFoundPage() {
  return (
    <main
      className="mx-auto w-full max-w-content min-w-0 px-4 py-16 text-center focus:outline-none"
      id="main-content"
      tabIndex={-1}
    >
      <p className="font-display text-display text-accent" aria-hidden="true">
        404
      </p>
      <h1 className="mt-2 font-display text-title text-ink">
        Nie znaleziono strony
      </h1>
      <p className="mt-4 font-body text-body text-ink-muted">
        Ta strona nie istnieje albo została przeniesiona. Sprawdź adres lub wróć
        do sklepu.
      </p>
      <nav
        aria-label="Co dalej"
        className="mt-8 flex flex-wrap justify-center gap-3"
      >
        <Link
          className="inline-flex min-h-touch items-center rounded-pill bg-accent-action px-6 text-label font-bold text-surface"
          href="/"
        >
          Strona główna
        </Link>
        <Link
          className="inline-flex min-h-touch items-center rounded-pill border border-accent-action px-6 text-label font-bold text-ink"
          href="/sklep"
        >
          Przejdź do sklepu
        </Link>
        <Link
          className="inline-flex min-h-touch items-center rounded-pill border border-border px-6 text-label font-bold text-ink"
          href="/pomoc"
        >
          Centrum pomocy
        </Link>
      </nav>
    </main>
  );
}

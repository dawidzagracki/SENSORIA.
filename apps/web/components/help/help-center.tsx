"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Accordion } from "@/components/ui/accordion";
import { Alert } from "@/components/ui/alert";
import { apiJson } from "@/lib/client-api";

type Help = {
  query: string;
  total: number;
  categories: Array<{
    name: string;
    items: Array<{ id: string; question: string; answer: string }>;
  }>;
  contact: { email: string | null; phone: string | null };
};

export function HelpCenter() {
  const [query, setQuery] = useState("");
  const [data, setData] = useState<Help | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const timer = window.setTimeout(
      async () => {
        try {
          setError("");
          setData(
            await apiJson<Help>(
              `/help${query.trim() ? `?q=${encodeURIComponent(query.trim())}` : ""}`,
            ),
          );
        } catch {
          setError("Nie udało się wczytać pytań. Spróbuj ponownie.");
        }
      },
      query ? 250 : 0,
    );
    return () => window.clearTimeout(timer);
  }, [query]);

  return (
    <main
      id="main-content"
      tabIndex={-1}
      className="mx-auto w-full max-w-page-shell min-w-0 px-4 py-10 focus:outline-none sm:py-14"
    >
      <p className="text-caption font-bold tracking-wide text-accent-action">
        CENTRUM POMOCY
      </p>
      <h1 className="mt-2 font-display text-title text-ink">
        Jak możemy pomóc?
      </h1>
      <form
        role="search"
        className="mt-6 max-w-content"
        onSubmit={(e) => e.preventDefault()}
      >
        <label className="block text-label text-ink" htmlFor="help-search">
          Szukaj w pytaniach
        </label>
        <input
          id="help-search"
          type="search"
          value={query}
          maxLength={100}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="np. jak odebrać e-book"
          className="mt-2 min-h-touch w-full rounded-pill border border-border bg-surface px-5 text-body focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
        />
      </form>
      <nav
        aria-label="Najczęstsze sprawy"
        className="mt-6 flex flex-wrap gap-3 text-body-small"
      >
        {[
          ["/dostawa-i-platnosci", "Dostawa i płatności"],
          ["/pomoc/zwroty-i-reklamacje", "Zwroty i reklamacje"],
          ["/pomoc/odstapienie", "Odstąpienie od umowy"],
          ["/konto/biblioteka", "Moja biblioteka"],
          ["/konto/vouchery", "Moje vouchery"],
        ].map(([href, label]) => (
          <Link
            key={href}
            href={href as string}
            className="inline-flex min-h-touch items-center rounded-pill border border-border px-4 hover:bg-surface-muted"
          >
            {label}
          </Link>
        ))}
      </nav>
      {error ? (
        <div className="mt-6">
          <Alert variant="error">{error}</Alert>
        </div>
      ) : null}
      <div aria-live="polite" className="mt-8">
        {!data && !error ? <p role="status">Wczytujemy pytania…</p> : null}
        {data && data.total === 0 ? (
          <Alert variant="info">
            {query
              ? `Nie znaleźliśmy odpowiedzi dla „${query}”. Spróbuj innych słów albo napisz do nas.`
              : "Pytania są w przygotowaniu."}
          </Alert>
        ) : null}
        {data?.categories.map((category) => (
          <section
            key={category.name}
            className="mb-8"
            aria-labelledby={`cat-${category.name}`}
          >
            <h2
              id={`cat-${category.name}`}
              className="font-display text-subtitle text-ink"
            >
              {category.name}
            </h2>
            <div className="mt-3">
              <Accordion
                mode="multiple"
                defaultExpandedIds={
                  query ? category.items.map((i) => i.id) : []
                }
                items={category.items.map((item) => ({
                  id: item.id,
                  title: item.question,
                  content: (
                    <div className="space-y-3 font-body text-body">
                      {item.answer.split(/\n{2,}/).map((paragraph, i) => (
                        <p key={`${item.id}-${i}`}>{paragraph}</p>
                      ))}
                    </div>
                  ),
                }))}
              />
            </div>
          </section>
        ))}
      </div>
      <section
        aria-labelledby="contact"
        className="mt-10 rounded-card border border-border bg-surface-muted p-6"
      >
        <h2 id="contact" className="font-display text-subtitle text-ink">
          Nie znalazłaś odpowiedzi?
        </h2>
        <p className="mt-2 text-body text-ink-muted">
          Napisz lub zadzwoń — odpowiadamy w dni robocze.
        </p>
        <p className="mt-3 text-body">
          {data?.contact.email ? (
            <a
              className="text-accent-action underline"
              href={`mailto:${data.contact.email}`}
            >
              {data.contact.email}
            </a>
          ) : null}
          {data?.contact.phone ? <span> · {data.contact.phone}</span> : null}
          {!data?.contact.email && !data?.contact.phone ? (
            <span>Dane kontaktowe znajdziesz w stopce strony.</span>
          ) : null}
        </p>
      </section>
    </main>
  );
}

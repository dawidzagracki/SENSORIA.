import type { PublicReviews } from "@/lib/reviews-api";

function Stars({ value }: { value: number }) {
  return (
    <span aria-hidden="true" className="tracking-widest text-accent-action">
      {"★".repeat(value)}
      <span className="text-border">{"★".repeat(5 - value)}</span>
    </span>
  );
}

const date = (value: string) =>
  new Intl.DateTimeFormat("pl-PL", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "Europe/Warsaw",
  }).format(new Date(value));

/** Server-rendered, text-only review list; review text is never interpreted as markup. */
export function ProductReviews({ reviews }: { reviews: PublicReviews | null }) {
  if (!reviews) return null;
  const { summary } = reviews;
  return (
    <section
      aria-labelledby="reviews-title"
      className="mx-auto w-full max-w-page-shell min-w-0 px-4 py-10"
    >
      <h2 id="reviews-title" className="font-display text-title text-ink">
        Opinie
      </h2>
      {summary.count === 0 ? (
        <p className="mt-3 text-body text-ink-muted">
          Ten produkt nie ma jeszcze opinii. Opinię mogą dodać osoby, które go
          kupiły — dostaniesz od nas zaproszenie po zakupie, jeśli wyrazisz
          zgodę.
        </p>
      ) : (
        <>
          <div className="mt-4 flex flex-wrap items-center gap-6">
            <p className="font-display text-display text-ink">
              {String(summary.average).replace(".", ",")}
              <span className="sr-only"> na 5</span>
            </p>
            <div>
              <Stars value={Math.round(summary.average ?? 0)} />
              <p className="text-body-small text-ink-muted">
                {summary.count}{" "}
                {summary.count === 1
                  ? "opinia"
                  : summary.count < 5
                    ? "opinie"
                    : "opinii"}{" "}
                potwierdzonych zakupem
              </p>
            </div>
            <dl className="min-w-48 flex-1 space-y-1 text-caption">
              {[5, 4, 3, 2, 1].map((star) => {
                const n = summary.distribution[String(star)] ?? 0;
                return (
                  <div key={star} className="flex items-center gap-2">
                    <dt className="w-10">{star} ★</dt>
                    <dd className="flex flex-1 items-center gap-2">
                      <span
                        aria-hidden="true"
                        className="h-2 flex-1 rounded-pill bg-surface-muted"
                      >
                        <span
                          className="block h-2 rounded-pill bg-accent-action"
                          style={{ width: `${(n / summary.count) * 100}%` }}
                        />
                      </span>
                      <span>{n}</span>
                    </dd>
                  </div>
                );
              })}
            </dl>
          </div>
          <ul className="mt-8 grid gap-4 md:grid-cols-2">
            {reviews.items.map((review) => (
              <li
                key={review.id}
                className="rounded-card border border-border bg-surface p-5"
              >
                <p className="flex items-center gap-2">
                  <Stars value={review.rating} />
                  <span className="sr-only">Ocena {review.rating} z 5</span>
                </p>
                {review.title ? (
                  <h3 className="mt-2 font-display text-emphasis text-ink">
                    {review.title}
                  </h3>
                ) : null}
                <p className="mt-2 whitespace-pre-line font-body text-body text-ink">
                  {review.body}
                </p>
                <p className="mt-3 text-caption text-ink-muted">
                  {review.author} · {date(review.created_at)} · zakup
                  potwierdzony
                </p>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

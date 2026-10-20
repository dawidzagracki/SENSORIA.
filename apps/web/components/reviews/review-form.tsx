"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { TextField } from "@/components/ui/text-field";
import { apiJson, ClientApiError } from "@/lib/client-api";

type Eligible = {
  items: Array<{
    order_item_id: string;
    name: string | null;
    reviewed: boolean;
  }>;
};

export function ReviewForm({
  orderId,
  itemId,
  token,
}: {
  orderId: string | null;
  itemId: string | null;
  token: string | null;
}) {
  const [eligible, setEligible] = useState<Eligible | null>(null);
  const [selected, setSelected] = useState(itemId ?? "");
  const [rating, setRating] = useState(0);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fieldError, setFieldError] = useState<{
    rating?: string;
    body?: string;
  }>({});
  const [done, setDone] = useState(false);
  const q = token ? `&order_token=${encodeURIComponent(token)}` : "";

  useEffect(() => {
    if (!orderId) return;
    (async () => {
      try {
        const data = await apiJson<Eligible>(
          `/reviews/eligible?order_id=${encodeURIComponent(orderId)}${q}`,
        );
        setEligible(data);
        if (!itemId) {
          const first = data.items.find((i) => !i.reviewed);
          if (first) setSelected(first.order_item_id);
        }
      } catch (caught) {
        if (
          caught instanceof ClientApiError &&
          caught.status === 401 &&
          !token
        ) {
          window.location.assign(
            `/konto?next=${encodeURIComponent(`/opinie/nowa?order=${orderId}`)}`,
          );
          return;
        }
        setError(
          caught instanceof Error
            ? caught.message
            : "Nie udało się wczytać zamówienia.",
        );
      }
    })();
  }, [orderId, itemId, q, token]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const errors: { rating?: string; body?: string } = {};
    if (rating < 1) errors.rating = "Wybierz ocenę od 1 do 5 gwiazdek.";
    if (body.trim().length < 10)
      errors.body = "Opinia musi mieć co najmniej 10 znaków.";
    setFieldError(errors);
    if (Object.keys(errors).length || !orderId || !selected) return;
    setBusy(true);
    setError("");
    try {
      await apiJson(
        `/reviews${token ? `?order_token=${encodeURIComponent(token)}` : ""}`,
        {
          method: "POST",
          json: {
            order_id: orderId,
            order_item_id: selected,
            rating,
            title: title.trim() || null,
            body,
          },
        },
      );
      setDone(true);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Nie udało się zapisać opinii.",
      );
    } finally {
      setBusy(false);
    }
  }

  const heading = (
    <h1 className="font-display text-title text-ink">Twoja opinia</h1>
  );
  if (!orderId)
    return (
      <Wrapper>
        {heading}
        <div className="mt-4">
          <Alert variant="warning">
            Użyj linku z wiadomości e-mail albo przejdź do swoich zamówień.
          </Alert>
        </div>
      </Wrapper>
    );
  if (done)
    return (
      <Wrapper>
        {heading}
        <div className="mt-4">
          <Alert variant="success" title="Dziękujemy!">
            Opinia pojawi się na stronie produktu po moderacji.
          </Alert>
        </div>
        <Link
          className="mt-4 inline-flex min-h-touch items-center text-accent-action underline"
          href="/sklep"
        >
          Wróć do sklepu
        </Link>
      </Wrapper>
    );
  const open = eligible?.items.filter((i) => !i.reviewed) ?? [];
  return (
    <Wrapper>
      {heading}
      <p className="mt-2 text-body text-ink-muted">
        Opinie mogą dodawać tylko osoby, które kupiły produkt. Nie pokazujemy
        Twojego adresu e-mail.
      </p>
      {error ? (
        <div className="mt-4">
          <Alert variant="error">{error}</Alert>
        </div>
      ) : null}
      {eligible && open.length === 0 ? (
        <div className="mt-4">
          <Alert variant="info">
            Nie ma tu już produktów czekających na opinię albo zamówienie nie
            zostało opłacone.
          </Alert>
        </div>
      ) : null}
      {eligible && open.length > 0 ? (
        <form onSubmit={submit} noValidate className="mt-6 space-y-5">
          {open.length > 1 ? (
            <div>
              <label
                className="block text-label text-ink"
                htmlFor="review-item"
              >
                Produkt
              </label>
              <select
                id="review-item"
                value={selected}
                onChange={(e) => setSelected(e.target.value)}
                className="mt-2 min-h-touch w-full rounded-control border border-border bg-surface px-3"
              >
                {open.map((i) => (
                  <option key={i.order_item_id} value={i.order_item_id}>
                    {i.name}
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <p className="font-bold">{open[0]?.name}</p>
          )}
          <fieldset
            aria-describedby={fieldError.rating ? "rating-error" : undefined}
          >
            <legend className="text-label text-ink">Ocena</legend>
            <div className="mt-2 flex gap-2">
              {[1, 2, 3, 4, 5].map((value) => (
                <label key={value} className="relative">
                  <input
                    type="radio"
                    name="rating"
                    value={value}
                    checked={rating === value}
                    onChange={() => setRating(value)}
                    className="peer sr-only"
                  />
                  <span
                    aria-hidden="true"
                    className={`flex h-12 w-12 cursor-pointer items-center justify-center rounded-pill border text-body-small font-bold peer-focus-visible:ring-2 peer-focus-visible:ring-accent-action ${
                      rating >= value
                        ? "border-accent-action bg-accent-action text-surface"
                        : "border-border"
                    }`}
                  >
                    {value}★
                  </span>
                  <span className="sr-only">{value} z 5</span>
                </label>
              ))}
            </div>
            {fieldError.rating ? (
              <p
                id="rating-error"
                role="alert"
                className="mt-2 text-caption text-on-danger"
              >
                {fieldError.rating}
              </p>
            ) : null}
          </fieldset>
          <TextField
            label="Tytuł (opcjonalnie)"
            maxLength={120}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <Textarea
            label="Twoja opinia"
            required
            rows={6}
            maxLength={2000}
            value={body}
            onChange={(e) => setBody(e.target.value)}
            error={fieldError.body}
            hint="Od 10 do 2000 znaków. Opinia przejdzie moderację."
          />
          <Button type="submit" loading={busy} size="lg">
            Wyślij opinię
          </Button>
        </form>
      ) : null}
    </Wrapper>
  );
}

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <main
      id="main-content"
      tabIndex={-1}
      className="mx-auto w-full max-w-content min-w-0 px-4 py-10 focus:outline-none sm:py-14"
    >
      {children}
    </main>
  );
}

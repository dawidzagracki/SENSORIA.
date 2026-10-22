"use client";

import { useId, useState, type FormEvent } from "react";
import { InPostLogo } from "@/components/brand/logos";
import { VatBreakdown } from "@/components/cart/vat-breakdown";
import type { CartMutation, CartView } from "./cart-types";

function formatGrosz(value: number): string {
  if (!Number.isSafeInteger(value)) return "—";
  return `${Math.trunc(value / 100)},${String(Math.abs(value % 100)).padStart(2, "0")} zł`;
}

export function DiscountSummary({
  cart,
  mutate,
}: {
  cart: CartView;
  mutate: CartMutation;
}) {
  const inputId = useId();
  const errorId = useId();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const calculation = cart.calculation;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await runMutation("POST", "/discount", { code: code.trim() });
  }

  async function remove() {
    await runMutation("DELETE", "/discount");
  }

  async function runMutation(
    method: "POST" | "DELETE",
    path: string,
    body?: object,
  ) {
    setBusy(true);
    setError(null);
    try {
      await mutate(method, path, body);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Nie udało się zmienić kodu rabatowego.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      aria-labelledby="cart-summary-title"
      className="space-y-4 rounded-card border border-border bg-surface p-6"
    >
      <h2 id="cart-summary-title" className="font-display text-title text-ink">
        Podsumowanie
      </h2>
      <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1">
          <label htmlFor={inputId} className="mb-2 block text-label text-ink">
            Kod rabatowy
          </label>
          <input
            id={inputId}
            name="code"
            value={code}
            onChange={(event) => setCode(event.target.value)}
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? errorId : undefined}
            autoComplete="off"
            className="min-h-control-md w-full rounded-card border border-border bg-surface px-4 text-body text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
          />
        </div>
        <button
          type="submit"
          disabled={busy || !code.trim()}
          className="min-h-touch rounded-card border border-accent-action px-5 text-label text-ink disabled:opacity-60"
        >
          {busy ? "Sprawdzam…" : "Użyj"}
        </button>
      </form>
      {error ? (
        <p id={errorId} role="alert" className="text-body text-on-danger">
          {error}
        </p>
      ) : null}
      {cart.discount_code ? (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-body text-on-success">
            Kod {cart.discount_code} został przypisany.
          </p>
          <button
            type="button"
            onClick={remove}
            disabled={busy}
            className="min-h-touch rounded-card px-3 text-label text-ink underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
          >
            Usuń kod
          </button>
        </div>
      ) : null}
      {cart.discount_notice ? (
        <p role="status" className="text-body text-on-warning">
          {cart.discount_notice}
        </p>
      ) : null}
      {cart.delivery.requires_shipping ? (
        <fieldset className="space-y-3 border-b border-border pb-4">
          <legend className="text-label text-ink">Metoda dostawy</legend>
          {cart.delivery.available_quotes.map((quote) => (
            <label
              key={quote.method}
              className="flex min-h-touch cursor-pointer items-center justify-between gap-3 rounded-card border border-border p-3 text-body text-ink focus-within:outline focus-within:outline-2 focus-within:outline-accent"
            >
              <span className="flex min-w-0 items-center gap-3">
                <input
                  type="radio"
                  name="delivery-method"
                  value={quote.method}
                  checked={cart.delivery.selected_method === quote.method}
                  disabled={busy}
                  onChange={() =>
                    void mutate("PATCH", "/delivery", {
                      method: quote.method,
                    }).catch((cause: unknown) =>
                      setError(
                        cause instanceof Error
                          ? cause.message
                          : "Nie udało się wybrać dostawy.",
                      ),
                    )
                  }
                />
                <span>
                  {quote.method === "parcel_locker"
                    ? "Paczkomat InPost"
                    : quote.method === "pickup_in_person"
                      ? "Odbiór w gabinecie"
                      : "Kurier"}
                </span>
              </span>
              <span className="flex shrink-0 items-center gap-3 text-label">
                {quote.method === "pickup_in_person" ? null : (
                  <InPostLogo className="h-6" />
                )}
                {formatGrosz(quote.gross_grosz)}
              </span>
            </label>
          ))}
          {cart.delivery.message ? (
            <p className="text-body text-ink" role="status">
              {cart.delivery.message}
            </p>
          ) : null}
          {cart.delivery.requires_method_selection ? (
            <p className="text-caption text-ink-muted">
              Wybierz metodę, aby potwierdzić koszt dostawy i sumę.
            </p>
          ) : null}
        </fieldset>
      ) : null}
      <dl className="space-y-2 border-t border-border pt-4 text-body text-ink">
        <div className="flex justify-between gap-4">
          <dt>Produkty</dt>
          <dd>
            {formatGrosz(calculation.products_gross_before_discount_grosz)}
          </dd>
        </div>
        {calculation.discount_grosz > 0 ? (
          <div className="flex justify-between gap-4">
            <dt>Rabat</dt>
            <dd>−{formatGrosz(calculation.discount_grosz)}</dd>
          </div>
        ) : null}
        {cart.delivery.requires_shipping && cart.delivery.selected_method ? (
          <div className="flex justify-between gap-4">
            <dt>
              Dostawa ·{" "}
              {cart.delivery.selected_method === "parcel_locker"
                ? "paczkomat"
                : "kurier"}
            </dt>
            <dd>{formatGrosz(calculation.delivery.gross_grosz)}</dd>
          </div>
        ) : null}
        <div className="flex justify-between gap-4 border-t border-border pt-3 font-semibold">
          <dt>
            {calculation.amount_due_is_final ? "Razem" : "Suma produktów"}
          </dt>
          <dd>{formatGrosz(calculation.amount_due_grosz)}</dd>
        </div>
        {!calculation.amount_due_is_final ? (
          <p className="text-caption text-ink-muted">
            Wybierz metodę dostawy, aby poznać końcową sumę.
          </p>
        ) : null}
      </dl>
      <VatBreakdown
        deliveryTaxGrosz={calculation.delivery.tax_grosz}
        deliveryVatLabel={calculation.delivery.vat_label}
        exemptGrossGrosz={calculation.exempt.gross_grosz}
        format={formatGrosz}
        groups={calculation.vat_groups}
      />
      <p className="text-caption text-ink-muted">
        Kwoty i rabat są obliczane przez serwer.
      </p>
    </section>
  );
}

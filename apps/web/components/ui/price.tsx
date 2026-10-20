import type { VatRate } from "../../types/money";
import { formatMoney } from "../../lib/format-money";

export type PriceProps = {
  amountInGrosze: number;
  previousAmountInGrosze?: number;
  /**
   * Omnibus: lowest price from the 30 days before the reduction. `undefined` means the caller
   * does not track it; `null` means it could not be established, so the reduction is not shown.
   */
  lowestPriceInGrosze?: number | null;
  vatRate?: VatRate;
};

export function Price({
  amountInGrosze,
  previousAmountInGrosze,
  lowestPriceInGrosze,
  vatRate,
}: PriceProps) {
  const formattedAmount = formatMoney(amountInGrosze);
  const formattedPrevious =
    previousAmountInGrosze === undefined || lowestPriceInGrosze === null
      ? undefined
      : formatMoney(previousAmountInGrosze);
  const formattedLowest =
    formattedPrevious && typeof lowestPriceInGrosze === "number"
      ? formatMoney(lowestPriceInGrosze)
      : undefined;

  return (
    <span className="inline-flex flex-wrap items-baseline gap-2">
      <strong className="font-interface text-subtitle font-bold text-ink">
        {formattedAmount}
      </strong>
      {formattedPrevious ? (
        <span className="text-caption text-ink-muted">
          <span className="sr-only">Poprzednia cena: </span>
          <s>{formattedPrevious}</s>
        </span>
      ) : null}
      {formattedLowest ? (
        <span className="basis-full text-caption text-ink-muted">
          Najniższa cena z 30 dni przed obniżką: {formattedLowest}
        </span>
      ) : null}
      {vatRate === "EXEMPT" ? (
        <span className="text-caption text-ink-muted">zw. z VAT</span>
      ) : vatRate ? (
        <span className="text-caption text-ink-muted">
          VAT{" "}
          {vatRate === "RATE_23"
            ? "23%"
            : vatRate === "RATE_8"
              ? "8%"
              : vatRate === "RATE_5"
                ? "5%"
                : "0%"}
        </span>
      ) : null}
    </span>
  );
}

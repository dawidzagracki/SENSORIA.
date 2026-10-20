import type { VatRate } from "../../types/money";
import { formatMoney } from "../../lib/format-money";

export type PriceProps = {
  amountInGrosze: number;
  previousAmountInGrosze?: number;
  vatRate?: VatRate;
};

export function Price({
  amountInGrosze,
  previousAmountInGrosze,
  vatRate,
}: PriceProps) {
  const formattedAmount = formatMoney(amountInGrosze);
  const formattedPrevious =
    previousAmountInGrosze === undefined
      ? undefined
      : formatMoney(previousAmountInGrosze);

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

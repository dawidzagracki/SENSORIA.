type VatGroup = {
  vat_rate: string;
  vat_label: string;
  gross_grosz: number;
  tax_grosz: number;
};

type VatBreakdownProps = {
  groups: VatGroup[];
  exemptGrossGrosz: number;
  deliveryTaxGrosz?: number;
  deliveryVatLabel?: string | null;
  format: (grosz: number) => string;
};

export function VatBreakdown({
  groups,
  exemptGrossGrosz,
  deliveryTaxGrosz = 0,
  deliveryVatLabel = null,
  format,
}: VatBreakdownProps) {
  const rows = groups
    .filter((group) => group.gross_grosz > 0)
    .map((group) => ({
      key: group.vat_rate,
      label: group.vat_label,
      value: group.tax_grosz,
    }));
  if (deliveryTaxGrosz > 0 && deliveryVatLabel) {
    rows.push({
      key: "delivery",
      label: `${deliveryVatLabel} (dostawa)`,
      value: deliveryTaxGrosz,
    });
  }
  if (!rows.length && exemptGrossGrosz <= 0) {
    return null;
  }
  const total = rows.reduce((sum, row) => sum + row.value, 0);
  return (
    <details className="group rounded-control bg-surface-muted px-3 py-2 text-caption text-ink">
      <summary className="flex min-h-touch cursor-pointer list-none items-center justify-between gap-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action [&::-webkit-details-marker]:hidden">
        <span>W tym VAT (szczegóły)</span>
        <span className="font-semibold">{format(total)}</span>
      </summary>
      <ul className="space-y-1 border-t border-border pb-1 pt-2">
        {rows.map((row) => (
          <li className="flex justify-between gap-3" key={row.key}>
            <span>stawka {row.label}</span>
            <span>{format(row.value)}</span>
          </li>
        ))}
        {exemptGrossGrosz > 0 ? (
          <li className="flex justify-between gap-3">
            <span>sprzedaż zwolniona z VAT</span>
            <span>{format(exemptGrossGrosz)}</span>
          </li>
        ) : null}
      </ul>
    </details>
  );
}

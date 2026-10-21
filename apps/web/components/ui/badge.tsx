import {
  colorTokens,
  productTypeTokens,
  badgeTokens,
} from "../../tailwind.config";

export type ProductBadgeLabel = (typeof productTypeTokens)[number]["label"];
export type StatusBadgeLabel = (typeof badgeTokens)[number]["label"];
export type BadgeLabel = ProductBadgeLabel | StatusBadgeLabel;

export type BadgeProps = {
  label: BadgeLabel;
};

export function Badge({ label }: BadgeProps) {
  const token = [...productTypeTokens, ...badgeTokens].find(
    (candidate) => candidate.label === label,
  );
  if (!token) throw new Error(`Brak tokenu etykiety: ${label}`);

  return (
    <span
      className="inline-flex items-center whitespace-nowrap rounded-pill px-3 py-1 font-interface text-eyebrow font-bold tracking-caps"
      style={{
        backgroundColor: colorTokens[token.background].value,
        color: colorTokens[token.foreground].value,
      }}
    >
      {label}
    </span>
  );
}

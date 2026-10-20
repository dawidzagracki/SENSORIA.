import Link from "next/link";

export type BreadcrumbItem = {
  href?: string;
  label: string;
};

export type BreadcrumbsProps = {
  items: [BreadcrumbItem, ...BreadcrumbItem[]];
  label?: string;
};

export function Breadcrumbs({
  items,
  label = "Okruszki nawigacyjne",
}: BreadcrumbsProps) {
  return (
    <nav aria-label={label}>
      <ol className="flex flex-wrap items-center gap-2 text-caption text-ink-muted">
        {items.map((item, index) => {
          const current = index === items.length - 1;
          return (
            <li
              className="flex min-h-touch items-center gap-2"
              key={`${item.label}-${index}`}
            >
              {current ? (
                <span aria-current="page" className="text-ink">
                  {item.label}
                </span>
              ) : item.href ? (
                <Link
                  className="inline-flex min-h-touch items-center rounded-card px-2 underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
                  href={item.href}
                >
                  {item.label}
                </Link>
              ) : (
                <span>{item.label}</span>
              )}
              {!current ? <span aria-hidden="true">/</span> : null}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

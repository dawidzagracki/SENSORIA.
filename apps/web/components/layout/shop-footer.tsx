import Link from "next/link";
import { InPostLogo, PaymentLogos, StripeLogo } from "../brand/logos";
import { BrandLogo } from "./brand-logo";
import { CookiePreferencesAction } from "./cookie-preferences-action";
import { copyrightText, footerColumns } from "./site-config";

export function ShopFooter({ demoEnabled }: { demoEnabled: boolean }) {
  return (
    <footer className="bg-footer">
      <div className="mx-auto grid max-w-page-shell grid-cols-1 gap-8 px-4 py-12 sm:grid-cols-2 lg:grid-cols-4 lg:gap-12">
        {footerColumns.map((column, index) => (
          <section
            aria-labelledby={`footer-column-${index}`}
            key={column.title}
          >
            <h2
              className="uppercase-label mb-4 text-ink"
              id={`footer-column-${index}`}
            >
              {column.title}
            </h2>
            {column.kind === "brand" ? (
              <div className="space-y-2 text-body-small text-ink-muted">
                {column.items.map((item, index) =>
                  item.href ? (
                    <Link
                      className="inline-flex min-h-touch items-center rounded-card text-[26px] leading-none text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
                      href={item.href}
                      key={item.label}
                    >
                      <BrandLogo />
                    </Link>
                  ) : (
                    <p key={`${item.label}-${index}`}>{item.label}</p>
                  ),
                )}
              </div>
            ) : (
              <nav aria-label={`Stopka: ${column.title}`}>
                <ul className="space-y-1 text-body-small">
                  {column.items.map((item) => (
                    <li key={item.label}>
                      {item.label === "Ustawienia cookies" ? (
                        <CookiePreferencesAction demoEnabled={demoEnabled} />
                      ) : item.href ? (
                        <Link
                          className="inline-flex min-h-touch items-center rounded-card text-ink-muted underline-offset-4 hover:text-ink hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
                          href={item.href}
                        >
                          {item.label}
                        </Link>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </nav>
            )}
          </section>
        ))}
      </div>
      <div className="border-t border-border">
        <div className="mx-auto flex max-w-page-shell flex-wrap items-center gap-x-8 gap-y-4 px-4 py-6">
          <div className="flex flex-wrap items-center gap-3">
            <span className="uppercase-label text-ink-muted">Płatności</span>
            <PaymentLogos />
            <StripeLogo />
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="uppercase-label text-ink-muted">Dostawa</span>
            <InPostLogo />
          </div>
        </div>
      </div>
      <div className="border-t border-border">
        <div className="mx-auto flex max-w-page-shell flex-wrap items-center justify-between gap-3 px-4 py-4 text-caption text-ink-muted">
          <p>{copyrightText}</p>
          <p>sensoria.shop</p>
        </div>
      </div>
    </footer>
  );
}

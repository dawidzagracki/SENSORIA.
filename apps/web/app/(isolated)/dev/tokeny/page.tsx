import { notFound } from "next/navigation";
import { UiGallery } from "@/components/ui-gallery";
import { contrastRatio } from "@/lib/contrast";
import {
  breakpointTokens,
  colorTokens,
  contrastPairs,
  fontTokens,
  gradientTokens,
  letterSpacingTokens,
  productTypeTokens,
  radiusTokens,
  shadowTokens,
  spacingTokens,
  statusLabelTokens,
  typographyTokens,
} from "@/tailwind.config";

export const dynamic = "force-dynamic";

const familyClasses = {
  display: "font-display",
  body: "font-body",
  interface: "font-interface",
  decorative: "font-decorative italic",
} as const;

export default function TokenPreviewPage() {
  if (process.env.ENVIRONMENT !== "development") {
    notFound();
  }

  return (
    <main className="page-shell space-y-8" id="main-content" tabIndex={-1}>
      <header className="space-y-2">
        <h1 className="font-display text-title font-bold">
          Tokeny i komponenty interfejsu
        </h1>
        <p className="text-body-small">
          Źródła: 01-katalog-desktop.pdf i 08-produkt-ebook-desktop.pdf.
          Przypisania kolorów typów produktów, cienie i tracking są propozycjami
          poza źródłami PDF.
        </p>
      </header>

      <section aria-labelledby="palette-title" className="space-y-4">
        <h2
          className="font-interface text-subtitle font-bold"
          id="palette-title"
        >
          Kolory semantyczne
        </h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Object.entries(colorTokens).map(([name, token]) => (
            <article
              className="rounded-card border border-border p-4"
              key={name}
            >
              <div
                aria-label={`${name}: ${token.value}`}
                className="h-8 rounded-pill border border-border"
                role="img"
                style={{ backgroundColor: token.value }}
              />
              <h3 className="mt-3 font-interface text-label font-bold">
                {name}
              </h3>
              <p className="font-interface text-caption">{token.value}</p>
              <p className="mt-2 text-body-small">{token.role}</p>
              <p className="mt-2 text-caption">Źródło: {token.source}</p>
            </article>
          ))}
        </div>
      </section>

      <section aria-labelledby="gradient-title" className="space-y-4">
        <h2
          className="font-interface text-subtitle font-bold"
          id="gradient-title"
        >
          Gradient z makiety
        </h2>
        <div
          className="rounded-card border border-border p-4 text-ink"
          style={{
            backgroundImage: `linear-gradient(${gradientTokens.footer.direction}, ${gradientTokens.footer.start}, ${gradientTokens.footer.end})`,
          }}
        >
          <p className="font-interface text-label font-bold">
            Stopka — tekst ink
          </p>
          <p className="text-body-small">{gradientTokens.footer.source}</p>
          <p className="text-caption">
            ink:{" "}
            {contrastRatio(
              colorTokens.ink.value,
              gradientTokens.footer.start,
            ).toFixed(2)}
            :1 /{" "}
            {contrastRatio(
              colorTokens.ink.value,
              gradientTokens.footer.end,
            ).toFixed(2)}
            :1; ink-muted:{" "}
            {contrastRatio(
              colorTokens["ink-muted"].value,
              gradientTokens.footer.start,
            ).toFixed(2)}
            :1 /{" "}
            {contrastRatio(
              colorTokens["ink-muted"].value,
              gradientTokens.footer.end,
            ).toFixed(2)}
            :1.
          </p>
        </div>
        <p className="text-body-small">
          Pozostałe wykryte gradienty są na ilustracjach/okładkach produktów i
          nie należą do palety interfejsu. Przezroczyste obiekty PDF nie zostały
          przypisane do par tekst/tło bez potwierdzenia, że podkładają tło pod
          tekst.
        </p>
      </section>

      <section aria-labelledby="contrast-title" className="space-y-4">
        <h2
          className="font-interface text-subtitle font-bold"
          id="contrast-title"
        >
          Zestawienia i kontrast WCAG
        </h2>
        <ul className="space-y-3">
          {contrastPairs.map((pair) => {
            const foreground = colorTokens[pair.foreground];
            const background = colorTokens[pair.background];
            const ratio = contrastRatio(foreground.value, background.value);

            return (
              <li
                className="rounded-card border border-border p-4"
                key={`${pair.foreground}-${pair.background}`}
                style={{
                  backgroundColor: background.value,
                  color:
                    "status" in pair && pair.status === "blocked"
                      ? colorTokens.ink.value
                      : foreground.value,
                }}
              >
                <p className="font-interface text-label font-bold">
                  {pair.foreground} na {pair.background}: {ratio.toFixed(2)}:1
                </p>
                <p className="text-body-small">{pair.source}</p>
                <p className="text-caption">
                  Zwykły tekst wymaga 4,5:1; duży tekst 3:1.
                </p>
                {"status" in pair && pair.status === "blocked" ? (
                  <p className="font-interface text-label font-bold">
                    Niedozwolone dla etykiety; używamy ciemnego ink.
                  </p>
                ) : null}
              </li>
            );
          })}
          {productTypeTokens.map((product) => {
            const foreground = colorTokens[product.foreground];
            const background = colorTokens[product.background];
            const ratio = contrastRatio(foreground.value, background.value);

            return (
              <li
                className="rounded-card border border-border p-4"
                key={product.label}
                style={{
                  backgroundColor: background.value,
                  color: foreground.value,
                }}
              >
                <p className="font-interface text-label font-bold">
                  {product.label}: {ratio.toFixed(2)}:1
                </p>
                <p className="text-caption">{product.source}</p>
                {product.status === "proposal" ? (
                  <p className="font-interface text-label font-bold">
                    Propozycja przypisania koloru; PDF nie rozróżniają typów.
                  </p>
                ) : null}
              </li>
            );
          })}
        </ul>
      </section>

      <section aria-labelledby="type-title" className="space-y-4">
        <h2 className="font-interface text-subtitle font-bold" id="type-title">
          Typografia
        </h2>
        <p className="text-body-small">
          Nazwy rodzin odczytane z osadzonych fontów PDF. Plików pełnych fontów
          nie znaleziono w repozytorium; lokalne ładowanie wymaga ich
          dostarczenia.
        </p>
        <ul className="space-y-2">
          {fontTokens.map((font) => (
            <li className="text-body-small" key={font.role}>
              <strong>{font.role}:</strong> {font.family}, {font.style}.{" "}
              {font.source}
            </li>
          ))}
        </ul>
        <div className="space-y-3">
          {typographyTokens.map((type) => (
            <div className="border-b border-border pb-3" key={type.role}>
              <p className="font-interface text-caption">
                {type.role} · {type.size} · line-height {type.lineHeight}
              </p>
              <p
                className={familyClasses[type.family]}
                style={{ fontSize: type.size, lineHeight: type.lineHeight }}
              >
                Zażółć gęślą jaźń — ąćęłńóśźż
              </p>
              <p className="text-caption">{type.source}</p>
            </div>
          ))}
        </div>
        <p className="uppercase-label">Kategorie · Pytania · Szczegóły</p>
        <p className="text-caption">
          Letter-spacing: {letterSpacingTokens[0].value} —{" "}
          {letterSpacingTokens[0].source}
        </p>
      </section>

      <section aria-labelledby="spacing-title" className="space-y-4">
        <h2
          className="font-interface text-subtitle font-bold"
          id="spacing-title"
        >
          Odstępy — skala 4 px
        </h2>
        <ul className="space-y-2">
          {spacingTokens.map((space) => (
            <li className="flex items-center gap-3" key={space.name}>
              <span className="w-16 font-interface text-caption">
                {space.name}: {space.value}
              </span>
              <span
                aria-hidden="true"
                className="block h-4 bg-accent"
                style={{ width: space.value }}
              />
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="breakpoint-title" className="space-y-4">
        <h2
          className="font-interface text-subtitle font-bold"
          id="breakpoint-title"
        >
          Breakpointy
        </h2>
        <ul className="space-y-2">
          {breakpointTokens.map((breakpoint) => (
            <li
              className="font-interface text-body-small"
              key={breakpoint.name}
            >
              {breakpoint.name}: {breakpoint.value}
            </li>
          ))}
        </ul>
        <p className="w-full rounded-card bg-surface-muted p-4 sm:font-bold md:max-w-content lg:max-w-wide xl:max-w-page-shell">
          Szerokość tej próbki reaguje na ustawione breakpointy.
        </p>
      </section>

      <section aria-labelledby="shape-title" className="space-y-4">
        <h2 className="font-interface text-subtitle font-bold" id="shape-title">
          Zaokrąglenia i cienie
        </h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {radiusTokens.map((radius) => (
            <div
              className="border border-border bg-surface-muted p-4"
              key={radius.name}
              style={{ borderRadius: radius.value }}
            >
              {radius.name}: {radius.value}. {radius.source}
            </div>
          ))}
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {shadowTokens.map((shadow) => (
            <div
              className="rounded-card bg-surface p-4"
              key={shadow.name}
              style={{ boxShadow: shadow.value }}
            >
              {shadow.name}: {shadow.value}. {shadow.source}
            </div>
          ))}
        </div>
      </section>

      <section aria-labelledby="product-title" className="space-y-4">
        <h2
          className="font-interface text-subtitle font-bold"
          id="product-title"
        >
          Typy produktów
        </h2>
        <div className="flex flex-wrap gap-3">
          {productTypeTokens.map((product) => (
            <span
              className="rounded-pill px-3 py-2 font-interface text-label font-bold"
              key={product.label}
              style={{
                backgroundColor: colorTokens[product.background].value,
                color: colorTokens[product.foreground].value,
              }}
            >
              {product.label}
            </span>
          ))}
        </div>
        <p className="text-body-small">
          Każdy typ ma inną parę tokenów. Przypisania są propozycjami — PDF-y
          pokazują etykiety, ale nie definiują osobnych kolorów dla typów.
        </p>
        <div className="flex flex-wrap gap-3">
          {statusLabelTokens.map((status) => (
            <span
              className="rounded-pill px-3 py-2 font-interface text-label font-bold"
              key={status.label}
              style={{
                backgroundColor: colorTokens[status.background].value,
                color: colorTokens[status.foreground].value,
              }}
            >
              {status.label}
            </span>
          ))}
        </div>
      </section>
      <section aria-labelledby="components-title" className="space-y-4">
        <h2
          className="font-interface text-subtitle font-bold"
          id="components-title"
        >
          Galeria komponentów UI
        </h2>
        <UiGallery />
      </section>
    </main>
  );
}

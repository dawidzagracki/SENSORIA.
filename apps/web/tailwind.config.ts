import type { Config } from "tailwindcss";

type ColorToken = {
  value: string;
  role: string;
  source: string;
  status: "source" | "approved" | "proposal";
};

export const colorTokens = {
  surface: {
    value: "#ffffff",
    role: "Podstawowa powierzchnia i tło kart.",
    source: "Obie makiety; białe tła wektorowe.",
    status: "source",
  },
  "surface-muted": {
    value: "#fff1f5",
    role: "Delikatnie wyróżnione sekcje i tła etykiet.",
    source: "08-produkt-ebook-desktop.pdf; jasne pasy sekcji.",
    status: "source",
  },
  ink: {
    value: "#2a0c18",
    role: "Podstawowy tekst; wspólna, ciemniejsza wartość dla kontrastu.",
    source:
      "01-katalog-desktop.pdf; wybrana zamiast nieco jaśniejszego #33101f z makiety produktu.",
    status: "source",
  },
  "ink-muted": {
    value: "#6e4356",
    role: "Tekst pomocniczy; wspólna, ciemniejsza wartość dla kontrastu.",
    source: "08-produkt-ebook-desktop.pdf; wybrana zamiast #7a5064 z katalogu.",
    status: "source",
  },
  accent: {
    value: "#f0568c",
    role: "Jasny akcent dekoracyjny; z ciemnym tekstem, nie z białym.",
    source: "Wspólny kolor wektorowy obu makiet.",
    status: "source",
  },
  "accent-action": {
    value: "#c81e5e",
    role: "Tło głównej akcji i etykiet z białym tekstem.",
    source:
      "08-produkt-ebook-desktop.pdf; wartość źródłowa o wyższym kontraście.",
    status: "source",
  },
  border: {
    value: "#f0d5e0",
    role: "Delikatne obrysy i separatory; nie używać jako tekstu.",
    source: "Wspólna wartość #f0d5e0 w obu PDF-ach; delikatne obrysy kart.",
    status: "source",
  },
  success: {
    value: "#dcfce7",
    role: "Tło stanu powodzenia, np. aktywny.",
    source: "Propozycja zatwierdzona przez użytkownika; brak w PDF-ach.",
    status: "approved",
  },
  "on-success": {
    value: "#14532d",
    role: "Tekst na tle powodzenia.",
    source: "Para zatwierdzona przez użytkownika; brak w PDF-ach.",
    status: "approved",
  },
  warning: {
    value: "#fef3c7",
    role: "Tło stanu wymagającego uwagi.",
    source: "Propozycja zatwierdzona przez użytkownika; brak w PDF-ach.",
    status: "approved",
  },
  "on-warning": {
    value: "#854d0e",
    role: "Tekst na tle ostrzeżenia.",
    source: "Para zatwierdzona przez użytkownika; brak w PDF-ach.",
    status: "approved",
  },
  danger: {
    value: "#fee2e2",
    role: "Tło stanu błędu lub zagrożenia.",
    source: "Propozycja zatwierdzona przez użytkownika; brak w PDF-ach.",
    status: "approved",
  },
  "on-danger": {
    value: "#991b1b",
    role: "Tekst na tle błędu.",
    source: "Para zatwierdzona przez użytkownika; brak w PDF-ach.",
    status: "approved",
  },
  info: {
    value: "#dbeafe",
    role: "Tło informacji.",
    source: "Propozycja zatwierdzona przez użytkownika; brak w PDF-ach.",
    status: "approved",
  },
  "on-info": {
    value: "#1e40af",
    role: "Tekst na tle informacji.",
    source: "Para zatwierdzona przez użytkownika; brak w PDF-ach.",
    status: "approved",
  },
} as const satisfies Record<string, ColorToken>;

export const spacingTokens = [
  { name: "1", value: "4px" },
  { name: "2", value: "8px" },
  { name: "3", value: "12px" },
  { name: "4", value: "16px" },
  { name: "5", value: "20px" },
  { name: "6", value: "24px" },
  { name: "8", value: "32px" },
  { name: "12", value: "48px" },
  { name: "16", value: "64px" },
  { name: "24", value: "96px" },
  { name: "30", value: "120px" },
] as const;

export const controlHeightTokens = [
  {
    name: "touch",
    value: "44px",
    source: "Minimalny obszar dotykowy WCAG dla kontrolek.",
  },
  {
    name: "control-sm",
    value: "44px",
    source: "Mały wariant kontrolki; zachowuje minimum dotykowe.",
  },
  {
    name: "control-md",
    value: "48px",
    source: "Średni wariant kontrolki z istniejącej skali odstępów.",
  },
  {
    name: "control-lg",
    value: "56px",
    source: "Duży wariant kontrolki z istniejącej skali odstępów.",
  },
] as const;

// Self-hosted variable fonts from @fontsource-variable (latin + latin-ext, so Polish letters work).
const sans = [
  "Plus Jakarta Sans Variable",
  "Plus Jakarta Sans",
  "system-ui",
  "sans-serif",
];
const serif = ["Lora Variable", "Lora", "Georgia", "serif"];
const fontStacks = {
  display: sans,
  body: sans,
  interface: sans,
  decorative: serif,
} as const;

export const fontTokens = [
  {
    role: "Nagłówki UI",
    family: "Plus Jakarta Sans",
    style: "Bold 700 / ExtraBold 800",
    source:
      "Zamiennik zastępczego DejaVu z makiet; zmienny font hostowany lokalnie.",
  },
  {
    role: "Tekst redakcyjny",
    family: "Plus Jakarta Sans",
    style: "Regular 400",
    source:
      "Zamiennik Liberation Serif; czytelniejszy w sklepie, hostowany lokalnie.",
  },
  {
    role: "Akcent redakcyjny",
    family: "Lora",
    style: "Italic 400–600",
    source:
      "Zamiennik Liberation Serif Italic; zmienny font hostowany lokalnie.",
  },
  {
    role: "Tekst interfejsu",
    family: "Plus Jakarta Sans",
    style: "Regular 400 – ExtraBold 800",
    source: "Zamiennik Liberation Sans; ta sama rodzina co nagłówki.",
  },
] as const;

export const typographyTokens = [
  {
    role: "home",
    family: "display",
    size: "80px",
    lineHeight: "1.02",
    source: "Wielkość nagłówka hero zmierzona z 00-strona-glowna-desktop.pdf.",
  },
  {
    role: "display",
    family: "display",
    size: "62px",
    lineHeight: "1.1",
    source: "46.5 pt w katalogu; skala odtworzona z transformacji PDF 0.75.",
  },
  {
    role: "title",
    family: "display",
    size: "38px",
    lineHeight: "1.2",
    source:
      "28.5 pt w makiecie produktu; skala odtworzona z transformacji PDF 0.75.",
  },
  {
    role: "subtitle",
    family: "interface",
    size: "23px",
    lineHeight: "1.25",
    source: "17.2 pt w katalogu; skala odtworzona z transformacji PDF 0.75.",
  },
  {
    role: "body",
    family: "body",
    size: "17px",
    lineHeight: "1.6",
    source:
      "12.7 pt w makiecie produktu; skala odtworzona z transformacji PDF 0.75.",
  },
  {
    role: "emphasis",
    family: "decorative",
    size: "22px",
    lineHeight: "1.35",
    source:
      "16.5 pt kursywy Liberation Serif w makiecie produktu; skala po transformacji PDF 0.75.",
  },
  {
    role: "card-title",
    family: "interface",
    size: "19px",
    lineHeight: "1.3",
    source:
      "Nowy token (redesign): tytuły kart i sekcji; wcześniej błędnie używano 11 px.",
  },
  {
    role: "button",
    family: "interface",
    size: "15px",
    lineHeight: "1.2",
    source: "Nowy token (redesign): czytelny tekst przycisków i nawigacji.",
  },
  {
    role: "body-small",
    family: "body",
    size: "15px",
    lineHeight: "1.5",
    source:
      "11.2 pt w obu makietach; skala odtworzona z transformacji PDF 0.75.",
  },
  {
    role: "caption",
    family: "interface",
    size: "14px",
    lineHeight: "1.45",
    source:
      "9.7 pt w obu makietach; skala odtworzona z transformacji PDF 0.75.",
  },
  {
    role: "eyebrow",
    family: "interface",
    size: "12px",
    lineHeight: "1.3",
    source: "Nowy token (redesign): małe etykiety wersalikowe i plakietki.",
  },
  {
    role: "label",
    family: "interface",
    size: "14px",
    lineHeight: "1.35",
    source:
      "8.2 pt w oznaczeniach produktów; skala odtworzona z transformacji PDF 0.75.",
  },
] as const;

export const breakpointTokens = [
  { name: "sm", value: "360px" },
  { name: "md", value: "768px" },
  { name: "lg", value: "1024px" },
  { name: "xl", value: "1280px" },
] as const;

export const letterSpacingTokens = [
  {
    name: "caps",
    value: "0.08em",
    source:
      "Robocze odtworzenie rozstrzelenia nagłówków działowych widocznego w PDF; dopasować z docelowymi fontami.",
  },
] as const;

export const productTypeTokens = [
  {
    label: "VOUCHER",
    foreground: "surface",
    background: "accent-action",
    source: "Propozycja z istniejącej palety; odrębna para dla typu produktu.",
    status: "proposal",
  },
  {
    label: "KSIĄŻKA",
    foreground: "ink",
    background: "surface-muted",
    source: "Propozycja z istniejącej palety; odrębna para dla typu produktu.",
    status: "proposal",
  },
  {
    label: "AUDIOBOOK",
    foreground: "on-info",
    background: "info",
    source: "Propozycja z zatwierdzonych tokenów info.",
    status: "proposal",
  },
  {
    label: "KURS PDF",
    foreground: "on-warning",
    background: "warning",
    source: "Propozycja z zatwierdzonych tokenów warning.",
    status: "proposal",
  },
  {
    label: "E-BOOK PDF",
    foreground: "ink",
    background: "accent",
    source:
      "Propozycja z istniejącej palety; para źródłowa z białym tekstem miała 3,27:1.",
    status: "proposal",
  },
] as const;

export const statusLabelTokens = [
  { label: "AKTYWNY", foreground: "on-success", background: "success" },
  {
    label: "WYGASA WKRÓTCE",
    foreground: "on-warning",
    background: "warning",
  },
  { label: "ZREALIZOWANY", foreground: "on-info", background: "info" },
] as const;

export const badgeTokens = [
  { label: "AKTYWNY", foreground: "on-success", background: "success" },
  { label: "WYGASA WKRÓTCE", foreground: "on-warning", background: "warning" },
  { label: "ZREALIZOWANY", foreground: "on-info", background: "info" },
  { label: "BESTSELLER", foreground: "surface", background: "accent-action" },
  { label: "OPŁACONE", foreground: "on-success", background: "success" },
  { label: "WYSYŁKA W TOKU", foreground: "on-info", background: "info" },
] as const;

export const contrastPairs = [
  {
    foreground: "ink",
    background: "surface",
    source: "Tekst podstawowy na białej powierzchni.",
  },
  {
    foreground: "ink-muted",
    background: "surface",
    source: "Tekst pomocniczy na białej powierzchni.",
  },
  {
    foreground: "ink",
    background: "surface-muted",
    source: "Tekst podstawowy na jasnej powierzchni.",
  },
  {
    foreground: "ink-muted",
    background: "surface-muted",
    source: "Tekst pomocniczy na jasnej powierzchni.",
  },
  {
    foreground: "ink",
    background: "accent",
    source: "Jasny akcent używany wyłącznie z ciemnym tekstem.",
  },
  {
    foreground: "surface",
    background: "accent",
    source:
      "Oryginalny biały tekst etykiety E-BOOK PDF; para odrzucona dla tekstu 11 px po wyniku 3,27:1.",
    status: "blocked",
  },
  {
    foreground: "surface",
    background: "accent-action",
    source: "Ciemny akcent z białym tekstem.",
  },
  {
    foreground: "on-success",
    background: "success",
    source:
      "Para zatwierdzona przez użytkownika; brak w dostarczonych PDF-ach.",
  },
  {
    foreground: "on-warning",
    background: "warning",
    source:
      "Para zatwierdzona przez użytkownika; brak w dostarczonych PDF-ach.",
  },
  {
    foreground: "on-danger",
    background: "danger",
    source:
      "Para zatwierdzona przez użytkownika; brak w dostarczonych PDF-ach.",
  },
  {
    foreground: "on-info",
    background: "info",
    source:
      "Para zatwierdzona przez użytkownika; brak w dostarczonych PDF-ach.",
  },
] as const;

export const gradientTokens = {
  footer: {
    start: colorTokens.surface.value,
    end: "#fffafc",
    direction: "180deg",
    source:
      "01-katalog-desktop.pdf, P4 footer surface; opaque DeviceRGB axial gradient.",
  },
} as const;

const footerGradient = `linear-gradient(${gradientTokens.footer.direction}, ${gradientTokens.footer.start}, ${gradientTokens.footer.end})`;

export const radiusTokens = [
  {
    name: "card",
    value: "20px",
    source:
      "Zaokrąglone karty w PDF; wektorowy promień ok. 15 pt przy transformacji 0.75.",
  },
  {
    name: "control",
    value: "20px",
    source:
      "Redesign: pola formularzy i drobne kontrolki mają ten sam promień co karty — w aplikacji nie ma kanciastych narożników.",
  },
  {
    name: "pill",
    value: "9999px",
    source: "Kontrolki o pełnym, pigułkowym kształcie w PDF.",
  },
] as const;

export const shadowTokens = [
  {
    name: "subtle",
    value: "0 2px 8px color-mix(in srgb, var(--color-ink) 10%, transparent)",
    source: "Propozycja do potwierdzenia; PDF nie ma jednoznacznego cienia.",
  },
  {
    name: "overlay",
    value: "0 8px 24px color-mix(in srgb, var(--color-ink) 14%, transparent)",
    source: "Propozycja do potwierdzenia; PDF nie ma jednoznacznego cienia.",
  },
] as const;

const colors = Object.fromEntries(
  Object.entries(colorTokens).map(([name, token]) => [name, token.value]),
) as Record<string, string>;

const spacing = Object.fromEntries(
  spacingTokens.map(({ name, value }) => [name, value]),
);

const screens = Object.fromEntries(
  breakpointTokens.map(({ name, value }) => [name, value]),
);

const borderRadius = Object.fromEntries(
  radiusTokens.map(({ name, value }) => [name, value]),
);

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    screens,
    extend: {
      colors,
      spacing,
      minHeight: Object.fromEntries(
        controlHeightTokens.map(({ name, value }) => [name, value]),
      ),
      minWidth: Object.fromEntries(
        controlHeightTokens.map(({ name, value }) => [name, value]),
      ),
      maxWidth: { content: "48rem", wide: "64rem", "page-shell": "75rem" },
      fontFamily: Object.fromEntries(
        Object.entries(fontStacks).map(([name, stack]) => [name, [...stack]]),
      ),
      fontSize: Object.fromEntries(
        typographyTokens.map(({ role, size, lineHeight }) => [
          role,
          [size, { lineHeight }],
        ]),
      ),
      fontWeight: {
        normal: "400",
        medium: "500",
        semibold: "600",
        bold: "700",
        extrabold: "800",
      },
      width: {
        ...Object.fromEntries(
          controlHeightTokens.map(({ name, value }) => [name, value]),
        ),
        dialog: "calc(100vw - theme('spacing.8'))",
        hero: "calc(100% + max(0px, (100vw - 75rem) / 2))",
      },
      height: { "sample-preview": "min(70vh, 48rem)" },
      aspectRatio: {
        "product-image": "1 / 1",
        "ticket-preview": "4 / 3",
        "ebook-cover": "4 / 5",
      },
      letterSpacing: Object.fromEntries(
        letterSpacingTokens.map(({ name, value }) => [name, value]),
      ),
      borderRadius,
      backgroundImage: { footer: footerGradient },
      boxShadow: Object.fromEntries(
        shadowTokens.map(({ name, value }) => [name, value]),
      ),
    },
  },
  plugins: [],
};

export default config;

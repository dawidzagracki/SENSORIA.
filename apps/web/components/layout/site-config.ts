export const announcementText =
  "Materiały cyfrowe dostajesz od razu po opłaceniu · książki wysyłamy InPostem · sensoria.shop";

export const productCategoryLinks = [
  { label: "Vouchery", href: "/sklep?kind=VOUCHER" },
  { label: "Książki", href: "/sklep?kind=BOOK" },
  { label: "Audiobooki", href: "/sklep?kind=AUDIOBOOK" },
  { label: "Kursy", href: "/sklep?category=kursy-pdf" },
] as const;

// Product categories live in the catalog filters; the header keeps only top-level destinations.
export const primaryNavigationLinks = [
  { label: "Sklep", href: "/sklep" },
  { label: "O autorce", href: "/o-autorce" },
  { label: "Pomoc", href: "/pomoc" },
] as const;

export const footerColumns = [
  {
    title: "Marka i adres",
    kind: "brand",
    items: [
      { label: "SENSORIA.", href: "/" },
      { label: "ul. Knosały 7B/A, 10-015 Olsztyn.", href: null },
      { label: "Wejście bezpośrednio z ulicy, parter.", href: null },
    ],
  },
  {
    title: "Sklep",
    kind: "links",
    items: [
      productCategoryLinks[0],
      productCategoryLinks[1],
      productCategoryLinks[2],
      { label: "Kursy PDF", href: productCategoryLinks[3].href },
    ],
  },
  {
    title: "Pomoc",
    kind: "links",
    items: [
      { label: "Dostawa i płatności", href: "/dostawa-i-platnosci" },
      { label: "Zwroty i reklamacje", href: "/pomoc/zwroty-i-reklamacje" },
      { label: "Odstąpienie od umowy", href: "/pomoc/odstapienie" },
      { label: "Centrum pomocy", href: "/pomoc" },
    ],
  },
  {
    title: "Formalności",
    kind: "legal",
    items: [
      { label: "Regulamin", href: "/regulamin" },
      { label: "Polityka prywatności", href: "/polityka-prywatnosci" },
      { label: "Polityka cookies", href: "/polityka-cookies" },
      { label: "Ustawienia cookies", href: null },
    ],
  },
] as const;

export const copyrightText = "© 2026 Sensoria Terapia — Anna Parakiewicz";

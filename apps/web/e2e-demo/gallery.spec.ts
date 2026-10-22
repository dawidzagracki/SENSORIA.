import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
import {
  expect,
  test,
  type Browser,
  type BrowserContext,
  type Page,
} from "@playwright/test";
import { acceptEssentialCookies, ADMIN, CUSTOMER } from "./helpers";

/**
 * Presentation generator (not a regular test): walks through every screen of the demo stack,
 * takes desktop (+ phone) screenshots and assembles a PDF with a description of each screen so
 * the client can accept the work stage by stage.
 *   GALLERY=1 DEMO_URL=http://localhost:8090 npx playwright test -c playwright.demo.config.ts \
 *     --project=desktop gallery.spec.ts
 */
test.skip(
  !process.env.GALLERY,
  "Uruchamiane wyłącznie do wygenerowania prezentacji.",
);
test.setTimeout(600_000);

const OUT = "gallery-out";
const BASE = process.env.DEMO_URL ?? "http://localhost:8090";

type Slide = {
  section: string;
  title: string;
  path: string;
  description: string;
  checks: string[];
  phone?: boolean;
  run: (page: Page) => Promise<void>;
};

const go = (path: string) => async (page: Page) => {
  await page.goto(path);
  await page.waitForTimeout(1600);
};

async function newContext(browser: Browser, phone: boolean, consent = true) {
  const context = await browser.newContext(
    phone
      ? {
          viewport: { width: 390, height: 844 },
          deviceScaleFactor: 2,
          isMobile: true,
          hasTouch: true,
          baseURL: BASE,
        }
      : { viewport: { width: 1440, height: 900 }, baseURL: BASE },
  );
  if (consent) await acceptEssentialCookies(context, BASE);
  return context;
}

async function customerLogin(page: Page) {
  await page.goto("/konto");
  await page.getByLabel(/Adres e-mail/).fill(CUSTOMER.email);
  await page.getByLabel(/^Hasło/).fill(CUSTOMER.password);
  await page
    .getByRole("button", { name: "Zaloguj się", exact: true })
    .last()
    .click();
  await expect(
    page.getByRole("heading", { name: /Witaj, Anna/ }),
  ).toBeVisible();
}

async function adminLogin(page: Page) {
  await page.goto("/admin/logowanie");
  await page.getByLabel("Adres e-mail").fill(ADMIN.email);
  await page.getByLabel("Hasło").fill(ADMIN.password);
  await page.getByRole("button", { name: "Zaloguj się" }).click();
  await page.waitForURL(/\/admin$/);
}

const PUBLIC: Slide[] = [
  {
    section: "Sklep",
    title: "Strona główna",
    path: "/",
    description:
      "Wizytówka sklepu: hasło marki, najważniejsze kategorie, polecane materiały i krótkie zasady zakupów (cyfrowe od razu, książki InPostem).",
    checks: [
      "Logo i różowa kropka",
      "Pasek informacyjny",
      "Karty polecanych produktów",
      "Stopka z logotypami płatności i InPost",
    ],
    phone: true,
    run: go("/"),
  },
  {
    section: "Sklep",
    title: "Katalog produktów",
    path: "/sklep",
    description:
      "Wszystkie materiały w jednym miejscu. Filtry po lewej (kategorie, dla kogo, cena, dostępność), wyszukiwarka, sortowanie oraz widok siatki i listy. Menu u góry prowadzi do sklepu, a nie powiela filtrów.",
    checks: [
      "Filtry kategorii",
      "Wyszukiwarka",
      "Sortowanie i widok siatka/lista",
      "Przycisk „Do koszyka” na karcie",
    ],
    phone: true,
    run: go("/sklep"),
  },
  {
    section: "Sklep",
    title: "Katalog — wyszukiwanie i filtr",
    path: "/sklep?q=zmysły&category=e-booki",
    description:
      "Wyszukiwarka pełnotekstowa (z polskimi znakami) połączona z filtrem kategorii. Brak wyników pokazuje podpowiedzi.",
    checks: [
      "Wynik zawiera tylko pasujące produkty",
      "Aktywny filtr jest widoczny",
    ],
    run: go("/sklep?q=zmysły"),
  },
  {
    section: "Produkty",
    title: "Voucher na wizytę",
    path: "/sklep/konsultacja-psychologiczna",
    description:
      "Voucher na konsultację z wyborem wariantu (online / stacjonarnie), ceną z VAT i informacją o ważności. Po zakupie voucher przychodzi mailem jako PDF z kodem QR.",
    checks: [
      "Wybór wariantu",
      "Cena brutto i VAT",
      "Informacja o najniższej cenie z 30 dni (Omnibus)",
    ],
    phone: true,
    run: go("/sklep/konsultacja-psychologiczna"),
  },
  {
    section: "Produkty",
    title: "Książka papierowa",
    path: "/sklep/integracja-sensoryczna-w-codziennosci",
    description:
      "Książka wysyłana InPostem: stan magazynowy, dostawa (paczkomat / kurier), cena z VAT 5%.",
    checks: [
      "Dostępność",
      "Logo InPost przy dostawie",
      "Przycisk „Kup książkę”",
    ],
    phone: true,
    run: go("/sklep/integracja-sensoryczna-w-codziennosci"),
  },
  {
    section: "Produkty",
    title: "E-book PDF z darmowym fragmentem",
    path: "/sklep/zmysly-w-domu",
    description:
      "E-book dostępny od razu po zapłacie. Przed zakupem można obejrzeć bezpłatny fragment PDF. Po zakupie: czytnik z rozdziałami oraz pobranie pliku PDF.",
    checks: [
      "Podgląd fragmentu PDF",
      "Przycisk zakupu cyfrowego",
      "Informacja o pobraniu i czytniku",
    ],
    phone: true,
    run: go("/sklep/zmysly-w-domu"),
  },
  {
    section: "Produkty",
    title: "Audiobook",
    path: "/sklep/kiedy-zmysly-mowia-glosniej",
    description:
      "Audiobook z rozdziałami i darmowym fragmentem audio. Po zakupie: odtwarzacz w przeglądarce z pamięcią miejsca, w którym skończyłaś słuchać.",
    checks: ["Odtwarzacz fragmentu", "Lista rozdziałów i czas trwania"],
    phone: true,
    run: go("/sklep/kiedy-zmysly-mowia-glosniej"),
  },
  {
    section: "Produkty",
    title: "Kurs PDF",
    path: "/sklep/regulacja-emocji-u-dziecka-kurs-pdf",
    description:
      "Kurs w formie PDF: po zakupie dostępny jako kurs w przeglądarce (lekcje, postęp w procentach) albo jako plik do pobrania.",
    checks: ["Podgląd fragmentu", "Opis dwóch form korzystania: kurs / PDF"],
    phone: true,
    run: go("/sklep/regulacja-emocji-u-dziecka-kurs-pdf"),
  },
];

const PAGES: Slide[] = [
  {
    section: "Strony informacyjne",
    title: "O autorce",
    path: "/o-autorce",
    description: "Kim jest autorka i czym zajmuje się gabinet.",
    checks: ["Zdjęcie/tekst", "Link do rezerwacji wizyt"],
    run: go("/o-autorce"),
  },
  {
    section: "Strony informacyjne",
    title: "Centrum pomocy",
    path: "/pomoc",
    description:
      "Najczęstsze pytania (FAQ) z wyszukiwarką i kategoriami; linki do dostawy, zwrotów i odstąpienia.",
    checks: ["Wyszukiwarka pytań", "Rozwijane odpowiedzi"],
    run: go("/pomoc"),
  },
  {
    section: "Strony informacyjne",
    title: "Dostawa i płatności",
    path: "/dostawa-i-platnosci",
    description:
      "Koszty i terminy dostawy (paczkomat, kurier, odbiór w gabinecie), darmowa dostawa od progu, metody płatności i logotypy operatorów.",
    checks: ["Koszty z ustawień panelu", "Logo InPost i płatności"],
    run: go("/dostawa-i-platnosci"),
  },
  {
    section: "Strony informacyjne",
    title: "Zwroty i reklamacje",
    path: "/pomoc/zwroty-i-reklamacje",
    description: "Zasady zwrotów i reklamacji wraz z formularzem zgłoszenia.",
    checks: ["Formularz zgłoszenia", "Potwierdzenie mailowe"],
    run: go("/pomoc/zwroty-i-reklamacje"),
  },
  {
    section: "Strony informacyjne",
    title: "Odstąpienie od umowy",
    path: "/pomoc/odstapienie",
    description:
      "Informacja o prawie odstąpienia od umowy (z wyłączeniem treści cyfrowych) i wzór oświadczenia.",
    checks: ["Treść prawna", "Wzór formularza"],
    run: go("/pomoc/odstapienie"),
  },
  {
    section: "Strony informacyjne",
    title: "Regulamin",
    path: "/regulamin",
    description: "Regulamin sklepu edytowalny w panelu (Strony i FAQ).",
    checks: ["Spis paragrafów", "Aktualna wersja"],
    run: go("/regulamin"),
  },
  {
    section: "Strony informacyjne",
    title: "Polityka prywatności",
    path: "/polityka-prywatnosci",
    description: "Informacja o przetwarzaniu danych (RODO).",
    checks: ["Treść prawna"],
    run: go("/polityka-prywatnosci"),
  },
  {
    section: "Strony informacyjne",
    title: "Polityka cookies",
    path: "/polityka-cookies",
    description: "Opis plików cookies i sposobu zarządzania zgodami.",
    checks: ["Lista cookies", "Link do ustawień zgód"],
    run: go("/polityka-cookies"),
  },
];

const ACCOUNT_ANON: Slide[] = [
  {
    section: "Konto i logowanie",
    title: "Logowanie hasłem i przez Google",
    path: "/konto",
    description:
      "Logowanie e-mailem i hasłem albo przez konto Google, link do logowania bez hasła oraz odzyskiwanie hasła.",
    checks: [
      "Przycisk Google",
      "Pole hasła z podglądem",
      "Link „Zapomniałam hasła”",
    ],
    phone: true,
    run: go("/konto"),
  },
  {
    section: "Konto i logowanie",
    title: "Wejście bez konta (kod z e-maila)",
    path: "/konto → „Bez konta”",
    description:
      "Kupiłaś jako gość? Wpisz adres z zamówienia, dostaniesz 6-cyfrowy kod na e-mail i wchodzisz na „konto gościa” — widzisz kursy, audiobooki, e-booki i zamówienia bez zakładania konta.",
    checks: [
      "Wysyłka kodu na e-mail",
      "Kod ważny 10 minut, 5 prób",
      "Po wpisaniu kodu — biblioteka",
    ],
    phone: true,
    run: async (page) => {
      await page.goto("/konto");
      await page.getByRole("button", { name: "Bez konta" }).click();
      await page
        .getByLabel(/Adres e-mail z zamówienia/)
        .fill("anna.kowalska@sensoria.demo");
      await page.waitForTimeout(400);
    },
  },
  {
    section: "Konto i logowanie",
    title: "Zakładanie konta",
    path: "/konto → „Załóż konto”",
    description:
      "Rejestracja z potwierdzeniem adresu e-mail oraz zgodami (regulamin, marketing — dobrowolne).",
    checks: ["Wymagania hasła", "Zgody rozdzielone", "Mail z potwierdzeniem"],
    phone: true,
    run: async (page) => {
      await page.goto("/konto");
      await page.getByRole("button", { name: "Załóż konto" }).click();
      await page.waitForTimeout(400);
    },
  },
];

test("prezentacja: zrzuty wszystkich ekranów i PDF", async ({ browser }) => {
  mkdirSync(OUT, { recursive: true });
  const shots: Array<Slide & { desktop: string; mobile?: string }> = [];
  let counter = 0;

  async function capture(slide: Slide, desktopPage: Page, phonePage?: Page) {
    counter += 1;
    const id = String(counter).padStart(2, "0");
    await slide.run(desktopPage);
    const desktop = `${OUT}/${id}-d.png`;
    await desktopPage.screenshot({ path: desktop });
    let mobile: string | undefined;
    if (slide.phone && phonePage) {
      await slide.run(phonePage);
      mobile = `${OUT}/${id}-m.png`;
      await phonePage.screenshot({ path: mobile });
    }
    shots.push({ ...slide, desktop, mobile });
  }

  async function group(
    slides: Slide[],
    setup?: (page: Page) => Promise<void>,
    consent = true,
  ) {
    const dctx = await newContext(browser, false, consent);
    const mctx = await newContext(browser, true, consent);
    const dpage = await dctx.newPage();
    const mpage = await mctx.newPage();
    if (setup) {
      await setup(dpage);
      await setup(mpage);
    }
    for (const slide of slides) await capture(slide, dpage, mpage);
    await dctx.close();
    await mctx.close();
  }

  // 1. banner cookies on the first visit (no stored consent)
  await group(
    [
      {
        section: "Sklep",
        title: "Baner zgód na cookies (pierwsza wizyta)",
        path: "/",
        description:
          "Przy pierwszej wizycie klient wybiera zgody: tylko niezbędne, wszystkie albo ustawienia szczegółowe. Wybór jest zapamiętany i zapisywany w rejestrze zgód.",
        checks: [
          "Domyślnie tylko niezbędne",
          "Przycisk „Ustawienia”",
          "Zapis wyboru",
        ],
        phone: true,
        run: go("/"),
      },
    ],
    undefined,
    false,
  );

  await group(PUBLIC);
  await group(PAGES);
  await group(ACCOUNT_ANON);

  // 2. purchase flow as a guest (desktop only; sequential state)
  {
    const ctx = await newContext(browser, false);
    const page = await ctx.newPage();
    const flow: Slide[] = [
      {
        section: "Zakup jako gość",
        title: "Koszyk",
        path: "/koszyk",
        description:
          "Koszyk gościa (zapamiętany 30 dni, bez konta): zmiana ilości, kod rabatowy, wybór dostawy z kosztem i progiem darmowej dostawy oraz podsumowanie z VAT w jednym zwijanym wierszu.",
        checks: [
          "Kod rabatowy",
          "Wybór dostawy z logo InPost",
          "Rozwijany szczegół VAT",
        ],
        run: async (p) => {
          await p.goto("/sklep/integracja-sensoryczna-w-codziennosci");
          await p.getByRole("button", { name: "Kup książkę" }).first().click();
          await p.waitForURL(/\/zamowienie/);
          await go("/koszyk")(p);
        },
      },
      {
        section: "Zakup jako gość",
        title: "Zamówienie — dane i dostawa",
        path: "/zamowienie",
        description:
          "Jeden ekran: kontakt, dostawa, dane do faktury (osoba/firma z NIP), płatność i zgody. Po prawej stałe podsumowanie.",
        checks: ["Walidacja pól", "Faktura na firmę", "Zgody rozdzielone"],
        run: async (p) => {
          await go("/zamowienie")(p);
          await p.getByLabel(/Adres e-mail/).fill("klientka@przyklad.pl");
          await p.getByLabel("Imię").fill("Ewa");
          await p.getByLabel("Nazwisko").fill("Przykładowa");
          await p.getByLabel("Telefon").fill("600200300");
          await p.locator("label", { hasText: "Paczkomat InPost" }).click();
          await p.waitForTimeout(900);
        },
      },
      {
        section: "Zakup jako gość",
        title: "Wybór Paczkomatu na mapie",
        path: "/zamowienie → „Wybierz Paczkomat”",
        description:
          "Mapa Polski z punktami InPost: wyszukiwanie po mieście/kodzie, „Szukaj w tej okolicy mapy”, lokalizacja klienta i lista punktów. Punkt potwierdza serwer w API InPost.",
        checks: [
          "Piny na mapie",
          "Zaznaczenie punktu na liście",
          "Wpisanie kodu paczkomatu",
        ],
        run: async (p) => {
          await p.getByRole("button", { name: "Wybierz Paczkomat" }).click();
          await p.getByLabel("Miasto lub kod pocztowy").fill("Olsztyn");
          await p.getByRole("button", { name: "Szukaj punktów" }).click();
          await p.waitForTimeout(3500);
          await p.locator(".leaflet-marker-icon").nth(1).click();
          await p.waitForTimeout(600);
        },
      },
      {
        section: "Zakup jako gość",
        title: "Podsumowanie po wyborze punktu",
        path: "/zamowienie",
        description:
          "Wybrany Paczkomat jest zapisany w zamówieniu; podsumowanie pokazuje koszt dostawy i rozwijany VAT.",
        checks: [
          "Adres punktu odbioru",
          "Koszt dostawy",
          "Przycisk „Zamawiam i płacę”",
        ],
        run: async (p) => {
          await p
            .locator("li.border-accent-action")
            .getByRole("button", { name: "Wybierz ten punkt" })
            .click();
          await p.waitForTimeout(900);
          await p
            .getByText("W tym VAT (szczegóły)")
            .first()
            .click()
            .catch(() => undefined);
        },
      },
      {
        section: "Zakup jako gość",
        title: "Płatność (bramka demonstracyjna)",
        path: "bramka Stripe (atrapa)",
        description:
          "W wersji pokazowej płatność obsługuje atrapa bramki; na produkcji będzie to Stripe (BLIK, karta, Google Pay/Apple Pay). Zamówienie zostaje opłacone wyłącznie po podpisanym webhooku.",
        checks: ["Wybór BLIK / karta", "Powrót do sklepu po anulowaniu"],
        run: async (p) => {
          await p.getByLabel(/Akceptuję regulamin/).check();
          await p.getByRole("button", { name: /Zamawiam i płacę/ }).click();
          await p.waitForURL(/localhost:9911\/pay\//);
          await p.waitForTimeout(500);
        },
      },
      {
        section: "Zakup jako gość",
        title: "Potwierdzenie zamówienia",
        path: "/zamowienie/potwierdzenie",
        description:
          "Po opłaceniu: numer zamówienia, statusy, materiały cyfrowe do otwarcia od razu, dokumenty (paragon/faktura) i informacja o wysyłce.",
        checks: [
          "Status „Opłacone”",
          "Dokumenty do pobrania",
          "Wskazówka o powrocie przez kod z e-maila",
        ],
        run: async (p) => {
          await p.getByRole("button", { name: /Zapłać BLIK/ }).click();
          await p.waitForURL(/\/zamowienie\/potwierdzenie/);
          await p.waitForTimeout(2500);
        },
      },
    ];
    for (const slide of flow) await capture(slide, page);
    await ctx.close();
  }

  // 3. e-mail (Mailpit)
  {
    const ctx = await newContext(browser, false);
    const page = await ctx.newPage();
    await capture(
      {
        section: "Poczta",
        title: "Wiadomości do klienta (Mailpit — podgląd skrzynki)",
        path: "http://localhost:8025",
        description:
          "W wersji pokazowej maile trafiają do podglądu: potwierdzenie zamówienia, dostęp do materiałów, voucher z PDF, kody logowania, przypomnienia, prośby o opinię. Na produkcji wychodzą przez SMTP.",
        checks: [
          "Potwierdzenie zamówienia",
          "Kod logowania",
          "Voucher PDF w załączniku",
        ],
        run: async (p) => {
          await p.goto("http://localhost:8025");
          await p.waitForTimeout(1500);
        },
      },
      page,
    );
    await capture(
      {
        section: "Poczta",
        title: "Przykładowa wiadomość z potwierdzeniem",
        path: "Mailpit → wiadomość",
        description:
          "Treść maila w stylu sklepu: numer zamówienia, kwoty, linki do materiałów i dokumentów.",
        checks: ["Spójna szata graficzna", "Czytelne przyciski"],
        run: async (p) => {
          await p.goto("http://localhost:8025");
          await p
            .locator("a.message, .message")
            .first()
            .click()
            .catch(() => undefined);
          await p.waitForTimeout(1500);
        },
      },
      page,
    );
    await ctx.close();
  }

  // 4. customer account
  const accountSlides: Slide[] = [
    {
      section: "Konto klienta",
      title: "Panel konta",
      path: "/konto",
      description:
        "Skróty do biblioteki, zamówień, voucherów i danych oraz powitanie po zalogowaniu.",
      checks: ["Skróty do sekcji", "Wylogowanie"],
      phone: true,
      run: go("/konto"),
    },
    {
      section: "Konto klienta",
      title: "Moja biblioteka",
      path: "/konto/biblioteka",
      description:
        "Zakupione e-booki, kursy i audiobooki. Każdy PDF można czytać jako kurs w przeglądarce (z pamięcią postępu) albo pobrać jako plik.",
      checks: [
        "Przycisk „Czytaj jako kurs / Kontynuuj”",
        "Przycisk „Pobierz PDF”",
        "Pasek postępu w procentach",
      ],
      phone: true,
      run: go("/konto/biblioteka"),
    },
    {
      section: "Konto klienta",
      title: "Kurs PDF — lekcje i strony",
      path: "/konto/czytnik/…",
      description:
        "PDF w formie kursu: spis lekcji (z zakładek pliku), strony wyświetlane w przeglądarce, procent ukończenia i ile zostało, przycisk „Następny rozdział”, pobranie pliku PDF oraz zapamiętane miejsce.",
      checks: [
        "Spis lekcji z ✓",
        "Ukończono X% · zostało Y%",
        "Pobierz PDF",
        "Powrót w to samo miejsce",
      ],
      phone: true,
      run: async (p) => {
        await p.goto("/konto/biblioteka");
        await p
          .locator("li", { hasText: "Regulacja emocji u dziecka" })
          .first()
          .getByRole("link", { name: /kurs/i })
          .click();
        await p.waitForURL(/czytnik/);
        await p
          .getByRole("button", { name: /Lekcja 2/ })
          .click()
          .catch(() => undefined);
        await p.waitForTimeout(2500);
      },
    },
    {
      section: "Konto klienta",
      title: "E-book — czytnik z rozdziałami",
      path: "/konto/czytnik/…",
      description:
        "E-book z rozdziałami redakcyjnymi: spis treści, postęp, rozmiar tekstu 80–200%, pobranie PDF.",
      checks: [
        "Zmiana rozmiaru tekstu",
        "Nawigacja między rozdziałami",
        "Stopka z danymi kupującej",
      ],
      phone: true,
      run: async (p) => {
        await p.goto("/konto/biblioteka");
        await p
          .locator("li", { hasText: "Zmysły w domu" })
          .first()
          .getByRole("link", { name: /kurs/i })
          .click();
        await p.waitForURL(/czytnik/);
        await p.waitForTimeout(1800);
      },
    },
    {
      section: "Konto klienta",
      title: "Odtwarzacz audiobooka",
      path: "/konto/odtwarzacz/…",
      description:
        "Odtwarzacz z rozdziałami, prędkością, przewijaniem i zapamiętanym miejscem odsłuchu.",
      checks: [
        "Lista rozdziałów",
        "Prędkość odtwarzania",
        "Wznowienie od ostatniego miejsca",
      ],
      phone: true,
      run: async (p) => {
        await p.goto("/konto/biblioteka");
        await p.getByRole("link", { name: "Słuchaj" }).first().click();
        await p.waitForURL(/odtwarzacz/);
        await p.waitForTimeout(1800);
      },
    },
    {
      section: "Konto klienta",
      title: "Historia zamówień",
      path: "/konto/zamowienia",
      description:
        "Lista zamówień ze statusami, dokumentami, śledzeniem przesyłki i przyciskiem „Zamów ponownie”.",
      checks: ["Statusy", "Faktury i paragony", "Zamów ponownie"],
      phone: true,
      run: go("/konto/zamowienia"),
    },
    {
      section: "Konto klienta",
      title: "Moje vouchery",
      path: "/konto/vouchery",
      description:
        "Vouchery klientki z kodem QR, ważnością i możliwością prośby o przedłużenie lub wysłania w prezencie.",
      checks: ["Kod QR i PDF", "Prośba o przedłużenie"],
      phone: true,
      run: go("/konto/vouchery"),
    },
    {
      section: "Konto klienta",
      title: "Dane i zgody",
      path: "/konto/dane",
      description:
        "Dane osobowe, adresy, dane do faktury, zgody (marketing, opinie) oraz eksport i usunięcie danych (RODO).",
      checks: ["Eksport danych", "Usunięcie konta", "Zgody z historią"],
      phone: true,
      run: go("/konto/dane"),
    },
  ];
  await group(accountSlides, customerLogin);

  // 5. voucher verification (code from the account page)
  {
    const ctx = await newContext(browser, false);
    const page = await ctx.newPage();
    await customerLogin(page);
    await page.goto("/konto/vouchery");
    await page.waitForTimeout(1500);
    const html = await page.content();
    const code = html.match(/\/voucher\/([A-Za-z0-9_-]{8,})/)?.[1];
    if (code) {
      await capture(
        {
          section: "Konto klienta",
          title: "Weryfikacja vouchera (po zeskanowaniu QR)",
          path: `/voucher/${code.slice(0, 6)}…`,
          description:
            "Strona otwierana po zeskanowaniu kodu QR w gabinecie: status vouchera, ważność i usługa — bez ujawniania danych osobowych.",
          checks: ["Status aktywny/zrealizowany", "Brak danych osobowych"],
          run: go(`/voucher/${code}`),
        },
        page,
      );
    }
    await ctx.close();
  }

  // 6. admin
  const adminAnon: Slide[] = [
    {
      section: "Panel administracyjny",
      title: "Logowanie do panelu",
      path: "/admin/logowanie",
      description:
        "Osobne logowanie dla właścicielki i obsługi (role). Zabezpieczone limitem prób.",
      checks: ["Błędne hasło → komunikat", "Role: właścicielka / obsługa"],
      phone: true,
      run: go("/admin/logowanie"),
    },
  ];
  await group(adminAnon);

  const adminSlides: Slide[] = [
    {
      section: "Panel administracyjny",
      title: "Pulpit",
      path: "/admin",
      description:
        "Sprzedaż (dziś / 7 dni / 30 dni) i lista rzeczy wymagających uwagi: przesyłki fizyczne do realizacji, płatności, prośby o przedłużenie, niskie stany, niewysłane maile.",
      checks: [
        "Liczniki prowadzą do przefiltrowanych list",
        "„Do wysyłki” tylko dla produktów fizycznych",
      ],
      phone: true,
      run: go("/admin"),
    },
    {
      section: "Panel administracyjny",
      title: "Zamówienia",
      path: "/admin/zamowienia",
      description:
        "Lista zamówień z wyszukiwaniem i filtrami. Realizacja (wysyłka/odbiór) dotyczy wyłącznie zamówień fizycznych — cyfrowe i vouchery wydają się automatycznie.",
      checks: ["Filtr płatności i realizacji", "Kolumna „Klient” (także gość)"],
      phone: true,
      run: go("/admin/zamowienia"),
    },
    {
      section: "Panel administracyjny",
      title: "Do wysyłki (tylko produkty fizyczne)",
      path: "/admin/zamowienia?fulfillment=awaiting_fulfillment",
      description:
        "Widok zamówień, które wymagają działania: nadanie przesyłki lub przygotowanie odbioru w gabinecie. Cyfrowych tu nie ma.",
      checks: ["Tylko książki", "Nadanie przesyłki z numerem"],
      run: go("/admin/zamowienia?status=paid&fulfillment=awaiting_fulfillment"),
    },
    {
      section: "Panel administracyjny",
      title: "Szczegóły zamówienia",
      path: "/admin/zamowienia/…",
      description:
        "Pozycje, płatność, dokumenty, adres i punkt odbioru, notatki wewnętrzne, historia wiadomości, nadanie przesyłki z numerem śledzenia i ponowne wysłanie dostępu.",
      checks: ["Nadaj przesyłkę", "Notatki", "Ponowne wysłanie dostępu"],
      phone: true,
      run: async (p) => {
        await p.goto(
          "/admin/zamowienia?status=paid&fulfillment=awaiting_fulfillment",
        );
        await p.locator("tbody tr a").first().click();
        await p.waitForTimeout(1500);
      },
    },
    {
      section: "Panel administracyjny",
      title: "Produkty",
      path: "/admin/produkty",
      description:
        "Katalog: wyszukiwanie, rodzaj, status, cena i stan magazynu.",
      checks: ["Dodaj produkt", "Edycja"],
      phone: true,
      run: go("/admin/produkty"),
    },
    {
      section: "Panel administracyjny",
      title: "Edycja produktu",
      path: "/admin/produkty/…",
      description:
        "Dane produktu, cena i historia cen (Omnibus), kategorie, zdjęcia, pliki cyfrowe i rozdziały czytnika, fragmenty do podglądu, SEO.",
      checks: [
        "Zmiana ceny z powodem",
        "Wgranie pliku PDF/audio",
        "Rozdziały czytnika",
      ],
      run: async (p) => {
        await p.goto("/admin/produkty");
        await p.getByRole("link", { name: "Edytuj" }).first().click();
        await p.waitForTimeout(1800);
      },
    },
    {
      section: "Panel administracyjny",
      title: "Nowy produkt",
      path: "/admin/produkty/nowy",
      description:
        "Kreator dodawania produktu każdego rodzaju (voucher, książka, audiobook, e-book/kurs).",
      checks: ["Pola zależne od rodzaju", "Walidacja przed publikacją"],
      run: go("/admin/produkty/nowy"),
    },
    {
      section: "Panel administracyjny",
      title: "Vouchery",
      path: "/admin/vouchery",
      description:
        "Rejestr voucherów, wystawianie, realizacja w gabinecie (po kodzie) i prośby o przedłużenie ważności.",
      checks: ["Realizacja po kodzie", "Zakładka próśb"],
      phone: true,
      run: go("/admin/vouchery"),
    },
    {
      section: "Panel administracyjny",
      title: "Klienci (każdy kupujący)",
      path: "/admin/klienci",
      description:
        "Klientem jest każda osoba, która kupiła — także bez konta. Lista pokazuje e-mail, imię, rodzaj (gość / z kontem), liczbę zamówień i wartość zakupów.",
      checks: [
        "Gość i konto na jednej liście",
        "Szczegóły z historią zamówień",
      ],
      phone: true,
      run: async (p) => {
        await p.goto("/admin/klienci");
        await p.waitForTimeout(1200);
        await p
          .getByRole("button", { name: "Szczegóły" })
          .first()
          .click()
          .catch(() => undefined);
        await p.waitForTimeout(800);
      },
    },
    {
      section: "Panel administracyjny",
      title: "Opinie",
      path: "/admin/opinie",
      description: "Moderacja opinii: zatwierdzanie i odrzucanie.",
      checks: ["Zatwierdź / odrzuć"],
      phone: true,
      run: go("/admin/opinie"),
    },
    {
      section: "Panel administracyjny",
      title: "Zgłoszenia",
      path: "/admin/zgloszenia",
      description:
        "Reklamacje i zwroty z formularza: status, notatki, odpowiedź.",
      checks: ["Zmiana statusu", "Odpowiedź do klienta"],
      phone: true,
      run: go("/admin/zgloszenia"),
    },
    {
      section: "Panel administracyjny",
      title: "Kody rabatowe",
      path: "/admin/rabaty",
      description:
        "Tworzenie kodów (procent / kwota), limity, ważność i liczba użyć.",
      checks: ["Nowy kod", "Wyłączenie kodu"],
      phone: true,
      run: go("/admin/rabaty"),
    },
    {
      section: "Panel administracyjny",
      title: "Strony i FAQ",
      path: "/admin/strony",
      description:
        "Edycja regulaminu, polityk i centrum pomocy bez udziału programisty.",
      checks: ["Zapisz szkic / opublikuj", "Dodaj pytanie FAQ"],
      phone: true,
      run: go("/admin/strony"),
    },
    {
      section: "Panel administracyjny",
      title: "Raporty",
      path: "/admin/raporty",
      description:
        "Raporty sprzedaży i eksporty CSV (zamówienia, produkty, vouchery).",
      checks: ["Zakres dat", "Eksport CSV"],
      phone: true,
      run: go("/admin/raporty"),
    },
    {
      section: "Panel administracyjny",
      title: "Ustawienia",
      path: "/admin/ustawienia",
      description:
        "Dane sprzedawcy (paragony/faktury), koszty i progi dostawy, adresy kontaktowe i alertów, opóźnienie próśb o opinię.",
      checks: ["Koszty dostawy z VAT", "Dane na fakturach"],
      phone: true,
      run: go("/admin/ustawienia"),
    },
    {
      section: "Panel administracyjny",
      title: "Dziennik zdarzeń",
      path: "/admin/dziennik",
      description:
        "Rejestr działań w panelu i systemie (audyt): kto, kiedy i co zmienił.",
      checks: ["Filtrowanie", "Zdarzenia administratorów"],
      phone: true,
      run: go("/admin/dziennik"),
    },
  ];
  await group(adminSlides, adminLogin);

  // ---- assemble the PDF ----
  const img = (file?: string) =>
    file
      ? `data:image/png;base64,${readFileSync(file).toString("base64")}`
      : "";
  const esc = (value: string) =>
    value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const sections: string[] = [];
  for (const shot of shots)
    if (!sections.includes(shot.section)) sections.push(shot.section);
  const today = new Date().toLocaleDateString("pl-PL", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
  const slides = shots
    .map(
      (shot, index) => `
<section class="slide">
  <header><span class="sec">${esc(shot.section)}</span><span class="num">${index + 1} / ${shots.length}</span></header>
  <h2>${esc(shot.title)}</h2>
  <p class="path">${esc(shot.path)}</p>
  <div class="grid">
    <div class="left">
      <img class="desk" src="${img(shot.desktop)}" alt="">
      <p class="desc">${esc(shot.description)}</p>
    </div>
    <div class="right">
      ${shot.mobile ? `<img class="phone" src="${img(shot.mobile)}" alt="">` : ""}
    </div>
  </div>
</section>`,
    )
    .join("\n");
  const html = `<!doctype html><html lang="pl"><meta charset="utf-8"><style>
@page { size: A4 landscape; margin: 0 }
*{box-sizing:border-box} body{margin:0;font-family:Helvetica,Arial,sans-serif;color:#2a0c18}
.slide{width:297mm;height:210mm;padding:11mm 13mm;page-break-after:always;position:relative;overflow:hidden}
header{display:flex;justify-content:space-between;font-size:9pt;color:#c81e5e;font-weight:700;letter-spacing:.06em;text-transform:uppercase}
h2{margin:2mm 0 0;font-size:21pt} .path{margin:1mm 0 3mm;font-size:9pt;color:#6e4356;font-family:monospace}
.grid{display:grid;grid-template-columns:182mm 80mm;gap:8mm}
.desk{width:182mm;height:auto;border:1px solid #f0d5e0;border-radius:6px;display:block}
.desc{font-size:10.5pt;line-height:1.45;margin:3mm 0 0}
.phone{height:88mm;width:auto;border:1px solid #f0d5e0;border-radius:10px;display:block;margin:0 auto 3mm}
.checks{font-size:9.5pt;background:#fff1f5;border-radius:6px;padding:3mm 4mm} .checks ul{margin:1mm 0 0;padding-left:4.5mm} .checks li{margin:.7mm 0}
.accept{margin-top:3mm;border:1px solid #f0d5e0;border-radius:6px;padding:3mm 4mm;font-size:9.5pt} .accept p{margin:1.5mm 0}
.line{border-bottom:1px solid #d9b9c7;height:6mm}
.cover{background:#2a0c18;color:#fff;display:flex;flex-direction:column;justify-content:center}
.cover h1{font-size:44pt;margin:0} .cover .dot{color:#f0568c} .cover p{font-size:14pt;margin:4mm 0 0;color:#f6d5e1}
.toc{font-size:11pt} .toc li{margin:2mm 0}
</style><body>
<section class="slide cover"><h1>SENSORIA<span class="dot">.</span></h1><p>Przewodnik po wszystkich ekranach sklepu i panelu administracyjnego</p><p>Wersja pokazowa · ${today} · ${shots.length} ekranów do odbioru</p></section>
<section class="slide"><h2>Jak korzystać z dokumentu</h2><ul class="toc"><li>Każda strona opisuje jeden ekran: zrzut z komputera, (jeśli ma wersję mobilną) zrzut z telefonu oraz opis.</li><li>Dane w wersji pokazowej są przykładowe; płatność i poczta to atrapy, wszystko inne działa naprawdę.</li></ul><h2 style="margin-top:8mm">Spis części</h2><ol class="toc">${sections.map((s) => `<li>${esc(s)} — ${shots.filter((x) => x.section === s).length} ekr.</li>`).join("")}</ol></section>
${slides}
</body></html>`;
  writeFileSync(`${OUT}/prezentacja.html`, html);
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await page.setContent(html, { waitUntil: "load" });
  await page.pdf({
    path: `${OUT}/prezentacja-sensoria.pdf`,
    format: "A4",
    landscape: true,
    printBackground: true,
  });
  await ctx.close();
});

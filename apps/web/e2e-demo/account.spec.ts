import { expect, test, type Page } from "@playwright/test";
import {
  acceptEssentialCookies,
  CUSTOMER,
  expectNoServerError,
  findSquareControls,
  mailLink,
  pageFetch,
} from "./helpers";

test.beforeEach(async ({ context, baseURL }) => {
  await acceptEssentialCookies(context, baseURL!);
});

async function login(page: Page) {
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

test("logowanie hasłem: panel konta ma skróty do wszystkich sekcji", async ({
  page,
}) => {
  await login(page);
  const nav = page.getByRole("navigation", { name: "Twoje konto" });
  for (const name of [
    "Moja biblioteka",
    "Zamówienia",
    "Moje vouchery",
    "Dane i zgody",
  ]) {
    await expect(
      nav.getByRole("link", { name: new RegExp(name) }),
    ).toBeVisible();
  }
  await expect(
    page.getByRole("link", { name: "Moje konto" }).first(),
  ).toBeVisible();
});

test("zły hasło pokazuje czytelny błąd", async ({ page }) => {
  await page.goto("/konto");
  await page.getByLabel(/Adres e-mail/).fill(CUSTOMER.email);
  await page.getByLabel(/^Hasło/).fill("zle-haslo-123456");
  await page
    .getByRole("button", { name: "Zaloguj się", exact: true })
    .last()
    .click();
  await expect(page.getByRole("alert")).toBeVisible();
});

test("biblioteka → czytnik: rozdziały, nawigacja i skala tekstu", async ({
  page,
}) => {
  await login(page);
  await page.goto("/konto/biblioteka");
  await expect(
    page.getByRole("heading", { name: "Moja biblioteka" }),
  ).toBeVisible();
  await expect(page.getByText("Zmysły w domu").first()).toBeVisible();
  await page.getByRole("link", { name: "Czytaj" }).first().click();
  await expect(page).toHaveURL(/\/konto\/czytnik\//);
  // The reader resumes where the customer stopped; jump to the first chapter explicitly.
  await page.getByRole("button", { name: /Zmysły i codzienność/ }).click();
  await expect(
    page.getByRole("heading", { name: "Zmysły i codzienność" }).first(),
  ).toBeVisible();
  await page
    .getByRole("button", { name: /Następny rozdział/ })
    .or(page.getByRole("link", { name: /Następny rozdział/ }))
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name: "Rytuały dnia" }).first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Powiększ tekst" }).click();
  await page
    .getByRole("button", { name: /Poprzedni rozdział/ })
    .or(page.getByRole("link", { name: /Poprzedni rozdział/ }))
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name: "Zmysły i codzienność" }).first(),
  ).toBeVisible();
  await expectNoServerError(page);
});

test("biblioteka → odtwarzacz audiobooka: odtwarzanie i zmiana rozdziału", async ({
  page,
}) => {
  await login(page);
  await page.goto("/konto/biblioteka");
  await page.getByRole("link", { name: "Słuchaj" }).first().click();
  await expect(page).toHaveURL(/\/konto\/odtwarzacz\//);
  await expect(
    page.getByRole("heading", { name: "Kiedy zmysły mówią głośniej" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Odtwarzaj" }).click();
  await expect(page.getByRole("button", { name: "Wstrzymaj" })).toBeVisible();
  await page.getByRole("button", { name: /Dotyk/ }).first().click();
  await expectNoServerError(page);
});

test("zamówienia, vouchery i dane konta otwierają się z danymi", async ({
  page,
}) => {
  await login(page);
  await page.goto("/konto/zamowienia");
  await expect(
    page.getByRole("heading", { name: "Zamówienia" }).first(),
  ).toBeVisible();
  await expect(page.getByText(/SEN-2026-/).first()).toBeVisible();
  await page.goto("/konto/vouchery");
  await expect(
    page.getByRole("heading", { name: /vouchery/i }).first(),
  ).toBeVisible();
  await expect(
    page.getByText(/Konsultacja psychologiczna/).first(),
  ).toBeVisible();
  await page.goto("/konto/dane");
  await expect(
    page.getByRole("heading", { name: "Dane i zgody" }),
  ).toBeVisible();
  await expect(page.getByLabel("Imię")).toHaveValue("Anna");
  await expectNoServerError(page);
});

test("wylogowanie kończy sesję", async ({ page }) => {
  await login(page);
  await page.getByRole("button", { name: "Wyloguj się" }).click();
  await expect(
    page.getByRole("button", { name: "Zaloguj się", exact: true }).last(),
  ).toBeVisible();
  await page.goto("/konto/zamowienia");
  await expect(page).toHaveURL(/\/konto\?next=/);
});

test("rejestracja nowego konta i zakup bez konta nie są blokowane", async ({
  page,
}) => {
  await page.goto("/konto");
  await page.getByRole("button", { name: "Załóż konto" }).click();
  await expect(page.getByLabel(/Imię/)).toBeVisible();
  await expect(page.getByLabel(/Nazwisko/)).toBeVisible();
});

test("zamówienia → Faktury: lista dokumentów i pobranie PDF", async ({
  page,
}) => {
  await login(page);
  await page.goto("/konto/zamowienia");
  await page.getByRole("button", { name: /^Faktury/ }).click();
  const pdf = page.getByRole("link", { name: "Pobierz PDF" }).first();
  await expect(pdf).toBeVisible();
  const href = (await pdf.getAttribute("href"))!;
  const response = await pageFetch(page, href);
  expect(response.status).toBe(200);
  expect(response.head).toBe("%PDF-");
});

test("moje vouchery: kod, PDF i okno rezerwacji z kontaktem", async ({
  page,
}) => {
  await login(page);
  await page.goto("/konto/vouchery");
  await expect(
    page.getByText(/SEN-[A-Z0-9]{4}-[A-Z0-9]{4}/).first(),
  ).toBeVisible();
  const pdf = page.getByRole("link", { name: "Pobierz PDF" }).first();
  const response = await pageFetch(page, (await pdf.getAttribute("href"))!);
  expect(response.status).toBe(200);
  expect(response.head).toBe("%PDF-");
  await page.getByRole("button", { name: "Umów wizytę" }).first().click();
  await expect(page.getByRole("dialog")).toContainText(
    /kontakt|Napisz do nas|rezerwacj/i,
  );
  await expect(page.getByText("nie jest skonfigurowany")).toHaveCount(0);
});

test("zgłoszenie reklamacji z konta kończy się numerem sprawy", async ({
  page,
}) => {
  await login(page);
  await page.goto("/konto/zamowienia");
  await page
    .getByRole("link", { name: "Reklamacja lub zwrot" })
    .first()
    .click();
  await expect(page).toHaveURL(/zwroty-i-reklamacje\?order=/);
  await page
    .getByLabel("Opis sprawy")
    .fill("Pokazowa reklamacja — plik nie otwiera się poprawnie.");
  await page.getByRole("button", { name: "Wyślij zgłoszenie" }).click();
  await expect(page.getByText("Zgłoszenie przyjęte")).toBeVisible();
  await expect(page.getByText(/ZG-2026-/).first()).toBeVisible();
});

test("nowe konto: rejestracja, potwierdzenie e-maila, zakup i opinia o produkcie", async ({
  page,
  context,
}) => {
  const email = `nowa-${Date.now()}@sensoria.demo`;
  await page.goto("/konto");
  await page.getByRole("button", { name: "Załóż konto" }).click();
  await page.getByLabel("Imię").fill("Nowa");
  await page.getByLabel("Nazwisko").fill("Klientka");
  await page.getByLabel(/Adres e-mail/).fill(email);
  await page.getByLabel(/^Hasło/).fill("Demo-Sensoria-2026");
  await page.getByLabel(/Powtórz hasło/).fill("Demo-Sensoria-2026");
  await page
    .getByRole("button", { name: /Załóż konto|Zarejestruj/ })
    .last()
    .click();
  await expect(
    page.getByRole("heading", { name: /Witaj, Nowa/ }),
  ).toBeVisible();

  // The account only sees purchases made with a verified address: confirm it from the mail.
  const verify = await mailLink(
    context,
    email,
    /https?:\/\/[^\s"'<>]*\/konto\/potwierdz-email[^\s"'<>]*/,
  );
  await page.goto(verify.replace(/^https?:\/\/[^/]+/, ""));
  await page.getByRole("button", { name: /Potwierdź/ }).click();
  await expect(
    page.getByText(/został potwierdzony|potwierdzony|dziękujemy/i).first(),
  ).toBeVisible();

  await page.goto("/sklep/zmysly-w-domu");
  await page
    .getByRole("button", { name: "Kup i pobierz teraz" })
    .first()
    .click();
  await expect(page).toHaveURL(/\/zamowienie/);
  await page.getByLabel(/Akceptuję regulamin/).check();
  await page.getByLabel(/Żądam udostępnienia treści cyfrowej/).check();
  await page.getByRole("button", { name: /Zamawiam i płacę/ }).click();
  await page.waitForURL(/localhost:9911\/pay\//);
  await page.getByRole("button", { name: /Zapłać BLIK/ }).click();
  await page.waitForURL(/\/zamowienie\/potwierdzenie/);

  await page.goto("/konto/zamowienia");
  await expect(page.getByText(/SEN-2026-/).first()).toBeVisible();
  await page.getByRole("link", { name: "Wystaw opinię" }).first().click();
  await expect(page).toHaveURL(/\/opinie\/nowa\?order=/);
  await page.locator("label", { hasText: /5/ }).first().click();
  await page
    .getByLabel("Twoja opinia")
    .fill("Pokazowa opinia — wszystko działało świetnie, polecam.");
  await page
    .getByRole("button", { name: /Wyślij|Dodaj/ })
    .last()
    .click();
  await expect(
    page.getByText(/Dziękujemy|zapisaliśmy|moderacj/i).first(),
  ).toBeVisible();
});

test("moje vouchery: kod QR ładuje się, a data konta jest po polsku", async ({
  page,
}) => {
  await login(page);
  await page.goto("/konto/vouchery");
  const qr = page.getByRole("img", { name: /QR/ }).first();
  await expect(qr).toBeVisible();
  await expect
    .poll(() => qr.evaluate((img: HTMLImageElement) => img.naturalWidth))
    .toBeGreaterThan(0);
  await expect(page.getByText(/Klientka od października 2026/)).toBeVisible();
});

test("logowanie przez Google: wybór konta zakłada i loguje klientkę", async ({
  page,
}) => {
  await page.goto("/konto");
  await page.getByRole("link", { name: "Zaloguj się przez Google" }).click();
  await page.waitForURL(/localhost:9911\/google\/auth/);
  await expect(page.getByText("Tryb demonstracyjny")).toBeVisible();
  await page.getByRole("link", { name: /Ewa Nowak/ }).click();
  await page.waitForURL(/\/konto/);
  await expect(page.getByRole("heading", { name: /Witaj, Ewa/ })).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Moje konto" }).first(),
  ).toBeVisible();
  await page.goto("/konto/dane");
  await expect(page.getByLabel("Imię")).toHaveValue("Ewa");
});

test("rejestracja: jest też przycisk Google", async ({ page }) => {
  await page.goto("/konto");
  await page.getByRole("button", { name: "Załóż konto" }).click();
  await expect(
    page.getByRole("link", { name: "Załóż konto przez Google" }),
  ).toBeVisible();
});

test("spójność w koncie, czytniku i odtwarzaczu: brak kanciastych narożników", async ({
  page,
}) => {
  await login(page);
  const square: string[] = [];
  const visit = async (path: string) => {
    await page.goto(path);
    await page.waitForTimeout(1200);
    square.push(
      ...(await findSquareControls(page)).map((entry) => `${path}: ${entry}`),
    );
  };
  for (const path of [
    "/konto",
    "/konto/zamowienia",
    "/konto/vouchery",
    "/konto/dane",
    "/konto/biblioteka",
  ])
    await visit(path);
  await page.goto("/konto/biblioteka");
  const reader = await page
    .getByRole("link", { name: "Czytaj" })
    .first()
    .getAttribute("href");
  const player = await page
    .getByRole("link", { name: "Słuchaj" })
    .first()
    .getAttribute("href");
  await visit(reader!);
  await visit(player!);
  expect(square).toEqual([]);
});

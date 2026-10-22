import { expect, test, type Page } from "@playwright/test";
import {
  acceptEssentialCookies,
  CUSTOMER,
  expectNoServerError,
  findSquareControls,
  clearMailFor,
  mailLink,
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

test("kurs PDF: rozdziały z zakładek PDF, strony jako obrazy, postęp i pobranie pliku", async ({
  page,
}) => {
  await login(page);
  await page.goto("/konto/biblioteka");
  const card = page
    .locator("li", { hasText: "Regulacja emocji u dziecka" })
    .first();
  await expect(card.getByRole("link", { name: /kurs/i })).toBeVisible();
  await expect(card.getByRole("button", { name: /Pobierz PDF/ })).toBeVisible();
  await card.getByRole("link", { name: /kurs/i }).click();
  await expect(page).toHaveURL(/\/konto\/czytnik\//);
  const toc = page.getByRole("complementary", { name: "Spis treści" });
  await expect(toc.getByRole("list").getByRole("button")).toHaveCount(5);
  await toc.getByRole("button", { name: /Lekcja 1/ }).click();
  const image = page.getByRole("img", { name: "Strona 1" });
  await expect(image).toBeVisible();
  await expect
    .poll(() => image.evaluate((el) => (el as HTMLImageElement).naturalWidth))
    .toBeGreaterThan(300);
  await expect(page.getByRole("img", { name: "Strona 2" })).toBeVisible();
  await expect(toc.getByText(/Ukończono \d+% · zostało \d+%/)).toBeVisible();
  await expect(toc.getByRole("button", { name: /Pobierz PDF/ })).toBeVisible();
  await page.getByRole("button", { name: /Następny rozdział/ }).click();
  await expect(
    page.getByRole("heading", { name: /Lekcja 2/ }).first(),
  ).toBeVisible();
  await expect(
    toc.getByText(/Ukończono [1-9]\d*% · zostało \d+%/),
  ).toBeVisible();
  // Progress survives a reload: the reader resumes on the same lesson.
  await page.reload();
  await expect(
    page.getByRole("heading", { name: /Lekcja 2/ }).first(),
  ).toBeVisible();
  expect(await findSquareControls(page)).toEqual([]);
  await expectNoServerError(page);
});

test("e-book z rozdziałami redakcyjnymi też ma pobranie PDF obok czytnika", async ({
  page,
}) => {
  await login(page);
  await page.goto("/konto/biblioteka");
  const card = page.locator("li", { hasText: "Zmysły w domu" }).first();
  await expect(card.getByRole("link", { name: /kurs/i })).toBeVisible();
  await expect(card.getByRole("button", { name: /Pobierz PDF/ })).toBeVisible();
});

test("klient bez konta: kod z e-maila otwiera bibliotekę i zamówienia", async ({
  page,
  context,
}) => {
  const email = "karolina.wisniewska@sensoria.demo";
  await clearMailFor(context, email);
  await page.goto("/konto");
  await page.getByRole("button", { name: "Bez konta" }).click();
  await page.getByLabel(/Adres e-mail z zamówienia/).fill(email);
  await page.getByRole("button", { name: "Wyślij mi kod" }).click();
  await expect(page.getByText(/wysłaliśmy na niego kod/i)).toBeVisible();
  const mail = await mailLink(context, email, /Twój kod logowania: \d{6}/);
  const code = mail.match(/\d{6}/)![0];
  await page.getByLabel("Kod z wiadomości").fill(code);
  await page.getByRole("button", { name: "Wejdź na konto" }).click();
  await expect(page).toHaveURL(/\/konto\/biblioteka/);
  await expect(page.getByText("Kiedy zmysły mówią głośniej")).toBeVisible();
  await page.goto("/konto/zamowienia");
  await expect(page.getByText(/SEN-2026-/).first()).toBeVisible();
});

test("zły kod nie wpuszcza na konto", async ({ page }) => {
  await page.goto("/konto");
  await page.getByRole("button", { name: "Bez konta" }).click();
  await page
    .getByLabel(/Adres e-mail z zamówienia/)
    .fill("karolina.wisniewska@sensoria.demo");
  await page.getByRole("button", { name: "Wyślij mi kod" }).click();
  await page.getByLabel("Kod z wiadomości").fill("000000");
  await page.getByRole("button", { name: "Wejdź na konto" }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: /nieprawidłowy/i }),
  ).toBeVisible();
});

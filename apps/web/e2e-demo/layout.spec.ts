import { expect, test } from "@playwright/test";
import {
  acceptEssentialCookies,
  ADMIN,
  CUSTOMER,
  findLayoutProblems,
} from "./helpers";

/** The same pages at phone, tablet and desktop widths must have no overflow or overlapping controls. */
const WIDTHS = [360, 390, 768, 820, 1024, 1280, 1440];
const SHOP = [
  "/",
  "/sklep",
  "/sklep?kind=VOUCHER",
  "/sklep/zmysly-w-domu",
  "/sklep/regulacja-emocji-u-dziecka-kurs-pdf",
  "/sklep/kiedy-zmysly-mowia-glosniej",
  "/sklep/integracja-sensoryczna-w-codziennosci",
  "/sklep/konsultacja-psychologiczna",
  "/koszyk",
  "/zamowienie",
  "/konto",
  "/pomoc",
  "/pomoc/odstapienie",
  "/regulamin",
  "/o-autorce",
  "/dostawa-i-platnosci",
];

test.beforeEach(async ({ context, baseURL }) => {
  await acceptEssentialCookies(context, baseURL!);
});

test("układ: sklep bez przepełnień i nakładających się kontrolek we wszystkich szerokościach", async ({
  page,
}) => {
  test.setTimeout(600_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/sklep/zmysly-w-domu");
  await page.getByRole("button", { name: "Do koszyka" }).first().click();
  await expect(page.getByText("Produkt dodano do koszyka.")).toBeVisible();
  const problems: string[] = [];
  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: 900 });
    for (const path of SHOP) {
      await page.goto(path);
      await page.waitForTimeout(700);
      problems.push(
        ...(await findLayoutProblems(page)).map(
          (entry) => `${width}px ${path}: ${entry}`,
        ),
      );
    }
  }
  expect(problems).toEqual([]);
});

test("układ: konto, biblioteka i panel we wszystkich szerokościach", async ({
  page,
}) => {
  test.setTimeout(600_000);
  const problems: string[] = [];
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
  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: 900 });
    for (const path of [
      "/konto",
      "/konto/zamowienia",
      "/konto/vouchery",
      "/konto/dane",
      "/konto/biblioteka",
    ]) {
      await page.goto(path);
      await page.waitForTimeout(900);
      problems.push(
        ...(await findLayoutProblems(page)).map(
          (entry) => `${width}px ${path}: ${entry}`,
        ),
      );
    }
  }
  await page.goto("/konto/biblioteka");
  const reader = (await page
    .getByRole("link", { name: "Czytaj" })
    .first()
    .getAttribute("href"))!;
  const player = (await page
    .getByRole("link", { name: "Słuchaj" })
    .first()
    .getAttribute("href"))!;
  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: 900 });
    for (const path of [reader, player]) {
      await page.goto(path);
      await page.waitForTimeout(900);
      problems.push(
        ...(await findLayoutProblems(page)).map(
          (entry) => `${width}px ${path}: ${entry}`,
        ),
      );
    }
  }
  expect(problems).toEqual([]);
});

test("układ: panel administracyjny we wszystkich szerokościach", async ({
  page,
}) => {
  test.setTimeout(600_000);
  const problems: string[] = [];
  await page.goto("/admin/logowanie");
  await page.getByLabel("Adres e-mail").fill(ADMIN.email);
  await page.getByLabel("Hasło").fill(ADMIN.password);
  await page.getByRole("button", { name: "Zaloguj się" }).click();
  await page.waitForURL(/\/admin$/);
  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: 900 });
    for (const path of [
      "/admin",
      "/admin/zamowienia",
      "/admin/produkty",
      "/admin/vouchery",
      "/admin/klienci",
      "/admin/rabaty",
      "/admin/strony",
      "/admin/ustawienia",
      "/admin/raporty",
    ]) {
      await page.goto(path);
      await page.waitForTimeout(900);
      problems.push(
        ...(await findLayoutProblems(page)).map(
          (entry) => `${width}px ${path}: ${entry}`,
        ),
      );
    }
  }
  expect(problems).toEqual([]);
});

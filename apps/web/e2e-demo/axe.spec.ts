import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { ADMIN, acceptEssentialCookies, CUSTOMER } from "./helpers";

/**
 * Accessibility and contrast (WCAG 2.1 A/AA) on the real stack, including states that only exist
 * after interaction: a delivery method chosen, a company invoice, an open modal.
 */
test.beforeEach(async ({ context, baseURL }) => {
  await acceptEssentialCookies(context, baseURL!);
});

async function violations(page: Page, name: string): Promise<string[]> {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  return result.violations
    .filter(
      (violation) =>
        violation.impact === "serious" || violation.impact === "critical",
    )
    .map(
      (violation) =>
        `${name}: ${violation.id} (${violation.impact}) — ${violation.nodes
          .slice(0, 3)
          .map(
            (node) =>
              `${node.target.join(" ")} [${node.any[0]?.message ?? node.failureSummary?.split("\n")[1] ?? ""}]`,
          )
          .join(" | ")}`,
    );
}

test("axe: strony publiczne i produkty", async ({ page }) => {
  test.setTimeout(300_000);
  const found: string[] = [];
  for (const path of [
    "/",
    "/sklep",
    "/sklep?q=xyzxyz",
    "/sklep/zmysly-w-domu",
    "/sklep/kiedy-zmysly-mowia-glosniej",
    "/sklep/integracja-sensoryczna-w-codziennosci",
    "/sklep/konsultacja-psychologiczna",
    "/konto",
    "/pomoc",
    "/pomoc/odstapienie",
    "/regulamin",
    "/o-autorce",
    "/dostawa-i-platnosci",
    "/nie-ma-takiej",
  ]) {
    await page.goto(path);
    await page.waitForTimeout(900);
    found.push(...(await violations(page, path)));
  }
  expect(found).toEqual([]);
});

test("axe: koszyk i checkout we wszystkich stanach dostawy i faktury", async ({
  page,
}) => {
  test.setTimeout(300_000);
  const found: string[] = [];
  await page.goto("/sklep/integracja-sensoryczna-w-codziennosci");
  await page.getByRole("button", { name: "Kup książkę" }).first().click();
  await expect(page).toHaveURL(/\/zamowienie/);
  await expect(page.getByLabel("Imię")).toBeVisible();
  found.push(...(await violations(page, "/zamowienie (start)")));
  for (const label of [
    "Paczkomat InPost",
    "Kurier InPost",
    "Odbiór w gabinecie",
  ]) {
    await page.locator("label", { hasText: label }).first().click();
    await page.waitForTimeout(900);
    found.push(...(await violations(page, `/zamowienie (${label})`)));
  }
  await page.locator("label", { hasText: "Paczkomat InPost" }).first().click();
  await page.getByRole("button", { name: "Wybierz Paczkomat" }).click();
  await page.waitForTimeout(500);
  found.push(...(await violations(page, "/zamowienie (okno Paczkomatu)")));
  await page.getByLabel("Miasto lub kod pocztowy").fill("Olsztyn");
  await page.getByRole("button", { name: "Szukaj punktów" }).click();
  await expect(
    page.getByRole("button", { name: "Wybierz ten punkt" }).first(),
  ).toBeVisible();
  found.push(...(await violations(page, "/zamowienie (wyniki Paczkomatów)")));
  await page.getByRole("button", { name: "Wybierz ten punkt" }).first().click();
  await page.waitForTimeout(500);
  found.push(...(await violations(page, "/zamowienie (wybrany Paczkomat)")));
  await page.locator("label", { hasText: "Dane firmy i NIP" }).click();
  await page.waitForTimeout(300);
  found.push(...(await violations(page, "/zamowienie (firma)")));
  await page.goto("/koszyk");
  await page.waitForTimeout(900);
  found.push(...(await violations(page, "/koszyk")));
  await page.locator("label", { hasText: "Paczkomat InPost" }).first().click();
  await page.waitForTimeout(900);
  found.push(...(await violations(page, "/koszyk (dostawa wybrana)")));
  expect(found).toEqual([]);
});

test("axe: konto, biblioteka, czytnik i odtwarzacz", async ({ page }) => {
  test.setTimeout(300_000);
  const found: string[] = [];
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
  found.push(...(await violations(page, "/konto (zalogowana)")));
  for (const path of [
    "/konto/zamowienia",
    "/konto/vouchery",
    "/konto/dane",
    "/konto/biblioteka",
  ]) {
    await page.goto(path);
    await page.waitForTimeout(1200);
    found.push(...(await violations(page, path)));
  }
  const reader = (await page
    .getByRole("link", { name: "Czytaj" })
    .first()
    .getAttribute("href"))!;
  const player = (await page
    .getByRole("link", { name: "Słuchaj" })
    .first()
    .getAttribute("href"))!;
  for (const path of [reader, player]) {
    await page.goto(path);
    await page.waitForTimeout(1200);
    found.push(...(await violations(page, path)));
  }
  expect(found).toEqual([]);
});

test("axe: panel administracyjny", async ({ page }) => {
  test.setTimeout(300_000);
  const found: string[] = [];
  await page.goto("/admin/logowanie");
  found.push(...(await violations(page, "/admin/logowanie")));
  await page.getByLabel("Adres e-mail").fill(ADMIN.email);
  await page.getByLabel("Hasło").fill(ADMIN.password);
  await page.getByRole("button", { name: "Zaloguj się" }).click();
  await page.waitForURL(/\/admin$/);
  for (const path of [
    "/admin",
    "/admin/zamowienia",
    "/admin/produkty",
    "/admin/vouchery",
    "/admin/klienci",
    "/admin/opinie",
    "/admin/zgloszenia",
    "/admin/rabaty",
    "/admin/strony",
    "/admin/raporty",
    "/admin/ustawienia",
    "/admin/dziennik",
  ]) {
    await page.goto(path);
    await page.waitForTimeout(1200);
    found.push(...(await violations(page, path)));
  }
  expect(found).toEqual([]);
});

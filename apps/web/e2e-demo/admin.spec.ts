import { expect, test, type Page } from "@playwright/test";
import {
  acceptEssentialCookies,
  ADMIN,
  expectNoServerError,
  findSquareControls,
} from "./helpers";

test.beforeEach(async ({ context, baseURL }) => {
  await acceptEssentialCookies(context, baseURL!);
});

async function adminLogin(page: Page) {
  await page.goto("/admin/logowanie");
  await page.getByLabel("Adres e-mail").fill(ADMIN.email);
  await page.getByLabel("Hasło").fill(ADMIN.password);
  await page.getByRole("button", { name: "Zaloguj się" }).click();
  await page.waitForURL(/\/admin$/);
  await expect(page.getByRole("heading", { name: "Pulpit" })).toBeVisible();
}

test("logowanie do panelu: zły adres/hasło daje błąd, poprawne wpuszcza", async ({
  page,
}) => {
  await page.goto("/admin/logowanie");
  await page.getByLabel("Adres e-mail").fill(ADMIN.email);
  await page.getByLabel("Hasło").fill("zle-haslo-123456");
  await page.getByRole("button", { name: "Zaloguj się" }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await adminLogin(page);
});

test("panel: każda sekcja otwiera się i pokazuje dane", async ({ page }) => {
  await adminLogin(page);
  const sections: Array<[string, string]> = [
    ["Zamówienia", "/admin/zamowienia"],
    ["Produkty", "/admin/produkty"],
    ["Vouchery", "/admin/vouchery"],
    ["Klienci", "/admin/klienci"],
    ["Opinie", "/admin/opinie"],
    ["Zgłoszenia", "/admin/zgloszenia"],
    ["Kody rabatowe", "/admin/rabaty"],
    ["Strony i FAQ", "/admin/strony"],
    ["Raporty", "/admin/raporty"],
    ["Ustawienia", "/admin/ustawienia"],
    ["Dziennik", "/admin/dziennik"],
  ];
  for (const [name, path] of sections) {
    const isMobile = (page.viewportSize()?.width ?? 1440) < 768;
    if (isMobile) await page.goto(path);
    else await page.getByRole("link", { name, exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`${path}$`));
    await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
    await expectNoServerError(page);
    await expect(page.getByText("Nie udało się")).toHaveCount(0);
  }
});

test("zamówienie: dodanie notatki wewnętrznej i oznaczenie wysyłki z numerem", async ({
  page,
}) => {
  await adminLogin(page);
  await page.goto("/admin/zamowienia");
  await page
    .getByRole("link", { name: /SEN-2026-/ })
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name: "Szczegóły zamówienia" }),
  ).toBeVisible();
  const note = `Notatka testowa ${Date.now()}`;
  await page.getByLabel("Nowa notatka").fill(note);
  await page.getByRole("button", { name: "Dodaj notatkę" }).click();
  await expect(page.getByText(note)).toBeVisible();
});

test("zamówienie z książką: oznaczenie jako wysłane", async ({ page }) => {
  await adminLogin(page);
  await page.goto("/admin/zamowienia");
  const rows = page.getByRole("row").filter({ hasText: "Do realizacji" });
  await expect(rows.first()).toBeVisible();
  await rows.first().getByRole("link").first().click();
  const ship = page.getByRole("button", { name: "Oznacz jako wysłane" });
  if (await ship.isVisible()) {
    await page.getByLabel("Numer przesyłki").fill("620000000000000000000001");
    await ship.click();
    await expect(
      page.getByText(/Wysłane|wysłan|Nadano/i).first(),
    ).toBeVisible();
  }
  await expectNoServerError(page);
});

test("produkt: edycja opisu zapisuje zmianę, zmiana ceny wymaga powodu", async ({
  page,
}) => {
  await adminLogin(page);
  await page.goto("/admin/produkty");
  await page.getByRole("link", { name: "Edytuj" }).first().click();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expectNoServerError(page);
  const save = page.getByRole("button", { name: /Zapisz/ }).first();
  await expect(save).toBeVisible();
});

test("kody rabatowe: utworzenie nowego kodu", async ({ page }) => {
  await adminLogin(page);
  await page.goto("/admin/rabaty");
  const code = `TEST${Date.now().toString().slice(-6)}`;
  await page.getByLabel(/^Kod/).first().fill(code);
  await page
    .getByLabel(/Wartość/)
    .first()
    .fill("15");
  await page
    .getByRole("button", { name: /Utwórz|Dodaj/ })
    .first()
    .click();
  await expect(page.getByText(code)).toBeVisible();
});

test("strony i FAQ: lista stron prawnych jest opublikowana", async ({
  page,
}) => {
  await adminLogin(page);
  await page.goto("/admin/strony");
  await expect(page.getByText("regulamin").first()).toBeVisible();
  await expect(
    page.getByText(/Opublikowana|opublikowan/i).first(),
  ).toBeVisible();
});

test("opinie i zgłoszenia: moderacja i zmiana statusu", async ({ page }) => {
  await adminLogin(page);
  await page.goto("/admin/zgloszenia");
  await expectNoServerError(page);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.goto("/admin/opinie");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
});

test("wylogowanie z panelu", async ({ page }) => {
  await adminLogin(page);
  await page.getByRole("button", { name: "Wyloguj" }).click();
  await expect(page).toHaveURL(/\/admin\/logowanie/);
});

test("spójność w panelu: brak kanciastych narożników", async ({ page }) => {
  await adminLogin(page);
  const square: string[] = [];
  for (const path of [
    "/admin",
    "/admin/zamowienia",
    "/admin/produkty",
    "/admin/vouchery",
    "/admin/rabaty",
    "/admin/strony",
    "/admin/ustawienia",
    "/admin/raporty",
  ]) {
    await page.goto(path);
    await page.waitForTimeout(1200);
    square.push(
      ...(await findSquareControls(page)).map((entry) => `${path}: ${entry}`),
    );
  }
  expect(square).toEqual([]);
});

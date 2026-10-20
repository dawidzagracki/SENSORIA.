import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { blockingAxeViolations } from "../a11y-tests/a11y-gate";

type State = {
  order_id: string;
  token: string;
  entitlement_id: string;
  voucher_code: string;
  admin_password: string;
};
const state = JSON.parse(process.env.STACK_STATE ?? "{}") as State;

async function audit(page: Page, label: string) {
  await expect(page.locator("main#main-content")).toHaveCount(1);
  await expect(page.locator("h1")).toHaveCount(1);
  for (const width of [360, 768, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    const sizes = await page.evaluate(() => ({
      viewport: window.innerWidth,
      document: document.documentElement.scrollWidth,
    }));
    expect(sizes.document, `${label}: poziome przewijanie przy ${width}px`).toBeLessThanOrEqual(
      sizes.viewport,
    );
  }
  await page.setViewportSize({ width: 1280, height: 900 });
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  const blocking = blockingAxeViolations(results.violations);
  expect(
    blocking.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`),
    `${label}: naruszenia critical/serious`,
  ).toEqual([]);
}

async function dismissCookies(page: Page) {
  const only = page.getByRole("button", { name: "Tylko niezbędne" });
  if (await only.isVisible().catch(() => false)) await only.click();
}

const publicRoutes: Array<[string, string]> = [
  ["/", "strona główna"],
  ["/sklep", "katalog"],
  ["/sklep/e2e-e-book", "produkt e-book"],
  ["/pomoc", "centrum pomocy"],
  ["/regulamin", "regulamin"],
  ["/polityka-prywatnosci", "polityka prywatności"],
  ["/polityka-cookies", "polityka cookies"],
  ["/o-autorce", "o autorce"],
  ["/dostawa-i-platnosci", "dostawa i płatności"],
  ["/pomoc/odstapienie", "odstąpienie"],
  ["/pomoc/zwroty-i-reklamacje", "zwroty i reklamacje"],
  ["/koszyk", "koszyk"],
  ["/nie-ma-takiej-strony", "404"],
];

test("cookie banner zapisuje wybór i znika", async ({ page }) => {
  await page.goto("/");
  const banner = page.getByRole("region", { name: "Pliki cookies" });
  await expect(banner).toBeVisible();
  await page.getByRole("button", { name: "Tylko niezbędne" }).click();
  await expect(banner).toBeHidden();
  const cookie = (await page.context().cookies()).find((c) => c.name === "sensoria_cookie_consent");
  expect(cookie).toBeTruthy();
  await page.reload();
  await expect(page.getByRole("region", { name: "Pliki cookies" })).toBeHidden();
  await page.getByRole("button", { name: "Ustawienia cookies" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("dialog").getByRole("button", { name: "Zapisz wybór" }).click();
});

for (const [path, label] of publicRoutes) {
  test(`dostępność: ${label}`, async ({ page }) => {
    await page.goto(path);
    await dismissCookies(page);
    await audit(page, label);
  });
}

test("potwierdzenie zamówienia pokazuje materiały, voucher i dokumenty", async ({ page }) => {
  await page.goto(`/zamowienie/potwierdzenie?order=${state.order_id}&token=${state.token}`);
  await dismissCookies(page);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Zamówienie opłacone");
  await expect(page.getByText("Twoje materiały")).toBeVisible();
  await expect(page.getByRole("link", { name: /Czytaj w przeglądarce/ })).toBeVisible();
  await expect(page.getByText(state.voucher_code)).toBeVisible();
  await expect(page.getByRole("link", { name: /Paragon PAR\// })).toBeVisible();
  await audit(page, "potwierdzenie");
});

test("czytnik: spis treści, nawigacja i powiększanie", async ({ page }) => {
  await page.goto(`/konto/czytnik/${state.entitlement_id}?order_token=${state.token}`);
  await dismissCookies(page);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Wstęp");
  await expect(page.getByText("Egzemplarz dla: kupujaca@sensoria.test")).toBeVisible();
  await page.getByRole("button", { name: "Następny rozdział →" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Dalej");
  await page.getByRole("button", { name: "Powiększ tekst" }).click();
  await audit(page, "czytnik");
});

test("odtwarzacz audiobooka nie istnieje dla e-booka (komunikat)", async ({ page }) => {
  await page.goto(`/konto/odtwarzacz/${state.entitlement_id}?order_token=${state.token}`);
  await expect(page.locator("main#main-content")).toHaveCount(1);
});

test("weryfikacja vouchera po kodzie", async ({ page }) => {
  await page.goto(`/voucher/${state.voucher_code}`);
  await dismissCookies(page);
  await expect(page.getByText(state.voucher_code)).toBeVisible();
  await expect(page.getByText(/Aktywny|Zrealizowany/)).toBeVisible();
  await audit(page, "weryfikacja vouchera");
});

test("formularz opinii z linku z e-maila", async ({ page }) => {
  await page.goto(`/opinie/nowa?order=${state.order_id}&token=${state.token}`);
  await dismissCookies(page);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Twoja opinia");
  await audit(page, "opinia");
});

test("panel: logowanie, pulpit i widoki", async ({ page }) => {
  await page.goto("/admin/logowanie");
  await dismissCookies(page);
  await audit(page, "logowanie admina");
  await page.getByLabel("Adres e-mail").fill("owner@sensoria.test");
  await page.getByLabel("Hasło").fill(state.admin_password);
  await page.getByRole("button", { name: "Zaloguj się" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Pulpit" })).toBeVisible();
  await audit(page, "pulpit");
  for (const [href, heading] of [
    ["/admin/zamowienia", "Zamówienia"],
    ["/admin/produkty", "Produkty"],
    ["/admin/vouchery", "Vouchery"],
    ["/admin/klienci", "Klienci"],
    ["/admin/opinie", "Moderacja opinii"],
    ["/admin/zgloszenia", "Zgłoszenia klientek"],
    ["/admin/rabaty", "Kody rabatowe"],
    ["/admin/strony", "Strony i FAQ"],
    ["/admin/raporty", "Raporty sprzedaży"],
    ["/admin/ustawienia", "Ustawienia"],
    ["/admin/dziennik", "Dziennik zdarzeń"],
  ] as const) {
    await page.goto(href);
    await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
    await audit(page, heading);
  }
  await page.goto("/admin/zamowienia");
  await page.getByRole("link", { name: /^SEN-/ }).first().click();
  await expect(page.getByRole("heading", { level: 1, name: "Szczegóły zamówienia" })).toBeVisible();
  await expect(page.getByText("Pozycje")).toBeVisible();
  await audit(page, "szczegóły zamówienia");
});

test("panel: niezalogowana dostaje ekran logowania", async ({ page }) => {
  await page.goto("/admin/zamowienia");
  await page.waitForURL("**/admin/logowanie");
});

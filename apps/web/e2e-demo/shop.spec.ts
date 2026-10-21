import { expect, test } from "@playwright/test";
import {
  acceptEssentialCookies,
  cartCount,
  expectNoServerError,
} from "./helpers";

test.beforeEach(async ({ context, baseURL }) => {
  await acceptEssentialCookies(context, baseURL!);
});

test("strona główna: karta produktu dodaje do koszyka i pokazuje potwierdzenie", async ({
  page,
}) => {
  await page.goto("/");
  await expectNoServerError(page);
  const card = page.locator("article", { hasText: "Zmysły w domu" }).first();
  await card.getByRole("button", { name: "Do koszyka" }).click();
  await expect(
    page.getByRole("status").getByText("Dodano do koszyka: Zmysły w domu"),
  ).toBeVisible();
  await expect.poll(() => cartCount(page)).toBe(1);
});

test("katalog: filtry, wyszukiwarka i brak wyników działają", async ({
  page,
}) => {
  await page.goto("/sklep");
  await expect(
    page.getByText("6 produktów", { exact: true }).locator("visible=true"),
  ).toBeVisible();
  const filters = page
    .locator("aside, dialog")
    .filter({ hasText: "Kategorie" })
    .first();
  if (!(await filters.isVisible()))
    await page.getByRole("button", { name: /^Filtry/ }).click();
  await page
    .getByRole("button", { name: /^Audiobooki/ })
    .first()
    .click();
  await expect(page).toHaveURL(/category=audiobooki/);
  await expect(
    page.getByText("1 produkt", { exact: true }).locator("visible=true"),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Kiedy zmysły mówią głośniej" }),
  ).toBeVisible();

  await page.goto("/sklep");
  await page
    .getByRole("searchbox", { name: "Szukaj w katalogu" })
    .fill("voucher");
  await page.getByRole("button", { name: "Szukaj", exact: true }).click();
  await expect(page).toHaveURL(/q=voucher/);
  await expect(
    page.getByRole("heading", { name: "Konsultacja psychologiczna" }),
  ).toBeVisible();

  await page.goto("/sklep?q=xyzxyzxyz");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    /Nie znaleziono|Brak/i,
  );
  await expectNoServerError(page);
});

test("katalog: karta prowadzi do strony produktu, a stary adres /produkt/ przekierowuje", async ({
  page,
}) => {
  await page.goto("/sklep");
  await page
    .getByRole("link", { name: "Regulacja emocji u dziecka — kurs PDF" })
    .first()
    .click();
  await expect(page).toHaveURL(/\/sklep\/regulacja-emocji-u-dziecka-kurs-pdf/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Regulacja emocji",
  );
  await page.goto("/produkt/regulacja-emocji-u-dziecka-kurs-pdf");
  await expect(page).toHaveURL(/\/sklep\/regulacja-emocji-u-dziecka-kurs-pdf/);
});

for (const [slug, heading] of [
  ["zmysly-w-domu", "Zmysły w domu"],
  ["regulacja-emocji-u-dziecka-kurs-pdf", "Regulacja emocji"],
  ["kiedy-zmysly-mowia-glosniej", "Kiedy zmysły mówią głośniej"],
  ["integracja-sensoryczna-w-codziennosci", "Integracja sensoryczna"],
] as const) {
  test(`produkt ${slug}: można dodać do koszyka`, async ({ page }) => {
    await page.goto(`/sklep/${slug}`);
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      heading,
    );
    await expectNoServerError(page);
    await page.getByRole("button", { name: "Do koszyka" }).first().click();
    await expect(page.getByText("Produkt dodano do koszyka.")).toBeVisible();
    await expect.poll(() => cartCount(page)).toBe(1);
    await page.getByRole("link", { name: /^Koszyk/ }).click();
    await expect(page).toHaveURL(/\/koszyk/);
    await expect(
      page.getByRole("heading", { name: new RegExp(heading) }).first(),
    ).toBeVisible();
  });
}

test("voucher: wybór wariantu zmienia cenę, a zakup prowadzi do zamówienia", async ({
  page,
}) => {
  await page.goto("/sklep/konsultacja-psychologiczna");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Konsultacja psychologiczna",
  );
  await page.locator("label", { hasText: "Wideorozmowa" }).click();
  await expect(page.getByText("220,00 zł").first()).toBeVisible();
  await page.getByRole("button", { name: "Kup voucher" }).first().click();
  await expect(page).toHaveURL(/\/zamowienie/);
  await expect(
    page.getByText("Konsultacja psychologiczna").first(),
  ).toBeVisible();
});

test("koszyk: ilość, kod rabatowy, usuwanie i wybór dostawy", async ({
  page,
}) => {
  await page.goto("/sklep/integracja-sensoryczna-w-codziennosci");
  await page.getByRole("button", { name: "Do koszyka" }).first().click();
  await expect(page.getByText("Produkt dodano do koszyka.")).toBeVisible();
  await page.goto("/sklep/zmysly-w-domu");
  await page.getByRole("button", { name: "Do koszyka" }).first().click();
  await expect(page.getByText("Produkt dodano do koszyka.")).toBeVisible();

  await page.goto("/koszyk");
  await expect(
    page.getByText("Integracja sensoryczna w codzienności").first(),
  ).toBeVisible();
  await page
    .getByRole("button", { name: /Zwiększ ilość|\+/ })
    .first()
    .click();
  await expect(page.getByText("2", { exact: true }).first()).toBeVisible();

  await page.getByLabel("Kod rabatowy").fill("WITAJ10");
  await page.getByRole("button", { name: "Użyj" }).click();
  await expect(page.getByText(/WITAJ10/).first()).toBeVisible();

  await page.locator("label", { hasText: "Odbiór w gabinecie" }).click();
  await expect(
    page.getByRole("radio", { name: /Odbiór w gabinecie/ }),
  ).toBeChecked();
  await expect(
    page.getByRole("link", { name: /Przejdź do płatności/ }),
  ).toBeVisible();

  await page.getByRole("button", { name: /Usuń/ }).first().click();
  await expect.poll(() => cartCount(page)).toBeLessThan(3);
});

test("zakup gościa: checkout → bramka płatności → potwierdzenie → dostęp do materiału", async ({
  page,
}) => {
  await page.goto("/sklep/zmysly-w-domu");
  await page
    .getByRole("button", { name: "Kup i pobierz teraz" })
    .first()
    .click();
  await expect(page).toHaveURL(/\/zamowienie/);
  await page
    .getByLabel(/Adres e-mail/)
    .fill(`gosc-${Date.now()}@sensoria.demo`);
  await page.getByLabel(/Akceptuję regulamin/).check();
  await page.getByLabel(/Żądam udostępnienia treści cyfrowej/).check();
  await page.getByRole("button", { name: /Zamawiam i płacę/ }).click();
  await page.waitForURL(/localhost:9911\/pay\//);
  await expect(page.getByText("Tryb demonstracyjny")).toBeVisible();
  await page.getByRole("button", { name: /Zapłać BLIK/ }).click();
  await page.waitForURL(/\/zamowienie\/potwierdzenie/);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expectNoServerError(page);
  await expect(page.getByText(/opłacone|Dziękujemy/i).first()).toBeVisible();
  const read = page
    .getByRole("link", { name: /Czytaj|Otwórz|Czytnik/ })
    .first();
  await expect(read).toBeVisible();
  await read.click();
  await expect(page).toHaveURL(/\/konto\/czytnik\//);
  await expect(
    page.getByRole("heading", { name: /Zmysły i codzienność/ }).first(),
  ).toBeVisible();
});

test("strony informacyjne i prawne otwierają się bez błędów", async ({
  page,
}) => {
  for (const path of [
    "/regulamin",
    "/polityka-prywatnosci",
    "/polityka-cookies",
    "/dostawa-i-platnosci",
    "/o-autorce",
    "/pomoc",
    "/pomoc/odstapienie",
    "/pomoc/zwroty-i-reklamacje",
  ]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
    await expectNoServerError(page);
    await expect(page.getByText("Ta treść jest w przygotowaniu")).toHaveCount(
      0,
    );
  }
});

test("pomoc: wyszukiwarka FAQ i rozwijanie odpowiedzi", async ({ page }) => {
  await page.goto("/pomoc");
  await page.getByRole("button", { name: "Jak zrealizować voucher?" }).click();
  await expect(page.getByText(/Podaj kod z vouchera/)).toBeVisible();
});

test("stopka: ustawienia cookies otwierają okno i zapisują wybór", async ({
  page,
  context,
  baseURL,
}) => {
  await context.clearCookies();
  await page.goto("/");
  await page.getByRole("button", { name: "Tylko niezbędne" }).click();
  await expect(
    page.getByRole("button", { name: "Tylko niezbędne" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Ustawienia cookies" }).click();
  await expect(
    page.getByRole("dialog", { name: "Ustawienia cookies" }),
  ).toBeVisible();
  await page.getByLabel(/Analityczne/).check();
  await page.getByRole("button", { name: "Zapisz wybór" }).click();
  await expect(page.getByRole("dialog")).toBeHidden();
  void baseURL;
});

test("e-book: darmowy fragment PDF otwiera się w oknie", async ({ page }) => {
  await page.goto("/sklep/zmysly-w-domu");
  await page
    .getByRole("button", { name: /Przeczytaj darmowy fragment/ })
    .click();
  await expect(
    page.getByRole("dialog", { name: "Darmowy fragment PDF" }),
  ).toBeVisible();
  await expect(page.getByTitle(/Darmowy fragment produktu/)).toBeVisible();
});

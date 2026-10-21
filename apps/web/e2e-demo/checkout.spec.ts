import { expect, test, type Page } from "@playwright/test";
import { acceptEssentialCookies, expectNoServerError } from "./helpers";

test.beforeEach(async ({ context, baseURL }) => {
  await acceptEssentialCookies(context, baseURL!);
});

async function addBookAndOpenCheckout(page: Page) {
  await page.goto("/sklep/integracja-sensoryczna-w-codziennosci");
  await page.getByRole("button", { name: "Kup książkę" }).first().click();
  await expect(page).toHaveURL(/\/zamowienie/);
  await expect(page.getByLabel("Imię")).toBeVisible();
}

async function fillBuyer(
  page: Page,
  email = `kupujacy-${Date.now()}@sensoria.demo`,
) {
  await page.getByLabel(/Adres e-mail/).fill(email);
  await page.getByLabel("Imię").fill("Ewa");
  await page.getByLabel("Nazwisko").fill("Pokazowa");
  await page.getByLabel("Telefon").fill("600200300");
}

async function acceptTermsAndPay(page: Page) {
  await page.getByLabel(/Akceptuję regulamin/).check();
  await page.getByRole("button", { name: /Zamawiam i płacę/ }).click();
  await page.waitForURL(/localhost:9911\/pay\//);
  await page.getByRole("button", { name: /Zapłać BLIK/ }).click();
  await page.waitForURL(/\/zamowienie\/potwierdzenie/);
  await expectNoServerError(page);
}

test("książka: odbiór w gabinecie, bez adresu, płatność i potwierdzenie", async ({
  page,
}) => {
  await addBookAndOpenCheckout(page);
  await fillBuyer(page);
  await page.locator("label", { hasText: "Odbiór w gabinecie" }).click();
  await acceptTermsAndPay(page);
  await expect(page.getByText(/odbi[oó]r|gabinet/i).first()).toBeVisible();
});

test("książka: kurier z adresem dostawy", async ({ page }) => {
  await addBookAndOpenCheckout(page);
  await fillBuyer(page);
  await page.locator("label", { hasText: "Kurier InPost" }).click();
  await page.getByLabel("Ulica i numer").first().fill("ul. Lipowa 5/3");
  await page.getByLabel("Kod pocztowy").first().fill("10-123");
  await page.getByLabel("Miejscowość").first().fill("Olsztyn");
  await expect(page.getByText(/30,00 zł|18,00 zł/).first()).toBeVisible();
  await acceptTermsAndPay(page);
  await expect(
    page.getByText(/Dostawa: Kurier — ul. Lipowa 5\/3, 10-123 Olsztyn/),
  ).toBeVisible();
  await expect
    .poll(
      async () =>
        (await page
          .getByRole("link", { name: /^Koszyk/ })
          .getAttribute("aria-label")) ?? "",
    )
    .toContain("pusty");
});

test("książka: wybór Paczkomatu z wyszukiwarki punktów", async ({ page }) => {
  await addBookAndOpenCheckout(page);
  await fillBuyer(page);
  await page.locator("label", { hasText: "Paczkomat InPost" }).click();
  await page.getByRole("button", { name: "Wybierz Paczkomat" }).click();
  await page.getByLabel("Miasto lub kod pocztowy").fill("Olsztyn");
  await page.getByRole("button", { name: "Szukaj punktów" }).click();
  const point = page.getByRole("button", { name: "Wybierz ten punkt" }).first();
  await expect(point).toBeVisible();
  await point.click();
  await expect(page.getByText(/OLS0\dM/).first()).toBeVisible();
  await acceptTermsAndPay(page);
  await expect(page.getByText(/OLS0\dM/).first()).toBeVisible();
});

test("firma: dane do faktury z NIP i faktura VAT po płatności", async ({
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
    .fill(`firma-${Date.now()}@sensoria.demo`);
  await page.locator("label", { hasText: "Dane firmy i NIP" }).click();
  await page.getByLabel(/Nazwa firmy/).fill("Pokazowa Sp. z o.o.");
  await page.getByRole("textbox", { name: "NIP" }).fill("5260250995");
  await page
    .getByLabel(/Ulica i numer/)
    .last()
    .fill("ul. Prosta 1");
  await page
    .getByLabel(/Kod pocztowy/)
    .last()
    .fill("00-001");
  await page
    .getByLabel(/Miejscowość/)
    .last()
    .fill("Warszawa");
  await page.getByLabel(/Akceptuję regulamin/).check();
  await page.getByLabel(/Żądam udostępnienia treści cyfrowej/).check();
  await page.getByRole("button", { name: /Zamawiam i płacę/ }).click();
  await page.waitForURL(/localhost:9911\/pay\//);
  await page.getByRole("button", { name: /Zapłać kartą/ }).click();
  await page.waitForURL(/\/zamowienie\/potwierdzenie/);
  await expect(page.getByText(/Faktura VAT|FV\//).first()).toBeVisible({
    timeout: 30_000,
  });
});

test("kod rabatowy obniża kwotę do zapłaty w koszyku i checkoucie", async ({
  page,
}) => {
  await page.goto("/sklep/regulacja-emocji-u-dziecka-kurs-pdf");
  await page.getByRole("button", { name: "Do koszyka" }).first().click();
  await expect(page.getByText("Produkt dodano do koszyka.")).toBeVisible();
  await page.goto("/koszyk");
  await page.getByLabel("Kod rabatowy").fill("WITAJ10");
  await page.getByRole("button", { name: "Użyj" }).click();
  await expect(page.getByText(/89,10 zł/).first()).toBeVisible();
  await page.getByRole("link", { name: /Przejdź do płatności/ }).click();
  await expect(page).toHaveURL(/\/zamowienie/);
  await expect(page.getByText(/89,10 zł/).first()).toBeVisible();
});

test("voucher w prezencie: dane obdarowanej osoby i termin wysyłki", async ({
  page,
}) => {
  await page.goto("/sklep/konsultacja-psychologiczna");
  await page
    .locator("label", { hasText: "Kupujesz w prezencie?" })
    .first()
    .click();
  await page.getByRole("button", { name: "Kup voucher" }).first().click();
  await expect(page).toHaveURL(/\/zamowienie/);
  await expect(
    page.getByText(/Dane prezentowe|obdarowan/i).first(),
  ).toBeVisible();
});

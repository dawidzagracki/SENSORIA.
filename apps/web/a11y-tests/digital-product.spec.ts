import { expect, test } from "@playwright/test";

test("e-book SSR uses real fixture fields, sale history, and safe product JSON-LD", async ({
  page,
}) => {
  const response = await page.goto("/sklep/ebook-testowy");
  expect(response?.status()).toBe(200);
  await expect(
    page.getByRole("heading", { level: 1, name: "E-book demonstracyjny" }),
  ).toBeVisible();
  await expect(
    page.locator("main").getByText("PDF · 148 stron").first(),
  ).toBeVisible();
  await expect(
    page.getByText("Najniższa cena z 30 dni przed obniżką: 89,00 zł").first(),
  ).toBeVisible();
  await expect(page.getByText("−20%", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Podobne materiały" }),
  ).toBeVisible();
  await expect(page.getByText("Kupując treść cyfrową")).toBeVisible();

  const html = await response?.text();
  expect(html).toContain("E-book demonstracyjny");
  const jsonLd = await page
    .locator('script[type="application/ld+json"]')
    .textContent();
  expect(JSON.parse(jsonLd ?? "{}")).toMatchObject({
    "@type": "Product",
    name: "E-book demonstracyjny",
    offers: { price: "79.00", priceCurrency: "PLN" },
  });
  expect(jsonLd).not.toContain("aggregateRating");
  expect(html).not.toContain("128 opinii");
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.screenshot({
    path: "../../docs/audit/evidence/after/ebook-08-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 768, height: 1024 });
  await page.screenshot({
    path: "../../docs/audit/evidence/after/ebook-08-768.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 360, height: 800 });
  await page.screenshot({
    path: "../../docs/audit/evidence/after/ebook-08-360.png",
    fullPage: true,
  });
});

test("kurs PDF używa swojego rodzaju i nie pokazuje obniżki bez compare_at_price", async ({
  page,
}) => {
  await page.goto("/sklep/kurs-testowy");
  await expect(
    page.getByRole("heading", { level: 1, name: "Kurs testowy PDF" }),
  ).toBeVisible();
  await expect(
    page.getByText("KURS PDF", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByText("Najniższa cena z 30 dni przed obniżką:"),
  ).toHaveCount(0);
  await expect(page.getByText("−20%", { exact: true })).toHaveCount(0);
});

test("otwiera osobny, publiczny podgląd PDF po świadomym żądaniu", async ({
  page,
}) => {
  await page.goto("/sklep/ebook-testowy");
  const opening = page.waitForRequest(
    (request) =>
      request.method() === "POST" && request.url().includes("/sample/open"),
  );
  await page
    .getByRole("button", { name: "Przeczytaj darmowy fragment · 2 strony" })
    .click();
  await opening;
  await expect(
    page.getByRole("dialog", { name: "Darmowy fragment PDF" }),
  ).toBeVisible();
  await expect(
    page.getByTitle("Darmowy fragment produktu, 2 stron"),
  ).toBeVisible();
});

test("produkt cyfrowy dodaje się do serwerowego koszyka przed przejściem do zamówienia", async ({
  page,
}) => {
  await page.goto("/sklep/ebook-testowy");
  await page.getByRole("button", { name: "Kup i pobierz teraz" }).click();
  await expect(page).toHaveURL(/\/zamowienie$/);
  await expect(page.getByRole("link", { name: /Koszyk/ })).toHaveAccessibleName(
    /Koszyk, 1 produkt/,
  );
});

test("produkt cyfrowy nie powoduje poziomego przepełnienia na breakpointach", async ({
  page,
}) => {
  await page.goto("/sklep/ebook-testowy");
  for (const width of [360, 768, 1024, 1280]) {
    await page.setViewportSize({ width, height: width === 360 ? 780 : 1000 });
    const dimensions = await page.evaluate(() => ({
      client: document.documentElement.clientWidth,
      scroll: document.documentElement.scrollWidth,
    }));
    expect(dimensions.scroll, `overflow at ${width}px`).toBeLessThanOrEqual(
      dimensions.client,
    );
    if (width === 768 || width === 1024) {
      await page.screenshot({
        path: `../../docs/audit/evidence/after/ebook-08-${width}.png`,
        fullPage: true,
      });
    }
  }
  await page.setViewportSize({ width: 360, height: 780 });
  await expect(
    page.getByRole("button", { name: "Kup i pobierz", exact: true }),
  ).toBeVisible();
});

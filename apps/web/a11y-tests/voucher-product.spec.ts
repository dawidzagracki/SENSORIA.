import { expect, test } from "@playwright/test";

test("voucher renderuje dane API i JSON-LD wariantów z cenami PLN", async ({
  page,
}) => {
  const response = await page.goto(
    "/sklep/konsultacja-z-psychologiem?variant=online",
  );
  expect(response?.status()).toBe(200);
  await expect(
    page.getByRole("heading", { name: "Konsultacja z psychologiem", level: 1 }),
  ).toBeVisible();
  await expect(page.getByRole("radio", { name: /Online/ })).toBeChecked();
  await expect(
    page.getByText("220,00 zł", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByText("Usługa zwolniona z VAT · cena ostateczna"),
  ).toBeVisible();
  await expect(
    page.getByRole("checkbox", { name: /Kupujesz w prezencie/ }),
  ).toBeEnabled();
  await expect(
    page.getByRole("button", {
      name: "Czy voucher mogę podarować komuś innemu?",
    }),
  ).toHaveAttribute("aria-expanded", "true");
  await expect(
    page.getByRole("button", { name: /Czy dostanę fakturę/ }),
  ).toHaveAttribute("aria-expanded", "false");
  const jsonLd = await page
    .locator('script[type="application/ld+json"]')
    .textContent();
  const parsed = JSON.parse(jsonLd ?? "null") as {
    "@type": string;
    hasVariant: Array<{
      identifier: string;
      offers: { price: string; priceCurrency: string; url: string };
    }>;
  };
  expect(parsed["@type"]).toBe("ProductGroup");
  expect(parsed.hasVariant).toHaveLength(2);
  expect(parsed.hasVariant[1]).toMatchObject({
    identifier: "00000000-0000-4000-8000-000000000912",
    offers: {
      price: "220.00",
      priceCurrency: "PLN",
      url: "http://localhost:3102/sklep/konsultacja-z-psychologiem?variant=online",
    },
  });
  await page.goto("/sklep/konsultacja-z-psychologiem");
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.screenshot({
    path: "../../docs/audit/evidence/after/voucher-02-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 768, height: 1024 });
  await page.screenshot({
    path: "../../docs/audit/evidence/after/voucher-02-768.png",
    fullPage: true,
  });
});

test("wariant synchronizuje radio, cenę, URL oraz Back/Forward", async ({
  page,
}) => {
  await page.goto("/sklep/konsultacja-z-psychologiem");
  const online = page.getByRole("radio", { name: /Online/ });
  await page.getByRole("radio", { name: /W gabinecie w Olsztynie/ }).focus();
  await page.keyboard.press("ArrowDown");
  await expect(online).toBeChecked();
  await expect(page).toHaveURL(/variant=online/);
  await expect(
    page.getByText("220,00 zł", { exact: true }).first(),
  ).toBeVisible();

  await page.goBack();
  await expect(page).toHaveURL(/\/sklep\/konsultacja-z-psychologiem$/);
  await expect(
    page.getByRole("radio", { name: /W gabinecie w Olsztynie/ }),
  ).toBeChecked();
  await expect(
    page.getByText("250,00 zł", { exact: true }).first(),
  ).toBeVisible();
  await page.goForward();
  await expect(online).toBeChecked();
  await page.reload();
  await expect(online).toBeChecked();
});

test("nieprawidłowy wariant jest usuwany, a brak produktu zwraca 404", async ({
  page,
}) => {
  await page.goto(
    "/sklep/konsultacja-z-psychologiem?campaign=sample&variant=unknown",
  );
  await expect(page).toHaveURL(/campaign=sample/);
  await expect(page).not.toHaveURL(/variant=/);
  await expect(
    page.getByRole("radio", { name: /W gabinecie w Olsztynie/ }),
  ).toBeChecked();

  const response = await page.goto("/sklep/brak-produktu");
  expect(response?.status()).toBe(404);
});

test("produkt innego rodzaju nie dostaje widoku vouchera", async ({ page }) => {
  await page.goto("/sklep/produkt-ksiazka-testowa");
  await expect(page).toHaveURL(/\/sklep\/produkt-ksiazka-testowa$/);
  await expect(
    page.getByRole("heading", { name: "Książka testowa", level: 1 }),
  ).toBeVisible();
  await expect(page.getByText("Voucher na wizytę")).toHaveCount(0);
});

test("strona i pasek zakupu nie powodują poziomego przewijania na breakpointach", async ({
  page,
}) => {
  await page.goto("/sklep/konsultacja-z-psychologiem?variant=online");
  for (const width of [360, 768, 1024, 1280]) {
    await page.setViewportSize({ width, height: width === 360 ? 800 : 1000 });
    const dimensions = await page.evaluate(() => ({
      documentWidth: document.documentElement.scrollWidth,
      viewportWidth: document.documentElement.clientWidth,
    }));
    expect(
      dimensions.documentWidth,
      `overflow at ${width}px`,
    ).toBeLessThanOrEqual(dimensions.viewportWidth);
    if (width === 360 || width === 768 || width === 1280) {
      await page.screenshot({
        path: `../../docs/audit/evidence/after/voucher-02-${width === 1280 ? "desktop" : width}.png`,
        fullPage: true,
      });
    }
  }
  await expect(
    page.getByRole("button", { name: "Kup voucher" }).last(),
  ).toBeVisible();
  await expect(
    page.getByRole("figure", { name: /Przykładowy podgląd/ }),
  ).toBeVisible();
});

test("dodaje voucher do koszyka i przechodzi do zamówienia po potwierdzeniu serwera", async ({
  page,
}) => {
  await page.goto("/sklep/konsultacja-z-psychologiem?variant=online");
  await page.getByRole("button", { name: "Kup voucher" }).first().click();
  await expect(page).toHaveURL(/\/zamowienie$/);
  await expect(page.getByRole("link", { name: /Koszyk/ })).toHaveAccessibleName(
    /Koszyk, 1 produkt/,
  );
});

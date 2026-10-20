import { expect, test } from "@playwright/test";

test("strona główna SSR pobiera treści i produkty, bez przepełnienia na breakpointach", async ({
  page,
}) => {
  const response = await page.goto("/");
  expect(response?.status()).toBe(200);
  const html = await response?.text();
  expect(html).toContain("INSTYTUT DIAGNOZY I TERAPII SENSORIA");
  expect(html).toContain("Płatność w 15 sekund");
  expect(html).toContain("Produkt testowy 4");

  await expect(page.locator("main#main-content")).toHaveCount(1);
  await expect(page.locator("h1")).toHaveCount(1);
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Terapia nie kończy się w gabinecie.",
  );
  await expect(
    page.getByRole("link", { name: /VOUCHER: Produkt testowy 1/ }),
  ).toHaveAttribute("href", "/sklep/produkt-testowy-1");
  await expect(
    page.getByRole("link", { name: /AUDIOBOOK: Produkt testowy 3/ }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: /KURS PDF: Produkt testowy 4/ }),
  ).toBeVisible();
  await expect(page.getByText("PRZEWIŃ, ŻEBY ZOBACZYĆ SKLEP")).toHaveAttribute(
    "aria-hidden",
    "true",
  );

  for (const width of [360, 768, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    const sizes = await page.evaluate(() => ({
      viewport: window.innerWidth,
      document: document.documentElement.scrollWidth,
    }));
    expect(sizes.document).toBeLessThanOrEqual(sizes.viewport);
  }
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.screenshot({
    path: "../../docs/audit/evidence/after/home-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 768, height: 1024 });
  await page.screenshot({
    path: "../../docs/audit/evidence/after/home-768.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 360, height: 800 });
  await page.screenshot({
    path: "../../docs/audit/evidence/after/home-360.png",
    fullPage: true,
  });
  expect(
    await page.locator('img[fetchpriority="high"]').count(),
  ).toBeLessThanOrEqual(1);
});

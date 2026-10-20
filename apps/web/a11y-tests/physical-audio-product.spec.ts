import { expect, test } from "@playwright/test";

test("BOOK z zerowym stockiem pozostaje publiczny, ale zakup jest zablokowany", async ({
  page,
}) => {
  const response = await page.goto("/sklep/produkt-ksiazka-testowa");
  expect(response?.status()).toBe(200);
  await expect(
    page.getByRole("heading", { level: 1, name: "Książka testowa" }),
  ).toBeVisible();
  await expect(page.getByText("Chwilowo niedostępna")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Kup książkę" }).first(),
  ).toBeDisabled();
  await expect(page.getByText("PDF", { exact: true })).toHaveCount(0);
  await expect(page.getByText(/utratę prawa do odstąpienia/)).toHaveCount(0);
  const html = await response?.text();
  expect(html).toContain("https://schema.org/OutOfStock");
});

test("BOOK pokazuje niski stan bez podawania liczby sztuk", async ({
  page,
}) => {
  await page.goto("/sklep/ksiazka-ostatnie-egzemplarze");
  await expect(page.getByText("Zostały ostatnie egzemplarze")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Kup książkę" }).first(),
  ).toBeEnabled();
  await expect(page.getByText("3 szt.")).toHaveCount(0);
});

test("dostępny audiobook trafia do koszyka przez potwierdzony endpoint serwera", async ({
  page,
}) => {
  await page.goto("/sklep/audiobook-testowy");
  await page.getByRole("button", { name: "Do koszyka" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Produkt dodano do koszyka.",
  );
  await expect(page.getByRole("link", { name: /Koszyk/ })).toHaveAccessibleName(
    /Koszyk, 1 produkt/,
  );
});

test("AUDIOBOOK formatuje czas i rozdziały z dokładnych sekund", async ({
  page,
}) => {
  await page.goto("/sklep/audiobook-testowy");
  await expect(
    page.getByRole("heading", { level: 1, name: "Audiobook testowy" }),
  ).toBeVisible();
  await expect(page.getByText("4 godz. 12 min").first()).toBeVisible();
  await expect(page.getByText("Lektorka testowa")).toBeVisible();
  await expect(page.getByText("MP3", { exact: true })).toBeVisible();
  await expect(page.getByText("Pierwszy rozdział")).toBeVisible();
  await expect(page.getByText("Drugi rozdział")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Odtwórz darmową próbkę" }),
  ).toBeVisible();
  const html = await page
    .locator('script[type="application/ld+json"]')
    .textContent();
  expect(JSON.parse(html ?? "{}")).toMatchObject({
    "@type": "Product",
    name: "Audiobook testowy",
    offers: {
      price: "50.00",
      priceCurrency: "PLN",
      availability: "https://schema.org/InStock",
    },
  });
});

test("odtwarzacz próbki jest jawny, klawiaturowy i nie startuje przy wejściu", async ({
  page,
}) => {
  await page.goto("/sklep/audiobook-testowy");
  const media = page.locator("audio");
  await expect(media).toHaveJSProperty("paused", true);
  const play = page.getByRole("button", { name: "Odtwórz darmową próbkę" });
  await expect(play).toBeVisible();
  await expect(
    page.getByText("Darmowy fragment · pełna wersja dostępna w sensoria.shop"),
  ).toBeVisible();
  await play.focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("button", { name: "Wstrzymaj próbkę" }),
  ).toBeVisible();
  await expect(media).toHaveJSProperty("paused", false);
  const pause = page.getByRole("button", { name: "Wstrzymaj próbkę" });
  await pause.focus();
  await pause.press("Enter");
  await expect(
    page.getByRole("button", { name: "Odtwórz ponownie" }),
  ).toBeVisible();
  await expect(
    page.getByRole("slider", { name: "Pozycja próbki audio" }),
  ).toBeEnabled();
});

test("audio i książka nie powodują poziomego przepełnienia przy 360 px", async ({
  page,
}) => {
  await page.setViewportSize({ width: 360, height: 780 });
  for (const path of [
    "/sklep/produkt-ksiazka-testowa",
    "/sklep/audiobook-testowy",
  ]) {
    await page.goto(path);
    const width = await page.evaluate(() => ({
      client: document.documentElement.clientWidth,
      scroll: document.documentElement.scrollWidth,
    }));
    expect(width.scroll, path).toBeLessThanOrEqual(width.client);
  }
});

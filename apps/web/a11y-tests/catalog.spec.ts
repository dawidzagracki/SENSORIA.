import { expect, test } from "@playwright/test";

test("katalog renderuje produkty po stronie serwera i zachowuje ostatnią stronę", async ({
  page,
}) => {
  const response = await page.goto("/sklep");
  expect(response?.status()).toBe(200);
  expect(await response?.text()).toContain("Produkt testowy 1");
  await expect(page.locator("main")).toHaveCount(1);
  await expect(page.locator("h1")).toHaveCount(1);
  await expect(page.locator("article")).toHaveCount(12);
  await expect(page.getByText("25 produktów", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.screenshot({
    path: "../../docs/audit/evidence/after/catalog-01-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 768, height: 1024 });
  await page.screenshot({
    path: "../../docs/audit/evidence/after/catalog-01-768.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 360, height: 800 });
  await page.screenshot({
    path: "../../docs/audit/evidence/after/catalog-01-360.png",
    fullPage: true,
  });

  await page.goto("/sklep?page=3&per_page=12&sort=price_asc");
  await expect(page.locator("article")).toHaveCount(1);
  await expect(page.getByRole("button", { name: "3" })).toHaveAttribute(
    "aria-current",
    "page",
  );
});

test("filtry, wyszukiwanie, sortowanie i historia zapisują stan w URL", async ({
  page,
}) => {
  await page.goto("/sklep?category=vouchery&page=3&per_page=24&q=terapia");
  await expect(
    page.getByRole("radio", { name: /Vouchery na wizyty/ }),
  ).toBeChecked();
  await page.getByRole("radio", { name: /Kursy PDF/ }).click();
  await expect(page).toHaveURL(/category=kursy-pdf/);
  await expect(page).toHaveURL(/q=terapia/);
  await expect(page).not.toHaveURL(/page=3/);
  await page.goBack();
  await expect(page).toHaveURL(/category=vouchery/);
  await expect(
    page.getByRole("radio", { name: /Vouchery na wizyty/ }),
  ).toBeChecked();
  await page.goForward();
  await expect(page).toHaveURL(/category=kursy-pdf/);

  const navigationCount = await page.evaluate(
    () => performance.getEntriesByType("navigation").length,
  );
  await page.getByLabel("Sortuj").selectOption("price_desc");
  await expect(page).toHaveURL(/sort=price_desc/);
  await expect(page).not.toHaveURL(/page=3/);
  expect(
    await page.evaluate(
      () => performance.getEntriesByType("navigation").length,
    ),
  ).toBe(navigationCount);
});

test("filtry wielokrotne zachowują parametry API i zerują numer strony", async ({
  page,
}) => {
  await page.goto(
    "/sklep?category=kursy-pdf&kind=DIGITAL&audience=rodzice&price_min=0&price_max=5000&delivery=digital&sort=price_desc&page=2&per_page=48&q=integracja",
  );
  await expect(page.getByRole("radio", { name: /Kursy PDF/ })).toBeChecked();
  await expect(page.getByRole("radio", { name: /Rodzice/ })).toBeChecked();
  await expect(page.getByRole("radio", { name: /do 50 zł/ })).toBeChecked();
  await expect(
    page.getByRole("radio", { name: /Od razu na mailu/ }),
  ).toBeChecked();
  await expect(page.getByLabel("Szukaj")).toHaveValue("integracja");
  await expect(page.getByLabel("Sortuj")).toHaveValue("price_desc");
  await page.getByRole("radio", { name: /Vouchery na wizyty/ }).click();
  await expect(page).toHaveURL(/category=vouchery/);
  await expect(page).toHaveURL(/kind=DIGITAL/);
  await expect(page).toHaveURL(/audience=rodzice/);
  await expect(page).toHaveURL(/price_min=0/);
  await expect(page).toHaveURL(/price_max=5000/);
  await expect(page).toHaveURL(/delivery=digital/);
  await expect(page).toHaveURL(/sort=price_desc/);
  await expect(page).toHaveURL(/per_page=48/);
  await expect(page).toHaveURL(/q=integracja/);
  await expect(page).not.toHaveURL(/page=2/);
});

test("panel mobilny ma focus, Escape, powrót fokusu i brak przepełnienia", async ({
  page,
}) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/sklep");
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(
    360,
  );
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Przejdź do treści" }),
  ).toBeFocused();
  const trigger = page.getByRole("button", { name: "Filtry" });
  await trigger.click();
  const dialog = page.getByRole("dialog", { name: "Filtry katalogu" });
  await expect(dialog).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Zamknij okno" }),
  ).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  await expect(trigger).toBeFocused();
});

test("podczas wolnego żądania pokazuje skeleton i nie przywraca starszej odpowiedzi", async ({
  page,
}) => {
  await page.goto("/sklep");
  await page.getByLabel("Szukaj").fill("delay");
  await page.getByLabel("Szukaj").press("Enter");
  await expect(
    page.getByRole("status", { name: "Ładowanie produktów" }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: /Brak wyników/ })).toHaveCount(
    0,
  );
  await page.getByLabel("Szukaj").fill("terapia");
  await page.getByLabel("Szukaj").press("Enter");
  await expect(page).toHaveURL(/q=terapia/);
  await expect(page.locator("article")).toHaveCount(12);
});

test("siatka zmienia liczbę kolumn przy szerokościach responsywnych", async ({
  page,
}) => {
  await page.goto("/sklep");
  for (const [width, expectedColumns] of [
    [360, 1],
    [768, 2],
    [1024, 3],
  ] as const) {
    await page.setViewportSize({ width, height: 900 });
    const result = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      viewport: window.innerWidth,
      columns: getComputedStyle(
        document.querySelector("article")?.parentElement as Element,
      ).gridTemplateColumns.split(" ").length,
    }));
    expect(result.scrollWidth).toBe(result.viewport);
    expect(result.columns).toBe(expectedColumns);
  }
});

test("wyszukiwanie bez wyników pokazuje ustawienia i bezpieczne rekomendacje", async ({
  page,
}) => {
  const response = await page.goto(
    "/sklep?q=brak&category=vouchery&sort=price_asc&per_page=24",
  );
  const navigationCount = await page.evaluate(
    () => performance.getEntriesByType("navigation").length,
  );
  expect(response?.status()).toBe(200);
  await expect(
    page.getByRole("heading", { name: /Brak wyników dla „brak”/ }),
  ).toBeVisible();
  await expect(page.getByLabel("Szukaj w katalogu")).toHaveValue("brak");
  await expect(page.getByText("Spróbuj:")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "integracja sensoryczna" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Materiały o zbliżonej tematyce" }),
  ).toBeVisible();
  await expect(page.locator("article")).toHaveCount(3);
  await expect(
    page.getByRole("link", { name: "Zobacz", exact: true }).first(),
  ).toHaveAttribute("href", /\/produkt\//);
  await page.setViewportSize({ width: 360, height: 900 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(
    360,
  );
  await expect(page.getByLabel("Szukaj w katalogu")).toBeVisible();
  await expect(page.getByRole("button", { name: "Szukaj" })).toBeVisible();
  expect(
    await page
      .locator("article")
      .first()
      .evaluate((card) => card.getBoundingClientRect().width),
  ).toBeLessThanOrEqual(360);

  await page.getByRole("button", { name: "integracja sensoryczna" }).click();
  await expect(page).toHaveURL(/q=integracja\+sensoryczna/);
  await expect(page.getByLabel("Szukaj w katalogu")).toHaveValue(
    "integracja sensoryczna",
  );
  await expect(page).toHaveURL(/sort=price_asc/);
  await expect(page).toHaveURL(/per_page=24/);
  await expect(page).toHaveURL(/category=vouchery/);
  expect(
    await page.evaluate(
      () => performance.getEntriesByType("navigation").length,
    ),
  ).toBe(navigationCount);
  await page.goBack();
  await expect(page).toHaveURL(/q=brak/);
  await expect(page.getByLabel("Szukaj w katalogu")).toHaveValue("brak");
  await page.goForward();
  await expect(page).toHaveURL(/q=integracja\+sensoryczna/);
  await expect(page.getByLabel("Szukaj w katalogu")).toHaveValue(
    "integracja sensoryczna",
  );
});

test("stan pusty filtrów pozwala je wyczyścić, zachowując q i sortowanie", async ({
  page,
}) => {
  await page.goto(
    "/sklep?q=brak&category=brak-produktow&sort=newest&page=3&per_page=24",
  );
  await expect(
    page.getByRole("button", { name: "Wyczyść filtry" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Wyczyść filtry" }).click();
  await expect(page).toHaveURL(/q=brak/);
  await expect(page).toHaveURL(/sort=newest/);
  await expect(page).toHaveURL(/per_page=24/);
  await expect(page).not.toHaveURL(/category=/);
  await expect(page).not.toHaveURL(/[?&]page=/);
});

test("wyniki poza zakresem i niezaufane q nie są traktowane jak pusty katalog", async ({
  page,
}) => {
  await page.goto("/sklep?page=4&per_page=12");
  await expect(
    page.getByText("Ta strona nie zawiera produktów", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: /Brak wyników/ })).toHaveCount(
    0,
  );

  let dialogOpened = false;
  page.on("dialog", async (dialog) => {
    dialogOpened = true;
    await dialog.dismiss();
  });
  await page.goto("/sklep?q=%3Cscript%3Ealert(1)%3C%2Fscript%3E");
  await expect(page.locator("#no-results-title")).toContainText(
    "<script>alert(1)</script>",
  );
  await expect(page.locator("main script")).toHaveCount(0);
  expect(dialogOpened).toBe(false);
  await expect(page.locator("main")).toHaveCount(1);
});

test("sam filtr bez wyników nie twierdzi, że temat nie istnieje", async ({
  page,
}) => {
  await page.goto("/sklep?category=brak-produktow");
  await expect(
    page.getByRole("heading", {
      name: "Brak produktów spełniających wybrane filtry",
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "Nie znaleźliśmy produktów z tym zestawem filtrów",
    }),
  ).toBeVisible();
});

test("błąd API nie jest prezentowany jako brak wyników", async ({ page }) => {
  await page.goto("/sklep?q=error");
  await expect(
    page.getByText("Nie udało się pobrać katalogu", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: /Brak wyników/ })).toHaveCount(
    0,
  );
  await expect(
    page.getByRole("button", { name: "Spróbuj ponownie" }),
  ).toBeVisible();
});

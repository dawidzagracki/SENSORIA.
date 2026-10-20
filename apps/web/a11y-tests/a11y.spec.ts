import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { blockingAxeViolations } from "./a11y-gate";

const routes = [
  "/",
  "/sklep",
  "/koszyk",
  "/zamowienie",
  "/konto",
  "/pomoc",
  "/dev/tokeny",
  "/nieistniejaca-trasa-testowa",
];
const viewportWidths = [360, 390, 640, 768, 1024, 1280];

async function scanAccessibility(page: Page, label: string) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  const blocking = blockingAxeViolations(results.violations);

  for (const violation of results.violations) {
    console.log(
      `[axe] ${label} | ${violation.impact ?? "unknown"} | ${violation.id}: ${violation.help}`,
    );
    for (const node of violation.nodes) {
      console.log(
        `  element: ${node.target.join(", ")}\n  problem: ${node.failureSummary ?? "No failure summary"}`,
      );
    }
  }
  for (const incomplete of results.incomplete) {
    console.log(
      `[axe incomplete — ręczna ocena] ${label} | ${incomplete.id}: ${incomplete.help}`,
    );
    for (const node of incomplete.nodes) {
      console.log(`  element do oceny: ${node.target.join(", ")}`);
    }
  }

  expect(
    blocking,
    `Axe reported critical/serious violations on ${label}; see the rule and element report above.`,
  ).toEqual([]);
}

test("WCAG 2.1 A/AA: wszystkie istniejące trasy i responsywne szerokości", async ({
  page,
}) => {
  for (const route of routes) {
    for (const width of viewportWidths) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(route);
      await expect(page.locator("main#main-content")).toHaveCount(1);

      const documentState = await page.evaluate(() => ({
        viewport: window.innerWidth,
        document: document.documentElement.scrollWidth,
        body: document.body.scrollWidth,
      }));
      if (
        documentState.document > documentState.viewport ||
        documentState.body > documentState.viewport
      ) {
        const offenders = await page.locator("body *").evaluateAll((elements) =>
          elements
            .map((element) => {
              const rect = element.getBoundingClientRect();
              const style = getComputedStyle(element);
              return {
                element: element.tagName.toLowerCase(),
                id: element.id,
                className:
                  typeof element.className === "string"
                    ? element.className
                    : "",
                right: Math.round(rect.right),
                width: Math.round(rect.width),
                display: style.display,
                visibility: style.visibility,
              };
            })
            .filter(
              ({ right, width, display, visibility }) =>
                width > 0 &&
                display !== "none" &&
                visibility !== "hidden" &&
                right > window.innerWidth,
            )
            .slice(0, 12),
        );
        throw new Error(
          `Poziome przepełnienie ${route} przy ${width}px: ${JSON.stringify({ documentState, offenders }, null, 2)}`,
        );
      }

      if (width === 360 || width === 1280) {
        await scanAccessibility(page, `${route} @ ${width}px`);
      }
    }
  }
});

test("axe obejmuje otwarte menu mobilne, modal, accordion i błędy pól", async ({
  page,
}) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/");
  await page.getByRole("button", { name: "Menu" }).click();
  await expect(
    page.getByRole("dialog", { name: "Nawigacja główna" }),
  ).toBeVisible();
  await scanAccessibility(page, "menu mobilne otwarte");

  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("dialog", { name: "Nawigacja główna" }),
  ).toBeHidden();

  await page.goto("/dev/tokeny");
  await scanAccessibility(page, "pola z błędami i galeria");
  const firstAccordionHeading = page
    .getByRole("button", { name: "Kiedy otrzymam materiały cyfrowe?" })
    .first();
  const secondAccordionHeading = page
    .getByRole("button", { name: "Jak wysyłana jest książka?" })
    .first();
  await firstAccordionHeading.focus();
  await page.keyboard.press("ArrowDown");
  await expect(secondAccordionHeading).toBeFocused();
  await page.keyboard.press("Home");
  await expect(firstAccordionHeading).toBeFocused();
  await page.keyboard.press("End");
  await expect(secondAccordionHeading).toBeFocused();
  await page.keyboard.press("Home");
  await page.keyboard.press("Space");
  await expect(firstAccordionHeading).toHaveAttribute("aria-expanded", "true");
  await scanAccessibility(page, "accordion rozwinięty");
  await page.getByRole("button", { name: "Otwórz Modal" }).click();
  await expect(
    page.getByRole("dialog", { name: "Przykładowe okno" }),
  ).toBeVisible();
  await scanAccessibility(page, "modal otwarty");
});

test("skip link jest pierwszym focusem i przenosi fokus do main", async ({
  page,
}) => {
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus")).toHaveText("Przejdź do treści");
  await page.keyboard.press("Enter");
  await expect(page.locator("main#main-content")).toBeFocused();
});

test("nawigacja i stopka są osiągalne klawiaturą, bez ukrytych celów", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/");
  const focusedNames: string[] = [];

  for (let index = 0; index < 40; index += 1) {
    await page.keyboard.press("Tab");
    const focusedName = await page.evaluate(() => {
      const element = document.activeElement;
      return element instanceof HTMLElement
        ? (element.innerText || element.getAttribute("aria-label") || "").trim()
        : "";
    });
    focusedNames.push(focusedName);
    if (focusedNames.some((name) => name.includes("Regulamin"))) break;
  }

  expect(focusedNames[0]).toBe("Przejdź do treści");
  expect(focusedNames.some((name) => name.includes("SENSORIA."))).toBe(true);
  expect(focusedNames.some((name) => name.includes("Vouchery"))).toBe(true);
  expect(focusedNames.some((name) => name.includes("Koszyk"))).toBe(true);
  expect(focusedNames.some((name) => name.includes("Regulamin"))).toBe(true);
});

test("długi niełamliwy tekst nie poszerza strony, a placeholder obrazu rezerwuje proporcje", async ({
  page,
}) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/dev/tokeny");
  const result = await page.locator("main#main-content").evaluate((main) => {
    const longText = document.createElement("p");
    longText.textContent = `adres-${"bardzodlugislowobezspacji".repeat(40)}.invalid`;
    main.append(longText);
    const imagePlaceholder = document.querySelector<HTMLElement>(
      '[role="img"].aspect-product-image',
    );
    const aspectRatio = imagePlaceholder
      ? getComputedStyle(imagePlaceholder).aspectRatio
      : "missing";
    return {
      viewport: window.innerWidth,
      document: document.documentElement.scrollWidth,
      body: document.body.scrollWidth,
      aspectRatio,
    };
  });

  expect(result.document).toBeLessThanOrEqual(result.viewport);
  expect(result.body).toBeLessThanOrEqual(result.viewport);
  expect(result.aspectRatio).toBe("1 / 1");
});

test("widoczne kontrolki i etykiety checkbox/radio mają obszar aktywny 44 × 44 px", async ({
  page,
}) => {
  await page.setViewportSize({ width: 360, height: 900 });
  const undersized = [];
  for (const route of ["/", "/dev/tokeny"]) {
    await page.goto(route);
    const routeUndersized = await page
      .locator("a[href], button, input, select, textarea")
      .evaluateAll((elements) =>
        elements
          .map((element) => {
            const target =
              element instanceof HTMLInputElement &&
              ["checkbox", "radio"].includes(element.type)
                ? (element.closest("label") ?? element)
                : element;
            const rect = target.getBoundingClientRect();
            return {
              name:
                target.textContent?.trim() ||
                target.getAttribute("aria-label") ||
                target.tagName.toLowerCase(),
              width: rect.width,
              height: rect.height,
              className:
                typeof target.className === "string" ? target.className : "",
              minHeight: getComputedStyle(target).minHeight,
              visible:
                rect.width > 0 &&
                rect.height > 0 &&
                getComputedStyle(target).visibility !== "hidden",
            };
          })
          .filter(
            ({ width, height, visible }) =>
              visible && (width < 44 || height < 44),
          ),
      );
    undersized.push(...routeUndersized.map((item) => ({ route, ...item })));
  }

  expect(undersized).toEqual([]);
});

test("menu zwalnia fokus i przywraca go po Escape; redukcja ruchu wyłącza animację", async ({
  page,
}) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/dev/tokeny");
  const spinner = page.locator(".animate-spin").first();
  await expect(spinner).toBeVisible();
  const reducedMotionStyles = await page.evaluate(() => ({
    preference: matchMedia("(prefers-reduced-motion: reduce)").matches,
    animationDuration: getComputedStyle(
      document.querySelector(".animate-spin")!,
    ).animationDuration,
    scrollBehavior: getComputedStyle(document.documentElement).scrollBehavior,
  }));
  expect(reducedMotionStyles.preference).toBe(true);
  expect(parseFloat(reducedMotionStyles.animationDuration)).toBeLessThanOrEqual(
    0.00001,
  );
  expect(reducedMotionStyles.scrollBehavior).toBe("auto");

  await page.goto("/");
  const menuButton = page.getByRole("button", { name: "Menu" });
  await menuButton.focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", { name: "Nawigacja główna" });
  await expect(dialog).toBeVisible();
  await page.keyboard.press("Shift+Tab");
  const focusStayedInDialog = await dialog.evaluate((element) =>
    element.contains(document.activeElement),
  );
  expect(focusStayedInDialog).toBe(true);
  await page.keyboard.press("Escape");
  await expect(menuButton).toBeFocused();

  await menuButton.click();
  await page.setViewportSize({ width: 768, height: 900 });
  await expect(dialog).toBeHidden();

  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/dev/tokeny");
  const modalTrigger = page.getByRole("button", { name: "Otwórz Modal" });
  await modalTrigger.click();
  const modal = page.getByRole("dialog", { name: "Przykładowe okno" });
  await expect(modal).toBeVisible();
  await expect(page.locator("body")).toHaveCSS("overflow", "hidden");
  await page.keyboard.press("Shift+Tab");
  expect(
    await modal.evaluate((element) => element.contains(document.activeElement)),
  ).toBe(true);
  await page.keyboard.press("Escape");
  await expect(modal).toBeHidden();
  await expect(modalTrigger).toBeFocused();
  await expect(page.locator("body")).toHaveCSS("overflow", "visible");
});

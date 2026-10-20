import { expect, test } from "@playwright/test";

const cartItem = {
  id: "cart-line-1",
  product_id: "book-1",
  slug: "ksiazka-testowa",
  name: "Książka testowa",
  kind: "BOOK",
  variant_id: null,
  variant_kind: null,
  quantity: 1,
  unit_price_snapshot: 5900,
  vat_rate_snapshot: "RATE_5",
  vat_label: "5%",
  line_total_grosz: 5900,
  short_description: "Opis książki",
  image: { url: "https://example.invalid/book.webp", alt: "Okładka książki" },
  details: "Książka papierowa",
  voucher_validity_months: null,
};

function cart(quantity = 1) {
  return {
    items: [{ ...cartItem, quantity, line_total_grosz: quantity * 5900 }],
    item_count: quantity,
    expires_at: null,
    discount_code: null,
    discount_notice: null,
    delivery: {
      requires_shipping: true,
      selected_method: "parcel_locker",
      available_quotes: [
        { method: "parcel_locker", gross_grosz: 1200, vat_label: "23%" },
      ],
      requires_method_selection: false,
      threshold_basis_grosz: quantity * 5900,
      free_shipping_threshold_grosz: 15000,
      remaining_amount_grosz: Math.max(0, 15000 - quantity * 5900),
      free_shipping_qualified: quantity * 5900 >= 15000,
      show_incentive: false,
      message: null,
    },
    calculation: {
      items: [],
      vat_groups: [
        {
          vat_rate: "RATE_5",
          vat_label: "5%",
          gross_grosz: quantity * 5900,
          net_grosz: quantity * 5619,
          tax_grosz: quantity * 281,
        },
      ],
      exempt: {
        vat_rate: "EXEMPT",
        vat_label: "zw.",
        gross_grosz: 0,
        net_grosz: 0,
        tax_grosz: 0,
      },
      products_gross_grosz: quantity * 5900,
      products_gross_before_discount_grosz: quantity * 5900,
      discount_grosz: 0,
      discount_code: null,
      delivery: {
        resolved: true,
        gross_grosz: 0,
        net_grosz: 0,
        tax_grosz: 0,
        vat_rate: "RATE_23",
        vat_label: "23%",
      },
      amount_due_grosz: quantity * 5900 + 1200,
      amount_due_is_final: true,
    },
  };
}

const emptyCart = {
  ...cart(1),
  items: [],
  item_count: 0,
  delivery: {
    requires_shipping: false,
    selected_method: null,
    available_quotes: [],
    requires_method_selection: false,
    threshold_basis_grosz: 0,
    free_shipping_threshold_grosz: null,
    remaining_amount_grosz: null,
    free_shipping_qualified: false,
    show_incentive: false,
    message: null,
  },
  calculation: {
    ...cart(1).calculation,
    items: [],
    vat_groups: [],
    products_gross_grosz: 0,
    products_gross_before_discount_grosz: 0,
    amount_due_grosz: 0,
  },
};

test("koszyk grupuje szybkie kliknięcia ilości w jeden PATCH i aktualizuje licznik", async ({
  page,
}) => {
  let current = cart(1);
  const quantityPatches: number[] = [];
  await page.route("**/api/cart**", async (route) => {
    const request = route.request();
    if (request.method() === "GET" && request.url().endsWith("/api/cart")) {
      await route.fulfill({ json: current });
      return;
    }
    if (
      request.method() === "PATCH" &&
      request.url().includes("/items/cart-line-1")
    ) {
      const body = request.postDataJSON() as { quantity: number };
      quantityPatches.push(body.quantity);
      current = cart(body.quantity);
      await route.fulfill({ json: current });
      return;
    }
    await route.fulfill({
      json: { error: { code: "NOT_FOUND", message: "Brak danych" } },
      status: 404,
    });
  });
  await page.route("**/api/products?*", (route) =>
    route.fulfill({
      json: {
        items: [],
        total: 0,
        page: 1,
        per_page: 12,
        total_pages: 0,
        facets: {
          categories: [],
          kinds: [],
          audiences: [],
          deliveries: [],
          prices: [],
        },
        suggestions: null,
      },
    }),
  );
  await page.route("**/api/catalog/public/search-presentation", (route) =>
    route.fulfill({
      json: { suggested_queries: [], contact_email: null, contact_phone: null },
    }),
  );

  await page.setViewportSize({ width: 360, height: 900 });
  await page.goto("/koszyk");
  await expect(
    page.getByRole("heading", { name: "Twój koszyk", level: 1 }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Koszyk, 1 produkt" }),
  ).toBeVisible();
  const increment = page.getByRole("button", {
    name: "Zwiększ ilość Książka testowa",
  });
  await increment.click();
  await increment.click();
  await increment.click();
  await expect(page.getByText("4 × 59,00 zł · VAT 5%")).toBeVisible({
    timeout: 5000,
  });
  expect(quantityPatches).toEqual([4]);
  await expect(
    page.getByRole("link", { name: "Koszyk, 4 produkty" }),
  ).toBeVisible();
  for (const width of [1280, 768, 360]) {
    await page.setViewportSize({ width, height: width === 360 ? 900 : 1000 });
    await page.screenshot({
      path: `../../docs/audit/evidence/after/mockup-check-cart-filled-${width}.png`,
      fullPage: true,
    });
  }
  await page.setViewportSize({ width: 360, height: 900 });
  const overflow = await page.evaluate(
    () =>
      document.documentElement.scrollWidth >
      document.documentElement.clientWidth,
  );
  expect(overflow).toBe(false);
});

test("usunięcie ostatniej pozycji pokazuje pusty stan bez sekcji płatności", async ({
  page,
}) => {
  let current: object = cart(1);
  await page.route("**/api/cart**", async (route) => {
    if (
      route.request().method() === "GET" &&
      route.request().url().endsWith("/api/cart")
    ) {
      await route.fulfill({ json: current });
      return;
    }
    if (
      route.request().method() === "DELETE" &&
      route.request().url().includes("/items/cart-line-1")
    ) {
      current = emptyCart;
      await route.fulfill({ json: current });
      return;
    }
    await route.fulfill({
      json: { error: { code: "NOT_FOUND", message: "Brak danych" } },
      status: 404,
    });
  });
  await page.route("**/api/products?*", (route) =>
    route.fulfill({
      json: {
        items: [],
        total: 0,
        page: 1,
        per_page: 12,
        total_pages: 0,
        facets: {
          categories: [],
          kinds: [],
          audiences: [],
          deliveries: [],
          prices: [],
        },
        suggestions: null,
      },
    }),
  );
  await page.route("**/api/catalog/public/search-presentation", (route) =>
    route.fulfill({
      json: { suggested_queries: [], contact_email: null, contact_phone: null },
    }),
  );
  await page.goto("/koszyk");
  await page
    .getByRole("button", { name: "Usuń Książka testowa z koszyka" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Twój koszyk jest jeszcze pusty" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Przejdź do płatności" }),
  ).toHaveCount(0);
  await expect(page.getByLabel("Kod rabatowy")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Koszyk, pusty" })).toBeVisible();
});

test("usunięcie pozycji anuluje niewysłaną zmianę ilości", async ({ page }) => {
  const patches: number[] = [];
  await page.route("**/api/cart**", async (route) => {
    const request = route.request();
    if (request.method() === "GET" && request.url().endsWith("/api/cart")) {
      await route.fulfill({ json: cart(1) });
      return;
    }
    if (request.method() === "PATCH") {
      patches.push((request.postDataJSON() as { quantity: number }).quantity);
      await route.fulfill({ json: cart(2) });
      return;
    }
    if (request.method() === "DELETE") {
      await route.fulfill({ json: emptyCart });
      return;
    }
    await route.fulfill({
      status: 404,
      json: { error: { message: "Brak danych" } },
    });
  });
  await page.route("**/api/products?*", (route) =>
    route.fulfill({
      json: {
        items: [],
        total: 0,
        page: 1,
        per_page: 12,
        total_pages: 0,
        facets: {
          categories: [],
          kinds: [],
          audiences: [],
          deliveries: [],
          prices: [],
        },
        suggestions: null,
      },
    }),
  );
  await page.route("**/api/catalog/public/search-presentation", (route) =>
    route.fulfill({
      json: { suggested_queries: [], contact_email: null, contact_phone: null },
    }),
  );
  await page.goto("/koszyk");
  await page
    .getByRole("button", { name: "Zwiększ ilość Książka testowa" })
    .click();
  await page
    .getByRole("button", { name: "Usuń Książka testowa z koszyka" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Twój koszyk jest jeszcze pusty" }),
  ).toBeVisible();
  expect(patches).toEqual([]);
});

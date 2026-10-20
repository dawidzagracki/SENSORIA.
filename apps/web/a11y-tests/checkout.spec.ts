import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { blockingAxeViolations } from "./a11y-gate";

const checkoutCart = {
  items: [
    {
      id: "line-1",
      product_id: "product-1",
      slug: "material-cyfrowy",
      name: "Materiał cyfrowy fixture",
      kind: "DIGITAL",
      variant_id: null,
      variant_kind: null,
      quantity: 1,
      unit_price_snapshot: 1000,
      vat_rate_snapshot: "RATE_5",
      vat_label: "5%",
      line_total_grosz: 1000,
      short_description: null,
      image: null,
      details: "E-book PDF",
      voucher_validity_months: null,
    },
  ],
  item_count: 1,
  expires_at: null,
  discount_code: null,
  discount_notice: null,
  delivery: {
    requires_shipping: false,
    selected_method: null,
    available_quotes: [],
    requires_method_selection: false,
    threshold_basis_grosz: 1000,
    free_shipping_threshold_grosz: null,
    remaining_amount_grosz: null,
    free_shipping_qualified: false,
    show_incentive: false,
    message: null,
  },
  calculation: {
    items: [
      {
        item_id: "line-1",
        unit_price_snapshot: 1000,
        quantity: 1,
        vat_rate: "RATE_5",
        vat_label: "5%",
        gross_grosz: 1000,
        discount_grosz: 0,
        gross_before_discount_grosz: 1000,
        net_grosz: 952,
        tax_grosz: 48,
        rounding_adjustment_grosz: 0,
      },
    ],
    vat_groups: [
      {
        vat_rate: "RATE_5",
        vat_label: "5%",
        gross_grosz: 1000,
        net_grosz: 952,
        tax_grosz: 48,
      },
    ],
    exempt: {
      vat_rate: "EXEMPT",
      vat_label: "zw.",
      gross_grosz: 0,
      net_grosz: 0,
      tax_grosz: 0,
    },
    products_gross_grosz: 1000,
    products_gross_before_discount_grosz: 1000,
    discount_grosz: 0,
    discount_code: null,
    delivery: {
      resolved: true,
      gross_grosz: 0,
      net_grosz: 0,
      tax_grosz: 0,
      vat_rate: null,
      vat_label: null,
    },
    amount_due_grosz: 1000,
    amount_due_is_final: true,
  },
};

const checkoutConfig = {
  consent_version: "fixture-v1",
  terms_text: "Akceptuję regulamin i politykę prywatności.",
  digital_text: "Żądam natychmiastowego udostępnienia treści cyfrowej.",
  marketing_text: "Zgoda marketingowa jest dobrowolna.",
};

test("checkout książki: zrzuty porównawcze gałęzi dostawy bez poziomego przepełnienia", async ({
  page,
}) => {
  const physicalCart = {
    ...checkoutCart,
    items: [
      {
        ...checkoutCart.items[0],
        slug: "ksiazka-demonstracyjna",
        name: "Książka demonstracyjna",
        kind: "BOOK" as const,
        details: "Książka papierowa",
      },
    ],
    delivery: {
      ...checkoutCart.delivery,
      requires_shipping: true,
      selected_method: "parcel_locker" as const,
      available_quotes: [
        {
          method: "parcel_locker" as const,
          gross_grosz: 1200,
          vat_label: "23%",
        },
        { method: "courier" as const, gross_grosz: 1800, vat_label: "23%" },
      ],
      requires_method_selection: false,
    },
    calculation: {
      ...checkoutCart.calculation,
      delivery: {
        resolved: true,
        gross_grosz: 1200,
        net_grosz: 976,
        tax_grosz: 224,
        vat_rate: "RATE_23" as const,
        vat_label: "23%",
      },
      amount_due_grosz: 2200,
    },
  };
  await page.route("**/api/cart/checkout-config", (route) =>
    route.fulfill({ json: checkoutConfig }),
  );
  await page.route("**/api/cart", (route) =>
    route.fulfill({ json: physicalCart }),
  );
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
  for (const width of [1280, 1024, 768, 360]) {
    await page.setViewportSize({ width, height: width === 360 ? 820 : 1000 });
    await page.goto("/zamowienie");
    await expect(
      page.getByRole("heading", { name: "Zamówienie", exact: true }),
    ).toBeVisible();
    await expect(page.getByRole("heading", { name: /Dostawa/ })).toBeVisible();
    await expect(page.getByRole("radio", { name: /Paczkomat/ })).toBeVisible();
    await page.screenshot({
      path: `../../docs/audit/evidence/after/mockup-check-checkout-physical-${width}.png`,
      fullPage: true,
    });
    const widths = await page.evaluate(() => ({
      client: document.documentElement.clientWidth,
      scroll: document.documentElement.scrollWidth,
    }));
    expect(
      widths.scroll,
      `checkout overflow at ${width}px`,
    ).toBeLessThanOrEqual(widths.client);
  }
});

test("checkout cyfrowy: responsywność, axe, zgody i payload bez dostawy", async ({
  page,
}) => {
  let checkoutPayload: Record<string, unknown> | null = null;
  await page.route("**/api/cart/checkout-config", (route) =>
    route.fulfill({ json: checkoutConfig }),
  );
  await page.route("**/api/cart", (route) =>
    route.fulfill({ json: checkoutCart }),
  );
  await page.route("**/api/cart/checkout", async (route) => {
    checkoutPayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 201,
      json: {
        order_id: "order-fixture",
        status: "pending_payment",
        amount_due_grosz: 1000,
        payment_integration: "not_configured",
        payment_url: null,
        access_token: "fixture-token-0123456789abcdef",
        message: "Fixture — operator płatności niepodłączony.",
      },
    });
  });

  await page.setViewportSize({ width: 360, height: 820 });
  await page.goto("/zamowienie");
  await expect(
    page.getByRole("heading", { name: "Zamówienie", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: /Dostawa/ })).toHaveCount(0);
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(360);
  await page.screenshot({
    path: "../../docs/audit/evidence/after/checkout-04-360.png",
    fullPage: true,
  });

  await page.setViewportSize({ width: 768, height: 1024 });
  await page.screenshot({
    path: "../../docs/audit/evidence/after/checkout-04-768.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.screenshot({
    path: "../../docs/audit/evidence/after/checkout-04-desktop.png",
    fullPage: true,
  });
  const axe = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(blockingAxeViolations(axe.violations)).toEqual([]);

  await page.getByLabel("Adres e-mail").fill("buyer@example.com");
  await page.getByRole("checkbox", { name: /Akceptuję regulamin/ }).check();
  await page.getByRole("checkbox", { name: /Żądam natychmiastowego/ }).check();
  await page.getByRole("button", { name: "Zamawiam i płacę" }).click();
  // After checkout the buyer lands on the confirmation page (payment starts there).
  await page.waitForURL(
    /\/zamowienie\/potwierdzenie\?order=order-fixture&token=fixture-token/,
  );
  expect(checkoutPayload).not.toBeNull();
  expect(checkoutPayload).not.toHaveProperty("delivery_method");
  expect(checkoutPayload).not.toHaveProperty("shipping_address");
  expect(checkoutPayload).not.toHaveProperty("pickup_point_id");
  expect(checkoutPayload).toMatchObject({
    email: "buyer@example.com",
    terms_accepted: true,
    digital_consent: true,
    marketing_consent: false,
  });
});

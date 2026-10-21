import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
vi.mock("next/navigation", () => ({ usePathname: () => "/zamowienie" }));
import { CartCountProvider } from "../layout/cart-count-provider";
import { CheckoutPage } from "./checkout-page";

const cart = {
  items: [
    {
      id: "line-1",
      product_id: "product-1",
      slug: "ebook",
      name: "E-book testowy",
      kind: "DIGITAL" as const,
      variant_id: null,
      variant_kind: null,
      quantity: 1,
      unit_price_snapshot: 1000,
      vat_rate_snapshot: "RATE_5" as const,
      vat_label: "5%",
      line_total_grosz: 1000,
      short_description: null,
      image: null,
      details: "PDF",
      voucher_validity_months: null,
    },
  ],
  item_count: 1,
  expires_at: null,
  delivery_point: null,
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
        vat_rate: "RATE_5" as const,
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
        vat_rate: "RATE_5" as const,
        vat_label: "5%",
        gross_grosz: 1000,
        net_grosz: 952,
        tax_grosz: 48,
      },
    ],
    exempt: {
      vat_rate: "EXEMPT" as const,
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

const config = {
  consent_version: "test-v1",
  terms_text: "Akceptuję regulamin i politykę prywatności.",
  digital_text: "Zgadzam się na natychmiastowe udostępnienie treści cyfrowej.",
  marketing_text: "Zgoda marketingowa",
};

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

// A gift can only be scheduled for a future day, so derive it from the clock.
const SEND_DAY = new Date(Date.now() + 5 * 86_400_000)
  .toISOString()
  .slice(0, 10);

describe("CheckoutPage", () => {
  beforeEach(() => {
    Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
      configurable: true,
      value: vi.fn(function (this: HTMLDialogElement) {
        this.setAttribute("open", "");
      }),
    });
    Object.defineProperty(HTMLDialogElement.prototype, "close", {
      configurable: true,
      value: vi.fn(function (this: HTMLDialogElement) {
        this.removeAttribute("open");
        this.dispatchEvent(new Event("close"));
      }),
    });
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("keeps one page heading visible while cart data is loading", () => {
    let resolveCart!: (value: Response) => void;
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        if (String(input).endsWith("/cart"))
          return new Promise<Response>((resolve) => (resolveCart = resolve));
        return Promise.resolve(response(config));
      }),
    );
    render(
      <CartCountProvider
        initialSnapshot={{ count: null, source: "integration-pending" }}
      >
        <CheckoutPage />
      </CartCountProvider>,
    );
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Zamówienie",
    );
    expect(screen.getByRole("status")).toHaveTextContent("Wczytujemy koszyk");
    resolveCart(response(cart));
  });

  it("omits delivery data for a digital-only guest order and keeps consents unchecked", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/cart")) return response(cart);
        if (url.endsWith("/checkout-config")) return response(config);
        if (url.endsWith("/checkout"))
          return response({
            order_id: "order-1",
            status: "pending_payment",
            amount_due_grosz: 1000,
            payment_integration: "not_configured",
            payment_url: null,
            access_token: "token-0123456789abcdef",
            message: "Oczekuje na płatność",
            received: JSON.parse(String(init?.body)),
          });
        return response({}, 404);
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("crypto", { randomUUID: () => "stable-idempotency-key" });
    render(
      <CartCountProvider
        initialSnapshot={{ count: null, source: "integration-pending" }}
      >
        <CheckoutPage />
      </CartCountProvider>,
    );

    await screen.findByRole("heading", { name: "Zamówienie" });
    expect(
      screen.queryByRole("heading", { name: /Dostawa/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("checkbox", { name: /Akceptuję regulamin/ }),
    ).not.toBeChecked();
    expect(
      screen.getByRole("checkbox", { name: /Zgadzam się na natychmiastowe/ }),
    ).not.toBeChecked();
    expect(
      screen.getByRole("checkbox", { name: config.marketing_text }),
    ).not.toBeChecked();

    await user.type(screen.getByLabelText("Adres e-mail"), "test@example.com");
    await user.click(
      screen.getByRole("checkbox", { name: /Akceptuję regulamin/ }),
    );
    await user.click(
      screen.getByRole("checkbox", { name: /Zgadzam się na natychmiastowe/ }),
    );
    await user.click(screen.getByRole("button", { name: "Zamawiam i płacę" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/cart/checkout",
        expect.objectContaining({ method: "POST" }),
      ),
    );
    const request = fetchMock.mock.calls.find(([url]) =>
      String(url).endsWith("/checkout"),
    );
    expect(request).toBeDefined();
    const payload = JSON.parse(String(request?.[1]?.body)) as Record<
      string,
      unknown
    >;
    expect(payload).not.toHaveProperty("delivery_method");
    expect(payload).not.toHaveProperty("shipping_address");
    expect(payload).not.toHaveProperty("first_name");
    expect(payload).not.toHaveProperty("pickup_point_id");
    expect(payload).toMatchObject({
      email: "test@example.com",
      terms_accepted: true,
      digital_consent: true,
    });
  });

  it("submits per-voucher gift recipient, dedication and scheduled day with the same order", async () => {
    const user = userEvent.setup();
    const giftCart = {
      ...cart,
      items: [
        {
          ...cart.items[0],
          name: "Voucher na konsultację",
          kind: "VOUCHER" as const,
          variant_id: "variant-1",
          variant_kind: "ONLINE" as const,
          voucher_validity_months: 12,
          is_gift: true,
        },
      ],
    };
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/cart")) return response(giftCart);
        if (url.endsWith("/checkout-config")) return response(config);
        if (url.endsWith("/checkout")) {
          return response({
            order_id: "order-same",
            status: "pending_payment",
            amount_due_grosz: 1000,
            payment_integration: "not_configured",
            payment_url: null,
            access_token: "token-0123456789abcdef",
            message: "Oczekuje na płatność",
            received: JSON.parse(String(init?.body)),
          });
        }
        return response({}, 404);
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign });
    vi.stubGlobal("crypto", { randomUUID: () => "gift-order-idempotency" });
    render(
      <CartCountProvider
        initialSnapshot={{ count: null, source: "integration-pending" }}
      >
        <CheckoutPage />
      </CartCountProvider>,
    );

    await screen.findByRole("heading", { name: "Zamówienie" });
    expect(
      screen.getByRole("checkbox", { name: /Kupuję w prezencie/ }),
    ).toBeChecked();
    await user.type(screen.getByLabelText("Adres e-mail"), "buyer@example.com");
    await user.type(
      screen.getByLabelText(/Imię obdarowanej osoby/),
      "Żaneta Nowak",
    );
    await user.type(screen.getByLabelText(/Dedykacja/), "Wszystkiego dobrego!");
    const scheduledRadio = screen.getByRole("radio", {
      name: "W wybranym dniu",
    });
    await user.click(scheduledRadio);
    expect(scheduledRadio).toBeChecked();
    fireEvent.change(await screen.findByLabelText(/Dzień wysyłki/), {
      target: { value: SEND_DAY },
    });
    await user.click(
      screen.getByRole("checkbox", { name: /Akceptuję regulamin/ }),
    );
    await user.click(screen.getByRole("button", { name: "Zamawiam i płacę" }));

    await screen.findByRole("heading", {
      name: "Przekierowujemy do płatności…",
    });
    expect(assign).toHaveBeenCalledWith(
      "/zamowienie/potwierdzenie?order=order-same&token=token-0123456789abcdef",
    );
    const request = fetchMock.mock.calls.find(([url]) =>
      String(url).endsWith("/checkout"),
    );
    const payload = JSON.parse(String(request?.[1]?.body)) as {
      email: string;
      gifts: Array<Record<string, unknown>>;
    };
    expect(payload.email).toBe("buyer@example.com");
    expect(payload.gifts).toEqual([
      {
        cart_item_id: "line-1",
        recipient_name: "Żaneta Nowak",
        recipient_email: null,
        dedication: "Wszystkiego dobrego!",
        delivery_mode: "scheduled",
        delivery_date: SEND_DAY,
      },
    ]);
  });

  it("searches and confirms an InPost point in the modal, then renders its server snapshot", async () => {
    const user = userEvent.setup();
    const point = {
      operator: "inpost" as const,
      code: "OLS01M",
      name: "InPost Paczkomat OLS01M",
      street: "Kętrzyńskiego 12",
      postal_code: "10-001",
      city: "Olsztyn",
      opening_hours: "24/7",
      point_types: ["parcel_locker"],
      functions: ["parcel_collect"],
      status: "Operating",
      verified_at: "2026-10-15T10:00:00Z",
    };
    const bookCart = {
      ...cart,
      items: [{ ...cart.items[0], kind: "BOOK" as const }],
      delivery: {
        ...cart.delivery,
        requires_shipping: true,
        selected_method: null,
        requires_method_selection: true,
        available_quotes: [
          {
            method: "parcel_locker" as const,
            gross_grosz: 1200,
            vat_label: "23%",
          },
          { method: "courier" as const, gross_grosz: 1800, vat_label: "23%" },
        ],
      },
    };
    const parcelCart = {
      ...bookCart,
      delivery: {
        ...bookCart.delivery,
        selected_method: "parcel_locker" as const,
      },
    };
    const chosenCart = { ...parcelCart, delivery_point: point };
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/cart")) return response(bookCart);
      if (url.endsWith("/checkout-config")) return response(config);
      if (url.endsWith("/delivery")) return response(parcelCart);
      if (url.includes("/pickup-points?")) return response({ items: [point] });
      if (url.endsWith("/pickup-point")) return response(chosenCart);
      return response({}, 404);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <CartCountProvider
        initialSnapshot={{ count: null, source: "integration-pending" }}
      >
        <CheckoutPage />
      </CartCountProvider>,
    );

    await screen.findByRole("heading", { name: "Zamówienie" });
    await user.click(screen.getByRole("radio", { name: /Paczkomat InPost/ }));
    await user.click(
      await screen.findByRole("button", { name: "Wybierz Paczkomat" }),
    );
    await user.type(
      screen.getByLabelText("Miasto lub kod pocztowy"),
      "Olsztyn",
    );
    await user.click(screen.getByRole("button", { name: "Szukaj punktów" }));
    await user.click(
      await screen.findByRole("button", { name: "Wybierz ten punkt" }),
    );

    expect(await screen.findAllByText(/OLS01M/)).not.toHaveLength(0);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/cart/pickup-point",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ code: "OLS01M" }),
      }),
    );
  });
});

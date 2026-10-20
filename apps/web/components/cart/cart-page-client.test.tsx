import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
vi.mock("next/navigation", () => ({ usePathname: () => "/koszyk" }));
import { CartCountProvider } from "../layout/cart-count-provider";
import { CartPageClient } from "./cart-page-client";

const emptyCart = {
  items: [],
  item_count: 0,
  expires_at: null,
  discount_code: null,
  discount_notice: null,
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
    items: [],
    vat_groups: [],
    exempt: {
      vat_rate: "EXEMPT",
      vat_label: "zw.",
      gross_grosz: 0,
      net_grosz: 0,
      tax_grosz: 0,
    },
    products_gross_grosz: 0,
    products_gross_before_discount_grosz: 0,
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
    amount_due_grosz: 0,
    amount_due_is_final: true,
  },
};

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderPage() {
  return render(
    <CartCountProvider
      initialSnapshot={{ count: null, source: "integration-pending" }}
    >
      <CartPageClient />
    </CartCountProvider>,
  );
}

describe("CartPageClient", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("does not show the empty state before the API confirms an empty cart", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://example.invalid/api");
    let resolveCart!: (value: Response) => void;
    const cartPromise = new Promise<Response>((resolve) => {
      resolveCart = resolve;
    });
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/cart")) return cartPromise;
        if (url.endsWith("/products?sort=recommended&per_page=12"))
          return Promise.resolve(
            response({
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
            }),
          );
        return Promise.resolve(response({ contact_email: null }));
      }),
    );
    renderPage();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Twój koszyk",
    );
    expect(screen.getByRole("status")).toHaveTextContent("Wczytujemy koszyk");
    expect(
      screen.queryByText("Twój koszyk jest jeszcze pusty"),
    ).not.toBeInTheDocument();
    resolveCart(response(emptyCart));
    expect(
      await screen.findByText("Twój koszyk jest jeszcze pusty"),
    ).toBeInTheDocument();
  });

  it("keeps purchase controls out of the confirmed empty-cart state", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://example.invalid/api");
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/cart")) return Promise.resolve(response(emptyCart));
        if (url.endsWith("/products?sort=recommended&per_page=12"))
          return Promise.resolve(
            response({
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
            }),
          );
        return Promise.resolve(response({ contact_email: null }));
      }),
    );
    renderPage();
    await screen.findByText("Twój koszyk jest jeszcze pusty");
    expect(
      screen.queryByRole("link", { name: "Przejdź do płatności" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Kod rabatowy")).not.toBeInTheDocument();
  });
});

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfirmationView } from "@/components/order/confirmation-view";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const TOKEN = "t".repeat(64);
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status });

function stubApi(routes: Record<string, unknown>) {
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const key = Object.keys(routes).find((route) => url.includes(route));
      if (!key) return json({ error: { code: "X", message: "brak" } }, 404);
      const value = routes[key];
      return typeof value === "function"
        ? (value as (i?: RequestInit) => Response)(init)
        : json(value);
    },
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const baseOrder = {
  order_id: "o-1",
  public_number: "SEN-2026-ABC",
  payment_method: "blik",
  amount_due_grosz: 7900,
  email_masked: "a***@example.com",
  created_at: "2026-10-20T10:00:00Z",
  requires_shipping: false,
  delivery_method: null,
  items: [
    { name: "E-book", quantity: 1, unit_price_grosz: 7900, is_voucher: false },
  ],
};

describe("ConfirmationView", () => {
  it("explains a missing link instead of failing silently", () => {
    render(<ConfirmationView orderId={null} token={null} />);
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Nie znaleziono zamówienia",
      }),
    ).toBeInTheDocument();
  });

  it("shows delivery of a paid order: library, voucher, documents", async () => {
    stubApi({
      "/payments/orders/o-1": {
        ...baseOrder,
        status: "paid",
        payment_status: "succeeded",
        can_retry_payment: false,
      },
      "/library/orders/o-1": {
        items: [
          {
            id: "e-1",
            kind: "digital",
            title: "E-book",
            order_number: "SEN",
            granted_at: "2026-10-20T10:00:00Z",
            has_reader: true,
            chapters_total: 2,
            chapters_completed: 0,
          },
        ],
      },
      "/library/entitlements/e-1": {
        files: [{ id: "f-1", kind: "pdf", label: "E-book", chapter_id: null }],
      },
      "/vouchers/orders/o-1": {
        items: [
          {
            id: "v-1",
            code: "SEN-AAAA-BBBB",
            service_name: "Konsultacja",
            status: "active",
            valid_until: "2027-10-20T00:00:00Z",
            pdf_ready: true,
            is_gift: false,
          },
        ],
      },
      "/documents/orders/o-1": {
        items: [{ id: "d-1", kind: "receipt", number: "PAR/2026/00001" }],
      },
    });
    render(<ConfirmationView orderId="o-1" token={TOKEN} />);
    await screen.findByRole("heading", {
      level: 1,
      name: /Zamówienie opłacone/,
    });
    expect(
      await screen.findByRole("link", { name: "Czytaj jako kurs" }),
    ).toHaveAttribute(
      "href",
      expect.stringContaining(`/konto/czytnik/e-1?order_token=${TOKEN}`),
    );
    expect(
      screen.getByRole("button", { name: /Pobierz E-book \(PDF\)/ }),
    ).toBeInTheDocument();
    expect(screen.getByText("SEN-AAAA-BBBB")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Pobierz voucher (PDF)" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Paragon PAR\/2026\/00001/ }),
    ).toBeInTheDocument();
  });

  it("offers a retry for a failed payment and redirects to the hosted page", async () => {
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign });
    const fetchMock = stubApi({
      "/payments/orders/o-1/session": {
        payment_url: "https://checkout.stripe.test/x",
        status: "pending",
        attempt: 2,
        payment_id: "p",
      },
      "/payments/orders/o-1": {
        ...baseOrder,
        status: "pending_payment",
        payment_status: "failed",
        can_retry_payment: true,
      },
    });
    const user = userEvent.setup();
    render(<ConfirmationView orderId="o-1" token={TOKEN} />);
    await user.click(
      await screen.findByRole("button", { name: "Zapłać ponownie" }),
    );
    await waitFor(() =>
      expect(assign).toHaveBeenCalledWith("https://checkout.stripe.test/x"),
    );
    const post = fetchMock.mock.calls.find(([url]) =>
      String(url).includes("/session"),
    );
    expect(post?.[1]?.method).toBe("POST");
  });

  it("tells a stranger the order was not found without leaking details", async () => {
    stubApi({});
    render(<ConfirmationView orderId="o-9" token={TOKEN} />);
    await screen.findByText(/Nie znaleziono zamówienia/);
  });
});

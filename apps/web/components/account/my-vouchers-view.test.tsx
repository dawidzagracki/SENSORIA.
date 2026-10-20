import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MyVouchersView } from "./my-vouchers-view";

const item = (
  id: string,
  status: "active" | "expiring_soon" | "expired" | "redeemed" | "cancelled",
) => ({
  id,
  code: "SEN-ABCD-" + id.slice(0, 4).toUpperCase(),
  status,
  name: "Konsultacja " + id,
  variant: "W gabinecie",
  issued_at: "2026-01-01T10:00:00Z",
  valid_until: "2026-12-31T22:59:59Z",
  days_until_expiry: status === "expiring_soon" ? 1 : 200,
  redeemed_at: status === "redeemed" ? "2026-06-01T10:00:00Z" : null,
  redeemed_by: status === "redeemed" ? "A. Obsługa" : null,
  place: "Gabinet — szczegóły w dokumencie",
  purchase_date: "2026-01-01T10:00:00Z",
  pdf_status: "ready" as const,
  qr_path: "/api/accounts/vouchers/" + id + "/qr",
  product_path: "/sklep/konsultacja",
  request_pending: false,
  requests: [],
});

const responseBody = {
  customer_name: "Anna Kowalska",
  first_purchase_at: "2026-01-01T10:00:00Z",
  items: [
    item("0001", "active"),
    item("0002", "expiring_soon"),
    item("0003", "expired"),
    item("0004", "redeemed"),
    item("0005", "cancelled"),
  ],
  total_count: 5,
  usable_count: 2,
  contact_email: null,
  contact_phone: null,
  booking_url: null,
  booking_instructions: null,
};

function jsonResponse(body: unknown, status = 200, headers?: HeadersInit) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(responseBody)));
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
    configurable: true,
    value: function (this: HTMLDialogElement) {
      this.setAttribute("open", "");
    },
  });
  Object.defineProperty(HTMLDialogElement.prototype, "close", {
    configurable: true,
    value: function (this: HTMLDialogElement) {
      this.removeAttribute("open");
      this.dispatchEvent(new Event("close"));
    },
  });
});

afterEach(() => {
  cleanup();
  Reflect.deleteProperty(HTMLDialogElement.prototype, "showModal");
  Reflect.deleteProperty(HTMLDialogElement.prototype, "close");
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("MyVouchersView", () => {
  it("shows complete history and counts usable vouchers separately", async () => {
    render(<MyVouchersView />);

    expect(await screen.findByText("Konsultacja 0001")).toBeInTheDocument();
    expect(screen.getByText("Konsultacja 0005")).toBeInTheDocument();
    expect(screen.getByText("5 voucherów w historii")).toBeInTheDocument();
    expect(
      screen.getByText("Licznik aktywnych i dostępnych: 2"),
    ).toBeInTheDocument();
    expect(screen.getByText("Zrealizowany")).toBeInTheDocument();
    expect(screen.getByText("Anulowany")).toBeInTheDocument();
  });

  it("shows the nearest warning from server calendar-day data", async () => {
    render(<MyVouchersView />);

    const warning = await screen.findByRole("status");
    expect(warning).toHaveTextContent("wygasa jutro");
    expect(warning).toHaveTextContent("Sama prośba nie zmienia terminu.");
  });

  it("keeps an API error distinct from an empty account", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse({ error: { message: "API niedostępne" } }, 503),
        ),
    );
    render(<MyVouchersView />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Nie udało się otworzyć listy voucherów",
    );
    expect(
      screen.queryByText("Nie masz jeszcze voucherów"),
    ).not.toBeInTheDocument();
  });

  it("posts an empty optional extension message and confirms a pending request", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/preview"))
        return Promise.resolve(jsonResponse({ can_add: true, message: null }));
      if (init?.method === "POST")
        return Promise.resolve(
          jsonResponse({ status: "pending", request_id: "request-1" }, 201),
        );
      return Promise.resolve(jsonResponse(responseBody));
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<MyVouchersView />);

    await screen.findByText("Konsultacja 0002");
    await user.click(
      screen.getAllByRole("button", { name: "Poproś o przedłużenie" })[0]!,
    );
    await user.click(screen.getByRole("button", { name: "Wyślij prośbę" }));

    expect(
      await screen.findByText(/Prośba wysłana i czeka na rozpatrzenie/),
    ).toBeInTheDocument();
    const postCall = fetchMock.mock.calls.find(
      (call) => (call[1] as RequestInit | undefined)?.method === "POST",
    );
    expect(postCall?.[1]).toMatchObject({
      method: "POST",
      body: JSON.stringify({ message: "" }),
    });
  });

  it("does not fetch a voucher PDF when rendering the list", async () => {
    const fetchMock = vi.mocked(fetch);
    render(<MyVouchersView />);

    await screen.findByText("Konsultacja 0001");
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/accounts/vouchers");
    expect(
      fetchMock.mock.calls.some(([url]) => String(url).includes("/pdf")),
    ).toBe(false);
  });
});

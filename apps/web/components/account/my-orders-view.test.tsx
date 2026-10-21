import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MyOrdersView } from "@/components/account/my-orders-view";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("MyOrdersView", () => {
  it("shows server order-count filters and separates an empty invoice view", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          customer_name: "Test Klientka",
          first_purchase_at: null,
          total_count: 0,
          counts: { all: 0, in_progress: 0, completed: 0, invoices: 0 },
          page: 1,
          page_size: 10,
          items: [],
        }),
      }),
    );
    render(<MyOrdersView />);
    await screen.findByText("Nie masz jeszcze zamówień");
    expect(
      screen.getByRole("button", { name: "Wszystkie 0" }),
    ).toBeInTheDocument();
    screen.getByRole("button", { name: "Faktury" }).click();
    await waitFor(() =>
      expect(screen.getByText("Brak dokumentów sprzedaży")).toBeInTheDocument(),
    );
    expect(screen.getByText(/po opłaceniu zamówienia/)).toBeInTheDocument();
  });

  it("does not render an API error as an empty order history", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("API niedostępne")),
    );
    render(<MyOrdersView />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Nie udało się pobrać danych",
    );
    expect(
      screen.queryByText("Nie masz jeszcze zamówień"),
    ).not.toBeInTheDocument();
  });
});

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DiscountSummary } from "./discount-summary";
import type { CartMutation, CartView } from "./cart-types";

const cart: CartView = {
  items: [],
  item_count: 0,
  expires_at: null,
  delivery_point: null,
  discount_code: null,
  discount_notice: null,
  delivery: {
    requires_shipping: false,
    selected_method: null,
    available_quotes: [],
    requires_method_selection: false,
    threshold_basis_grosz: 44700,
    free_shipping_threshold_grosz: null,
    remaining_amount_grosz: null,
    free_shipping_qualified: false,
    show_incentive: false,
    message: null,
  },
  calculation: {
    items: [],
    vat_groups: [
      {
        vat_rate: "RATE_5",
        vat_label: "5%",
        gross_grosz: 19700,
        net_grosz: 18762,
        tax_grosz: 938,
      },
    ],
    exempt: {
      vat_rate: "EXEMPT",
      vat_label: "zw.",
      gross_grosz: 25000,
      net_grosz: 25000,
      tax_grosz: 0,
    },
    products_gross_grosz: 44700,
    products_gross_before_discount_grosz: 44700,
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
    amount_due_grosz: 44700,
    amount_due_is_final: true,
  },
};

describe("DiscountSummary", () => {
  afterEach(cleanup);

  it("shows the full server settlement from the filled-cart mock without recalculating", () => {
    const filled: CartView = {
      ...cart,
      delivery: {
        ...cart.delivery,
        requires_shipping: true,
        selected_method: "parcel_locker",
        free_shipping_threshold_grosz: 15000,
        free_shipping_qualified: true,
        message: "Darmowa dostawa — Twoje zamówienie przekroczyło 150 zł.",
      },
      calculation: {
        ...cart.calculation,
        delivery: {
          resolved: true,
          gross_grosz: 0,
          net_grosz: 0,
          tax_grosz: 0,
          vat_rate: "RATE_23",
          vat_label: "23%",
        },
      },
    };
    render(<DiscountSummary cart={filled} mutate={vi.fn()} />);
    expect(screen.getByText("Produkty").parentElement).toHaveTextContent(
      "447,00 zł",
    );
    expect(
      screen.getByText("Dostawa · paczkomat").parentElement,
    ).toHaveTextContent("0,00 zł");
    expect(
      screen.getByText("W tym sprzedaż zwolniona z VAT").parentElement,
    ).toHaveTextContent("250,00 zł");
    expect(screen.getByText("W tym VAT 5%").parentElement).toHaveTextContent(
      "9,38 zł",
    );
    expect(screen.getByText("Razem").parentElement).toHaveTextContent(
      "447,00 zł",
    );
    expect(screen.getByText(/Darmowa dostawa/)).toBeInTheDocument();
  });

  it("keeps invalid code and links the server error to the field", async () => {
    const mutate: CartMutation = vi
      .fn()
      .mockRejectedValue(new Error("Kod jest nieprawidłowy."));
    const user = userEvent.setup();
    render(<DiscountSummary cart={cart} mutate={mutate} />);
    const input = screen.getByLabelText("Kod rabatowy");
    await user.type(input, "NOT-VALID");
    await user.click(screen.getByRole("button", { name: "Użyj" }));
    const message = await screen.findByRole("alert");
    expect(input).toHaveValue("NOT-VALID");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAttribute("aria-describedby", message.id);
    expect(mutate).toHaveBeenCalledWith("POST", "/discount", {
      code: "NOT-VALID",
    });
  });

  it("shows all server VAT rows and delivery amounts without recalculating them", async () => {
    const physical: CartView = {
      ...cart,
      delivery: {
        ...cart.delivery,
        requires_shipping: true,
        selected_method: null,
        available_quotes: [
          { method: "parcel_locker", gross_grosz: 1200, vat_label: "23%" },
          { method: "courier", gross_grosz: 1800, vat_label: "23%" },
        ],
        requires_method_selection: true,
        threshold_basis_grosz: 10000,
        free_shipping_threshold_grosz: 15000,
        remaining_amount_grosz: 5000,
      },
      calculation: {
        ...cart.calculation,
        amount_due_grosz: 10000,
        amount_due_is_final: false,
      },
    };
    const user = userEvent.setup();
    const mutate: CartMutation = vi.fn().mockResolvedValue(physical);
    render(<DiscountSummary cart={physical} mutate={mutate} />);
    expect(screen.getByText("W tym VAT 5%")).toBeInTheDocument();
    expect(
      screen.getByText("W tym sprzedaż zwolniona z VAT"),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: /Paczkomat InPost/ }));
    expect(mutate).toHaveBeenCalledWith("PATCH", "/delivery", {
      method: "parcel_locker",
    });
  });
});

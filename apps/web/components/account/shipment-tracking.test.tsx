import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ShipmentTracking } from "./shipment-tracking";
import type { CustomerShipment } from "@/lib/shipment-presentation";

afterEach(() => cleanup());

const data: CustomerShipment = {
  order_id: "order-1",
  delivery_method: "parcel_locker",
  fulfillment_status: "shipped",
  shipment_status: "shipped",
  carrier: "InPost",
  tracking_number: "001234567890123456789012",
  tracking_url: "https://tracking.example.test/001234567890123456789012",
  tracking_link_status: "available",
  shipped_at: "2026-10-16T10:00:00Z",
  delivered_at: null,
  pickup_ready_at: null,
  picked_up_at: null,
  pickup_point: { code: "OLS01M", street: "Leśna 4", city: "Olsztyn" },
  shipping_address: null,
  pickup_information: null,
  items: [
    {
      product_id: "book-1",
      name: "Książka",
      quantity: 2,
      cover_url: null,
      cover_alt: null,
    },
  ],
};

describe("ShipmentTracking", () => {
  it("renders the current snapshot number, status and safe carrier link", () => {
    render(<ShipmentTracking shipment={data} variant="order" />);
    expect(screen.getByText("W drodze")).toBeInTheDocument();
    expect(screen.getByText(data.tracking_number!)).toBeInTheDocument();
    expect(screen.getByText(/Paczkomat OLS01M/)).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /Śledź przesyłkę/ });
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(link).toHaveTextContent("otwiera się w nowej karcie");
  });

  it("copies the number on user action and announces the result", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    render(<ShipmentTracking shipment={data} variant="library" />);
    await userEvent.click(
      screen.getByRole("button", { name: "Skopiuj numer przesyłki" }),
    );
    expect(writeText).toHaveBeenCalledWith(data.tracking_number);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Numer przesyłki skopiowany.",
    );
  });

  it("shows preparation without a number or tracking action before shipment", () => {
    render(
      <ShipmentTracking
        shipment={{
          ...data,
          fulfillment_status: "awaiting_fulfillment",
          shipment_status: null,
          tracking_number: null,
          tracking_url: null,
          shipped_at: null,
          tracking_link_status: "not_shipped",
        }}
        variant="library"
      />,
    );
    expect(screen.getByText("W przygotowaniu")).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /Śledź przesyłkę/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Skopiuj numer przesyłki" }),
    ).not.toBeInTheDocument();
  });
});

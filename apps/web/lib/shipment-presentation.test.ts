import { describe, expect, it } from "vitest";
import {
  formatShipmentAddress,
  formatShipmentDate,
  presentShipmentStatus,
  type CustomerShipment,
} from "./shipment-presentation";

const shipment = (
  overrides: Partial<CustomerShipment> = {},
): CustomerShipment => ({
  order_id: "order-1",
  delivery_method: "parcel_locker",
  fulfillment_status: "awaiting_fulfillment",
  shipment_status: null,
  carrier: null,
  tracking_number: null,
  tracking_url: null,
  tracking_link_status: "not_shipped",
  shipped_at: null,
  delivered_at: null,
  pickup_ready_at: null,
  picked_up_at: null,
  pickup_point: {
    code: "OLS01M",
    street: "Leśna 4",
    postal_code: "10-001",
    city: "Olsztyn",
  },
  shipping_address: null,
  pickup_information: null,
  items: [],
  ...overrides,
});

describe("shipment presentation", () => {
  it.each([
    ["awaiting_fulfillment", "W przygotowaniu"],
    ["shipped", "W drodze"],
    ["delivered", "Dostarczona"],
    ["ready_for_pickup", "Gotowa do odbioru"],
    ["picked_up", "Odebrana"],
    ["cancelled", "Realizacja anulowana"],
  ] as const)("maps %s to a textual status", (fulfillment_status, label) => {
    expect(presentShipmentStatus(shipment({ fulfillment_status })).label).toBe(
      label,
    );
  });

  it("uses the order snapshot for locker and courier destinations", () => {
    expect(formatShipmentAddress(shipment())).toBe(
      "Paczkomat OLS01M · Leśna 4, 10-001 Olsztyn",
    );
    expect(
      formatShipmentAddress(
        shipment({
          delivery_method: "courier",
          pickup_point: null,
          shipping_address: {
            street: "Polna 2",
            postal_code: "00-001",
            city: "Warszawa",
          },
        }),
      ),
    ).toBe("Polna 2, 00-001 Warszawa");
  });

  it("does not fabricate tracking for pickup or unshipped orders", () => {
    expect(
      formatShipmentAddress(
        shipment({
          delivery_method: "pickup_in_person",
          pickup_information: "Odbiór: ul. Różana 1",
        }),
      ),
    ).toBe("Odbiór: ul. Różana 1");
    expect(presentShipmentStatus(shipment()).announcedAt).toBeNull();
  });

  it("uses local calendar days across midnight and daylight saving changes", () => {
    const now = new Date("2026-03-30T01:15:00Z");
    expect(
      formatShipmentDate("2026-03-29T22:30:00Z", now, "Europe/Warsaw"),
    ).toBe("dzisiaj");
    expect(
      formatShipmentDate("2026-03-28T23:30:00Z", now, "Europe/Warsaw"),
    ).toBe("wczoraj");
    expect(
      formatShipmentDate("2026-03-25T12:00:00Z", now, "Europe/Warsaw"),
    ).toBe("5 dni temu");
    expect(
      formatShipmentDate("2026-03-24T12:00:00Z", now, "Europe/Warsaw"),
    ).toBe("6 dni temu");
    expect(
      formatShipmentDate("2026-03-23T12:00:00Z", now, "Europe/Warsaw"),
    ).toContain("2026");
    expect(
      formatShipmentDate("2026-03-20T12:00:00Z", now, "Europe/Warsaw"),
    ).toContain("2026");
  });
});

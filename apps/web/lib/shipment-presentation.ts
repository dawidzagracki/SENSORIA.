export type FulfillmentStatus =
  | "awaiting_fulfillment"
  | "shipped"
  | "delivered"
  | "ready_for_pickup"
  | "picked_up"
  | "cancelled";

export type DeliveryMethod = "parcel_locker" | "courier" | "pickup_in_person";

export type PhysicalShipmentItem = {
  product_id: string;
  name: string;
  quantity: number;
  cover_url: string | null;
  cover_alt: string | null;
};

export type CustomerShipment = {
  order_id: string;
  delivery_method: DeliveryMethod | null;
  fulfillment_status: FulfillmentStatus;
  shipment_status: "shipped" | "delivered" | null;
  carrier: string | null;
  tracking_number: string | null;
  tracking_url: string | null;
  tracking_link_status: "available" | "not_shipped" | "unconfigured";
  shipped_at: string | null;
  delivered_at: string | null;
  pickup_ready_at: string | null;
  picked_up_at: string | null;
  pickup_point: Record<string, unknown> | null;
  shipping_address: Record<string, unknown> | null;
  pickup_information: string | null;
  items: PhysicalShipmentItem[];
};

export type CustomerShipmentList = { items: CustomerShipment[] };

export type ShipmentPresentationStatus = {
  label: string;
  description: string;
  announcedAt: string | null;
};

export function presentShipmentStatus(
  shipment: CustomerShipment,
): ShipmentPresentationStatus {
  switch (shipment.fulfillment_status) {
    case "awaiting_fulfillment":
      return {
        label: "W przygotowaniu",
        description: "Zamówienie czeka na przygotowanie do wysyłki.",
        announcedAt: null,
      };
    case "shipped":
      return {
        label: "W drodze",
        description: shipment.carrier
          ? `Przewoźnik: ${shipment.carrier}. Status sklepu nie jest aktualizowany na żywo.`
          : "Przesyłka została nadana. Status sklepu nie jest aktualizowany na żywo.",
        announcedAt: shipment.shipped_at,
      };
    case "delivered":
      return {
        label: "Dostarczona",
        description: "Sklep odnotował dostarczenie przesyłki.",
        announcedAt: shipment.delivered_at,
      };
    case "ready_for_pickup":
      return {
        label: "Gotowa do odbioru",
        description:
          shipment.pickup_information ??
          "Możesz odebrać zamówienie w ustalonym miejscu.",
        announcedAt: shipment.pickup_ready_at,
      };
    case "picked_up":
      return {
        label: "Odebrana",
        description: "Sklep odnotował odbiór zamówienia.",
        announcedAt: shipment.picked_up_at,
      };
    case "cancelled":
      return {
        label: "Realizacja anulowana",
        description: "To zamówienie nie oczekuje na przesyłkę ani odbiór.",
        announcedAt: null,
      };
  }
}

function localCalendarDay(value: Date, timeZone: string): number {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(value);
  const get = (type: "year" | "month" | "day") =>
    Number(parts.find((part) => part.type === type)?.value);
  return Date.UTC(get("year"), get("month") - 1, get("day")) / 86_400_000;
}

export function formatShipmentDate(
  value: string,
  now: Date,
  timeZone: string,
  locale = "pl-PL",
): string {
  const timestamp = new Date(value);
  if (!Number.isFinite(timestamp.getTime())) return "";
  const dayDifference =
    localCalendarDay(now, timeZone) - localCalendarDay(timestamp, timeZone);
  if (dayDifference === 0) return "dzisiaj";
  if (dayDifference === 1) return "wczoraj";
  if (dayDifference >= 2 && dayDifference <= 6)
    return `${dayDifference} dni temu`;
  return new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone,
  }).format(timestamp);
}

export function formatShipmentAddress(
  shipment: CustomerShipment,
): string | null {
  if (shipment.delivery_method === "parcel_locker") {
    const point = shipment.pickup_point;
    if (!point) return "Paczkomat wybrany przy składaniu zamówienia";
    const code = typeof point.code === "string" ? point.code : null;
    const street = typeof point.street === "string" ? point.street : null;
    const postalCode =
      typeof point.postal_code === "string" ? point.postal_code : null;
    const city = typeof point.city === "string" ? point.city : null;
    const address = [street, [postalCode, city].filter(Boolean).join(" ")]
      .filter(Boolean)
      .join(", ");
    return `Paczkomat${code ? ` ${code}` : ""}${address ? ` · ${address}` : ""}`;
  }
  if (shipment.delivery_method === "courier") {
    const address = shipment.shipping_address;
    if (!address) return "Dostawa kurierem";
    const street = typeof address.street === "string" ? address.street : null;
    const postalCode =
      typeof address.postal_code === "string" ? address.postal_code : null;
    const city = typeof address.city === "string" ? address.city : null;
    return (
      [street, [postalCode, city].filter(Boolean).join(" ")]
        .filter(Boolean)
        .join(", ") || "Dostawa kurierem"
    );
  }
  if (shipment.delivery_method === "pickup_in_person") {
    return shipment.pickup_information ?? "Odbiór osobisty w ustalonym miejscu";
  }
  return null;
}

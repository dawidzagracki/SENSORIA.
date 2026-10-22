import type { ProductKind, VoucherVariantKind } from "@/types/catalog";

export type CartItem = {
  id: string;
  product_id: string;
  slug: string;
  name: string;
  kind: ProductKind;
  variant_id: string | null;
  variant_kind: VoucherVariantKind | null;
  quantity: number;
  unit_price_snapshot: number;
  vat_rate_snapshot: "RATE_23" | "RATE_8" | "RATE_5" | "RATE_0" | "EXEMPT";
  vat_label: string;
  line_total_grosz: number;
  short_description: string | null;
  image: { url: string; alt: string } | null;
  details: string | null;
  voucher_validity_months: number | null;
  is_gift: boolean;
};

export type CartView = {
  items: CartItem[];
  item_count: number;
  expires_at: string | null;
  calculation: {
    items: Array<{
      item_id: string;
      unit_price_snapshot: number;
      quantity: number;
      vat_rate: CartItem["vat_rate_snapshot"];
      vat_label: string;
      gross_grosz: number;
      discount_grosz: number;
      gross_before_discount_grosz: number;
      net_grosz: number;
      tax_grosz: number;
      rounding_adjustment_grosz: number;
    }>;
    vat_groups: Array<{
      vat_rate: CartItem["vat_rate_snapshot"];
      vat_label: string;
      gross_grosz: number;
      net_grosz: number;
      tax_grosz: number;
    }>;
    exempt: {
      vat_rate: "EXEMPT";
      vat_label: string;
      gross_grosz: number;
      net_grosz: number;
      tax_grosz: number;
    };
    products_gross_grosz: number;
    products_gross_before_discount_grosz: number;
    discount_grosz: number;
    discount_code: string | null;
    delivery: {
      resolved: boolean;
      gross_grosz: number;
      net_grosz: number;
      tax_grosz: number;
      vat_rate: CartItem["vat_rate_snapshot"] | null;
      vat_label: string | null;
    };
    amount_due_grosz: number;
    amount_due_is_final: boolean;
  };
  delivery: {
    requires_shipping: boolean;
    selected_method: "parcel_locker" | "courier" | "pickup_in_person" | null;
    available_quotes: Array<{
      method: "parcel_locker" | "courier" | "pickup_in_person";
      gross_grosz: number;
      vat_label: string;
    }>;
    requires_method_selection: boolean;
    threshold_basis_grosz: number;
    free_shipping_threshold_grosz: number | null;
    remaining_amount_grosz: number | null;
    free_shipping_qualified: boolean;
    show_incentive: boolean;
    message: string | null;
  };
  delivery_point: PickupPointSnapshot | null;
  discount_code: string | null;
  discount_notice: string | null;
  reorder_report?: ReorderReport | null;
};

export type ReorderReport = {
  operation_id: string;
  source_kind: "order" | "voucher";
  source_id: string;
  source_label: string;
  cart_preserved: boolean;
  discount_preserved: boolean;
  discount_revalidation_notice: string | null;
  warnings: string[];
  message: string;
  lines: Array<{
    product_id: string;
    name: string;
    variant?: string | null;
    requested_quantity: number;
    added_quantity: number;
    status: "added" | "partial" | "already_in_cart" | "skipped";
    reason: string | null;
    old_unit_price_grosz: number;
    new_unit_price_grosz: number | null;
    price_changed: boolean;
    previous_cart_unit_price_grosz?: number | null;
    cart_repriced_quantity?: number;
    warnings?: string[];
  }>;
};

export type PickupPointSnapshot = {
  operator: "inpost";
  code: string;
  name: string;
  street: string;
  postal_code: string;
  city: string;
  opening_hours: string | null;
  latitude?: number | null;
  longitude?: number | null;
  point_types: string[];
  functions: string[];
  status: string;
  verified_at: string;
};

export type CartMutation = (
  method: "POST" | "PATCH" | "DELETE",
  path: string,
  body?: object,
) => Promise<CartView>;

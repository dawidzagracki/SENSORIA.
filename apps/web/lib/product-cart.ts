import { ApiError } from "@/lib/api";

export type AddCatalogProductInput = {
  productId: string;
  variantId?: string;
};
export type ConfirmedCatalogCart = { count: number };

/** Add a catalog item through the server-priced guest cart endpoint. */
export async function addCatalogProductToCart(
  input: AddCatalogProductInput,
): Promise<ConfirmedCatalogCart> {
  const response = await fetch("/api/cart/items", {
    method: "POST",
    credentials: "include",
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      product_id: input.productId,
      variant_id: input.variantId ?? null,
      quantity: 1,
      is_gift: false,
    }),
  });
  if (!response.ok) {
    let message = "Nie udało się dodać produktu do koszyka.";
    try {
      const result = (await response.json()) as {
        error?: { message?: string };
      };
      message = result.error?.message ?? message;
    } catch {
      // Keep the safe default message for non-JSON errors.
    }
    throw new ApiError("CART_ADD_FAILED", message, response.status);
  }
  const result = (await response.json()) as { item_count?: unknown };
  if (
    typeof result.item_count !== "number" ||
    !Number.isSafeInteger(result.item_count) ||
    result.item_count < 0
  ) {
    throw new ApiError(
      "INVALID_CART_RESPONSE",
      "Koszyk zwrócił nieprawidłową odpowiedź.",
    );
  }
  return { count: result.item_count };
}

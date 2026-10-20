import { ApiError } from "./api";

/** Contract for [24]. Price is intentionally absent; the server resolves it from IDs. */
export type AddVoucherToCartInput = {
  productId: string;
  variantId: string;
  gift: boolean;
};

export type ConfirmedCart = { count: number };
export type AddVoucherToCart = (
  input: AddVoucherToCartInput,
) => Promise<ConfirmedCart>;

/** Add a voucher using the existing server-priced guest cart endpoint. */
export const addVoucherToCart: AddVoucherToCart = async (input) => {
  const response = await fetch("/api/cart/items", {
    method: "POST",
    credentials: "include",
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      product_id: input.productId,
      variant_id: input.variantId,
      quantity: 1,
      is_gift: input.gift,
    }),
  });
  if (!response.ok) {
    let message = "Nie udało się dodać vouchera do koszyka.";
    try {
      const result = (await response.json()) as {
        error?: { code?: string; message?: string };
      };
      message = result.error?.message ?? message;
    } catch {
      // Keep the safe default message.
    }
    throw new ApiError("CART_ADD_FAILED", message);
  }
  const result = (await response.json()) as { item_count?: number };
  return { count: result.item_count ?? -1 };
};

export async function addVoucherAndContinue(
  input: AddVoucherToCartInput,
  addToCart: AddVoucherToCart,
  onConfirmed: (cart: ConfirmedCart) => void,
  navigate: () => void,
): Promise<void> {
  const result = await addToCart(input);
  if (!Number.isSafeInteger(result.count) || result.count < 0) {
    throw new ApiError(
      "INVALID_CART_RESPONSE",
      "Koszyk zwrócił nieprawidłową odpowiedź.",
    );
  }
  onConfirmed(result);
  navigate();
}

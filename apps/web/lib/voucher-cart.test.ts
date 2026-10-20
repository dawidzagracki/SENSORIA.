import { describe, expect, it, vi } from "vitest";
import { addVoucherAndContinue, addVoucherToCart } from "./voucher-cart";

describe("voucher cart integration boundary", () => {
  it("persists the gift choice through the server-priced voucher cart API", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ item_count: 2 }),
    });
    vi.stubGlobal("fetch", fetchMock);
    await expect(
      addVoucherToCart({ productId: "p1", variantId: "v1", gift: true }),
    ).resolves.toEqual({ count: 2 });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/cart/items",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          product_id: "p1",
          variant_id: "v1",
          quantity: 1,
          is_gift: true,
        }),
      }),
    );
  });

  it("updates count and navigates only after server confirmation", async () => {
    const update = vi.fn();
    const navigate = vi.fn();
    const add = vi.fn().mockResolvedValue({ count: 1 });
    await addVoucherAndContinue(
      { productId: "p1", variantId: "v1", gift: false },
      add,
      update,
      navigate,
    );
    expect(add).toHaveBeenCalledWith({
      productId: "p1",
      variantId: "v1",
      gift: false,
    });
    expect(update).toHaveBeenCalledWith({ count: 1 });
    expect(navigate).toHaveBeenCalledOnce();
  });

  it("does not update count or navigate after failure", async () => {
    const update = vi.fn();
    const navigate = vi.fn();
    await expect(
      addVoucherAndContinue(
        { productId: "p1", variantId: "v1", gift: false },
        async () => {
          throw new Error("failed");
        },
        update,
        navigate,
      ),
    ).rejects.toThrow("failed");
    expect(update).not.toHaveBeenCalled();
    expect(navigate).not.toHaveBeenCalled();
  });
});

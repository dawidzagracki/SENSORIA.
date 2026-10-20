import { describe, expect, it } from "vitest";
import { purchaseLinkingMessage } from "./purchase-linking-notice";

describe("purchase linking notice", () => {
  it("announces linked order counts with Polish plural forms", () => {
    expect(purchaseLinkingMessage({ orders_linked: 1 })).toBe(
      "Znaleźliśmy 1 wcześniejsze zamówienie i dodaliśmy je do konta.",
    );
    expect(purchaseLinkingMessage({ orders_linked: 3 })).toBe(
      "Znaleźliśmy 3 wcześniejsze zamówienia i dodaliśmy je do konta.",
    );
    expect(purchaseLinkingMessage({ orders_linked: 12 })).toBe(
      "Znaleźliśmy 12 wcześniejszych zamówień i dodaliśmy je do konta.",
    );
  });

  it("does not expose notices for unverified or invalid results", () => {
    expect(purchaseLinkingMessage({ orders_linked: 0 })).toBeNull();
    expect(purchaseLinkingMessage({ orders_linked: "2" })).toBeNull();
    expect(purchaseLinkingMessage(null)).toBeNull();
  });
});

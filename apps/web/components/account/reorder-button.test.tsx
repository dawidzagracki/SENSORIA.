import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ReorderButton } from "@/components/account/reorder-button";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("ReorderButton", () => {
  it("checks availability, uses CSRF/idempotency, then navigates to the cart", async () => {
    const navigate = vi.fn();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ can_add: true, message: null }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ csrf_token: "csrf-test" }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ redirect: "/koszyk" }),
      });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("crypto", { randomUUID: () => "operation-test" });

    render(
      <ReorderButton
        endpoint="/cart/reorder/orders/order-id"
        label="Zamów ponownie"
        onNavigate={navigate}
      />,
    );
    fireEvent.click(
      await screen.findByRole("button", { name: "Zamów ponownie" }),
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(fetchMock.mock.calls[0]?.[0]).toContain("/preview");
    const [, request] = fetchMock.mock.calls[2] as [string, RequestInit];
    expect(request.method).toBe("POST");
    expect(request.headers).toEqual({
      "X-CSRF-Token": "csrf-test",
      "Idempotency-Key": "operation-test",
    });
    expect(navigate).toHaveBeenCalledWith("/koszyk");
  });

  it("keeps the button disabled and explains when preview finds no addable item", async () => {
    let resolvePreview: ((value: unknown) => void) | undefined;
    const fetchMock = vi.fn().mockImplementation(
      () =>
        new Promise((resolve) => {
          resolvePreview = resolve;
        }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ReorderButton
        endpoint="/cart/reorder/orders/order-id"
        label="Zamów ponownie"
      />,
    );
    expect(
      screen.getByRole("button", { name: /Sprawdzam możliwość/ }),
    ).toBeDisabled();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    resolvePreview?.({
      ok: true,
      json: async () => ({
        can_add: false,
        message: "Brak dostępnych pozycji.",
      }),
    });
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Brak dostępnych pozycji.",
    );
    expect(
      screen.getByRole("button", { name: "Zamów ponownie" }),
    ).toBeDisabled();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

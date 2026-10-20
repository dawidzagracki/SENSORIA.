import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  CartCountProvider,
  formatCartAccessibleName,
  useCartCount,
} from "./cart-count-provider";
import { CartLink } from "./cart-link";
import { AccountLink } from "./account-link";

const routerState = vi.hoisted(() => ({
  pathname: "/sklep",
  query: "kind=VOUCHER",
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    ...props
  }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...props} />
  ),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => routerState.pathname,
  useSearchParams: () => new URLSearchParams(routerState.query),
}));

import { MainNavigation } from "./main-navigation";

afterEach(() => {
  cleanup();
  routerState.pathname = "/sklep";
  routerState.query = "kind=VOUCHER";
});

describe("shop layout adapters", () => {
  it("formats Polish cart labels, including teens and compound counts", () => {
    const labels: [number | null, string][] = [
      [null, "Koszyk, licznik niedostępny"],
      [0, "Koszyk, pusty"],
      [1, "Koszyk, 1 produkt"],
      [2, "Koszyk, 2 produkty"],
      [5, "Koszyk, 5 produktów"],
      [12, "Koszyk, 12 produktów"],
      [14, "Koszyk, 14 produktów"],
      [22, "Koszyk, 22 produkty"],
    ];

    for (const [count, label] of labels) {
      expect(formatCartAccessibleName(count)).toBe(label);
    }
  });

  it("marks exactly the category matching the current URL and updates on rerender", () => {
    const { rerender } = render(<MainNavigation />);
    expect(screen.getByRole("link", { name: "Vouchery" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getAllByRole("link")).toHaveLength(5);

    routerState.query = "kind=BOOK";
    rerender(<MainNavigation />);
    expect(screen.getByRole("link", { name: "Książki" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "Vouchery" })).not.toHaveAttribute(
      "aria-current",
    );
  });

  it("keeps account access visible as a direct header action on every layout", () => {
    routerState.pathname = "/konto/vouchery";
    render(<AccountLink />);

    expect(screen.getByRole("link", { name: "Zaloguj się" })).toHaveAttribute(
      "href",
      "/konto",
    );
    expect(screen.getByRole("link", { name: "Zaloguj się" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("renders an unavailable initial count until the server confirms it", () => {
    function ConfirmedCountControl() {
      const { acceptConfirmedCount } = useCartCount();
      return (
        <button onClick={() => acceptConfirmedCount(22)} type="button">
          Potwierdź stan z serwera
        </button>
      );
    }

    render(
      <CartCountProvider
        initialSnapshot={{ count: null, source: "integration-pending" }}
      >
        <CartLink />
        <ConfirmedCountControl />
      </CartCountProvider>,
    );
    expect(
      screen.getByRole("link", {
        name: "Koszyk, licznik niedostępny",
      }),
    ).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Potwierdź stan z serwera" }),
    );
    expect(
      screen.getByRole("link", { name: "Koszyk, 22 produkty" }),
    ).toBeInTheDocument();
  });

  it("loads the count from the cart API without allowing an older read to overwrite a mutation", async () => {
    let resolveCart!: (value: Response) => void;
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>((resolve) => (resolveCart = resolve))),
    );
    function ConfirmedCountControl() {
      const { acceptConfirmedCount } = useCartCount();
      return (
        <button onClick={() => acceptConfirmedCount(4)} type="button">
          Potwierdź zmianę
        </button>
      );
    }
    render(
      <CartCountProvider
        initialSnapshot={{ count: null, source: "integration-pending" }}
      >
        <CartLink />
        <ConfirmedCountControl />
      </CartCountProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Potwierdź zmianę" }));
    resolveCart(
      new Response(JSON.stringify({ item_count: 1 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await waitFor(() =>
      expect(
        screen.getByRole("link", { name: "Koszyk, 4 produkty" }),
      ).toBeInTheDocument(),
    );
  });
});

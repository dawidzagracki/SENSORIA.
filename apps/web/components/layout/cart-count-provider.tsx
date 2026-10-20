"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { usePathname } from "next/navigation";
import type { CartSnapshot } from "./cart-adapter";

type CartCountContextValue = {
  count: number | null;
  source: CartSnapshot["source"];
  acceptConfirmedCount: (count: number) => void;
};

const CartCountContext = createContext<CartCountContextValue | null>(null);

export function CartCountProvider({
  children,
  initialSnapshot,
}: {
  children: ReactNode;
  initialSnapshot: CartSnapshot;
}) {
  const [snapshot, setSnapshot] = useState(initialSnapshot);
  const revision = useRef(0);
  const pathname = usePathname();
  const acceptConfirmedCount = useCallback((count: number) => {
    if (!Number.isSafeInteger(count) || count < 0) {
      throw new RangeError(
        "Licznik koszyka musi być nieujemną liczbą całkowitą.",
      );
    }
    revision.current += 1;
    setSnapshot({ count, source: "server-confirmed" });
  }, []);
  useEffect(() => {
    if (pathname === "/koszyk" || pathname === "/zamowienie") return;
    const startingRevision = revision.current;
    let active = true;
    void fetch("/api/cart", {
      credentials: "include",
      cache: "no-store",
    })
      .then(async (response) => {
        if (!response.ok) return;
        const payload: unknown = await response.json();
        if (
          typeof payload !== "object" ||
          payload === null ||
          !("item_count" in payload) ||
          !Number.isSafeInteger(payload.item_count) ||
          (payload.item_count as number) < 0
        ) {
          return;
        }
        if (active && revision.current === startingRevision) {
          setSnapshot({
            count: payload.item_count as number,
            source: "server-confirmed",
          });
        }
      })
      .catch(() => {
        // Keep the count unavailable when the server cannot confirm it.
      });
    return () => {
      active = false;
    };
  }, [pathname]);
  const value = useMemo(
    () => ({ ...snapshot, acceptConfirmedCount }),
    [snapshot, acceptConfirmedCount],
  );

  return (
    <CartCountContext.Provider value={value}>
      {children}
    </CartCountContext.Provider>
  );
}

export function useCartCount() {
  const value = useContext(CartCountContext);
  if (!value) {
    throw new Error("CartCountProvider is required for the cart indicator.");
  }
  return value;
}

export function formatCartAccessibleName(count: number | null): string {
  if (count === null) return "Koszyk, licznik niedostępny";
  if (!Number.isSafeInteger(count) || count < 0) {
    throw new RangeError(
      "Licznik koszyka musi być nieujemną liczbą całkowitą.",
    );
  }
  if (count === 0) return "Koszyk, pusty";
  if (count === 1) return "Koszyk, 1 produkt";

  const lastTwoDigits = count % 100;
  const lastDigit = count % 10;
  if (lastTwoDigits < 12 || lastTwoDigits > 14) {
    if (lastDigit >= 2 && lastDigit <= 4) {
      return `Koszyk, ${count} produkty`;
    }
  }
  return `Koszyk, ${count} produktów`;
}

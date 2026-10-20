"use client";

import { useEffect, useState } from "react";

const STORAGE_KEY = "sensoria.purchase-linking-notice.v1";

type PurchaseLinkingResult = {
  orders_linked?: unknown;
};

export function purchaseLinkingMessage(value: unknown): string | null {
  if (!value || typeof value !== "object") return null;
  const count = (value as PurchaseLinkingResult).orders_linked;
  if (typeof count !== "number" || !Number.isSafeInteger(count) || count < 1)
    return null;
  const noun =
    count === 1
      ? "wcześniejsze zamówienie"
      : count % 10 >= 2 &&
          count % 10 <= 4 &&
          !(count % 100 >= 12 && count % 100 <= 14)
        ? "wcześniejsze zamówienia"
        : "wcześniejszych zamówień";
  return `Znaleźliśmy ${count} ${noun} i dodaliśmy ${count === 1 ? "je" : "je"} do konta.`;
}

export function savePurchaseLinkingNotice(value: unknown): void {
  const message = purchaseLinkingMessage(value);
  if (message) window.sessionStorage.setItem(STORAGE_KEY, message);
}

export function PurchaseLinkingNotice() {
  const [message, setMessage] = useState("");
  useEffect(() => {
    const saved = window.sessionStorage.getItem(STORAGE_KEY);
    if (saved) {
      window.sessionStorage.removeItem(STORAGE_KEY);
      setMessage(saved);
    }
  }, []);
  if (!message) return null;
  return (
    <p
      className="rounded-control border border-success/30 bg-success/10 p-4 text-body-small text-ink"
      role="status"
    >
      {message}
    </p>
  );
}

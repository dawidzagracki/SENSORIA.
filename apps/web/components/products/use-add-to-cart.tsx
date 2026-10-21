"use client";

import Link from "next/link";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useCartCount } from "@/components/layout/cart-count-provider";
import { addCatalogProductToCart } from "@/lib/product-cart";

type Notice = { tone: "success" | "error"; text: string } | null;

/** Adds catalog items to the server cart and reports the confirmed result. */
export function useAddToCart() {
  const { acceptConfirmedCount } = useCartCount();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [notice, setNotice] = useState<Notice>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  const add = useCallback(
    async (productId: string, name: string, variantId?: string) => {
      setBusyId(productId);
      setNotice(null);
      try {
        const result = await addCatalogProductToCart({ productId, variantId });
        acceptConfirmedCount(result.count);
        setNotice({ tone: "success", text: `Dodano do koszyka: ${name}` });
      } catch (error: unknown) {
        setNotice({
          tone: "error",
          text:
            error instanceof Error
              ? error.message
              : "Nie udało się dodać produktu do koszyka.",
        });
      } finally {
        setBusyId(null);
        if (timer.current) clearTimeout(timer.current);
        timer.current = setTimeout(() => setNotice(null), 6000);
      }
    },
    [acceptConfirmedCount],
  );

  return { add, busyId, notice, dismiss: () => setNotice(null) };
}

/** Floating confirmation that never steals focus; announced politely to screen readers. */
export function CartToast({
  notice,
  onDismiss,
}: {
  notice: Notice;
  onDismiss: () => void;
}): ReactNode {
  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed inset-x-4 bottom-4 z-50 flex justify-center sm:inset-x-auto sm:right-6 sm:justify-end"
      role="status"
    >
      {notice ? (
        <div
          className={`pointer-events-auto flex max-w-md items-center gap-4 rounded-card border px-5 py-4 shadow-overlay ${
            notice.tone === "success"
              ? "border-success bg-surface text-ink"
              : "border-danger bg-danger text-on-danger"
          }`}
        >
          <span className="text-body-small font-semibold">{notice.text}</span>
          {notice.tone === "success" ? (
            <Link
              className="shrink-0 rounded-pill bg-accent-action px-4 py-2 text-caption font-semibold text-surface hover:bg-accent hover:text-ink"
              href="/koszyk"
            >
              Do koszyka
            </Link>
          ) : null}
          <button
            aria-label="Zamknij powiadomienie"
            className="shrink-0 rounded-pill px-2 py-1 text-caption text-ink-muted hover:text-ink"
            onClick={onDismiss}
            type="button"
          >
            ✕
          </button>
        </div>
      ) : null}
    </div>
  );
}

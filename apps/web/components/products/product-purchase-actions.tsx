"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useCartCount } from "@/components/layout/cart-count-provider";
import { Button, Price } from "@/components/ui";
import { addCatalogProductToCart } from "@/lib/product-cart";
import type { VatRate } from "@/types/catalog";

type Props = {
  available: boolean;
  compareAtPrice: number | null;
  disabledReason?: string;
  mobileLabel: string;
  price: number;
  productId: string;
  variantId?: string;
  primaryLabel: string;
  vatRate: VatRate | null;
};

export function ProductPurchaseActions({
  available,
  compareAtPrice,
  disabledReason,
  mobileLabel,
  price,
  productId,
  variantId,
  primaryLabel,
  vatRate,
}: Props) {
  const router = useRouter();
  const { acceptConfirmedCount } = useCartCount();
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const unavailable = !available || busy;

  async function purchase(goToOrder: boolean) {
    if (unavailable) return;
    setBusy(true);
    setNotice("");
    try {
      const result = await addCatalogProductToCart({
        productId,
        variantId,
      });
      if (!Number.isSafeInteger(result.count) || result.count < 0) {
        throw new Error("Koszyk zwrócił nieprawidłową odpowiedź.");
      }
      acceptConfirmedCount(result.count);
      if (goToOrder) router.push("/zamowienie");
      setNotice("Produkt dodano do koszyka.");
    } catch (error: unknown) {
      setNotice(
        error instanceof Error
          ? error.message
          : "Nie udało się dodać produktu do koszyka.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="space-y-4 rounded-card border border-border bg-surface p-4 shadow-subtle md:p-6">
        <Price
          amountInGrosze={price}
          previousAmountInGrosze={compareAtPrice ?? undefined}
          vatRate={vatRate ?? undefined}
        />
        <div className="flex flex-col gap-3 sm:flex-row">
          <Button
            className="w-full"
            disabled={unavailable}
            aria-describedby={disabledReason ? "purchase-reason" : undefined}
            loading={busy}
            onClick={() => void purchase(true)}
            size="lg"
          >
            {primaryLabel}
          </Button>
          <Button
            className="w-full"
            disabled={unavailable}
            aria-describedby={disabledReason ? "purchase-reason" : undefined}
            loading={busy}
            onClick={() => void purchase(false)}
            size="lg"
            variant="secondary"
          >
            Do koszyka
          </Button>
        </div>
        {disabledReason ? (
          <p className="text-body-small text-ink-muted" id="purchase-reason">
            {disabledReason}
          </p>
        ) : null}
        <p
          aria-live="polite"
          className="min-h-6 text-body-small text-ink-muted"
          role="status"
        >
          {notice ||
            (available
              ? "Zakupy wymagają potwierdzenia przez serwer koszyka."
              : "Zakup niedostępny.")}
        </p>
      </div>
      <div className="fixed inset-x-0 bottom-0 z-20 border-t border-border bg-surface p-4 pb-[calc(theme(spacing.4)+env(safe-area-inset-bottom))] shadow-overlay lg:hidden">
        <div className="mx-auto flex max-w-page-shell items-center gap-4">
          <div className="min-w-0 flex-1">
            <Price
              amountInGrosze={price}
              previousAmountInGrosze={compareAtPrice ?? undefined}
              vatRate={vatRate ?? undefined}
            />
          </div>
          <Button
            disabled={unavailable}
            aria-describedby={disabledReason ? "purchase-reason" : undefined}
            loading={busy}
            onClick={() => void purchase(true)}
            size="md"
          >
            {mobileLabel}
          </Button>
        </div>
      </div>
    </>
  );
}

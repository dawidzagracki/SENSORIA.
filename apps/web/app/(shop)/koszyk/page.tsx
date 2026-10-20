import type { Metadata } from "next";
import { CartPageClient } from "@/components/cart/cart-page-client";

export const metadata: Metadata = { robots: { index: false, follow: false } };

export default function CartPage() {
  return <CartPageClient />;
}

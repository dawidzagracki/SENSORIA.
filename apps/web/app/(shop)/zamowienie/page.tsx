import type { Metadata } from "next";
import { CheckoutPage } from "@/components/checkout/checkout-page";

export const metadata: Metadata = {
  title: "Zamówienie | Sensoria",
  robots: { index: false, follow: false },
};

export default function OrderPage() {
  return <CheckoutPage />;
}

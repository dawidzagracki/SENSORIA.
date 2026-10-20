import type { Metadata } from "next";
import { HelpCenter } from "@/components/help/help-center";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Centrum pomocy | SENSORIA",
  description:
    "Odpowiedzi na najczęstsze pytania o zamówienia, dostawę, vouchery i materiały cyfrowe.",
};

export default function HelpPage() {
  return <HelpCenter />;
}

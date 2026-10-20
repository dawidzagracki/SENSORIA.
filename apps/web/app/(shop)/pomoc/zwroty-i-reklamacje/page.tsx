import type { Metadata } from "next";
import Link from "next/link";
import { SupportCaseForm } from "@/components/support/support-case-form";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Zwroty i reklamacje | SENSORIA",
  description:
    "Zgłoś reklamację albo zwrot towaru i sprawdź status zgłoszenia.",
};

export default async function ReturnsPage({
  searchParams,
}: {
  searchParams: Promise<{ order?: string; token?: string }>;
}) {
  const { order, token } = await searchParams;
  const orderId = typeof order === "string" ? order : null;
  const orderToken = typeof token === "string" ? token : null;
  return (
    <main
      id="main-content"
      tabIndex={-1}
      className="mx-auto w-full max-w-content min-w-0 px-4 py-10 focus:outline-none sm:py-14"
    >
      <h1 className="font-display text-title text-ink">Zwroty i reklamacje</h1>
      <div className="mt-4 space-y-4 font-body text-body text-ink">
        <h2 className="font-display text-emphasis">Reklamacja</h2>
        <p>
          Jeśli produkt ma wadę, plik nie otwiera się albo zamówienie nie
          odpowiada opisowi, opisz problem poniżej. Na reklamację odpowiadamy
          najpóźniej w ciągu <strong>14 dni</strong>.
        </p>
        <h2 className="font-display text-emphasis">Zwrot towaru</h2>
        <p>
          Zwrot dotyczy przesyłek fizycznych w ciągu 14 dni od otrzymania.
          Zasady odstąpienia opisaliśmy w osobnej sekcji:{" "}
          <Link
            className="text-accent-action underline"
            href="/pomoc/odstapienie"
          >
            odstąpienie od umowy
          </Link>
          .
        </p>
      </div>
      <SupportCaseForm
        kinds={["complaint", "return"]}
        orderId={orderId}
        token={orderToken}
        nextPath="/pomoc/zwroty-i-reklamacje"
      />
    </main>
  );
}

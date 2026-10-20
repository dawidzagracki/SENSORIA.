import type { Metadata } from "next";
import Link from "next/link";
import { SupportCaseForm } from "@/components/support/support-case-form";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Odstąpienie od umowy | SENSORIA",
  description:
    "Jak odstąpić od umowy w ciągu 14 dni i kiedy prawo odstąpienia nie przysługuje.",
};

export default async function WithdrawalPage({
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
      <h1 className="font-display text-title text-ink">Odstąpienie od umowy</h1>
      <div className="mt-4 space-y-4 font-body text-body text-ink">
        <p>
          Zamówienie możesz wycofać bez podania przyczyny w ciągu{" "}
          <strong>14 dni</strong>. Dla książek termin liczymy od dnia ich
          otrzymania, dla voucherów — od dnia zawarcia umowy.
        </p>
        <h2 className="font-display text-emphasis">Treści cyfrowe</h2>
        <p>
          Przy e-bookach, kursach PDF i audiobookach udostępnianych od razu po
          płatności prawo odstąpienia nie przysługuje, ponieważ w trakcie
          zamówienia wyrażasz zgodę na rozpoczęcie świadczenia i przyjmujesz do
          wiadomości jego utratę. Jeśli plik nie działa lub nie odpowiada
          opisowi, złóż{" "}
          <Link
            className="text-accent-action underline"
            href="/pomoc/zwroty-i-reklamacje"
          >
            reklamację
          </Link>
          .
        </p>
        <p>
          Szczegółowe zasady znajdziesz w{" "}
          <Link className="text-accent-action underline" href="/regulamin">
            regulaminie
          </Link>
          .
        </p>
      </div>
      <SupportCaseForm
        kinds={["withdrawal", "return"]}
        orderId={orderId}
        token={orderToken}
        nextPath="/pomoc/odstapienie"
      />
    </main>
  );
}

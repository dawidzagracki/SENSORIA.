import type { Metadata } from "next";
import Link from "next/link";
import { ApiError, requestJson } from "@/lib/api";
import { getServerApiUrl } from "@/lib/server-api-url";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Sprawdzenie vouchera | SENSORIA",
  robots: { index: false, follow: false, noarchive: true },
  referrer: "no-referrer",
};

type Verification = {
  status: string;
  valid_until: string | null;
  code: string;
};

const labels: Record<string, { text: string; tone: string }> = {
  active: { text: "Aktywny", tone: "bg-success text-on-success" },
  expiring_soon: {
    text: "Aktywny — wkrótce wygasa",
    tone: "bg-warning text-on-warning",
  },
  redeemed: { text: "Zrealizowany", tone: "bg-info text-on-info" },
  expired: { text: "Wygasły", tone: "bg-danger text-on-danger" },
  cancelled: { text: "Anulowany", tone: "bg-danger text-on-danger" },
  scheduled: {
    text: "Oczekuje na wysyłkę prezentu",
    tone: "bg-info text-on-info",
  },
};

async function verify(
  code: string,
): Promise<Verification | "missing" | "limited" | "error"> {
  const apiUrl = getServerApiUrl();
  if (!apiUrl) return "error";
  try {
    return (await requestJson(
      apiUrl,
      `/vouchers/verify/${encodeURIComponent(code)}`,
      { cache: "no-store" },
    )) as Verification;
  } catch (error: unknown) {
    if (error instanceof ApiError && error.status === 404) return "missing";
    if (error instanceof ApiError && error.status === 429) return "limited";
    return "error";
  }
}

export default async function VoucherCheckPage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = await params;
  const result = await verify(code);
  const info = typeof result === "object" ? labels[result.status] : undefined;
  return (
    <main
      id="main-content"
      tabIndex={-1}
      className="mx-auto w-full max-w-content min-w-0 px-4 py-14 focus:outline-none"
    >
      <h1 className="font-display text-title text-ink">Sprawdzenie vouchera</h1>
      {typeof result === "object" ? (
        <section
          className="mt-6 rounded-card border border-border bg-surface p-6"
          aria-live="polite"
        >
          <p className="font-display text-emphasis tracking-wider">
            {result.code}
          </p>
          <p
            className={`mt-3 inline-block rounded-pill px-4 py-2 text-label font-bold ${info?.tone ?? ""}`}
          >
            {info?.text ?? result.status}
          </p>
          {result.valid_until ? (
            <p className="mt-4 text-body text-ink">
              Ważny do:{" "}
              <strong>
                {new Intl.DateTimeFormat("pl-PL", {
                  day: "numeric",
                  month: "long",
                  year: "numeric",
                }).format(new Date(`${result.valid_until}T12:00:00`))}
              </strong>{" "}
              (włącznie)
            </p>
          ) : null}
          <p className="mt-4 text-caption text-ink-muted">
            Nie pokazujemy danych osobowych. Realizacja vouchera następuje
            wyłącznie w gabinecie.
          </p>
        </section>
      ) : (
        <section
          className="mt-6 rounded-card border border-border bg-surface-muted p-6"
          role="status"
        >
          <p className="text-body text-ink">
            {result === "missing"
              ? "Nie znaleźliśmy vouchera o takim kodzie. Sprawdź, czy kod jest przepisany poprawnie."
              : result === "limited"
                ? "Zbyt wiele sprawdzeń. Spróbuj ponownie za minutę."
                : "Nie udało się sprawdzić vouchera. Spróbuj ponownie za chwilę."}
          </p>
        </section>
      )}
      <Link
        className="mt-6 inline-flex min-h-touch items-center text-accent-action underline"
        href="/"
      >
        Strona główna
      </Link>
    </main>
  );
}

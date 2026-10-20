"use client";

import Link from "next/link";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
import { Button } from "@/components/ui/button";

const API = process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") || "/api";
type ConsentType = "new_materials" | "voucher_reminders" | "review_requests";
type Consent = { type: ConsentType; granted: boolean; description: string };
type ExportJob = {
  id: string;
  status: string;
  expires_at?: string | null;
  error?: string | null;
};

const consentLabels: Record<ConsentType, string> = {
  new_materials: "Wiadomości o nowych materiałach",
  voucher_reminders: "Przypomnienia o voucherach",
  review_requests: "Prośby o opinię",
};

async function messageFrom(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { error?: { message?: string } };
    return body.error?.message ?? "Nie udało się wykonać tej operacji.";
  } catch {
    return "Nie udało się wykonać tej operacji.";
  }
}

export function PrivacyControls({ email }: { email: string }) {
  const [consents, setConsents] = useState<Consent[]>([]);
  const [consentLoading, setConsentLoading] = useState(true);
  const [busyType, setBusyType] = useState<ConsentType | null>(null);
  const [exportJob, setExportJob] = useState<ExportJob | null>(null);
  const [exportBusy, setExportBusy] = useState(false);
  const [deleteEmail, setDeleteEmail] = useState("");
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);

  const csrfHeaders = useCallback(async () => {
    const response = await fetch(`${API}/accounts/csrf`, {
      credentials: "include",
      cache: "no-store",
    });
    if (!response.ok) throw new Error("Sesja wygasła. Zaloguj się ponownie.");
    const body = (await response.json()) as { csrf_token?: string };
    if (!body.csrf_token) throw new Error("Odśwież stronę i spróbuj ponownie.");
    return {
      "Content-Type": "application/json",
      "X-CSRF-Token": body.csrf_token,
    };
  }, []);

  const loadConsents = useCallback(async () => {
    setConsentLoading(true);
    try {
      const response = await fetch(`${API}/accounts/privacy/consents`, {
        credentials: "include",
        cache: "no-store",
      });
      if (response.status === 401) {
        window.location.assign(
          `/konto?next=${encodeURIComponent("/konto/dane")}`,
        );
        return;
      }
      if (!response.ok) throw new Error(await messageFrom(response));
      const body = (await response.json()) as { items: Consent[] };
      setConsents(body.items);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Nie udało się pobrać zgód.",
      );
    } finally {
      setConsentLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadConsents();
  }, [loadConsents]);

  useEffect(() => {
    if (!exportJob || !["pending", "processing"].includes(exportJob.status))
      return;
    const timer = window.setInterval(() => {
      void fetch(`${API}/accounts/privacy/export/${exportJob.id}`, {
        credentials: "include",
        cache: "no-store",
      })
        .then(async (response) => {
          if (!response.ok) throw new Error(await messageFrom(response));
          setExportJob((await response.json()) as ExportJob);
        })
        .catch((cause: unknown) => {
          setError(
            cause instanceof Error
              ? cause.message
              : "Nie udało się sprawdzić eksportu.",
          );
        });
    }, 3000);
    return () => window.clearInterval(timer);
  }, [exportJob]);

  async function updateConsent(item: Consent) {
    setBusyType(item.type);
    setError("");
    setStatus("");
    try {
      const response = await fetch(
        `${API}/accounts/privacy/consents/${item.type}`,
        {
          method: "PUT",
          credentials: "include",
          headers: await csrfHeaders(),
          body: JSON.stringify({ granted: !item.granted }),
        },
      );
      if (!response.ok) throw new Error(await messageFrom(response));
      const saved = (await response.json()) as { granted: boolean };
      setConsents((current) =>
        current.map((entry) =>
          entry.type === item.type
            ? { ...entry, granted: saved.granted }
            : entry,
        ),
      );
      setStatus(saved.granted ? "Zapisano zgodę." : "Zgoda została cofnięta.");
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Nie udało się zapisać zgody.",
      );
    } finally {
      setBusyType(null);
    }
  }

  async function startExport() {
    setExportBusy(true);
    setError("");
    setStatus("");
    try {
      const response = await fetch(`${API}/accounts/privacy/export`, {
        method: "POST",
        credentials: "include",
        headers: await csrfHeaders(),
        body: "{}",
      });
      if (!response.ok) throw new Error(await messageFrom(response));
      const body = (await response.json()) as ExportJob;
      setExportJob(body);
      setStatus(
        "Zlecono przygotowanie archiwum. Gdy będzie gotowe, pobierzesz je tutaj.",
      );
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Nie udało się zlecić eksportu.",
      );
    } finally {
      setExportBusy(false);
    }
  }

  async function confirmDeletion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setDeleteBusy(true);
    setError("");
    try {
      const response = await fetch(`${API}/accounts/privacy/delete`, {
        method: "POST",
        credentials: "include",
        headers: await csrfHeaders(),
        body: JSON.stringify({ email: deleteEmail }),
      });
      if (!response.ok) throw new Error(await messageFrom(response));
      const body = (await response.json()) as { message: string };
      setStatus(body.message);
      dialog.current?.close();
      window.setTimeout(() => window.location.assign("/"), 800);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Nie udało się zamknąć konta.",
      );
    } finally {
      setDeleteBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <section
        id="zgody"
        className="scroll-mt-6 rounded-card border border-border bg-surface p-5 sm:p-6"
      >
        <h2 className="text-subtitle font-bold">Zgody</h2>
        <p className="mt-2 text-body-small text-ink-muted">
          Każdą możesz cofnąć w dowolnym momencie. Nie wpływa to na Twoje
          zamówienia ani dostęp do materiałów.
        </p>
        {consentLoading ? (
          <p role="status" className="mt-5">
            Ładowanie zgód…
          </p>
        ) : (
          <div className="mt-5 divide-y divide-border">
            {consents.map((item) => (
              <div
                key={item.type}
                className="flex items-start justify-between gap-4 py-4 first:pt-0 last:pb-0"
              >
                <div className="min-w-0">
                  <h3 className="text-label font-bold">
                    {consentLabels[item.type]}
                  </h3>
                  <p className="mt-1 max-w-prose text-body-small text-ink-muted">
                    {item.description}
                  </p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={item.granted}
                  aria-label={consentLabels[item.type]}
                  disabled={busyType !== null}
                  onClick={() => void updateConsent(item)}
                  className={`relative mt-1 inline-flex h-7 w-12 shrink-0 items-center rounded-full border border-border p-1 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action disabled:opacity-60 ${item.granted ? "bg-accent-action" : "bg-surface-muted"}`}
                >
                  <span
                    aria-hidden="true"
                    className={`size-5 rounded-full bg-surface shadow-card transition-transform ${item.granted ? "translate-x-5" : "translate-x-0"}`}
                  />
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-card border border-border bg-surface p-5 sm:p-6">
        <h2 className="text-subtitle font-bold">Twoje dane, Twoja decyzja</h2>
        <p className="mt-2 text-body-small text-ink-muted">
          Możesz pobrać kopię danych swojego konta. Dokumenty sprzedaży i dane
          wymagane do ich rozliczenia są zachowywane z ograniczonym dostępem.
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <Button
            variant="secondary"
            disabled={
              exportBusy ||
              Boolean(
                exportJob &&
                ["pending", "processing"].includes(exportJob.status),
              )
            }
            loading={exportBusy}
            onClick={() => void startExport()}
          >
            Pobierz moje dane
          </Button>
          <Link
            href="/konto/zmien-haslo"
            className="inline-flex min-h-control-md items-center justify-center rounded-pill border border-accent-action bg-surface px-4 py-3 text-label font-bold text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
          >
            Zmień hasło
          </Link>
        </div>
        {exportJob && (
          <div className="mt-3 text-body-small" role="status">
            {exportJob.status === "ready" ? (
              <>
                <span>
                  Archiwum jest gotowe. Dostęp wygaśnie po 15 minutach.{" "}
                </span>
                <a
                  className="font-bold underline"
                  href={`${API}/accounts/privacy/export/${exportJob.id}/download`}
                >
                  Pobierz archiwum ZIP
                </a>
              </>
            ) : exportJob.status === "pending" ||
              exportJob.status === "processing" ? (
              "Przygotowujemy archiwum…"
            ) : exportJob.status === "failed" ? (
              "Przygotowanie nie powiodło się. Możesz ponowić zlecenie."
            ) : (
              "Poprzednie archiwum wygasło. Możesz przygotować nowe."
            )}
          </div>
        )}
        <div className="mt-5 rounded-card border border-dashed border-border p-4 sm:p-5">
          <h3 className="font-bold">Usunięcie konta</h3>
          <p className="mt-2 max-w-prose text-body-small text-ink-muted">
            Zamkniemy możliwość logowania, unieważnimy sesje i zakończymy dostęp
            do kupionych plików. Usuniemy kontakty i zapisane adresy, a
            pozostały rekord konta odidentyfikujemy. Wymagane dokumenty
            sprzedaży oraz minimalny dowód zgód pozostaną z ograniczonym
            dostępem przez wymagany okres. Niewykorzystane vouchery ani
            zobowiązania z opłaconych zamówień nie zostaną automatycznie
            anulowane.
          </p>
          <p className="mt-2 max-w-prose text-body-small text-ink-muted">
            Zamknięcie konta oznacza utratę bezterminowego dostępu obiecanego
            dla materiałów cyfrowych — pobierz potrzebne pliki przed
            potwierdzeniem. Kopie zapasowe mogą podlegać własnemu cyklowi
            retencji.
          </p>
          <Button
            className="mt-4"
            variant="secondary"
            onClick={() => {
              setDeleteEmail("");
              setError("");
              dialog.current?.showModal();
            }}
          >
            Usuń konto
          </Button>
        </div>
      </section>

      {error && (
        <p
          role="alert"
          className="rounded-control bg-danger px-4 py-3 text-on-danger"
        >
          {error}
        </p>
      )}
      {status && (
        <p
          role="status"
          className="rounded-control bg-success px-4 py-3 text-on-success"
        >
          {status}
        </p>
      )}

      <dialog
        ref={dialog}
        aria-labelledby="account-delete-title"
        className="m-auto max-h-[90dvh] w-[calc(100%-2rem)] max-w-xl rounded-card border border-border bg-surface p-5 text-ink backdrop:bg-ink/40 sm:p-7"
      >
        <form onSubmit={(event) => void confirmDeletion(event)}>
          <h2 id="account-delete-title" className="text-subtitle font-bold">
            Potwierdź zamknięcie konta
          </h2>
          <p className="mt-3 text-body-small text-ink-muted">
            Wpisz aktualny adres e-mail konta. Operacja wymaga świeżego
            logowania; jeśli logowałaś się dawno temu, zaloguj się ponownie
            przed potwierdzeniem.
          </p>
          <label
            className="mt-4 block text-label"
            htmlFor="delete-account-email"
          >
            Aktualny adres e-mail
          </label>
          <input
            id="delete-account-email"
            type="email"
            autoComplete="email"
            required
            value={deleteEmail}
            onChange={(event) => setDeleteEmail(event.target.value)}
            className="mt-2 min-h-touch w-full rounded-control border border-border bg-surface px-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
          />
          <p className="mt-3 text-body-small text-ink-muted">
            Historia rozliczeń i dokumenty wymagane prawem nie zostaną usunięte.
            Ich zachowanie nie oznacza aktywnego konta ani dostępu do
            materiałów.
          </p>
          <div className="mt-5 flex flex-wrap justify-end gap-3">
            <Button
              type="button"
              variant="secondary"
              disabled={deleteBusy}
              onClick={() => dialog.current?.close()}
            >
              Anuluj
            </Button>
            <Button
              type="submit"
              disabled={
                deleteBusy ||
                deleteEmail.trim().toLowerCase() !== email.toLowerCase()
              }
              loading={deleteBusy}
            >
              Potwierdź usunięcie
            </Button>
          </div>
        </form>
      </dialog>
    </div>
  );
}

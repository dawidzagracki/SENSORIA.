"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";

const API = process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") || "/api";

export function EmailChangeConfirmation() {
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [doneMessage, setDoneMessage] = useState("");

  useEffect(() => {
    setToken(window.location.hash.slice(1));
  }, []);

  async function confirm() {
    setBusy(true);
    setError("");
    try {
      const csrfResponse = await fetch(`${API}/accounts/csrf`, {
        credentials: "include",
        cache: "no-store",
      });
      if (!csrfResponse.ok)
        throw new Error(
          "Zaloguj się ponownie i otwórz link z wiadomości jeszcze raz.",
        );
      const csrf = (await csrfResponse.json()) as { csrf_token: string };
      const response = await fetch(
        `${API}/accounts/profile/email-change/confirm`,
        {
          method: "POST",
          credentials: "include",
          cache: "no-store",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": csrf.csrf_token,
          },
          body: JSON.stringify({ token }),
        },
      );
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as {
          error?: { message?: string };
        } | null;
        throw new Error(
          body?.error?.message ?? "Link jest nieprawidłowy lub wygasł.",
        );
      }
      const result = (await response.json()) as { message: string };
      window.history.replaceState(null, "", "/konto/dane");
      setDoneMessage(result.message);
      setDone(true);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Nie udało się potwierdzić adresu.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main
      id="main-content"
      className="min-h-[60vh] bg-surface px-4 py-12 text-ink"
    >
      <section className="mx-auto max-w-xl rounded-card border border-border bg-surface p-6 sm:p-8">
        <p className="text-label font-bold tracking-caps text-accent-action">
          TWOJE KONTO
        </p>
        <h1 className="mt-3 font-display text-title font-bold">
          Potwierdź nowy adres e-mail
        </h1>
        {done ? (
          <div className="mt-5">
            <p role="status">{doneMessage}</p>
            <Link
              className="mt-4 inline-flex min-h-touch items-center rounded-pill border border-accent-action px-4 font-bold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
              href="/konto"
            >
              Przejdź do logowania
            </Link>
          </div>
        ) : (
          <>
            <p className="mt-4 text-body text-ink-muted">
              Potwierdź zmianę świadomie. Samo otwarcie tej strony nie zmienia
              adresu.
            </p>
            {!token && (
              <p
                role="alert"
                className="mt-4 rounded-control bg-warning p-3 text-on-warning"
              >
                Brakuje tokenu potwierdzenia. Otwórz pełny odnośnik z
                wiadomości.
              </p>
            )}
            {error && (
              <p
                role="alert"
                className="mt-4 rounded-control bg-danger p-3 text-on-danger"
              >
                {error}
              </p>
            )}
            <Button
              className="mt-6 w-full"
              disabled={!token || busy}
              loading={busy}
              onClick={() => void confirm()}
            >
              Potwierdź zmianę adresu
            </Button>
            <p className="mt-4 text-body-small text-ink-muted">
              Potwierdzenie działa także na innym urządzeniu. Wymaga
              wcześniejszego zalogowania przy składaniu prośby, nie ponownego
              logowania w tej przeglądarce.
            </p>
          </>
        )}
        <Link
          className="mt-5 inline-flex min-h-touch items-center text-label underline underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
          href="/konto/dane"
        >
          Wróć do danych konta
        </Link>
      </section>
    </main>
  );
}

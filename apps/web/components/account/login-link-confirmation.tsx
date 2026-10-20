"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { safeReturnPath } from "@/lib/safe-return";
import { savePurchaseLinkingNotice } from "@/components/account/purchase-linking-notice";

const API = process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") || "/api";
const INVALID_MESSAGE =
  "Ten link jest nieprawidłowy, wygasł lub został już użyty. Poproś o nowy link.";

export function LoginLinkConfirmation({
  initialToken,
}: {
  initialToken: string;
}) {
  const router = useRouter();
  const [token, setToken] = useState(initialToken);
  const [checking, setChecking] = useState(true);
  const [valid, setValid] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (initialToken)
      window.history.replaceState(null, "", "/konto/link-logowania");
    else setChecking(false);
  }, [initialToken]);

  useEffect(() => {
    if (!token) return;
    let active = true;
    void fetch(`${API}/auth/login-link/${encodeURIComponent(token)}`, {
      method: "GET",
      credentials: "include",
      cache: "no-store",
      referrerPolicy: "no-referrer",
    })
      .then(async (response) => {
        const body = (await response.json().catch(() => ({}))) as {
          valid?: boolean;
        };
        if (active) setValid(response.ok && body.valid === true);
      })
      .catch(() => {
        if (active) setValid(false);
      })
      .finally(() => {
        if (active) setChecking(false);
      });
    return () => {
      active = false;
    };
  }, [token]);

  async function confirmLogin() {
    if (!token || busy) return;
    setBusy(true);
    setError("");
    try {
      const csrfResponse = await fetch(`${API}/accounts/csrf`, {
        credentials: "include",
        cache: "no-store",
      });
      if (!csrfResponse.ok)
        throw new Error("Odśwież stronę i spróbuj ponownie.");
      const csrfBody = (await csrfResponse.json()) as { csrf_token?: string };
      if (!csrfBody.csrf_token)
        throw new Error("Odśwież stronę i spróbuj ponownie.");
      const response = await fetch(
        `${API}/auth/login-link/${encodeURIComponent(token)}`,
        {
          method: "POST",
          credentials: "include",
          cache: "no-store",
          referrerPolicy: "no-referrer",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": csrfBody.csrf_token,
          },
          body: "{}",
        },
      );
      const body = (await response.json().catch(() => ({}))) as {
        redirect_to?: string;
        purchase_linking?: unknown;
        error?: { message?: string };
      };
      if (!response.ok) {
        if (response.status !== 409) setValid(false);
        throw new Error(body.error?.message || INVALID_MESSAGE);
      }
      const destination = safeReturnPath(body.redirect_to);
      savePurchaseLinkingNotice(body.purchase_linking);
      setToken("");
      router.replace(destination);
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : INVALID_MESSAGE);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="w-full max-w-xl rounded-card border border-border bg-surface p-5 shadow-subtle sm:p-8">
      <h2 className="font-display text-subtitle text-ink">
        Logowanie odnośnikiem
      </h2>
      {checking ? (
        <p className="mt-4 text-body-small text-ink-muted" role="status">
          Sprawdzamy ważność linku…
        </p>
      ) : valid ? (
        <>
          <p className="mt-4 text-body-small text-ink-muted">
            Zalogowanie nastąpi dopiero po wybraniu przycisku. Link jest
            jednorazowy i ważny przez 15 minut.
          </p>
          <Button
            className="mt-6 w-full"
            loading={busy}
            loadingLabel="Trwa logowanie"
            onClick={() => void confirmLogin()}
            size="lg"
          >
            Zaloguj mnie
          </Button>
        </>
      ) : (
        <>
          <p className="mt-4 text-body-small text-ink-muted" role="status">
            {INVALID_MESSAGE}
          </p>
          <Link
            className="mt-6 inline-flex min-h-control-lg items-center justify-center rounded-pill border border-border px-5 py-3 font-bold text-ink underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
            href="/konto"
          >
            Poproś o nowy link
          </Link>
        </>
      )}
      {error ? (
        <p className="mt-4 text-body-small text-on-danger" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  );
}

"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { ACCOUNT_SESSION_EVENT } from "@/components/layout/account-link";
import { TextField } from "@/components/ui/text-field";

const API = process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") || "/api";

async function postJson(path: string, data: unknown) {
  const csrfResponse = await fetch(`${API}/accounts/csrf`, {
    credentials: "include",
    cache: "no-store",
  });
  const { csrf_token: token } = (await csrfResponse.json()) as {
    csrf_token?: string;
  };
  const response = await fetch(`${API}${path}`, {
    method: "POST",
    credentials: "include",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": token ?? "",
    },
    body: JSON.stringify(data),
  });
  const body = (await response.json().catch(() => ({}))) as {
    error?: { message?: string };
    return_to?: string;
    message?: string;
  };
  if (!response.ok)
    throw new Error(
      body.error?.message ||
        "Nie udało się wykonać operacji. Spróbuj ponownie.",
    );
  return body;
}

export function EmailCodeLogin({ nextPath }: { nextPath: string }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function requestCode(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    setBusy(true);
    setError("");
    try {
      const body = await postJson("/auth/email-code/request", { email });
      setNotice(body.message ?? "Wysłaliśmy kod.");
      setSent(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Błąd.");
    } finally {
      setBusy(false);
    }
  }

  async function verify(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const body = await postJson("/auth/email-code/verify", {
        email,
        code,
        return_to:
          nextPath && nextPath !== "/konto" ? nextPath : "/konto/biblioteka",
      });
      window.dispatchEvent(new Event(ACCOUNT_SESSION_EVENT));
      router.push(body.return_to ?? "/konto/biblioteka");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Błąd.");
      setBusy(false);
    }
  }

  return (
    <div className="mt-7 space-y-5">
      <p className="text-body-small text-ink-muted">
        Kupiłaś bez konta? Wpisz adres e-mail z zamówienia — wyślemy na niego
        6-cyfrowy kod. Po jego wpisaniu zobaczysz swoje kursy, audiobooki,
        e-booki i zamówienia.
      </p>
      {sent ? (
        <form className="space-y-5" onSubmit={verify}>
          <p className="text-body-small text-on-success" role="status">
            {notice}
          </p>
          <TextField
            autoComplete="one-time-code"
            inputMode="numeric"
            label="Kod z wiadomości"
            maxLength={6}
            minLength={6}
            name="code"
            onChange={(event) =>
              setCode(event.target.value.replace(/\D/g, "").slice(0, 6))
            }
            pattern="\d{6}"
            required
            value={code}
          />
          {error ? (
            <p className="text-body-small text-on-danger" role="alert">
              {error}
            </p>
          ) : null}
          <Button
            className="w-full"
            disabled={busy || code.length !== 6}
            loading={busy}
            size="lg"
            type="submit"
          >
            Wejdź na konto
          </Button>
          <button
            className="min-h-touch text-label font-bold text-accent-action underline"
            disabled={busy}
            onClick={() => void requestCode()}
            type="button"
          >
            Wyślij kod ponownie
          </button>
        </form>
      ) : (
        <form className="space-y-5" onSubmit={requestCode}>
          <TextField
            autoComplete="email"
            label="Adres e-mail z zamówienia"
            name="email"
            onChange={(event) => setEmail(event.target.value)}
            required
            type="email"
            value={email}
          />
          {error ? (
            <p className="text-body-small text-on-danger" role="alert">
              {error}
            </p>
          ) : null}
          <Button
            className="w-full"
            disabled={busy}
            loading={busy}
            size="lg"
            type="submit"
          >
            Wyślij mi kod
          </Button>
        </form>
      )}
    </div>
  );
}

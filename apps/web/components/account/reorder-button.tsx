"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";

const API = process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") || "/api";

async function csrfToken(): Promise<string> {
  const response = await fetch(`${API}/accounts/csrf`, {
    credentials: "include",
    cache: "no-store",
  });
  const payload = (await response.json().catch(() => ({}))) as {
    csrf_token?: string;
  };
  if (!response.ok || !payload.csrf_token)
    throw new Error("Nie udało się przygotować bezpiecznej operacji.");
  return payload.csrf_token;
}

export function ReorderButton({
  endpoint,
  label,
  onNavigate,
}: {
  endpoint: string;
  label: string;
  onNavigate?: (path: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [key, setKey] = useState("");
  const [canAdd, setCanAdd] = useState<boolean | null>(null);
  const [availabilityMessage, setAvailabilityMessage] = useState("");

  useEffect(() => {
    let active = true;
    void fetch(`${API}${endpoint}/preview`, {
      credentials: "include",
      cache: "no-store",
    })
      .then(async (response) => {
        const payload = (await response.json().catch(() => ({}))) as {
          can_add?: boolean;
          message?: string | null;
          error?: { message?: string };
        };
        if (!response.ok)
          throw new Error(
            payload.error?.message || "Nie udało się sprawdzić dostępności.",
          );
        if (active) {
          setCanAdd(payload.can_add === true);
          setAvailabilityMessage(payload.message || "");
        }
      })
      .catch((cause: unknown) => {
        if (active) {
          setCanAdd(false);
          setAvailabilityMessage(
            cause instanceof Error
              ? cause.message
              : "Nie udało się sprawdzić dostępności.",
          );
        }
      });
    return () => {
      active = false;
    };
  }, [endpoint]);

  async function submit() {
    if (busy) return;
    setBusy(true);
    setError("");
    const operationKey = key || crypto.randomUUID();
    setKey(operationKey);
    try {
      const csrf = await csrfToken();
      const response = await fetch(`${API}${endpoint}`, {
        method: "POST",
        credentials: "include",
        cache: "no-store",
        headers: {
          "X-CSRF-Token": csrf,
          "Idempotency-Key": operationKey,
        },
      });
      const payload = (await response.json().catch(() => ({}))) as {
        error?: { message?: string };
        redirect?: string;
      };
      if (!response.ok)
        throw new Error(
          payload.error?.message || "Nie udało się ponowić zakupu.",
        );
      setKey("");
      (onNavigate ?? ((path: string) => window.location.assign(path)))(
        payload.redirect || "/koszyk",
      );
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Nie udało się ponowić zakupu. Spróbuj ponownie.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-w-0">
      <Button
        disabled={busy || canAdd !== true}
        loading={busy}
        onClick={() => void submit()}
        variant="secondary"
      >
        {busy
          ? "Dodaję do koszyka…"
          : canAdd === null
            ? "Sprawdzam możliwość…"
            : label}
      </Button>
      {availabilityMessage ? (
        <p className="mt-1 max-w-xs text-caption text-ink-muted" role="status">
          {availabilityMessage}
        </p>
      ) : null}
      {error ? (
        <p className="mt-1 max-w-xs text-caption text-danger" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

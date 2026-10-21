"use client";

import { BrandLogo } from "@/components/layout/brand-logo";
import { useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { TextField } from "@/components/ui/text-field";
import { setSession, type AdminIdentity } from "@/lib/admin-api";
import { apiJson } from "@/lib/client-api";

export function AdminLoginForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const data = await apiJson<{ admin: AdminIdentity; csrf_token: string }>(
        "/admin/auth/login",
        { method: "POST", json: { email, password } },
      );
      setSession(data.admin, data.csrf_token);
      window.location.assign("/admin");
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Nie udało się zalogować.",
      );
      setBusy(false);
    }
  }

  return (
    <main
      id="main-content"
      tabIndex={-1}
      className="mx-auto flex min-h-screen w-full max-w-md flex-col justify-center px-4 py-10 focus:outline-none"
    >
      <p className="font-display text-emphasis">
        <BrandLogo />
      </p>
      <h1 className="mt-2 font-display text-title text-ink">Panel sklepu</h1>
      <form onSubmit={submit} className="mt-6 space-y-4" noValidate>
        {error ? <Alert variant="error">{error}</Alert> : null}
        <TextField
          label="Adres e-mail"
          type="email"
          autoComplete="username"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <TextField
          label="Hasło"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <Button type="submit" size="lg" loading={busy} className="w-full">
          Zaloguj się
        </Button>
        <p className="text-caption text-ink-muted">
          Po kilku nieudanych próbach logowanie jest blokowane na 15 minut.
        </p>
      </form>
    </main>
  );
}

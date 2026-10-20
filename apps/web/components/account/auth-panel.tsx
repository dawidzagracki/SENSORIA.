"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { TextField } from "@/components/ui/text-field";
import { safeReturnPath } from "@/lib/safe-return";
import {
  PurchaseLinkingNotice,
  purchaseLinkingMessage,
  savePurchaseLinkingNotice,
} from "@/components/account/purchase-linking-notice";

const API = process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") || "/api";

class ApiFormError extends Error {
  constructor(
    message: string,
    readonly code?: string,
    readonly status?: number,
    readonly retryAfter?: string | null,
  ) {
    super(message);
  }
}

async function csrf(): Promise<string> {
  const response = await fetch(`${API}/accounts/csrf`, {
    credentials: "include",
    cache: "no-store",
  });
  if (!response.ok)
    throw new Error(
      "Nie udało się przygotować bezpiecznego formularza. Odśwież stronę.",
    );
  const body = (await response.json()) as { csrf_token?: string };
  if (!body.csrf_token)
    throw new Error(
      "Nie udało się przygotować bezpiecznego formularza. Odśwież stronę.",
    );
  return body.csrf_token;
}

async function post(
  path: string,
  data: unknown,
): Promise<Record<string, unknown>> {
  const csrfToken = await csrf();
  const response = await fetch(`${API}${path}`, {
    method: "POST",
    credentials: "include",
    cache: "no-store",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    body: JSON.stringify(data),
  });
  const body = (await response.json().catch(() => ({}))) as {
    error?: { code?: string; message?: string };
  } & Record<string, unknown>;
  if (!response.ok)
    throw new ApiFormError(
      body.error?.message ||
        "Nie udało się wykonać tej operacji. Spróbuj ponownie.",
      body.error?.code,
      response.status,
      response.headers.get("Retry-After"),
    );
  return body;
}

export function AccountBenefits() {
  return (
    <section className="max-w-xl">
      <p className="text-label font-bold tracking-wide text-accent-action">
        TWOJE KONTO
      </p>
      <h1 className="mt-4 font-display text-display text-ink">
        Wszystko w <span className="text-accent-action">jednym miejscu</span>
      </h1>
      <p className="mt-5 max-w-lg text-body text-ink-muted">
        Konto nie jest wymagane do zakupów. Załóż je, aby wygodnie wracać do
        swoich materiałów i zamówień.
      </p>
      <ul className="mt-8 grid gap-4 text-body-small text-ink sm:grid-cols-3 lg:grid-cols-1">
        {["Biblioteka na zawsze", "Vouchery pod ręką", "Historia zamówień"].map(
          (item, index) => (
            <li className="flex items-center gap-3" key={item}>
              <span
                aria-hidden="true"
                className="grid h-11 w-11 shrink-0 place-items-center rounded-pill bg-surface-muted text-accent-action"
              >
                {["▤", "♡", "↺"][index]}
              </span>
              {item}
            </li>
          ),
        )}
      </ul>
    </section>
  );
}

export function AccountAuthPanel({
  nextPath = "/konto",
}: {
  nextPath?: string;
}) {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState("");
  const [loginLinkNotice, setLoginLinkNotice] = useState("");
  const [customer, setCustomer] = useState<Record<string, unknown> | null>(
    null,
  );
  const [sessionChecked, setSessionChecked] = useState(false);
  const [email, setEmail] = useState("");
  const [linkBusy, setLinkBusy] = useState(false);
  useEffect(() => {
    let active = true;
    void fetch(`${API}/accounts/session`, {
      credentials: "include",
      cache: "no-store",
    })
      .then(async (response) => {
        if (!response.ok) return null;
        const body = (await response.json()) as {
          customer?: Record<string, unknown>;
        };
        return body.customer ?? null;
      })
      .catch(() => null)
      .then((value) => {
        if (active) {
          setCustomer(value);
          setSessionChecked(true);
        }
      });
    return () => {
      active = false;
    };
  }, []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setLoginLinkNotice("");
    setFieldErrors({});
    setNotice("");
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "");
    const password = String(form.get("password") ?? "");
    try {
      if (mode === "register") {
        const body = await post("/accounts/register", {
          email,
          password,
          first_name: form.get("first_name"),
          last_name: form.get("last_name"),
        });
        setNotice(
          String(body.verification_message || "Konto zostało utworzone."),
        );
        if (typeof body.customer === "object" && body.customer !== null) {
          setCustomer(body.customer as Record<string, unknown>);
        }
        return;
      } else {
        const body = await post("/accounts/login", {
          email,
          password,
          remember_me: form.get("remember_me") === "on",
        });
        if (typeof body.customer === "object" && body.customer !== null) {
          setCustomer(body.customer as Record<string, unknown>);
        }
        savePurchaseLinkingNotice(body.purchase_linking);
      }
      router.replace(safeReturnPath(nextPath));
      router.refresh();
    } catch (caught) {
      const formError = caught instanceof ApiFormError ? caught : null;
      const fieldByCode: Record<string, string> = {
        INVALID_EMAIL: "email",
        PASSWORD_TOO_SHORT: "password",
        PASSWORD_TOO_LONG: "password",
        PASSWORD_TOO_COMMON: "password",
        PASSWORD_CONFIRMATION_MISMATCH: "password_confirmation",
        NAME_REQUIRED: "first_name",
      };
      const field = formError?.code ? fieldByCode[formError.code] : undefined;
      if (field && formError) setFieldErrors({ [field]: formError.message });
      setError(
        caught instanceof Error ? caught.message : "Nie udało się zalogować.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function logout() {
    setBusy(true);
    setError("");
    try {
      const csrfToken = await csrf();
      const response = await fetch(`${API}/accounts/logout`, {
        method: "POST",
        credentials: "include",
        cache: "no-store",
        headers: { "X-CSRF-Token": csrfToken },
      });
      if (!response.ok) throw new Error("Nie udało się bezpiecznie wylogować.");
      setCustomer(null);
      setNotice("Zostałaś wylogowana.");
      router.refresh();
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Nie udało się wylogować.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function requestLoginLink() {
    setError("");
    setNotice("");
    setLoginLinkNotice("");
    setFieldErrors({});
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setFieldErrors({ email: "Podaj prawidłowy adres e-mail." });
      document.getElementById("login-email")?.focus();
      return;
    }
    setLinkBusy(true);
    try {
      const result = await post("/auth/login-link", {
        email,
        return_to: safeReturnPath(nextPath),
      });
      setLoginLinkNotice(
        String(
          result.message ||
            "Jeśli konto istnieje, wyślemy wiadomość z linkiem do logowania.",
        ),
      );
    } catch (caught) {
      const formError = caught instanceof ApiFormError ? caught : null;
      const retry = formError?.retryAfter
        ? ` Spróbuj ponownie za ${formError.retryAfter} s.`
        : "";
      setError(
        `${caught instanceof Error ? caught.message : "Nie udało się wysłać linku."}${retry}`,
      );
    } finally {
      setLinkBusy(false);
    }
  }
  if (sessionChecked && customer) {
    return (
      <section className="w-full max-w-xl rounded-card border border-border bg-surface p-5 shadow-subtle sm:p-8">
        <p className="text-label font-bold tracking-wide text-accent-action">
          TWOJE KONTO
        </p>
        <h2 className="mt-3 font-display text-heading text-ink">
          Witaj, {String(customer.first_name ?? "")}
        </h2>
        <p className="mt-2 break-words text-body-small text-ink-muted">
          {String(customer.email ?? "")}
        </p>
        {customer.email_verified === false ? (
          <>
            <p className="mt-4 text-body-small text-ink-muted">
              Po potwierdzeniu adresu e-mail zobaczysz tutaj swoje wcześniejsze
              zakupy.
            </p>
            <VerificationReminder onError={setError} onNotice={setNotice} />
          </>
        ) : null}
        <div className="mt-4">
          <PurchaseLinkingNotice />
        </div>
        <div className="mt-6 grid gap-3 sm:grid-cols-2">
          <Link
            className="inline-flex min-h-control-lg items-center justify-center rounded-pill border border-border px-4 py-3 text-label font-bold text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
            href="/konto/zmien-haslo"
          >
            Zmień hasło
          </Link>
          <Button loading={busy} onClick={logout} variant="secondary">
            Wyloguj się
          </Button>
        </div>
        {notice ? (
          <p className="mt-4 text-body-small text-on-success" role="status">
            {notice}
          </p>
        ) : null}
        {error ? (
          <p className="mt-4 text-body-small text-on-danger" role="alert">
            {error}
          </p>
        ) : null}
      </section>
    );
  }
  return (
    <section className="w-full max-w-xl rounded-card border border-border bg-surface p-5 shadow-subtle sm:p-8">
      <div
        aria-label="Wybierz sposób"
        className="grid grid-cols-2 rounded-pill bg-surface-muted p-1"
        role="group"
      >
        {[
          { id: "login", label: "Logowanie" },
          { id: "register", label: "Załóż konto" },
        ].map((tab) => (
          <button
            aria-pressed={mode === tab.id}
            className={`min-h-control-md rounded-pill px-3 font-interface text-label font-bold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action ${mode === tab.id ? "bg-surface text-ink shadow-subtle" : "text-ink-muted"}`}
            key={tab.id}
            onClick={() => {
              setMode(tab.id as "login" | "register");
              setError("");
              setFieldErrors({});
            }}
            type="button"
          >
            {tab.label}
          </button>
        ))}
      </div>
      <form className="mt-7 space-y-5" onSubmit={submit}>
        {mode === "register" ? (
          <div className="grid gap-5 sm:grid-cols-2">
            <TextField
              autoComplete="given-name"
              error={fieldErrors.first_name}
              label="Imię"
              name="first_name"
              required
            />
            <TextField
              autoComplete="family-name"
              error={fieldErrors.last_name}
              label="Nazwisko"
              name="last_name"
              required
            />
          </div>
        ) : null}
        <TextField
          autoComplete="email"
          error={fieldErrors.email}
          id="login-email"
          label="Adres e-mail"
          name="email"
          onChange={(event) => {
            setEmail(event.currentTarget.value);
            setFieldErrors((current) => ({ ...current, email: "" }));
          }}
          value={email}
          required
          type="email"
        />
        <TextField
          autoComplete={mode === "login" ? "current-password" : "new-password"}
          hint={
            mode === "register"
              ? "Co najmniej 10 znaków. Możesz wkleić hasło z menedżera."
              : undefined
          }
          label="Hasło"
          error={fieldErrors.password}
          maxLength={1024}
          minLength={mode === "register" ? 10 : undefined}
          name="password"
          required
          type="password"
        />
        {mode === "login" ? (
          <div className="flex flex-wrap items-center justify-between gap-3 text-caption">
            <label className="flex min-h-control-sm items-center gap-2 text-ink">
              <input
                className="h-4 w-4 accent-accent-action"
                name="remember_me"
                type="checkbox"
              />
              Zapamiętaj mnie
            </label>
            <Link
              className="min-h-control-sm py-2 font-bold text-accent-action underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
              href="/konto/odzyskaj-haslo"
            >
              Nie pamiętam hasła
            </Link>
          </div>
        ) : (
          <PasswordConfirm
            error={fieldErrors.password_confirmation}
            onChange={() =>
              setFieldErrors((current) => ({
                ...current,
                password_confirmation: "",
              }))
            }
          />
        )}
        {error ? (
          <p className="text-body-small text-on-danger" role="alert">
            {error}
          </p>
        ) : null}
        {notice ? (
          <div className="space-y-3" role="status">
            <p className="text-body-small text-on-success">{notice}</p>
            <Link
              className="inline-flex min-h-control-sm items-center font-bold text-accent-action underline"
              href={safeReturnPath(nextPath)}
            >
              Przejdź dalej
            </Link>
          </div>
        ) : null}
        <Button
          className="w-full"
          loading={busy || linkBusy}
          loadingLabel="Trwa wysyłanie formularza"
          size="lg"
          type="submit"
        >
          {mode === "login" ? "Zaloguj się" : "Załóż konto"}
        </Button>
      </form>
      {mode === "login" ? (
        <>
          <div className="my-6 flex items-center gap-4 text-caption font-bold tracking-wide text-ink-muted">
            <span className="h-px flex-1 bg-border" />
            ALBO
            <span className="h-px flex-1 bg-border" />
          </div>
          <button
            className="min-h-control-lg w-full rounded-pill border border-border px-4 py-3 text-label font-bold text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action disabled:cursor-wait disabled:opacity-60"
            disabled={linkBusy || busy}
            onClick={() => void requestLoginLink()}
            type="button"
          >
            {linkBusy ? "Wysyłamy prośbę…" : "Wyślij mi link do logowania"}
          </button>
          <p
            aria-live="polite"
            className="mt-2 text-caption text-ink-muted"
            role="status"
          >
            Jeśli konto istnieje, otrzymasz jednorazowy link ważny przez 15
            minut.
          </p>
          {loginLinkNotice ? (
            <p className="mt-3 text-body-small text-on-success" role="status">
              {loginLinkNotice}
            </p>
          ) : null}
          <div className="mt-6 rounded-card bg-surface-muted p-4 text-body-small">
            <strong>Kupujesz bez konta?</strong>
            <p className="mt-1 text-ink-muted">
              Możesz złożyć zamówienie bez rejestracji. Potwierdzenie adresu
              będzie potrzebne do bezpiecznego powiązania wcześniejszych
              zakupów.
            </p>
            <Link
              className="mt-2 inline-flex min-h-control-sm items-center font-bold text-accent-action underline"
              href="/"
            >
              Wróć do sklepu
            </Link>
          </div>
        </>
      ) : null}
    </section>
  );
}

function VerificationReminder({
  onError,
  onNotice,
}: {
  onError: (value: string) => void;
  onNotice: (value: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  async function resend() {
    setBusy(true);
    onError("");
    try {
      const body = await post("/accounts/email/verification-resend", {});
      onNotice(
        String(
          body.message ??
            "Jeśli potwierdzenie jest potrzebne, zlecono wiadomość.",
        ),
      );
    } catch (caught) {
      onError(
        caught instanceof Error
          ? caught.message
          : "Nie udało się zlecić wiadomości.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="mt-5 rounded-card bg-surface-muted p-4">
      <p className="text-body-small text-ink">
        Potwierdź adres e-mail, aby bezpiecznie powiązać wcześniejsze zakupy.
      </p>
      <Button
        className="mt-3"
        loading={busy}
        onClick={resend}
        variant="secondary"
      >
        Wyślij ponownie
      </Button>
    </div>
  );
}

function PasswordConfirm({
  error,
  onChange,
}: {
  error?: string;
  onChange?: () => void;
}) {
  return (
    <TextField
      autoComplete="new-password"
      error={error}
      label="Powtórz hasło"
      maxLength={1024}
      minLength={10}
      name="password_confirmation"
      onChange={onChange}
      required
      type="password"
    />
  );
}

export function AccountRecoveryForm({
  mode,
}: {
  mode: "request" | "reset" | "verify";
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState("");
  const [token, setToken] = useState("");
  useEffect(() => {
    const fragmentToken =
      new URLSearchParams(window.location.hash.slice(1)).get("token") || "";
    setToken(fragmentToken);
    if (fragmentToken)
      window.history.replaceState(
        null,
        "",
        `${window.location.pathname}${window.location.search}`,
      );
  }, []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setFieldErrors({});
    setNotice("");
    const form = new FormData(event.currentTarget);
    try {
      let body: Record<string, unknown>;
      if (mode === "request")
        body = await post("/accounts/password-reset/request", {
          email: form.get("email"),
        });
      else if (mode === "verify")
        body = await post("/accounts/email/verify", { token });
      else
        body = await post("/accounts/password-reset/confirm", {
          token,
          password: form.get("password"),
          password_confirmation: form.get("password_confirmation"),
        });
      const linked =
        mode === "verify"
          ? purchaseLinkingMessage(body.purchase_linking)
          : null;
      setNotice(
        [String(body.message || "Gotowe."), linked].filter(Boolean).join(" "),
      );
    } catch (caught) {
      const formError = caught instanceof ApiFormError ? caught : null;
      const fieldByCode: Record<string, string> = {
        INVALID_EMAIL: "email",
        PASSWORD_TOO_SHORT: "password",
        PASSWORD_TOO_LONG: "password",
        PASSWORD_TOO_COMMON: "password",
        PASSWORD_CONFIRMATION_MISMATCH: "password_confirmation",
      };
      const field = formError?.code ? fieldByCode[formError.code] : undefined;
      if (field && formError) setFieldErrors({ [field]: formError.message });
      setError(
        caught instanceof Error
          ? caught.message
          : "Nie udało się wykonać tej operacji.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="w-full max-w-xl rounded-card border border-border bg-surface p-5 shadow-subtle sm:p-8">
      <form className="space-y-5" onSubmit={submit}>
        {mode === "request" ? (
          <>
            <h2 className="font-display text-heading text-ink">
              Nie pamiętasz hasła?
            </h2>
            <p className="text-body-small text-ink-muted">
              Wyślemy instrukcję, jeśli konto jest zarejestrowane pod tym
              adresem.
            </p>
            <TextField
              autoComplete="email"
              error={fieldErrors.email}
              label="Adres e-mail"
              name="email"
              onChange={() =>
                setFieldErrors((current) => ({ ...current, email: "" }))
              }
              required
              type="email"
            />
          </>
        ) : null}
        {mode === "reset" ? (
          <>
            <h2 className="font-display text-heading text-ink">
              Ustaw nowe hasło
            </h2>
            {token ? (
              <>
                <TextField
                  autoComplete="new-password"
                  error={fieldErrors.password}
                  hint="Co najmniej 10 znaków."
                  label="Nowe hasło"
                  maxLength={1024}
                  minLength={10}
                  name="password"
                  onChange={() =>
                    setFieldErrors((current) => ({ ...current, password: "" }))
                  }
                  required
                  type="password"
                />
                <TextField
                  autoComplete="new-password"
                  error={fieldErrors.password_confirmation}
                  label="Powtórz nowe hasło"
                  maxLength={1024}
                  minLength={10}
                  name="password_confirmation"
                  onChange={() =>
                    setFieldErrors((current) => ({
                      ...current,
                      password_confirmation: "",
                    }))
                  }
                  required
                  type="password"
                />
              </>
            ) : (
              <p className="text-on-danger" role="alert">
                Link jest nieprawidłowy lub wygasł. Poproś o nową wiadomość.
              </p>
            )}
          </>
        ) : null}
        {mode === "verify" ? (
          <>
            <h2 className="font-display text-heading text-ink">
              Potwierdź adres e-mail
            </h2>
            {token ? (
              <p className="text-body-small text-ink-muted">
                Potwierdzenie pozwoli bezpiecznie powiązać wcześniejsze zakupy.
              </p>
            ) : (
              <p className="text-on-danger" role="alert">
                Link jest nieprawidłowy lub wygasł. Poproś o nową wiadomość.
              </p>
            )}
          </>
        ) : null}
        {error ? (
          <p role="alert" className="text-body-small text-on-danger">
            {error}
          </p>
        ) : null}
        {notice ? (
          <p role="status" className="text-body-small text-on-success">
            {notice}
          </p>
        ) : null}
        {!(mode !== "request" && !token) ? (
          <Button className="w-full" loading={busy} size="lg" type="submit">
            {mode === "request"
              ? "Wyślij instrukcję"
              : mode === "verify"
                ? "Potwierdź e-mail"
                : "Zapisz nowe hasło"}
          </Button>
        ) : null}
        <Link
          className="inline-flex min-h-control-sm items-center font-bold text-accent-action underline"
          href="/konto"
        >
          Wróć do logowania
        </Link>
      </form>
    </section>
  );
}

export function AccountPasswordChange() {
  const [authorized, setAuthorized] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  useEffect(() => {
    let active = true;
    void fetch(`${API}/accounts/session`, {
      credentials: "include",
      cache: "no-store",
    })
      .then((response) => {
        if (active) setAuthorized(response.ok);
      })
      .catch(() => {
        if (active) setAuthorized(false);
      });
    return () => {
      active = false;
    };
  }, []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      const result = await post("/accounts/password/change", {
        current_password: form.get("current_password"),
        password: form.get("password"),
        password_confirmation: form.get("password_confirmation"),
      });
      setNotice(String(result.message ?? "Hasło zostało zmienione."));
      formElement.reset();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Nie udało się zmienić hasła.",
      );
    } finally {
      setBusy(false);
    }
  }
  if (authorized === null) {
    return (
      <p className="text-body-small text-ink-muted" role="status">
        Sprawdzamy sesję…
      </p>
    );
  }
  if (!authorized) {
    return (
      <p className="rounded-card bg-surface p-5 text-body-small text-ink">
        Zaloguj się, aby zmienić hasło.{" "}
        <Link
          className="font-bold text-accent-action underline"
          href="/konto?next=%2Fkonto%2Fzmien-haslo"
        >
          Przejdź do logowania
        </Link>
      </p>
    );
  }
  return (
    <section className="w-full max-w-xl rounded-card border border-border bg-surface p-5 shadow-subtle sm:p-8">
      <form className="space-y-5" onSubmit={submit}>
        <TextField
          autoComplete="current-password"
          label="Bieżące hasło"
          maxLength={1024}
          name="current_password"
          required
          type="password"
        />
        <TextField
          autoComplete="new-password"
          hint="Co najmniej 10 znaków."
          label="Nowe hasło"
          maxLength={1024}
          minLength={10}
          name="password"
          required
          type="password"
        />
        <TextField
          autoComplete="new-password"
          label="Powtórz nowe hasło"
          maxLength={1024}
          minLength={10}
          name="password_confirmation"
          required
          type="password"
        />
        {error ? (
          <p className="text-body-small text-on-danger" role="alert">
            {error}
          </p>
        ) : null}
        {notice ? (
          <p className="text-body-small text-on-success" role="status">
            {notice}
          </p>
        ) : null}
        <Button className="w-full" loading={busy} size="lg" type="submit">
          Zmień hasło
        </Button>
      </form>
    </section>
  );
}

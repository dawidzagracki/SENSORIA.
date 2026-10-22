"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Modal } from "@/components/ui/modal";
import { apiJson } from "@/lib/client-api";

export const COOKIE_NAME = "sensoria_cookie_consent";
export const POLICY_VERSION = "v1";
export const OPEN_EVENT = "sensoria:open-cookie-settings";

export type CookieChoice = {
  v: string;
  subject: string | null;
  analytics: boolean;
  marketing: boolean;
};

export function readChoice(cookieString: string): CookieChoice | null {
  const entry = cookieString
    .split("; ")
    .find((part) => part.startsWith(`${COOKIE_NAME}=`));
  if (!entry) return null;
  try {
    const parsed = JSON.parse(
      decodeURIComponent(entry.slice(COOKIE_NAME.length + 1)),
    ) as Partial<CookieChoice>;
    if (
      parsed.v !== POLICY_VERSION ||
      typeof parsed.analytics !== "boolean" ||
      typeof parsed.marketing !== "boolean"
    )
      return null;
    return {
      v: parsed.v,
      subject: typeof parsed.subject === "string" ? parsed.subject : null,
      analytics: parsed.analytics,
      marketing: parsed.marketing,
    };
  } catch {
    return null;
  }
}

function writeChoice(choice: CookieChoice): void {
  const secure = window.location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${COOKIE_NAME}=${encodeURIComponent(
    JSON.stringify(choice),
  )}; Path=/; Max-Age=${60 * 60 * 24 * 180}; SameSite=Lax${secure}`;
}

/** Banner + settings dialog. Only the strictly necessary cookies are set without consent. */
export function CookieConsent() {
  const [choice, setChoice] = useState<CookieChoice | null>(null);
  const [ready, setReady] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [analytics, setAnalytics] = useState(false);
  const [marketing, setMarketing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    const stored = readChoice(document.cookie);
    setChoice(stored);
    if (stored) {
      setAnalytics(stored.analytics);
      setMarketing(stored.marketing);
    }
    setReady(true);
    const open = () => setSettingsOpen(true);
    window.addEventListener(OPEN_EVENT, open);
    return () => window.removeEventListener(OPEN_EVENT, open);
  }, []);

  const save = useCallback(
    async (next: { analytics: boolean; marketing: boolean }) => {
      setSaving(true);
      let subject = choice?.subject ?? null;
      let recordedOk = true;
      setNotice(null);
      try {
        // The register is evidence of consent; a failed write must not block the visitor.
        const recorded = await apiJson<{ subject_id: string }>(
          "/consents/cookies",
          {
            method: "POST",
            json: {
              ...next,
              policy_version: POLICY_VERSION,
              ...(subject ? { subject_id: subject } : {}),
            },
          },
        );
        subject = recorded.subject_id;
      } catch {
        recordedOk = false;
        // Keep the local choice, but tell the visitor the register was not reached.
        setNotice(
          "Wybór zapisaliśmy w przeglądarce, ale nie udało się go zapisać w rejestrze zgód. Spróbuj ponownie później.",
        );
      }
      const saved: CookieChoice = { v: POLICY_VERSION, subject, ...next };
      writeChoice(saved);
      setChoice(saved);
      setAnalytics(next.analytics);
      setMarketing(next.marketing);
      if (recordedOk) setSettingsOpen(false);
      setSaving(false);
    },
    [choice],
  );

  if (!ready) return null;
  return (
    <>
      {!choice ? (
        <section
          aria-labelledby="cookie-banner-title"
          className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-surface p-4 shadow-overlay"
        >
          <div className="mx-auto flex max-w-page-shell flex-wrap items-center gap-4">
            <div className="min-w-0 flex-1 basis-80">
              <h2
                id="cookie-banner-title"
                className="font-display text-emphasis text-ink"
              >
                Pliki cookies
              </h2>
              <p className="mt-1 text-body-small text-ink-muted">
                Używamy niezbędnych plików cookies (koszyk, logowanie). Narzędzi
                analitycznych ani marketingowych obecnie nie uruchamiamy; jeśli
                to się zmieni, zrobimy to tylko za Twoją zgodą.{" "}
                <a className="underline" href="/polityka-cookies">
                  Polityka cookies
                </a>
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Button
                variant="secondary"
                onClick={() => save({ analytics: false, marketing: false })}
                loading={saving}
              >
                Tylko niezbędne
              </Button>
              <Button variant="secondary" onClick={() => setSettingsOpen(true)}>
                Dostosuj
              </Button>
              <Button
                onClick={() => save({ analytics: true, marketing: true })}
                loading={saving}
              >
                Akceptuję wszystkie
              </Button>
            </div>
          </div>
        </section>
      ) : null}
      <Modal
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        title="Ustawienia cookies"
      >
        <div className="space-y-4">
          <p className="text-body-small">
            Niezbędne pliki cookies są zawsze włączone — bez nich nie działa
            koszyk ani logowanie.
          </p>
          <Checkbox
            label="Analityczne — obecnie nieużywane; zapiszemy Twój wybór na przyszłość."
            name="cookies-analytics"
            checked={analytics}
            onChange={(event) => setAnalytics(event.target.checked)}
          />
          <Checkbox
            label="Marketingowe — obecnie nieużywane; zapiszemy Twój wybór na przyszłość."
            name="cookies-marketing"
            checked={marketing}
            onChange={(event) => setMarketing(event.target.checked)}
          />
          <p className="text-caption text-ink-muted">
            Wybór możesz zmienić w każdej chwili w stopce strony.
          </p>
          {notice ? (
            <p className="text-body-small text-on-danger" role="alert">
              {notice}
            </p>
          ) : null}
          <div className="flex flex-wrap gap-3">
            <Button
              loading={saving}
              onClick={() => save({ analytics, marketing })}
            >
              Zapisz wybór
            </Button>
            <Button
              variant="secondary"
              loading={saving}
              onClick={() => save({ analytics: false, marketing: false })}
            >
              Odrzuć dodatkowe
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
}

"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { apiJson, ClientApiError, formatDate } from "@/lib/client-api";

type Kind = "withdrawal" | "return" | "complaint";
type Overview = {
  order_number: string | null;
  withdrawal_open: boolean;
  withdrawal_until: string;
  cases: Array<{
    number: string;
    kind: Kind;
    status: string;
    created_at: string;
    resolution_note: string | null;
  }>;
};
type AccountOrders = { items: Array<{ id: string; number: string }> };

const kindLabel: Record<Kind, string> = {
  withdrawal: "Odstąpienie od umowy",
  return: "Zwrot towaru",
  complaint: "Reklamacja",
};
const statusLabel: Record<string, string> = {
  new: "Nowe",
  in_progress: "W trakcie",
  resolved: "Rozpatrzone",
  rejected: "Odrzucone",
};

export function SupportCaseForm({
  kinds,
  orderId,
  token,
  nextPath,
}: {
  kinds: Kind[];
  orderId: string | null;
  token: string | null;
  nextPath: string;
}) {
  const [orders, setOrders] = useState<AccountOrders["items"]>([]);
  const [selectedOrder, setSelectedOrder] = useState(orderId ?? "");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [kind, setKind] = useState<Kind>(kinds[0] ?? "complaint");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [messageError, setMessageError] = useState("");
  const [created, setCreated] = useState<string | null>(null);
  const [needsLogin, setNeedsLogin] = useState(false);
  const q = token ? `?order_token=${encodeURIComponent(token)}` : "";

  useEffect(() => {
    if (orderId) return;
    (async () => {
      try {
        const data = await apiJson<AccountOrders>(
          "/accounts/orders?filter=all&page=1&page_size=50",
        );
        setOrders(data.items.map(({ id, number }) => ({ id, number })));
        if (data.items[0]) setSelectedOrder(data.items[0].id);
      } catch (caught) {
        if (caught instanceof ClientApiError && caught.status === 401)
          setNeedsLogin(true);
      }
    })();
  }, [orderId]);

  useEffect(() => {
    if (!selectedOrder) return;
    (async () => {
      try {
        setOverview(
          await apiJson<Overview>(`/support/orders/${selectedOrder}${q}`),
        );
        setError("");
      } catch (caught) {
        setOverview(null);
        setError(
          caught instanceof ClientApiError && caught.status === 404
            ? "Nie znaleziono zamówienia. Użyj linku z wiadomości e-mail."
            : "Nie udało się wczytać zamówienia.",
        );
      }
    })();
  }, [selectedOrder, q, created]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (message.trim().length < 5) {
      setMessageError("Opisz sprawę w co najmniej 5 znakach.");
      return;
    }
    setMessageError("");
    setBusy(true);
    setError("");
    try {
      const result = await apiJson<{ number: string }>(`/support/cases${q}`, {
        method: "POST",
        json: { order_id: selectedOrder, kind, message },
      });
      setCreated(result.number);
      setMessage("");
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Nie udało się wysłać zgłoszenia.",
      );
    } finally {
      setBusy(false);
    }
  }

  const noAccess = !orderId && needsLogin;
  return (
    <section
      aria-labelledby="case-form"
      className="mt-8 rounded-card border border-border bg-surface p-5 sm:p-6"
    >
      <h2 id="case-form" className="font-display text-subtitle text-ink">
        Złóż zgłoszenie
      </h2>
      {noAccess ? (
        <div className="mt-4 space-y-3">
          <Alert variant="info">
            Zgłoszenie dotyczy konkretnego zamówienia. Zaloguj się albo wejdź tu
            z linku w wiadomości e-mail po zakupie.
          </Alert>
          <Link
            className="inline-flex min-h-touch items-center rounded-pill bg-accent-action px-6 text-label font-bold text-surface"
            href={`/konto?next=${encodeURIComponent(nextPath)}`}
          >
            Zaloguj się
          </Link>
        </div>
      ) : (
        <>
          {created ? (
            <div className="mt-4">
              <Alert variant="success" title="Zgłoszenie przyjęte">
                Numer zgłoszenia: <strong>{created}</strong>. Potwierdzenie
                wysłaliśmy e-mailem.
              </Alert>
            </div>
          ) : null}
          {error ? (
            <div className="mt-4">
              <Alert variant="error">{error}</Alert>
            </div>
          ) : null}
          {overview ? (
            <form onSubmit={submit} noValidate className="mt-4 space-y-5">
              {!orderId && orders.length > 1 ? (
                <div>
                  <label className="block text-label" htmlFor="case-order">
                    Zamówienie
                  </label>
                  <select
                    id="case-order"
                    value={selectedOrder}
                    onChange={(e) => setSelectedOrder(e.target.value)}
                    className="mt-2 min-h-touch w-full rounded-control border border-border bg-surface px-3"
                  >
                    {orders.map((o) => (
                      <option key={o.id} value={o.id}>
                        {o.number}
                      </option>
                    ))}
                  </select>
                </div>
              ) : (
                <p className="text-body">
                  Zamówienie: <strong>{overview.order_number}</strong>
                </p>
              )}
              {kinds.length > 1 ? (
                <fieldset>
                  <legend className="text-label">Rodzaj zgłoszenia</legend>
                  <div className="mt-2 flex flex-wrap gap-3">
                    {kinds.map((value) => (
                      <label
                        key={value}
                        className="inline-flex min-h-touch cursor-pointer items-center gap-2 rounded-pill border border-border px-4 has-[:checked]:border-accent-action has-[:checked]:bg-surface-muted"
                      >
                        <input
                          type="radio"
                          name="kind"
                          value={value}
                          checked={kind === value}
                          onChange={() => setKind(value)}
                        />
                        {kindLabel[value]}
                      </label>
                    ))}
                  </div>
                </fieldset>
              ) : null}
              {kind !== "complaint" ? (
                <p className="text-body-small text-ink-muted">
                  {overview.withdrawal_open
                    ? `Termin na odstąpienie biegnie do ${formatDate(overview.withdrawal_until)}.`
                    : "Ustawowy termin na odstąpienie od tego zamówienia już minął."}
                </p>
              ) : null}
              <Textarea
                label="Opis sprawy"
                required
                rows={6}
                maxLength={3000}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                error={messageError}
                hint="Napisz, czego dotyczy zgłoszenie. Nie podawaj haseł ani danych karty."
              />
              <Button type="submit" size="lg" loading={busy}>
                Wyślij zgłoszenie
              </Button>
            </form>
          ) : null}
          {overview && overview.cases.length > 0 ? (
            <div className="mt-8">
              <h3 className="font-display text-emphasis text-ink">
                Twoje zgłoszenia do tego zamówienia
              </h3>
              <ul className="mt-3 space-y-3">
                {overview.cases.map((c) => (
                  <li
                    key={c.number}
                    className="rounded-control border border-border p-4"
                  >
                    <p className="font-bold">
                      {c.number} · {kindLabel[c.kind]} ·{" "}
                      {statusLabel[c.status] ?? c.status}
                    </p>
                    <p className="text-caption text-ink-muted">
                      {formatDate(c.created_at)}
                    </p>
                    {c.resolution_note ? (
                      <p className="mt-2 text-body-small">
                        {c.resolution_note}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}

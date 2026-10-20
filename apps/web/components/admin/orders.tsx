"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { AdminShell } from "@/components/admin/admin-shell";
import {
  Card,
  ErrorBox,
  Field,
  inputClass,
  Loading,
  Pager,
  Table,
} from "@/components/admin/ui";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { adminJson, errorText } from "@/lib/admin-api";
import { formatDateTime, money } from "@/lib/client-api";

type Row = {
  id: string;
  number: string;
  created_at: string;
  status: string;
  fulfillment_status: string;
  email: string;
  amount_due_grosz: number;
  payment_method: string;
  item_count: number;
  requires_shipping: boolean;
};
const STATUS: Record<string, string> = {
  pending_payment: "Czeka na płatność",
  paid: "Opłacone",
  cancelled: "Anulowane",
  expired: "Wygasłe",
};
const FULFILL: Record<string, string> = {
  awaiting_fulfillment: "Do realizacji",
  shipped: "Wysłane",
  delivered: "Dostarczone",
  ready_for_pickup: "Do odbioru",
  picked_up: "Odebrane",
  cancelled: "Anulowane",
};

function List() {
  const [status, setStatus] = useState("");
  const [fulfillment, setFulfillment] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<{ total: number; items: Row[] } | null>(
    null,
  );
  const [error, setError] = useState("");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setStatus(params.get("status") ?? "");
    setFulfillment(params.get("fulfillment") ?? "");
  }, []);

  const load = useCallback(async () => {
    const params = new URLSearchParams({ page: String(page), page_size: "25" });
    if (status) params.set("status", status);
    if (fulfillment) params.set("fulfillment", fulfillment);
    if (q.trim()) params.set("q", q.trim());
    try {
      setError("");
      setData(await adminJson(`/orders?${params}`));
    } catch (e) {
      setError(errorText(e, "Nie udało się wczytać zamówień."));
    }
  }, [page, status, fulfillment, q]);
  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-4">
      <Card>
        <form
          role="search"
          className="grid gap-4 sm:grid-cols-4"
          onSubmit={(e) => {
            e.preventDefault();
            setPage(1);
          }}
        >
          <Field label="Szukaj (numer lub e-mail)">
            <input
              className={inputClass}
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </Field>
          <Field label="Płatność">
            <select
              className={inputClass}
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setPage(1);
              }}
            >
              <option value="">Wszystkie</option>
              {Object.entries(STATUS).map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Realizacja">
            <select
              className={inputClass}
              value={fulfillment}
              onChange={(e) => {
                setFulfillment(e.target.value);
                setPage(1);
              }}
            >
              <option value="">Wszystkie</option>
              {Object.entries(FULFILL).map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </Field>
        </form>
      </Card>
      <ErrorBox message={error} />
      {!data && !error ? <Loading /> : null}
      {data ? (
        <Card>
          <Table
            caption="Zamówienia"
            head={[
              "Numer",
              "Data",
              "Klientka",
              "Kwota",
              "Płatność",
              "Realizacja",
            ]}
          >
            {data.items.map((o) => (
              <tr key={o.id}>
                <td className="px-3 py-3">
                  <Link
                    className="font-bold text-accent-action underline"
                    href={`/admin/zamowienia/${o.id}`}
                  >
                    {o.number}
                  </Link>
                </td>
                <td className="px-3 py-3">{formatDateTime(o.created_at)}</td>
                <td className="px-3 py-3">{o.email}</td>
                <td className="px-3 py-3">{money(o.amount_due_grosz)}</td>
                <td className="px-3 py-3">{STATUS[o.status] ?? o.status}</td>
                <td className="px-3 py-3">
                  {o.requires_shipping
                    ? (FULFILL[o.fulfillment_status] ?? o.fulfillment_status)
                    : "—"}
                </td>
              </tr>
            ))}
          </Table>
          {data.items.length === 0 ? (
            <p className="mt-4 text-ink-muted">
              Brak zamówień dla tych filtrów.
            </p>
          ) : null}
          <Pager
            page={page}
            total={data.total}
            pageSize={25}
            onPage={setPage}
          />
        </Card>
      ) : null}
    </div>
  );
}

export function AdminOrders() {
  return <AdminShell title="Zamówienia">{() => <List />}</AdminShell>;
}

type Detail = Row & {
  invoice_data: Record<string, unknown>;
  shipping_data: Record<string, unknown> | null;
  delivery_point: Record<string, unknown> | null;
  items: Array<{
    id: string;
    name: string | null;
    quantity: number;
    unit_price_grosz: number;
    vat_rate: string;
    is_gift: boolean;
  }>;
  payments: Array<{
    attempt: number;
    status: string;
    method: string;
    amount_grosz: number;
    failure_code: string | null;
    paid_at: string | null;
  }>;
  documents: Array<{ id: string; kind: string; number: string }>;
  shipment: {
    carrier: string;
    tracking_number: string;
    status: string;
    shipped_at: string;
  } | null;
  notes: Array<{
    id: string;
    body: string;
    author: string | null;
    created_at: string;
  }>;
  mails: Array<{
    template: string;
    status: string;
    attempts: number;
    sent_at: string | null;
    last_error: string | null;
  }>;
  has_digital_access: boolean;
};

function DetailView({ id }: { id: string }) {
  const [order, setOrder] = useState<Detail | null>(null);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [note, setNote] = useState("");
  const [carrier, setCarrier] = useState("inpost");
  const [tracking, setTracking] = useState("");
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    try {
      setOrder(await adminJson<Detail>(`/orders/${id}`));
    } catch (e) {
      setError(errorText(e, "Nie udało się wczytać zamówienia."));
    }
  }, [id]);
  useEffect(() => {
    void load();
  }, [load]);

  async function act(
    name: string,
    path: string,
    init?: Parameters<typeof adminJson>[1],
    done = "Zapisano.",
  ) {
    setBusy(name);
    setError("");
    setInfo("");
    try {
      await adminJson(path, { method: "POST", ...init });
      setInfo(done);
      await load();
    } catch (e) {
      setError(errorText(e, "Operacja nie powiodła się."));
    } finally {
      setBusy("");
    }
  }

  async function addNote(event: FormEvent) {
    event.preventDefault();
    if (!note.trim()) return;
    await act(
      "note",
      `/orders/${id}/notes`,
      { json: { body: note } },
      "Notatka dodana.",
    );
    setNote("");
  }

  if (!order) return error ? <ErrorBox message={error} /> : <Loading />;
  const physical = order.requires_shipping;
  const method = (order.shipping_data as { method?: string } | null)?.method;
  const pickup = method === "pickup_in_person";
  return (
    <div className="space-y-4">
      <Link
        href="/admin/zamowienia"
        className="inline-flex min-h-touch items-center text-accent-action underline"
      >
        ← Wszystkie zamówienia
      </Link>
      <ErrorBox message={error} />
      {info ? <Alert variant="success">{info}</Alert> : null}
      <Card title={`Zamówienie ${order.number}`}>
        <dl className="grid gap-3 sm:grid-cols-2">
          <div>
            <dt className="text-caption text-ink-muted">Klientka</dt>
            <dd>{order.email}</dd>
          </div>
          <div>
            <dt className="text-caption text-ink-muted">Data</dt>
            <dd>{formatDateTime(order.created_at)}</dd>
          </div>
          <div>
            <dt className="text-caption text-ink-muted">Płatność</dt>
            <dd>
              {STATUS[order.status] ?? order.status} · {order.payment_method}
            </dd>
          </div>
          <div>
            <dt className="text-caption text-ink-muted">Kwota</dt>
            <dd className="font-bold">{money(order.amount_due_grosz)}</dd>
          </div>
        </dl>
        <div className="mt-4 flex flex-wrap gap-3">
          {order.status === "pending_payment" ? (
            <Button
              variant="secondary"
              loading={busy === "cancel"}
              onClick={() =>
                act(
                  "cancel",
                  `/orders/${id}/cancel`,
                  {},
                  "Zamówienie anulowane.",
                )
              }
            >
              Anuluj zamówienie
            </Button>
          ) : null}
          {order.has_digital_access ? (
            <Button
              variant="secondary"
              loading={busy === "resend"}
              onClick={() =>
                act(
                  "resend",
                  `/orders/${id}/resend-access`,
                  { headers: { "Idempotency-Key": crypto.randomUUID() } },
                  "Wiadomość z dostępem została zakolejkowana.",
                )
              }
            >
              Wyślij ponownie dostęp
            </Button>
          ) : null}
        </div>
      </Card>
      <Card title="Pozycje">
        <Table
          caption="Pozycje zamówienia"
          head={["Produkt", "Ilość", "Cena", "VAT"]}
        >
          {order.items.map((i) => (
            <tr key={i.id}>
              <td className="px-3 py-2">
                {i.name}
                {i.is_gift ? " (prezent)" : ""}
              </td>
              <td className="px-3 py-2">{i.quantity}</td>
              <td className="px-3 py-2">{money(i.unit_price_grosz)}</td>
              <td className="px-3 py-2">{i.vat_rate}</td>
            </tr>
          ))}
        </Table>
      </Card>
      <Card title="Płatności">
        <ul className="space-y-2 text-body-small">
          {order.payments.map((p) => (
            <li key={p.attempt}>
              Próba {p.attempt}: <strong>{p.status}</strong> ·{" "}
              {money(p.amount_grosz)}
              {p.failure_code ? ` · ${p.failure_code}` : ""}
              {p.paid_at ? ` · opłacono ${formatDateTime(p.paid_at)}` : ""}
            </li>
          ))}
          {order.payments.length === 0 ? (
            <li className="text-ink-muted">Brak prób płatności.</li>
          ) : null}
        </ul>
      </Card>
      {physical && order.status === "paid" ? (
        <Card title="Wysyłka">
          {pickup ? <p className="mb-3">Odbiór osobisty w gabinecie.</p> : null}
          {order.shipment ? (
            <p className="mb-3">
              {order.shipment.carrier}:{" "}
              <strong>{order.shipment.tracking_number}</strong> ·{" "}
              {order.shipment.status}
            </p>
          ) : null}
          <div className="flex flex-wrap items-end gap-3">
            {pickup ? (
              <>
                <Button
                  variant="secondary"
                  loading={busy === "ready"}
                  onClick={() =>
                    act(
                      "ready",
                      `/orders/${id}/pickup-ready`,
                      {},
                      "Klientka dostanie powiadomienie o odbiorze.",
                    )
                  }
                >
                  Gotowe do odbioru
                </Button>
                <Button
                  variant="secondary"
                  loading={busy === "picked"}
                  onClick={() => act("picked", `/orders/${id}/picked-up`)}
                >
                  Odebrane
                </Button>
              </>
            ) : !order.shipment ? (
              <>
                <Field label="Przewoźnik">
                  <select
                    className={inputClass}
                    value={carrier}
                    onChange={(e) => setCarrier(e.target.value)}
                  >
                    <option value="inpost">InPost</option>
                  </select>
                </Field>
                <Field label="Numer przesyłki">
                  <input
                    className={inputClass}
                    value={tracking}
                    onChange={(e) => setTracking(e.target.value)}
                  />
                </Field>
                <Button
                  loading={busy === "ship"}
                  onClick={() =>
                    act(
                      "ship",
                      `/orders/${id}/ship`,
                      { json: { carrier, tracking_number: tracking } },
                      "Przesyłka nadana — klientka dostanie powiadomienie.",
                    )
                  }
                >
                  Oznacz jako wysłane
                </Button>
              </>
            ) : order.fulfillment_status === "shipped" ? (
              <Button
                variant="secondary"
                loading={busy === "delivered"}
                onClick={() => act("delivered", `/orders/${id}/delivered`)}
              >
                Oznacz jako dostarczone
              </Button>
            ) : null}
          </div>
        </Card>
      ) : null}
      <Card title="Dokumenty">
        {order.documents.length ? (
          <ul>
            {order.documents.map((d) => (
              <li key={d.id}>
                {d.kind === "invoice" ? "Faktura" : "Paragon"} {d.number}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-ink-muted">
            Brak wystawionych dokumentów (sprawdź dane sprzedawcy w
            ustawieniach).
          </p>
        )}
      </Card>
      <Card title="Wiadomości do klientki">
        <Table
          caption="Wysłane wiadomości"
          head={["Szablon", "Status", "Próby", "Wysłano"]}
        >
          {order.mails.map((m, i) => (
            <tr key={`${m.template}-${i}`}>
              <td className="px-3 py-2">{m.template}</td>
              <td className="px-3 py-2">
                {m.status}
                {m.last_error ? ` (${m.last_error})` : ""}
              </td>
              <td className="px-3 py-2">{m.attempts}</td>
              <td className="px-3 py-2">{formatDateTime(m.sent_at)}</td>
            </tr>
          ))}
        </Table>
      </Card>
      <Card title="Notatki wewnętrzne">
        <ul className="space-y-3">
          {order.notes.map((n) => (
            <li key={n.id} className="rounded-control border border-border p-3">
              <p className="whitespace-pre-line">{n.body}</p>
              <p className="mt-1 text-caption text-ink-muted">
                {n.author ?? "—"} · {formatDateTime(n.created_at)}
              </p>
            </li>
          ))}
        </ul>
        <form onSubmit={addNote} className="mt-4 space-y-3">
          <Field label="Nowa notatka">
            <textarea
              className={`${inputClass} py-2`}
              rows={3}
              maxLength={2000}
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </Field>
          <Button type="submit" loading={busy === "note"}>
            Dodaj notatkę
          </Button>
        </form>
      </Card>
    </div>
  );
}

export function AdminOrderDetail({ id }: { id: string }) {
  return (
    <AdminShell title="Szczegóły zamówienia">
      {() => <DetailView id={id} />}
    </AdminShell>
  );
}

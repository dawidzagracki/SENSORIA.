"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
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
import { formatDate, formatDateTime, money } from "@/lib/client-api";

/* ------------------------------ customers ------------------------------ */
type Customer = {
  email: string;
  name: string | null;
  has_account: boolean;
  orders_count: number;
  paid_total_grosz: number;
  last_order_at: string | null;
  account_created_at: string | null;
  last_login_at: string | null;
};
type CustomerDetail = {
  email: string;
  name: string | null;
  phone: string | null;
  has_account: boolean;
  email_verified: boolean;
  account_created_at: string | null;
  last_login_at: string | null;
  orders_count: number;
  paid_total_grosz: number;
  orders: Array<{
    id: string;
    number: string;
    status: string;
    amount_due_grosz: number;
    created_at: string;
  }>;
};

function Customers() {
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<{ total: number; items: Customer[] } | null>(
    null,
  );
  const [detail, setDetail] = useState<CustomerDetail | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try {
      setError("");
      const p = new URLSearchParams({ page: String(page), page_size: "25" });
      if (q.trim()) p.set("q", q.trim());
      setData(await adminJson(`/customers?${p}`));
    } catch (e) {
      setError(errorText(e, "Nie udało się wczytać klientów."));
    }
  }, [page, q]);
  useEffect(() => {
    void load();
  }, [load]);
  return (
    <div className="space-y-4">
      <Card>
        <p className="mb-3 text-body-small text-ink-muted">
          Klientem jest każda osoba, która kupiła w sklepie — także bez konta.
        </p>
        <form
          role="search"
          onSubmit={(e) => {
            e.preventDefault();
            setPage(1);
          }}
          className="max-w-md"
        >
          <Field label="Szukaj (e-mail, imię, nazwisko)">
            <input
              className={inputClass}
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </Field>
        </form>
      </Card>
      <ErrorBox message={error} />
      {!data && !error ? <Loading /> : null}
      {data ? (
        <Card>
          <Table
            caption="Klienci"
            head={[
              "E-mail",
              "Imię i nazwisko",
              "Konto",
              "Zamówienia",
              "Wydano",
              "Ostatni zakup",
              "",
            ]}
          >
            {data.items.map((c) => (
              <tr key={c.email}>
                <td className="px-3 py-2">{c.email}</td>
                <td className="px-3 py-2">{c.name ?? "—"}</td>
                <td className="px-3 py-2">
                  {c.has_account ? "Z kontem" : "Gość"}
                </td>
                <td className="px-3 py-2">{c.orders_count}</td>
                <td className="px-3 py-2">{money(c.paid_total_grosz)}</td>
                <td className="px-3 py-2">{formatDate(c.last_order_at)}</td>
                <td className="px-3 py-2">
                  <button
                    type="button"
                    className="min-h-touch text-accent-action underline"
                    onClick={async () =>
                      setDetail(
                        await adminJson<CustomerDetail>(
                          `/customers/detail?email=${encodeURIComponent(c.email)}`,
                        ),
                      )
                    }
                  >
                    Szczegóły
                  </button>
                </td>
              </tr>
            ))}
          </Table>
          <Pager
            page={page}
            total={data.total}
            pageSize={25}
            onPage={setPage}
          />
        </Card>
      ) : null}
      {detail ? (
        <Card title={detail.name ?? detail.email}>
          <p>
            {detail.email}
            {detail.phone ? ` · ${detail.phone}` : ""}
          </p>
          <p className="mt-1 text-body-small text-ink-muted">
            {detail.has_account
              ? `Konto od ${formatDate(detail.account_created_at)}${detail.email_verified ? "" : " (e-mail niepotwierdzony)"} · ostatnie logowanie: ${formatDateTime(detail.last_login_at)}`
              : "Klient bez konta (zakupy jako gość)."}
          </p>
          <p className="mt-1 text-body-small text-ink-muted">
            Zamówień: {detail.orders_count} · suma opłaconych:{" "}
            {money(detail.paid_total_grosz)}
          </p>
          <ul className="mt-3 space-y-1 text-body-small">
            {detail.orders.map((o) => (
              <li key={o.id}>
                <Link
                  className="text-accent-action underline"
                  href={`/admin/zamowienia/${o.id}`}
                >
                  {o.number}
                </Link>{" "}
                · {o.status} · {money(o.amount_due_grosz)} ·{" "}
                {formatDate(o.created_at)}
              </li>
            ))}
          </ul>
          <p className="mt-3 text-caption text-ink-muted">
            Wyświetlenie tych danych zostało zapisane w dzienniku.
          </p>
        </Card>
      ) : null}
    </div>
  );
}
export function AdminCustomers() {
  return <AdminShell title="Klienci">{() => <Customers />}</AdminShell>;
}

/* ------------------------------- reviews ------------------------------- */
type Review = {
  id: string;
  product: string;
  author: string;
  rating: number;
  title: string | null;
  body: string;
  status: string;
  created_at: string;
  moderation_note: string | null;
};
function Reviews() {
  const [status, setStatus] = useState("pending");
  const [data, setData] = useState<{ total: number; items: Review[] } | null>(
    null,
  );
  const [error, setError] = useState("");
  const [note, setNote] = useState<Record<string, string>>({});
  const load = useCallback(async () => {
    try {
      setError("");
      setData(await adminJson(`/reviews?status=${status}&page_size=50`));
    } catch (e) {
      setError(errorText(e, "Nie udało się wczytać opinii."));
    }
  }, [status]);
  useEffect(() => {
    void load();
  }, [load]);
  async function decide(id: string, approve: boolean) {
    try {
      await adminJson(`/reviews/${id}/decision`, {
        method: "POST",
        json: { approve, note: note[id] || null },
      });
      await load();
    } catch (e) {
      setError(errorText(e, "Nie udało się zapisać decyzji."));
    }
  }
  return (
    <div className="space-y-4">
      <div role="tablist" aria-label="Status opinii" className="flex gap-2">
        {(
          [
            ["pending", "Do moderacji"],
            ["approved", "Opublikowane"],
            ["rejected", "Odrzucone"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            role="tab"
            aria-selected={status === id}
            type="button"
            onClick={() => setStatus(id)}
            className={`min-h-touch rounded-pill border px-4 ${status === id ? "border-ink bg-ink text-surface" : "border-border"}`}
          >
            {label}
          </button>
        ))}
      </div>
      <ErrorBox message={error} />
      {!data && !error ? <Loading /> : null}
      <ul className="space-y-3">
        {data?.items.map((r) => (
          <li
            key={r.id}
            className="rounded-card border border-border bg-surface p-5"
          >
            <p className="font-bold">
              {r.product} · {"★".repeat(r.rating)}
              <span className="sr-only"> {r.rating} z 5</span>
            </p>
            {r.title ? <p className="font-bold">{r.title}</p> : null}
            <p className="mt-1 whitespace-pre-line">{r.body}</p>
            <p className="mt-2 text-caption text-ink-muted">
              {r.author} · {formatDateTime(r.created_at)}
              {r.moderation_note ? ` · ${r.moderation_note}` : ""}
            </p>
            <div className="mt-3 flex flex-wrap items-end gap-3">
              <Field label="Notatka moderatora (opcjonalnie)">
                <input
                  className={inputClass}
                  value={note[r.id] ?? ""}
                  onChange={(e) => setNote({ ...note, [r.id]: e.target.value })}
                />
              </Field>
              {r.status !== "approved" ? (
                <Button size="sm" onClick={() => decide(r.id, true)}>
                  Opublikuj
                </Button>
              ) : null}
              {r.status !== "rejected" ? (
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => decide(r.id, false)}
                >
                  Odrzuć
                </Button>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
      {data && data.items.length === 0 ? (
        <p className="text-ink-muted">Brak opinii w tym widoku.</p>
      ) : null}
    </div>
  );
}
export function AdminReviews() {
  return <AdminShell title="Moderacja opinii">{() => <Reviews />}</AdminShell>;
}

/* ----------------------------- support cases ---------------------------- */
type Case = {
  id: string;
  number: string;
  kind: string;
  status: string;
  email: string;
  order_number: string | null;
  message: string;
  resolution_note: string | null;
  created_at: string;
};
const KIND: Record<string, string> = {
  withdrawal: "Odstąpienie",
  return: "Zwrot",
  complaint: "Reklamacja",
};
function Cases() {
  const [status, setStatus] = useState("new");
  const [data, setData] = useState<{ total: number; items: Case[] } | null>(
    null,
  );
  const [error, setError] = useState("");
  const [note, setNote] = useState<Record<string, string>>({});
  const load = useCallback(async () => {
    try {
      setError("");
      setData(await adminJson(`/support-cases?status=${status}&page_size=50`));
    } catch (e) {
      setError(errorText(e, "Nie udało się wczytać zgłoszeń."));
    }
  }, [status]);
  useEffect(() => {
    void load();
  }, [load]);
  async function update(id: string, next: string) {
    try {
      await adminJson(`/support-cases/${id}`, {
        method: "PATCH",
        json: { status: next, resolution_note: note[id] || null },
      });
      await load();
    } catch (e) {
      setError(errorText(e, "Nie udało się zapisać."));
    }
  }
  return (
    <div className="space-y-4">
      <div
        role="tablist"
        aria-label="Status zgłoszeń"
        className="flex flex-wrap gap-2"
      >
        {(
          [
            ["new", "Nowe"],
            ["in_progress", "W trakcie"],
            ["resolved", "Rozpatrzone"],
            ["rejected", "Odrzucone"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            role="tab"
            aria-selected={status === id}
            type="button"
            onClick={() => setStatus(id)}
            className={`min-h-touch rounded-pill border px-4 ${status === id ? "border-ink bg-ink text-surface" : "border-border"}`}
          >
            {label}
          </button>
        ))}
      </div>
      <ErrorBox message={error} />
      {!data && !error ? <Loading /> : null}
      <ul className="space-y-3">
        {data?.items.map((c) => (
          <li
            key={c.id}
            className="rounded-card border border-border bg-surface p-5"
          >
            <p className="font-bold">
              {c.number} · {KIND[c.kind] ?? c.kind} · {c.order_number}
            </p>
            <p className="text-caption text-ink-muted">
              {c.email} · {formatDateTime(c.created_at)}
            </p>
            <p className="mt-2 whitespace-pre-line">{c.message}</p>
            {c.resolution_note ? (
              <p className="mt-2 rounded-control bg-surface-muted p-3 text-body-small">
                Decyzja: {c.resolution_note}
              </p>
            ) : null}
            {c.status === "new" || c.status === "in_progress" ? (
              <div className="mt-3 flex flex-wrap items-end gap-3">
                <Field label="Uzasadnienie decyzji">
                  <input
                    className={inputClass}
                    value={note[c.id] ?? ""}
                    onChange={(e) =>
                      setNote({ ...note, [c.id]: e.target.value })
                    }
                  />
                </Field>
                {c.status === "new" ? (
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => update(c.id, "in_progress")}
                  >
                    Przyjmij do realizacji
                  </Button>
                ) : null}
                <Button
                  size="sm"
                  disabled={!(note[c.id] ?? "").trim()}
                  onClick={() => update(c.id, "resolved")}
                >
                  Rozpatrz pozytywnie
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={!(note[c.id] ?? "").trim()}
                  onClick={() => update(c.id, "rejected")}
                >
                  Odrzuć
                </Button>
              </div>
            ) : null}
          </li>
        ))}
      </ul>
      {data && data.items.length === 0 ? (
        <p className="text-ink-muted">Brak zgłoszeń w tym widoku.</p>
      ) : null}
    </div>
  );
}
export function AdminCases() {
  return <AdminShell title="Zgłoszenia klientek">{() => <Cases />}</AdminShell>;
}

/* ------------------------------ discount codes ------------------------------ */
type Discount = {
  id: string;
  code: string;
  type: string;
  value: number;
  min_order_value: number;
  max_uses: number | null;
  used_count: number;
  is_active: boolean;
  valid_from: string | null;
  valid_to: string | null;
};
function Discounts() {
  const [data, setData] = useState<{ items: Discount[] } | null>(null);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [form, setForm] = useState({
    code: "",
    type: "percentage",
    value: "10",
    min_order_value: "0",
    max_uses: "",
  });
  const load = useCallback(async () => {
    try {
      setData(await adminJson("/discount-codes?page_size=100"));
    } catch (e) {
      setError(errorText(e, "Nie udało się wczytać kodów."));
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);
  async function create() {
    setError("");
    setInfo("");
    try {
      await adminJson("/discount-codes", {
        method: "POST",
        json: {
          code: form.code.trim(),
          type: form.type,
          value:
            form.type === "percentage"
              ? Number(form.value)
              : Math.round(Number(form.value.replace(",", ".")) * 100),
          min_order_value: Math.round(
            Number(form.min_order_value.replace(",", ".")) * 100,
          ),
          max_uses: form.max_uses ? Number(form.max_uses) : null,
        },
      });
      setInfo("Kod został utworzony.");
      setForm({ ...form, code: "" });
      await load();
    } catch (e) {
      setError(errorText(e, "Nie udało się utworzyć kodu."));
    }
  }
  async function toggle(d: Discount) {
    try {
      await adminJson(`/discount-codes/${d.id}`, {
        method: "PATCH",
        json: { is_active: !d.is_active },
      });
      await load();
    } catch (e) {
      setError(errorText(e, "Nie udało się zmienić kodu."));
    }
  }
  return (
    <div className="space-y-4">
      <ErrorBox message={error} />
      {info ? <Alert variant="success">{info}</Alert> : null}
      <Card title="Nowy kod rabatowy">
        <form
          className="grid gap-4 md:grid-cols-3"
          onSubmit={(e) => {
            e.preventDefault();
            void create();
          }}
        >
          <Field label="Kod">
            <input
              className={inputClass}
              required
              minLength={3}
              value={form.code}
              onChange={(e) => setForm({ ...form, code: e.target.value })}
            />
          </Field>
          <Field label="Rodzaj">
            <select
              className={inputClass}
              value={form.type}
              onChange={(e) => setForm({ ...form, type: e.target.value })}
            >
              <option value="percentage">Procentowy</option>
              <option value="fixed_amount">Kwotowy (zł)</option>
            </select>
          </Field>
          <Field
            label={form.type === "percentage" ? "Wartość (%)" : "Wartość (zł)"}
          >
            <input
              className={inputClass}
              required
              value={form.value}
              onChange={(e) => setForm({ ...form, value: e.target.value })}
            />
          </Field>
          <Field label="Minimalna wartość zamówienia (zł)">
            <input
              className={inputClass}
              value={form.min_order_value}
              onChange={(e) =>
                setForm({ ...form, min_order_value: e.target.value })
              }
            />
          </Field>
          <Field label="Limit użyć (puste = bez limitu)">
            <input
              className={inputClass}
              inputMode="numeric"
              value={form.max_uses}
              onChange={(e) => setForm({ ...form, max_uses: e.target.value })}
            />
          </Field>
          <div className="flex items-end">
            <Button type="submit">Utwórz kod</Button>
          </div>
        </form>
      </Card>
      {!data ? (
        <Loading />
      ) : (
        <Card title="Kody">
          <Table
            caption="Kody rabatowe"
            head={["Kod", "Rabat", "Min. zamówienie", "Użycia", "Aktywny", ""]}
          >
            {data.items.map((d) => (
              <tr key={d.id}>
                <td className="px-3 py-2 font-bold">{d.code}</td>
                <td className="px-3 py-2">
                  {d.type === "percentage" ? `${d.value}%` : money(d.value)}
                </td>
                <td className="px-3 py-2">{money(d.min_order_value)}</td>
                <td className="px-3 py-2">
                  {d.used_count}
                  {d.max_uses ? ` / ${d.max_uses}` : ""}
                </td>
                <td className="px-3 py-2">{d.is_active ? "Tak" : "Nie"}</td>
                <td className="px-3 py-2">
                  <button
                    type="button"
                    className="min-h-touch text-accent-action underline"
                    onClick={() => toggle(d)}
                  >
                    {d.is_active ? "Wyłącz" : "Włącz"}
                  </button>
                </td>
              </tr>
            ))}
          </Table>
        </Card>
      )}
    </div>
  );
}
export function AdminDiscounts() {
  return (
    <AdminShell title="Kody rabatowe">
      {(a) =>
        a.role === "owner" ? (
          <Discounts />
        ) : (
          <Alert variant="warning">
            Ta sekcja jest dostępna dla właścicielki.
          </Alert>
        )
      }
    </AdminShell>
  );
}

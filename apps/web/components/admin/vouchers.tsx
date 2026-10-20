"use client";

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
import { formatDate, formatDateTime } from "@/lib/client-api";

type Voucher = {
  id: string;
  code: string;
  service_name: string | null;
  status: string;
  issued_at: string;
  valid_until: string;
  redeemed_at: string | null;
  redeemed_by: string | null;
  buyer_email: string;
  order_number: string | null;
  recipient_name: string | null;
  recipient_email: string | null;
  is_gift: boolean;
  events?: Array<{
    action: string;
    occurred_at: string;
    performed_by: string | null;
    note: string | null;
    new_valid_until: string | null;
  }>;
};
type Ledger = {
  total: number;
  items: Array<{
    id: string;
    code: string;
    action: string;
    performed_by: string | null;
    occurred_at: string;
    note: string | null;
    new_valid_until: string | null;
  }>;
};
type Requests = {
  items: Array<{
    id: string;
    code: string;
    message: string;
    created_at: string;
  }>;
};

const STATUS: Record<string, string> = {
  active: "Aktywny",
  expiring_soon: "Wkrótce wygasa",
  redeemed: "Zrealizowany",
  expired: "Wygasły",
  cancelled: "Anulowany",
  scheduled: "Prezent oczekuje",
};
const ACTION: Record<string, string> = {
  redeemed: "Realizacja",
  redemption_reverted: "Cofnięcie realizacji",
  cancelled: "Anulowanie",
  extended: "Przedłużenie",
};

function Detail({
  id,
  role,
  onChanged,
}: {
  id: string;
  role: string;
  onChanged: () => void;
}) {
  const [v, setV] = useState<Voucher | null>(null);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [who, setWho] = useState("");
  const [reason, setReason] = useState("");
  const [day, setDay] = useState("");
  const [busy, setBusy] = useState("");
  const load = useCallback(async () => {
    try {
      setV(await adminJson<Voucher>(`/vouchers/${id}`));
    } catch (e) {
      setError(errorText(e, "Nie udało się wczytać vouchera."));
    }
  }, [id]);
  useEffect(() => {
    void load();
  }, [load]);

  async function act(name: string, path: string, json: unknown, done: string) {
    setBusy(name);
    setError("");
    setInfo("");
    try {
      await adminJson(path, { method: "POST", json });
      setInfo(done);
      await load();
      onChanged();
    } catch (e) {
      setError(errorText(e, "Operacja nie powiodła się."));
    } finally {
      setBusy("");
    }
  }

  if (!v) return error ? <ErrorBox message={error} /> : <Loading />;
  const open = v.status === "active" || v.status === "expiring_soon";
  return (
    <Card title={`Voucher ${v.code}`}>
      <ErrorBox message={error} />
      {info ? <Alert variant="success">{info}</Alert> : null}
      <dl className="mt-3 grid gap-3 sm:grid-cols-2">
        <div>
          <dt className="text-caption text-ink-muted">Usługa</dt>
          <dd>{v.service_name}</dd>
        </div>
        <div>
          <dt className="text-caption text-ink-muted">Status</dt>
          <dd className="font-bold">{STATUS[v.status] ?? v.status}</dd>
        </div>
        <div>
          <dt className="text-caption text-ink-muted">Ważny do</dt>
          <dd>{formatDate(v.valid_until)}</dd>
        </div>
        <div>
          <dt className="text-caption text-ink-muted">Kupujący</dt>
          <dd>
            {v.buyer_email} · {v.order_number}
          </dd>
        </div>
        {v.is_gift ? (
          <div>
            <dt className="text-caption text-ink-muted">Obdarowana</dt>
            <dd>
              {v.recipient_name} {v.recipient_email}
            </dd>
          </div>
        ) : null}
        {v.redeemed_at ? (
          <div>
            <dt className="text-caption text-ink-muted">Zrealizowano</dt>
            <dd>
              {formatDateTime(v.redeemed_at)} · {v.redeemed_by}
            </dd>
          </div>
        ) : null}
      </dl>
      {open ? (
        <form
          className="mt-5 flex flex-wrap items-end gap-3"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            void act(
              "redeem",
              `/vouchers/${id}/redeem`,
              { performed_by: who },
              "Voucher zrealizowany.",
            );
          }}
        >
          <Field label="Osoba realizująca wizytę">
            <input
              className={inputClass}
              required
              minLength={2}
              value={who}
              onChange={(e) => setWho(e.target.value)}
            />
          </Field>
          <Button type="submit" loading={busy === "redeem"}>
            Zrealizuj voucher
          </Button>
        </form>
      ) : null}
      {v.status !== "redeemed" && v.status !== "cancelled" ? (
        <form
          className="mt-5 flex flex-wrap items-end gap-3"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            void act(
              "extend",
              `/vouchers/${id}/extend`,
              { new_last_day: day, reason },
              "Ważność przedłużona; PDF zostanie wygenerowany ponownie.",
            );
          }}
        >
          <Field label="Nowy ostatni dzień ważności">
            <input
              type="date"
              className={inputClass}
              required
              value={day}
              onChange={(e) => setDay(e.target.value)}
            />
          </Field>
          <Field label="Powód">
            <input
              className={inputClass}
              required
              minLength={3}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </Field>
          <Button type="submit" variant="secondary" loading={busy === "extend"}>
            Przedłuż
          </Button>
        </form>
      ) : null}
      {role === "owner" &&
      (v.status === "redeemed" || v.status !== "cancelled") ? (
        <div className="mt-5 flex flex-wrap items-end gap-3 border-t border-border pt-4">
          <Field label="Powód (cofnięcie lub anulowanie)">
            <input
              className={inputClass}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </Field>
          {v.status === "redeemed" ? (
            <Button
              variant="secondary"
              loading={busy === "revert"}
              onClick={() =>
                act(
                  "revert",
                  `/vouchers/${id}/revert-redemption`,
                  { reason },
                  "Realizacja cofnięta.",
                )
              }
            >
              Cofnij realizację
            </Button>
          ) : null}
          {v.status !== "cancelled" && v.status !== "redeemed" ? (
            <Button
              variant="secondary"
              loading={busy === "cancel"}
              onClick={() =>
                act(
                  "cancel",
                  `/vouchers/${id}/cancel`,
                  { reason },
                  "Voucher anulowany.",
                )
              }
            >
              Anuluj voucher
            </Button>
          ) : null}
        </div>
      ) : null}
      <h3 className="mt-6 font-display text-emphasis">Historia</h3>
      <ul className="mt-2 space-y-2 text-body-small">
        {(v.events ?? []).map((ev, i) => (
          <li key={`${ev.action}-${i}`}>
            {formatDateTime(ev.occurred_at)} —{" "}
            <strong>{ACTION[ev.action] ?? ev.action}</strong>
            {ev.performed_by ? ` · ${ev.performed_by}` : ""}
            {ev.new_valid_until
              ? ` · do ${formatDate(ev.new_valid_until)}`
              : ""}
            {ev.note ? ` · ${ev.note}` : ""}
          </li>
        ))}
        {(v.events ?? []).length === 0 ? (
          <li className="text-ink-muted">Brak zdarzeń.</li>
        ) : null}
      </ul>
    </Card>
  );
}

function Search({ role }: { role: string }) {
  const [tab, setTab] = useState<"search" | "ledger" | "requests">("search");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<{ total: number; items: Voucher[] } | null>(
    null,
  );
  const [ledger, setLedger] = useState<Ledger | null>(null);
  const [requests, setRequests] = useState<Requests | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [decisionDay, setDecisionDay] = useState("");

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("tab") === "requests")
      setTab("requests");
  }, []);

  const load = useCallback(async () => {
    try {
      setError("");
      if (tab === "search") {
        const params = new URLSearchParams({
          page: String(page),
          page_size: "20",
        });
        if (q.trim()) params.set("q", q.trim());
        setData(await adminJson(`/vouchers?${params}`));
      } else if (tab === "ledger") {
        setLedger(await adminJson(`/vouchers/events?page_size=100`));
      } else {
        setRequests(await adminJson(`/vouchers/extension-requests`));
      }
    } catch (e) {
      setError(errorText(e, "Nie udało się wczytać danych."));
    }
  }, [tab, page, q]);
  useEffect(() => {
    void load();
  }, [load]);

  async function decide(id: string, approve: boolean) {
    try {
      await adminJson(`/vouchers/extension-requests/${id}/decision`, {
        method: "POST",
        json: {
          approve,
          new_last_day: approve ? decisionDay : null,
          note: approve ? "Zatwierdzono" : "Odrzucono",
        },
      });
      await load();
    } catch (e) {
      setError(errorText(e, "Nie udało się zapisać decyzji."));
    }
  }

  return (
    <div className="space-y-4">
      <div role="tablist" aria-label="Widok" className="flex gap-2">
        {(
          [
            ["search", "Wyszukiwanie"],
            ["ledger", "Rejestr realizacji"],
            ["requests", "Prośby o przedłużenie"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            role="tab"
            aria-selected={tab === id}
            type="button"
            onClick={() => setTab(id)}
            className={`min-h-touch rounded-pill border px-4 ${tab === id ? "border-ink bg-ink text-surface" : "border-border"}`}
          >
            {label}
          </button>
        ))}
      </div>
      <ErrorBox message={error} />
      {tab === "search" ? (
        <>
          <Card>
            <form
              role="search"
              onSubmit={(e) => {
                e.preventDefault();
                setPage(1);
                void load();
              }}
              className="flex flex-wrap items-end gap-3"
            >
              <Field label="Kod, e-mail, imię lub numer zamówienia">
                <input
                  className={inputClass}
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                />
              </Field>
              <Button type="submit">Szukaj</Button>
            </form>
          </Card>
          {!data ? (
            <Loading />
          ) : (
            <Card>
              <Table
                caption="Vouchery"
                head={["Kod", "Usługa", "Status", "Ważny do", "Kupujący", ""]}
              >
                {data.items.map((v) => (
                  <tr key={v.id}>
                    <td className="px-3 py-2 font-bold">{v.code}</td>
                    <td className="px-3 py-2">{v.service_name}</td>
                    <td className="px-3 py-2">
                      {STATUS[v.status] ?? v.status}
                    </td>
                    <td className="px-3 py-2">{formatDate(v.valid_until)}</td>
                    <td className="px-3 py-2">{v.buyer_email}</td>
                    <td className="px-3 py-2">
                      <button
                        type="button"
                        className="min-h-touch text-accent-action underline"
                        onClick={() => setSelected(v.id)}
                      >
                        Otwórz
                      </button>
                    </td>
                  </tr>
                ))}
              </Table>
              {data.items.length === 0 ? (
                <p className="mt-4 text-ink-muted">Nie znaleziono voucherów.</p>
              ) : null}
              <Pager
                page={page}
                total={data.total}
                pageSize={20}
                onPage={setPage}
              />
            </Card>
          )}
          {selected ? (
            <Detail id={selected} role={role} onChanged={() => void load()} />
          ) : null}
        </>
      ) : null}
      {tab === "ledger" ? (
        !ledger ? (
          <Loading />
        ) : (
          <Card title="Rejestr zdarzeń voucherów">
            <Table
              caption="Rejestr"
              head={["Data", "Kod", "Zdarzenie", "Osoba", "Uwagi"]}
            >
              {ledger.items.map((e) => (
                <tr key={e.id}>
                  <td className="px-3 py-2">{formatDateTime(e.occurred_at)}</td>
                  <td className="px-3 py-2 font-bold">{e.code}</td>
                  <td className="px-3 py-2">{ACTION[e.action] ?? e.action}</td>
                  <td className="px-3 py-2">{e.performed_by ?? "—"}</td>
                  <td className="px-3 py-2">
                    {e.note ?? ""}
                    {e.new_valid_until
                      ? ` (do ${formatDate(e.new_valid_until)})`
                      : ""}
                  </td>
                </tr>
              ))}
            </Table>
          </Card>
        )
      ) : null}
      {tab === "requests" ? (
        !requests ? (
          <Loading />
        ) : (
          <Card title="Oczekujące prośby">
            <Field label="Nowy ostatni dzień ważności (przy zatwierdzeniu)">
              <input
                type="date"
                className={inputClass}
                value={decisionDay}
                onChange={(e) => setDecisionDay(e.target.value)}
              />
            </Field>
            <ul className="mt-4 space-y-3">
              {requests.items.map((r) => (
                <li
                  key={r.id}
                  className="rounded-control border border-border p-4"
                >
                  <p className="font-bold">
                    {r.code} · {formatDateTime(r.created_at)}
                  </p>
                  <p className="mt-1 whitespace-pre-line text-body-small">
                    {r.message || "(bez wiadomości)"}
                  </p>
                  <div className="mt-3 flex gap-3">
                    <Button
                      size="sm"
                      disabled={!decisionDay}
                      onClick={() => decide(r.id, true)}
                    >
                      Zatwierdź
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => decide(r.id, false)}
                    >
                      Odrzuć
                    </Button>
                  </div>
                </li>
              ))}
              {requests.items.length === 0 ? (
                <li className="text-ink-muted">Brak oczekujących próśb.</li>
              ) : null}
            </ul>
          </Card>
        )
      ) : null}
    </div>
  );
}

export function AdminVouchers() {
  return (
    <AdminShell title="Vouchery">
      {(admin) => <Search role={admin.role} />}
    </AdminShell>
  );
}

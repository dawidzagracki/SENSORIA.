"use client";

import { useCallback, useEffect, useState } from "react";
import { AdminShell } from "@/components/admin/admin-shell";
import {
  Card,
  ErrorBox,
  Field,
  inputClass,
  Loading,
} from "@/components/admin/ui";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { adminJson, errorText } from "@/lib/admin-api";

type Item = {
  key: string;
  label: string;
  value: Record<string, unknown> | null;
};
const str = (value: unknown) => (typeof value === "string" ? value : "");
const zl = (value: unknown) =>
  typeof value === "number" ? (value / 100).toFixed(2).replace(".", ",") : "";
const grosz = (value: string) =>
  Math.round(Number(value.replace(",", ".")) * 100);

function useSaver(onSaved: () => void) {
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [busy, setBusy] = useState(false);
  async function save(key: string, value: Record<string, unknown>) {
    setBusy(true);
    setError("");
    setInfo("");
    try {
      await adminJson(`/settings/${key}`, { method: "PUT", json: { value } });
      setInfo("Zapisano.");
      onSaved();
    } catch (e) {
      setError(errorText(e, "Nie udało się zapisać ustawienia."));
    } finally {
      setBusy(false);
    }
  }
  return { error, info, busy, save };
}

function Status({ error, info }: { error: string; info: string }) {
  return (
    <>
      <ErrorBox message={error} />
      {info ? <Alert variant="success">{info}</Alert> : null}
    </>
  );
}

function Seller({ item, reload }: { item: Item; reload: () => void }) {
  const v = item.value ?? {};
  const [f, setF] = useState({
    name: str(v.name),
    street: str(v.street),
    postal_code: str(v.postal_code),
    city: str(v.city),
    nip: str(v.nip),
    vat_exempt_note: str(v.vat_exempt_note),
  });
  const { error, info, busy, save } = useSaver(reload);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setF({ ...f, [k]: e.target.value });
  return (
    <Card title="Dane sprzedawcy (paragony i faktury)">
      <Status error={error} info={info} />
      <form
        className="mt-3 grid gap-4 md:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault();
          void save(item.key, {
            ...f,
            nip: f.nip || null,
            vat_exempt_note: f.vat_exempt_note || null,
          });
        }}
      >
        <Field label="Nazwa firmy">
          <input
            className={inputClass}
            required
            value={f.name}
            onChange={set("name")}
          />
        </Field>
        <Field label="NIP">
          <input className={inputClass} value={f.nip} onChange={set("nip")} />
        </Field>
        <Field label="Ulica i numer">
          <input
            className={inputClass}
            required
            value={f.street}
            onChange={set("street")}
          />
        </Field>
        <Field label="Kod pocztowy">
          <input
            className={inputClass}
            required
            value={f.postal_code}
            onChange={set("postal_code")}
          />
        </Field>
        <Field label="Miejscowość">
          <input
            className={inputClass}
            required
            value={f.city}
            onChange={set("city")}
          />
        </Field>
        <Field label="Adnotacja o zwolnieniu z VAT (opcjonalnie)">
          <input
            className={inputClass}
            value={f.vat_exempt_note}
            onChange={set("vat_exempt_note")}
          />
        </Field>
        <div>
          <Button type="submit" loading={busy}>
            Zapisz
          </Button>
        </div>
      </form>
    </Card>
  );
}

function Delivery({ item, reload }: { item: Item; reload: () => void }) {
  const v = item.value ?? {};
  const [f, setF] = useState({
    parcel: zl(v.parcel_locker_cost_grosz),
    courier: zl(v.courier_cost_grosz),
    free: zl(v.free_shipping_threshold_grosz),
    incentive: zl(v.incentive_threshold_grosz),
    vat: str(v.vat_rate) || "RATE_23",
  });
  const { error, info, busy, save } = useSaver(reload);
  const set =
    (k: keyof typeof f) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setF({ ...f, [k]: e.target.value });
  return (
    <Card title="Dostawa: koszty i progi">
      <Status error={error} info={info} />
      <p className="text-body-small text-ink-muted">
        Bez tych ustawień koszyk z książką nie policzy dostawy. Odbiór w
        gabinecie jest zawsze bezpłatny.
      </p>
      <form
        className="mt-3 grid gap-4 md:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault();
          void save(item.key, {
            parcel_locker_cost_grosz: grosz(f.parcel),
            courier_cost_grosz: grosz(f.courier),
            free_shipping_threshold_grosz: grosz(f.free),
            incentive_threshold_grosz: grosz(f.incentive),
            vat_rate: f.vat,
          });
        }}
      >
        <Field label="Paczkomat — koszt brutto (zł)">
          <input
            className={inputClass}
            inputMode="decimal"
            required
            value={f.parcel}
            onChange={set("parcel")}
          />
        </Field>
        <Field label="Kurier — koszt brutto (zł)">
          <input
            className={inputClass}
            inputMode="decimal"
            required
            value={f.courier}
            onChange={set("courier")}
          />
        </Field>
        <Field label="Darmowa dostawa od (zł, wartość produktów po rabacie)">
          <input
            className={inputClass}
            inputMode="decimal"
            required
            value={f.free}
            onChange={set("free")}
          />
        </Field>
        <Field label="Pokaż zachętę, gdy brakuje mniej niż (zł)">
          <input
            className={inputClass}
            inputMode="decimal"
            required
            value={f.incentive}
            onChange={set("incentive")}
          />
        </Field>
        <Field label="Stawka VAT dostawy">
          <select className={inputClass} value={f.vat} onChange={set("vat")}>
            <option value="RATE_23">23%</option>
            <option value="RATE_8">8%</option>
            <option value="RATE_5">5%</option>
            <option value="RATE_0">0%</option>
            <option value="EXEMPT">zw.</option>
          </select>
        </Field>
        <div className="self-end">
          <Button type="submit" loading={busy}>
            Zapisz
          </Button>
        </div>
      </form>
    </Card>
  );
}

function Simple({
  item,
  reload,
  fields,
}: {
  item: Item;
  reload: () => void;
  fields: Array<{
    key: string;
    label: string;
    type?: "number";
    placeholder?: string;
  }>;
}) {
  const [f, setF] = useState<Record<string, string>>(
    Object.fromEntries(
      fields.map((x) => [x.key, String(item.value?.[x.key] ?? "")]),
    ),
  );
  const { error, info, busy, save } = useSaver(reload);
  return (
    <Card title={item.label}>
      <Status error={error} info={info} />
      <form
        className="mt-3 grid gap-4 md:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault();
          void save(
            item.key,
            Object.fromEntries(
              fields.map((x) => [
                x.key,
                x.type === "number" ? Number(f[x.key]) : f[x.key] || null,
              ]),
            ),
          );
        }}
      >
        {fields.map((x) => (
          <Field key={x.key} label={x.label}>
            <input
              className={inputClass}
              value={f[x.key] ?? ""}
              placeholder={x.placeholder}
              onChange={(e) => setF({ ...f, [x.key]: e.target.value })}
            />
          </Field>
        ))}
        <div className="self-end">
          <Button type="submit" loading={busy}>
            Zapisz
          </Button>
        </div>
      </form>
    </Card>
  );
}

function Editor() {
  const [items, setItems] = useState<Item[] | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try {
      setItems((await adminJson<{ items: Item[] }>("/settings")).items);
    } catch (e) {
      setError(errorText(e, "Nie udało się wczytać ustawień."));
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);
  if (error) return <ErrorBox message={error} />;
  if (!items) return <Loading />;
  const by = Object.fromEntries(items.map((i) => [i.key, i]));
  return (
    <div className="space-y-6">
      {by["company.seller.v1"] ? (
        <Seller
          key={JSON.stringify(by["company.seller.v1"].value)}
          item={by["company.seller.v1"]}
          reload={load}
        />
      ) : null}
      {by["orders.delivery.v1"] ? (
        <Delivery
          key={JSON.stringify(by["orders.delivery.v1"].value)}
          item={by["orders.delivery.v1"]}
          reload={load}
        />
      ) : null}
      {by["ops.alerts.v1"] ? (
        <Simple
          key={JSON.stringify(by["ops.alerts.v1"].value)}
          item={by["ops.alerts.v1"]}
          reload={load}
          fields={[
            {
              key: "email",
              label: "E-mail do alertów (nieudane płatności, reklamacje…)",
            },
          ]}
        />
      ) : null}
      {by["vouchers.public.v1"] ? (
        <Simple
          key={JSON.stringify(by["vouchers.public.v1"].value)}
          item={by["vouchers.public.v1"]}
          reload={load}
          fields={[
            { key: "contact_email", label: "E-mail kontaktowy" },
            { key: "contact_phone", label: "Telefon" },
            { key: "booking_url", label: "Adres rezerwacji wizyt (https://)" },
            { key: "booking_instructions", label: "Instrukcja rezerwacji" },
          ]}
        />
      ) : null}
      {by["reviews.requests.v1"] ? (
        <Simple
          key={JSON.stringify(by["reviews.requests.v1"].value)}
          item={by["reviews.requests.v1"]}
          reload={load}
          fields={[
            {
              key: "delay_days",
              label: "Po ilu dniach od zakupu prosić o opinię (1–90)",
              type: "number",
              placeholder: "domyślnie 7",
            },
          ]}
        />
      ) : null}
    </div>
  );
}

export function AdminSettings() {
  return (
    <AdminShell title="Ustawienia">
      {(a) =>
        a.role === "owner" ? (
          <Editor />
        ) : (
          <Alert variant="warning">
            Ta sekcja jest dostępna dla właścicielki.
          </Alert>
        )
      }
    </AdminShell>
  );
}

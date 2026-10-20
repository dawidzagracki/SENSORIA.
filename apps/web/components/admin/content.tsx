"use client";

import { useCallback, useEffect, useState } from "react";
import { AdminShell } from "@/components/admin/admin-shell";
import {
  Card,
  ErrorBox,
  Field,
  inputClass,
  Loading,
  Table,
} from "@/components/admin/ui";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { adminJson, adminDownloadUrl, errorText } from "@/lib/admin-api";
import { blocksToText, textToBlocks } from "@/lib/blocks-text";
import type { ContentBlock } from "@/components/library/library-types";
import { ClientApiError, formatDateTime, money } from "@/lib/client-api";

const PAGES: Array<[string, string]> = [
  ["regulamin", "Regulamin"],
  ["polityka-prywatnosci", "Polityka prywatności"],
  ["polityka-cookies", "Polityka cookies"],
  ["dostawa-i-platnosci", "Dostawa i płatności"],
  ["o-autorce", "O autorce"],
];

function PageEditor() {
  const [slug, setSlug] = useState(PAGES[0]![0]);
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [text, setText] = useState("");
  const [status, setStatus] = useState<"draft" | "published" | "new">("new");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  const load = useCallback(async () => {
    setError("");
    setInfo("");
    try {
      const page = await adminJson<{
        title: string;
        summary: string | null;
        blocks: ContentBlock[];
        status: "draft" | "published";
      }>(`/pages/${slug}`);
      setTitle(page.title);
      setSummary(page.summary ?? "");
      setText(blocksToText(page.blocks));
      setStatus(page.status);
    } catch (e) {
      if (e instanceof ClientApiError && e.status === 404) {
        setTitle(PAGES.find(([s]) => s === slug)?.[1] ?? "");
        setSummary("");
        setText("");
        setStatus("new");
      } else setError(errorText(e, "Nie udało się wczytać strony."));
    }
  }, [slug]);
  useEffect(() => {
    void load();
  }, [load]);

  async function save() {
    setError("");
    setInfo("");
    try {
      await adminJson(`/pages/${slug}`, {
        method: "PUT",
        json: {
          slug,
          title,
          summary: summary || null,
          blocks: textToBlocks(text),
        },
      });
      setInfo("Zapisano jako szkic. Opublikuj, aby strona była widoczna.");
      await load();
    } catch (e) {
      setError(errorText(e, "Nie udało się zapisać."));
    }
  }
  async function publish(on: boolean) {
    try {
      await adminJson(`/pages/${slug}/${on ? "publish" : "unpublish"}`, {
        method: "POST",
      });
      setInfo(on ? "Strona opublikowana." : "Strona wycofana do szkiców.");
      await load();
    } catch (e) {
      setError(errorText(e, "Nie udało się zmienić statusu."));
    }
  }
  return (
    <Card title="Strony informacyjne i prawne">
      <ErrorBox message={error} />
      {info ? <Alert variant="success">{info}</Alert> : null}
      <p className="mb-3 text-body-small text-ink-muted">
        Teksty prawne (regulamin, polityka prywatności) przygotuj lub zweryfikuj
        z prawnikiem przed publikacją. Format: „## ” nagłówek, „&gt; ” cytat, „-
        ” punkt listy, pusta linia rozdziela akapity.
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Strona">
          <select
            className={inputClass}
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
          >
            {PAGES.map(([s, l]) => (
              <option key={s} value={s}>
                {l}
              </option>
            ))}
          </select>
        </Field>
        <p className="self-end text-body-small">
          Status:{" "}
          <strong>
            {status === "published"
              ? "Opublikowana"
              : status === "draft"
                ? "Szkic"
                : "Nowa"}
          </strong>
        </p>
        <Field label="Tytuł">
          <input
            className={inputClass}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </Field>
        <Field label="Podsumowanie (opcjonalnie)">
          <input
            className={inputClass}
            maxLength={300}
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
          />
        </Field>
        <div className="sm:col-span-2">
          <Field label="Treść">
            <textarea
              className={`${inputClass} py-2`}
              rows={16}
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          </Field>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-3">
        <Button onClick={save} disabled={!title.trim()}>
          Zapisz szkic
        </Button>
        {status !== "new" && status !== "published" ? (
          <Button variant="secondary" onClick={() => publish(true)}>
            Opublikuj
          </Button>
        ) : null}
        {status === "published" ? (
          <Button variant="secondary" onClick={() => publish(false)}>
            Wycofaj
          </Button>
        ) : null}
      </div>
    </Card>
  );
}

type Faq = {
  id: string;
  category: string;
  question: string;
  answer: string;
  position: number;
  published: boolean;
};
function FaqEditor() {
  const [items, setItems] = useState<Faq[] | null>(null);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState<Partial<Faq> & { id?: string }>({
    category: "Zamówienia",
    position: 0,
    published: true,
  });
  const load = useCallback(async () => {
    try {
      setItems((await adminJson<{ items: Faq[] }>("/faq")).items);
    } catch (e) {
      setError(errorText(e, "Nie udało się wczytać pytań."));
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);
  async function save() {
    setError("");
    const body = {
      category: draft.category ?? "",
      question: draft.question ?? "",
      answer: draft.answer ?? "",
      position: Number(draft.position) || 0,
      published: Boolean(draft.published),
    };
    try {
      if (draft.id)
        await adminJson(`/faq/${draft.id}`, { method: "PUT", json: body });
      else await adminJson("/faq", { method: "POST", json: body });
      setDraft({ category: draft.category, position: 0, published: true });
      await load();
    } catch (e) {
      setError(errorText(e, "Nie udało się zapisać pytania."));
    }
  }
  return (
    <Card title="Centrum pomocy — pytania i odpowiedzi">
      <ErrorBox message={error} />
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Kategoria">
          <input
            className={inputClass}
            value={draft.category ?? ""}
            onChange={(e) => setDraft({ ...draft, category: e.target.value })}
          />
        </Field>
        <Field label="Kolejność">
          <input
            className={inputClass}
            inputMode="numeric"
            value={draft.position ?? 0}
            onChange={(e) =>
              setDraft({ ...draft, position: Number(e.target.value) })
            }
          />
        </Field>
        <div className="sm:col-span-2">
          <Field label="Pytanie">
            <input
              className={inputClass}
              value={draft.question ?? ""}
              onChange={(e) => setDraft({ ...draft, question: e.target.value })}
            />
          </Field>
        </div>
        <div className="sm:col-span-2">
          <Field label="Odpowiedź (akapity oddziel pustą linią)">
            <textarea
              className={`${inputClass} py-2`}
              rows={5}
              value={draft.answer ?? ""}
              onChange={(e) => setDraft({ ...draft, answer: e.target.value })}
            />
          </Field>
        </div>
        <label className="flex min-h-touch items-center gap-2">
          <input
            type="checkbox"
            checked={Boolean(draft.published)}
            onChange={(e) =>
              setDraft({ ...draft, published: e.target.checked })
            }
          />{" "}
          Opublikowane
        </label>
      </div>
      <div className="mt-3 flex gap-3">
        <Button
          onClick={save}
          disabled={
            !(draft.question ?? "").trim() || !(draft.answer ?? "").trim()
          }
        >
          {draft.id ? "Zapisz zmiany" : "Dodaj pytanie"}
        </Button>
        {draft.id ? (
          <Button
            variant="secondary"
            onClick={() =>
              setDraft({
                category: draft.category,
                position: 0,
                published: true,
              })
            }
          >
            Anuluj edycję
          </Button>
        ) : null}
      </div>
      {!items ? (
        <Loading />
      ) : (
        <div className="mt-6">
          <Table
            caption="Pytania"
            head={["Kategoria", "Pytanie", "Status", ""]}
          >
            {items.map((f) => (
              <tr key={f.id}>
                <td className="px-3 py-2">{f.category}</td>
                <td className="px-3 py-2">{f.question}</td>
                <td className="px-3 py-2">
                  {f.published ? "Opublikowane" : "Szkic"}
                </td>
                <td className="px-3 py-2 space-x-3">
                  <button
                    type="button"
                    className="min-h-touch text-accent-action underline"
                    onClick={() => setDraft(f)}
                  >
                    Edytuj
                  </button>
                  <button
                    type="button"
                    className="min-h-touch text-accent-action underline"
                    onClick={async () => {
                      await adminJson(`/faq/${f.id}`, { method: "DELETE" });
                      await load();
                    }}
                  >
                    Usuń
                  </button>
                </td>
              </tr>
            ))}
          </Table>
        </div>
      )}
    </Card>
  );
}

export function AdminContent() {
  return (
    <AdminShell title="Strony i FAQ">
      {(admin) =>
        admin.role === "owner" ? (
          <div className="space-y-6">
            <PageEditor />
            <FaqEditor />
          </div>
        ) : (
          <Alert variant="warning">
            Ta sekcja jest dostępna dla właścicielki.
          </Alert>
        )
      }
    </AdminShell>
  );
}

/* -------------------------------- reports -------------------------------- */
type Sales = {
  totals: {
    orders: number;
    gross_grosz: number;
    net_grosz: number;
    tax_grosz: number;
    discount_grosz: number;
  };
  periods: Array<{
    period: string;
    orders: number;
    gross_grosz: number;
    net_grosz: number;
    tax_grosz: number;
    discount_grosz: number;
  }>;
  vat: Array<{
    vat_label: string;
    gross_grosz: number;
    net_grosz: number;
    tax_grosz: number;
  }>;
};
type Products = {
  items: Array<{ name: string; quantity: number; gross_grosz: number }>;
};
const iso = (d: Date) => d.toISOString().slice(0, 10);

function Reports() {
  const today = new Date();
  const [from, setFrom] = useState(
    iso(new Date(today.getFullYear(), today.getMonth(), 1)),
  );
  const [to, setTo] = useState(iso(today));
  const [group, setGroup] = useState("day");
  const [sales, setSales] = useState<Sales | null>(null);
  const [products, setProducts] = useState<Products | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try {
      setError("");
      const q = `date_from=${from}&date_to=${to}`;
      setSales(await adminJson(`/reports/sales?${q}&group=${group}`));
      setProducts(await adminJson(`/reports/products?${q}`));
    } catch (e) {
      setError(errorText(e, "Nie udało się wygenerować raportu."));
    }
  }, [from, to, group]);
  useEffect(() => {
    void load();
  }, [load]);
  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-end gap-4">
          <Field label="Od">
            <input
              type="date"
              className={inputClass}
              value={from}
              onChange={(e) => setFrom(e.target.value)}
            />
          </Field>
          <Field label="Do">
            <input
              type="date"
              className={inputClass}
              value={to}
              onChange={(e) => setTo(e.target.value)}
            />
          </Field>
          <Field label="Grupowanie">
            <select
              className={inputClass}
              value={group}
              onChange={(e) => setGroup(e.target.value)}
            >
              <option value="day">Dzienne</option>
              <option value="month">Miesięczne</option>
            </select>
          </Field>
          <a
            className="inline-flex min-h-touch items-center rounded-pill border border-accent-action px-5 font-bold"
            href={adminDownloadUrl(
              `/reports/sales.csv?date_from=${from}&date_to=${to}&group=${group}`,
            )}
          >
            Pobierz CSV
          </a>
        </div>
      </Card>
      <ErrorBox message={error} />
      {!sales && !error ? <Loading /> : null}
      {sales ? (
        <>
          <Card title="Podsumowanie">
            <dl className="grid gap-4 sm:grid-cols-5">
              {(
                [
                  ["Zamówienia", String(sales.totals.orders)],
                  ["Brutto", money(sales.totals.gross_grosz)],
                  ["Netto", money(sales.totals.net_grosz)],
                  ["Podatek", money(sales.totals.tax_grosz)],
                  ["Rabaty", money(sales.totals.discount_grosz)],
                ] as const
              ).map(([label, value]) => (
                <div key={label}>
                  <dt className="text-caption text-ink-muted">{label}</dt>
                  <dd className="font-display text-emphasis">{value}</dd>
                </div>
              ))}
            </dl>
          </Card>
          <Card title="Okresy">
            <Table
              caption="Sprzedaż wg okresu"
              head={["Okres", "Zamówienia", "Brutto", "Netto", "Podatek"]}
            >
              {sales.periods.map((p) => (
                <tr key={p.period}>
                  <td className="px-3 py-2">{p.period}</td>
                  <td className="px-3 py-2">{p.orders}</td>
                  <td className="px-3 py-2">{money(p.gross_grosz)}</td>
                  <td className="px-3 py-2">{money(p.net_grosz)}</td>
                  <td className="px-3 py-2">{money(p.tax_grosz)}</td>
                </tr>
              ))}
            </Table>
          </Card>
          <Card title="Wg stawki VAT">
            <Table
              caption="Sprzedaż wg stawki VAT"
              head={["Stawka", "Brutto", "Netto", "Podatek"]}
            >
              {sales.vat.map((v) => (
                <tr key={v.vat_label}>
                  <td className="px-3 py-2">{v.vat_label}</td>
                  <td className="px-3 py-2">{money(v.gross_grosz)}</td>
                  <td className="px-3 py-2">{money(v.net_grosz)}</td>
                  <td className="px-3 py-2">{money(v.tax_grosz)}</td>
                </tr>
              ))}
            </Table>
          </Card>
        </>
      ) : null}
      {products ? (
        <Card title="Najlepiej sprzedające się produkty">
          <Table
            caption="Produkty"
            head={["Produkt", "Sztuk", "Przychód brutto"]}
          >
            {products.items.map((p) => (
              <tr key={p.name}>
                <td className="px-3 py-2">{p.name}</td>
                <td className="px-3 py-2">{p.quantity}</td>
                <td className="px-3 py-2">{money(p.gross_grosz)}</td>
              </tr>
            ))}
          </Table>
        </Card>
      ) : null}
    </div>
  );
}
export function AdminReports() {
  return <AdminShell title="Raporty sprzedaży">{() => <Reports />}</AdminShell>;
}

/* --------------------------------- audit --------------------------------- */
type AuditRow = {
  at: string;
  actor_type: string;
  actor_id: string | null;
  entity_type: string;
  entity_id: string;
  action: string;
};
type CookieRow = {
  subject_id: string;
  policy_version: string;
  analytics: boolean;
  marketing: boolean;
  created_at: string;
};
function Audit() {
  const [tab, setTab] = useState<"audit" | "cookies">("audit");
  const [action, setAction] = useState("");
  const [audit, setAudit] = useState<{
    total: number;
    items: AuditRow[];
  } | null>(null);
  const [cookies, setCookies] = useState<{
    total: number;
    items: CookieRow[];
  } | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try {
      setError("");
      if (tab === "audit")
        setAudit(
          await adminJson(
            `/audit?page_size=100${action ? `&action=${encodeURIComponent(action)}` : ""}`,
          ),
        );
      else setCookies(await adminJson("/cookie-consents?page_size=100"));
    } catch (e) {
      setError(errorText(e, "Nie udało się wczytać dziennika."));
    }
  }, [tab, action]);
  useEffect(() => {
    void load();
  }, [load]);
  return (
    <div className="space-y-4">
      <div role="tablist" aria-label="Dziennik" className="flex gap-2">
        {(
          [
            ["audit", "Zdarzenia"],
            ["cookies", "Zgody cookies"],
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
      {tab === "audit" ? (
        <Card>
          <Field label="Filtr akcji (początek nazwy, np. order., voucher., payment.)">
            <input
              className={inputClass}
              value={action}
              onChange={(e) => setAction(e.target.value)}
            />
          </Field>
          {!audit ? (
            <Loading />
          ) : (
            <div className="mt-4">
              <Table
                caption="Dziennik zdarzeń"
                head={["Czas", "Kto", "Obiekt", "Akcja"]}
              >
                {audit.items.map((r, i) => (
                  <tr key={`${r.at}-${i}`}>
                    <td className="px-3 py-2">{formatDateTime(r.at)}</td>
                    <td className="px-3 py-2">{r.actor_type}</td>
                    <td className="px-3 py-2">{r.entity_type}</td>
                    <td className="px-3 py-2">{r.action}</td>
                  </tr>
                ))}
              </Table>
              <p className="mt-2 text-caption text-ink-muted">
                Łącznie: {audit.total}
              </p>
            </div>
          )}
        </Card>
      ) : !cookies ? (
        <Loading />
      ) : (
        <Card title="Rejestr zgód na cookies">
          <Table
            caption="Zgody cookies"
            head={["Czas", "Wersja polityki", "Analityczne", "Marketingowe"]}
          >
            {cookies.items.map((r, i) => (
              <tr key={`${r.subject_id}-${i}`}>
                <td className="px-3 py-2">{formatDateTime(r.created_at)}</td>
                <td className="px-3 py-2">{r.policy_version}</td>
                <td className="px-3 py-2">{r.analytics ? "Tak" : "Nie"}</td>
                <td className="px-3 py-2">{r.marketing ? "Tak" : "Nie"}</td>
              </tr>
            ))}
          </Table>
        </Card>
      )}
    </div>
  );
}
export function AdminAudit() {
  return (
    <AdminShell title="Dziennik zdarzeń">
      {(a) =>
        a.role === "owner" ? (
          <Audit />
        ) : (
          <Alert variant="warning">
            Ta sekcja jest dostępna dla właścicielki.
          </Alert>
        )
      }
    </AdminShell>
  );
}

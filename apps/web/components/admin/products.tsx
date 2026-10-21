"use client";

import Image from "next/image";
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
import { adminJson, adminUpload, errorText } from "@/lib/admin-api";
import { money } from "@/lib/client-api";

type Product = {
  id: string;
  kind: string;
  name: string;
  slug: string;
  status: string;
  price: number | null;
  compare_at_price: number | null;
  vat_rate: string | null;
};
const KIND: Record<string, string> = {
  VOUCHER: "Voucher",
  BOOK: "Książka",
  AUDIOBOOK: "Audiobook",
  DIGITAL: "E-book / kurs PDF",
};
const STATUS: Record<string, string> = {
  DRAFT: "Szkic",
  PUBLISHED: "Opublikowany",
  WITHDRAWN: "Wycofany",
};
const toGrosz = (value: string) =>
  Math.round(Number(value.replace(",", ".")) * 100);
const fromGrosz = (value: number | null) =>
  value === null ? "" : (value / 100).toFixed(2).replace(".", ",");

function List() {
  const [kind, setKind] = useState("");
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<{ total: number; items: Product[] } | null>(
    null,
  );
  const [error, setError] = useState("");
  useEffect(() => {
    setKind(new URLSearchParams(window.location.search).get("kind") ?? "");
  }, []);
  const load = useCallback(async () => {
    const p = new URLSearchParams({ page: String(page), page_size: "25" });
    if (kind) p.set("kind", kind);
    if (status) p.set("status", status);
    if (q.trim()) p.set("q", q.trim());
    try {
      setError("");
      setData(await adminJson(`/products?${p}`));
    } catch (e) {
      setError(errorText(e, "Nie udało się wczytać produktów."));
    }
  }, [page, kind, status, q]);
  useEffect(() => {
    void load();
  }, [load]);
  return (
    <div className="space-y-4">
      <Card>
        <div className="grid gap-4 md:grid-cols-4">
          <Field label="Szukaj">
            <input
              className={inputClass}
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setPage(1);
              }}
            />
          </Field>
          <Field label="Rodzaj">
            <select
              className={inputClass}
              value={kind}
              onChange={(e) => {
                setKind(e.target.value);
                setPage(1);
              }}
            >
              <option value="">Wszystkie</option>
              {Object.entries(KIND).map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Status">
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
          <div className="flex items-end">
            <Link
              href="/admin/produkty/nowy"
              className="inline-flex min-h-touch items-center rounded-pill bg-accent-action px-6 font-bold text-surface"
            >
              Dodaj produkt
            </Link>
          </div>
        </div>
      </Card>
      <ErrorBox message={error} />
      {!data && !error ? <Loading /> : null}
      {data ? (
        <Card>
          <Table
            caption="Produkty"
            head={["Nazwa", "Rodzaj", "Status", "Cena", ""]}
          >
            {data.items.map((p) => (
              <tr key={p.id}>
                <td className="px-3 py-2 font-bold">
                  {p.name || "(bez nazwy)"}
                </td>
                <td className="px-3 py-2">{KIND[p.kind]}</td>
                <td className="px-3 py-2">{STATUS[p.status]}</td>
                <td className="px-3 py-2">
                  {p.price === null ? "—" : money(p.price)}
                </td>
                <td className="px-3 py-2">
                  <Link
                    className="text-accent-action underline"
                    href={`/admin/produkty/${p.id}`}
                  >
                    Edytuj
                  </Link>
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
    </div>
  );
}
export function AdminProducts() {
  return <AdminShell title="Produkty">{() => <List />}</AdminShell>;
}

/* ----------------------------- create & edit ----------------------------- */
type Detail = Product & {
  short_description: string | null;
  description: string | null;
  meta_title: string | null;
  meta_description: string | null;
  images: Array<{ url: string; alt: string; position: number }>;
  voucher?: {
    service_name: string;
    validity_months: number;
    variants: Array<{ kind: string; price: number }>;
  };
  book?: {
    stock_quantity: number;
    low_stock_threshold: number;
    weight_grams: number | null;
    isbn: string | null;
    binding: string | null;
  };
  audiobook?: {
    narrator: string | null;
    duration_seconds: number | null;
    chapters: Array<{
      position: number;
      title: string;
      length_seconds: number;
    }>;
  };
  digital?: {
    page_count: number | null;
    edition: string | null;
    label: string;
  };
  files: Array<{ id: string; kind: string; label: string; position: number }>;
  reader_chapters: Array<{
    position: number;
    title: string;
    page_count: number | null;
  }>;
};

function CreateForm() {
  const [kind, setKind] = useState("BOOK");
  const [name, setName] = useState("");
  const [price, setPrice] = useState("");
  const [vat, setVat] = useState("RATE_5");
  const [short, setShort] = useState("");
  const [stock, setStock] = useState("0");
  const [serviceName, setServiceName] = useState("");
  const [online, setOnline] = useState("");
  const [inPerson, setInPerson] = useState("");
  const [narrator, setNarrator] = useState("");
  const [chaptersText, setChaptersText] = useState("");
  const [digitalLabel, setDigitalLabel] = useState("EBOOK_PDF");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const body: Record<string, unknown> = {
      kind,
      name,
      short_description: short || null,
      vat_rate: vat,
      images: [],
    };
    if (kind !== "VOUCHER" && price) body.price = toGrosz(price);
    if (kind === "BOOK")
      body.book = {
        stock_quantity: Number(stock) || 0,
        low_stock_threshold: 2,
      };
    if (kind === "DIGITAL")
      body.digital = { label: digitalLabel, file_format: "PDF" };
    if (kind === "VOUCHER") {
      const variants = [
        ...(online ? [{ kind: "ONLINE", price: toGrosz(online) }] : []),
        ...(inPerson ? [{ kind: "IN_PERSON", price: toGrosz(inPerson) }] : []),
      ];
      body.voucher = {
        validity_months: 12,
        service_name: serviceName,
        variants,
      };
      body.price = variants[0]?.price ?? null;
    }
    if (kind === "AUDIOBOOK") {
      const chapters = chaptersText
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean)
        .map((line, position) => {
          const [title, minutes] = line.split(";");
          return {
            title: (title ?? "").trim(),
            length_seconds: Math.round(Number(minutes ?? 1) * 60),
            position,
          };
        });
      body.audiobook = {
        narrator: narrator || null,
        duration_seconds:
          chapters.reduce((s, c) => s + c.length_seconds, 0) || null,
        chapters,
      };
    }
    try {
      const created = await adminJson<{ id: string }>("/products", {
        method: "POST",
        json: body,
      });
      window.location.assign(`/admin/produkty/${created.id}`);
    } catch (e) {
      setError(errorText(e, "Nie udało się utworzyć produktu."));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="max-w-2xl space-y-4">
      <ErrorBox message={error} />
      <Field label="Rodzaj produktu">
        <select
          className={inputClass}
          value={kind}
          onChange={(e) => setKind(e.target.value)}
        >
          {Object.entries(KIND).map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Nazwa">
        <input
          className={inputClass}
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </Field>
      <Field label="Krótki opis">
        <input
          className={inputClass}
          maxLength={500}
          value={short}
          onChange={(e) => setShort(e.target.value)}
        />
      </Field>
      <Field label="Stawka VAT">
        <select
          className={inputClass}
          value={vat}
          onChange={(e) => setVat(e.target.value)}
        >
          <option value="RATE_23">23%</option>
          <option value="RATE_8">8%</option>
          <option value="RATE_5">5%</option>
          <option value="RATE_0">0%</option>
          <option value="EXEMPT">zw. z VAT</option>
        </select>
      </Field>
      {kind !== "VOUCHER" ? (
        <Field label="Cena brutto (zł)">
          <input
            className={inputClass}
            inputMode="decimal"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
          />
        </Field>
      ) : null}
      {kind === "BOOK" ? (
        <Field label="Stan początkowy (szt.)">
          <input
            className={inputClass}
            inputMode="numeric"
            value={stock}
            onChange={(e) => setStock(e.target.value)}
          />
        </Field>
      ) : null}
      {kind === "DIGITAL" ? (
        <Field label="Typ materiału">
          <select
            className={inputClass}
            value={digitalLabel}
            onChange={(e) => setDigitalLabel(e.target.value)}
          >
            <option value="EBOOK_PDF">E-book PDF</option>
            <option value="COURSE_PDF">Kurs PDF</option>
          </select>
        </Field>
      ) : null}
      {kind === "VOUCHER" ? (
        <>
          <Field label="Nazwa usługi">
            <input
              className={inputClass}
              required
              value={serviceName}
              onChange={(e) => setServiceName(e.target.value)}
            />
          </Field>
          <Field label="Cena — wizyta online (zł)">
            <input
              className={inputClass}
              inputMode="decimal"
              value={online}
              onChange={(e) => setOnline(e.target.value)}
            />
          </Field>
          <Field label="Cena — wizyta w gabinecie (zł)">
            <input
              className={inputClass}
              inputMode="decimal"
              value={inPerson}
              onChange={(e) => setInPerson(e.target.value)}
            />
          </Field>
        </>
      ) : null}
      {kind === "AUDIOBOOK" ? (
        <>
          <Field label="Lektor">
            <input
              className={inputClass}
              value={narrator}
              onChange={(e) => setNarrator(e.target.value)}
            />
          </Field>
          <Field
            label="Rozdziały (jeden w linii: tytuł;minuty)"
            hint="Np. „Wstęp;12”. Pliki audio dodasz po zapisaniu."
          >
            <textarea
              className={`${inputClass} py-2`}
              rows={6}
              value={chaptersText}
              onChange={(e) => setChaptersText(e.target.value)}
            />
          </Field>
        </>
      ) : null}
      <Button type="submit" size="lg" loading={busy}>
        Zapisz szkic
      </Button>
    </form>
  );
}
export function AdminProductNew() {
  return <AdminShell title="Nowy produkt">{() => <CreateForm />}</AdminShell>;
}

const SAMPLE_CHAPTER = JSON.stringify(
  [
    {
      title: "Wstęp",
      page_count: 10,
      blocks: [{ type: "p", text: "Treść rozdziału…" }],
    },
  ],
  null,
  2,
);

function Editor({ id, role }: { id: string; role: string }) {
  const [p, setP] = useState<Detail | null>(null);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [busy, setBusy] = useState("");
  const [form, setForm] = useState({
    name: "",
    short: "",
    description: "",
    price: "",
    compare: "",
    reason: "",
    metaTitle: "",
    metaDescription: "",
  });
  const [stock, setStock] = useState({ change: "", note: "" });
  const [fileLabel, setFileLabel] = useState("");
  const [chapterPos, setChapterPos] = useState("");
  const [chaptersJson, setChaptersJson] = useState(SAMPLE_CHAPTER);

  const load = useCallback(async () => {
    try {
      const d = await adminJson<Detail>(`/products/${id}`);
      setP(d);
      setForm({
        name: d.name,
        short: d.short_description ?? "",
        description: d.description ?? "",
        price: fromGrosz(d.price),
        compare: fromGrosz(d.compare_at_price),
        reason: "",
        metaTitle: d.meta_title ?? "",
        metaDescription: d.meta_description ?? "",
      });
    } catch (e) {
      setError(errorText(e, "Nie udało się wczytać produktu."));
    }
  }, [id]);
  useEffect(() => {
    void load();
  }, [load]);

  async function run(name: string, fn: () => Promise<unknown>, done: string) {
    setBusy(name);
    setError("");
    setInfo("");
    try {
      await fn();
      setInfo(done);
      await load();
    } catch (e) {
      setError(errorText(e, "Operacja nie powiodła się."));
    } finally {
      setBusy("");
    }
  }

  if (!p) return error ? <ErrorBox message={error} /> : <Loading />;
  const priceChanged =
    toGrosz(form.price || "0") !== (p.price ?? 0) ||
    (form.compare ? toGrosz(form.compare) : null) !== p.compare_at_price;
  return (
    <div className="space-y-4">
      <Link
        href="/admin/produkty"
        className="inline-flex min-h-touch items-center text-accent-action underline"
      >
        ← Wszystkie produkty
      </Link>
      <ErrorBox message={error} />
      {info ? <Alert variant="success">{info}</Alert> : null}
      <Card
        title={`${KIND[p.kind]} · ${STATUS[p.status]}`}
        actions={
          <div className="flex gap-3">
            {p.status === "DRAFT" ? (
              <Button
                loading={busy === "publish"}
                onClick={() =>
                  run(
                    "publish",
                    () =>
                      adminJson(`/products/${id}/publish`, { method: "POST" }),
                    "Produkt opublikowany.",
                  )
                }
              >
                Opublikuj
              </Button>
            ) : null}
            {p.status === "PUBLISHED" && role === "owner" ? (
              <Button
                variant="secondary"
                loading={busy === "withdraw"}
                onClick={() =>
                  run(
                    "withdraw",
                    () =>
                      adminJson(`/products/${id}/withdraw`, { method: "POST" }),
                    "Produkt wycofany.",
                  )
                }
              >
                Wycofaj
              </Button>
            ) : null}
          </div>
        }
      >
        <form
          className="grid gap-4 md:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault();
            void run(
              "save",
              () =>
                adminJson(`/products/${id}`, {
                  method: "PATCH",
                  json: {
                    name: form.name,
                    short_description: form.short || null,
                    description: form.description || null,
                    meta_title: form.metaTitle || null,
                    meta_description: form.metaDescription || null,
                    ...(priceChanged
                      ? {
                          price: toGrosz(form.price || "0"),
                          compare_at_price: form.compare
                            ? toGrosz(form.compare)
                            : null,
                          price_change_reason: form.reason,
                        }
                      : {}),
                  },
                }),
              "Zapisano zmiany.",
            );
          }}
        >
          <Field label="Nazwa">
            <input
              className={inputClass}
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </Field>
          <Field label="Krótki opis">
            <input
              className={inputClass}
              maxLength={500}
              value={form.short}
              onChange={(e) => setForm({ ...form, short: e.target.value })}
            />
          </Field>
          <Field label="Cena brutto (zł)">
            <input
              className={inputClass}
              inputMode="decimal"
              value={form.price}
              onChange={(e) => setForm({ ...form, price: e.target.value })}
            />
          </Field>
          <Field
            label="Cena przed obniżką (zł)"
            hint="Wypełnij tylko przy promocji; sklep pokaże najniższą cenę z 30 dni."
          >
            <input
              className={inputClass}
              inputMode="decimal"
              value={form.compare}
              onChange={(e) => setForm({ ...form, compare: e.target.value })}
            />
          </Field>
          {priceChanged ? (
            <div className="md:col-span-2">
              <Field label="Powód zmiany ceny (zapisywany w historii)">
                <input
                  className={inputClass}
                  required
                  minLength={3}
                  value={form.reason}
                  onChange={(e) => setForm({ ...form, reason: e.target.value })}
                />
              </Field>
            </div>
          ) : null}
          <div className="md:col-span-2">
            <Field label="Opis">
              <textarea
                className={`${inputClass} py-2`}
                rows={6}
                value={form.description}
                onChange={(e) =>
                  setForm({ ...form, description: e.target.value })
                }
              />
            </Field>
          </div>
          <Field label="Tytuł SEO">
            <input
              className={inputClass}
              maxLength={200}
              value={form.metaTitle}
              onChange={(e) => setForm({ ...form, metaTitle: e.target.value })}
            />
          </Field>
          <Field label="Opis SEO">
            <input
              className={inputClass}
              maxLength={500}
              value={form.metaDescription}
              onChange={(e) =>
                setForm({ ...form, metaDescription: e.target.value })
              }
            />
          </Field>
          <div>
            <Button type="submit" loading={busy === "save"}>
              Zapisz zmiany
            </Button>
          </div>
        </form>
      </Card>

      <Card title="Zdjęcia">
        <ul className="flex flex-wrap gap-3">
          {p.images.map((img) => (
            <li key={img.url}>
              <Image
                src={img.url}
                alt={img.alt}
                width={96}
                height={96}
                unoptimized
                className="h-24 w-24 rounded-control object-cover"
              />
            </li>
          ))}
        </ul>
        <div className="mt-3">
          <Field label="Dodaj zdjęcie (PNG, JPEG, WebP do 5 MB)">
            <input
              type="file"
              accept="image/png,image/jpeg,image/webp"
              className={inputClass}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                const body = new FormData();
                body.append("file", file);
                void run(
                  "image",
                  async () => {
                    const up = await adminUpload<{ url: string }>(
                      "/products/images",
                      body,
                    );
                    await adminJson(`/products/${id}`, {
                      method: "PATCH",
                      json: {
                        images: [
                          ...p.images,
                          { url: up.url, alt: form.name || "Zdjęcie produktu" },
                        ],
                      },
                    });
                  },
                  "Zdjęcie dodane.",
                );
              }}
            />
          </Field>
        </div>
      </Card>

      {p.kind === "BOOK" && p.book ? (
        <Card title="Stan magazynowy">
          <p>
            Stan: <strong>{p.book.stock_quantity}</strong> szt. (próg alertu:{" "}
            {p.book.low_stock_threshold})
          </p>
          <form
            className="mt-3 flex flex-wrap items-end gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              void run(
                "stock",
                () =>
                  adminJson(`/products/${id}/stock`, {
                    method: "POST",
                    headers: { "Idempotency-Key": crypto.randomUUID() },
                    json: { change: Number(stock.change), note: stock.note },
                  }),
                "Stan zaktualizowany.",
              );
              setStock({ change: "", note: "" });
            }}
          >
            <Field label="Zmiana (np. 5 lub -2)">
              <input
                className={inputClass}
                required
                inputMode="numeric"
                value={stock.change}
                onChange={(e) => setStock({ ...stock, change: e.target.value })}
              />
            </Field>
            <Field label="Uzasadnienie">
              <input
                className={inputClass}
                required
                minLength={3}
                value={stock.note}
                onChange={(e) => setStock({ ...stock, note: e.target.value })}
              />
            </Field>
            <Button
              type="submit"
              variant="secondary"
              loading={busy === "stock"}
            >
              Zapisz korektę
            </Button>
          </form>
        </Card>
      ) : null}

      {p.kind === "DIGITAL" || p.kind === "AUDIOBOOK" ? (
        <Card title="Pliki płatnych materiałów">
          <p className="text-body-small text-ink-muted">
            Pliki nie są publiczne. PDF jest oznaczany danymi kupującej przy
            każdym pobraniu.{" "}
            {p.kind === "AUDIOBOOK"
              ? "Dla audiobooka dodaj osobny plik MP3 do każdego rozdziału."
              : ""}
          </p>
          <ul className="mt-3 space-y-1 text-body-small">
            {p.files.map((f) => (
              <li key={f.id} className="flex items-center gap-3">
                {f.label} ({f.kind})
                {role === "owner" ? (
                  <button
                    type="button"
                    className="min-h-touch text-accent-action underline"
                    onClick={() =>
                      run(
                        "rmfile",
                        () =>
                          adminJson(`/products/${id}/files/${f.id}`, {
                            method: "DELETE",
                          }),
                        "Plik odłączony.",
                      )
                    }
                  >
                    Usuń
                  </button>
                ) : null}
              </li>
            ))}
            {p.files.length === 0 ? (
              <li className="text-ink-muted">Brak plików.</li>
            ) : null}
          </ul>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <Field label="Etykieta pliku">
              <input
                className={inputClass}
                value={fileLabel}
                onChange={(e) => setFileLabel(e.target.value)}
              />
            </Field>
            {p.kind === "AUDIOBOOK" ? (
              <Field label="Rozdział (numer od 0)">
                <select
                  className={inputClass}
                  value={chapterPos}
                  onChange={(e) => setChapterPos(e.target.value)}
                >
                  <option value="">—</option>
                  {p.audiobook?.chapters.map((c) => (
                    <option key={c.position} value={c.position}>
                      {c.position + 1}. {c.title}
                    </option>
                  ))}
                </select>
              </Field>
            ) : (
              <span />
            )}
            <Field label="Plik (PDF lub MP3)">
              <input
                type="file"
                accept={p.kind === "DIGITAL" ? "application/pdf" : "audio/mpeg"}
                className={inputClass}
                disabled={!fileLabel.trim()}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  const body = new FormData();
                  body.append("file", file);
                  body.append("label", fileLabel.trim());
                  if (chapterPos !== "")
                    body.append("chapter_position", chapterPos);
                  void run(
                    "file",
                    () => adminUpload(`/products/${id}/files`, body),
                    "Plik dodany.",
                  );
                }}
              />
            </Field>
          </div>
        </Card>
      ) : null}

      {p.kind === "DIGITAL" ? (
        <Card title="Treść czytnika (rozdziały)">
          <p className="text-body-small text-ink-muted">
            Aktualnie rozdziałów: {p.reader_chapters.length}. Wklej listę
            rozdziałów w formacie JSON — zastąpi obecną. Dozwolone bloki: p, h2,
            quote, list, exercise.
          </p>
          <textarea
            aria-label="Rozdziały w formacie JSON"
            className={`${inputClass} mt-3 py-2 font-mono text-caption`}
            rows={12}
            value={chaptersJson}
            onChange={(e) => setChaptersJson(e.target.value)}
          />
          <div className="mt-3">
            <Button
              loading={busy === "chapters"}
              onClick={() => {
                let parsed: unknown;
                try {
                  parsed = JSON.parse(chaptersJson);
                } catch {
                  setError("To nie jest poprawny JSON.");
                  return;
                }
                void run(
                  "chapters",
                  () =>
                    adminJson(`/products/${id}/chapters`, {
                      method: "PUT",
                      json: { chapters: parsed },
                    }),
                  "Rozdziały zapisane.",
                );
              }}
            >
              Zapisz rozdziały
            </Button>
          </div>
        </Card>
      ) : null}
    </div>
  );
}
export function AdminProductEdit({ id }: { id: string }) {
  return (
    <AdminShell title="Edycja produktu">
      {(a) => <Editor id={id} role={a.role} />}
    </AdminShell>
  );
}

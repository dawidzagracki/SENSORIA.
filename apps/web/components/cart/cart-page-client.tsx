"use client";

import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useCartCount } from "../layout/cart-count-provider";
import { ProductCard } from "../ui/product-card";
import { productMetric, productTypeLabel } from "../../lib/homepage-products";
import {
  parseCatalogList,
  type CatalogListItem,
} from "../../types/catalog-list";
import { DiscountSummary } from "./discount-summary";
import { Checkbox } from "../ui";
import type {
  CartItem,
  CartMutation,
  CartView,
  ReorderReport,
} from "./cart-types";

type ContactSettings = { contact_email: string | null };
type LoadState = "loading" | "ready" | "error";

function apiBase(): string {
  return "/api";
}

async function readError(response: Response): Promise<string> {
  try {
    const value = (await response.json()) as {
      error?: { message?: string };
    };
    return value.error?.message ?? "Nie udało się zaktualizować koszyka.";
  } catch {
    return "Nie udało się zaktualizować koszyka.";
  }
}

function formatGrosz(value: number): string {
  if (!Number.isSafeInteger(value)) return "—";
  return `${Math.trunc(value / 100)},${String(Math.abs(value % 100)).padStart(2, "0")} zł`;
}

function ReorderSummary({
  report,
  onDismiss,
}: {
  report: ReorderReport;
  onDismiss: () => void;
}) {
  return (
    <section
      aria-labelledby="reorder-summary-title"
      className="mb-6 rounded-card border border-accent/30 bg-surface-muted p-4 sm:p-5"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-caption font-semibold text-accent-action">
            Podsumowanie ponowienia · {report.source_label}
          </p>
          <h2
            id="reorder-summary-title"
            className="mt-1 font-display text-subtitle font-bold"
          >
            {report.message}
          </h2>
          <p className="mt-1 text-caption text-ink-muted">
            Dotychczasowa zawartość koszyka została zachowana. Ceny i warunki są
            aktualne.
          </p>
          {report.warnings.map((warning) => (
            <p className="mt-2 text-caption text-ink-muted" key={warning}>
              {warning}
            </p>
          ))}
        </div>
        <button
          className="min-h-touch rounded-control px-3 font-semibold underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
          onClick={onDismiss}
          type="button"
        >
          Zamknij podsumowanie
        </button>
      </div>
      <ul className="mt-4 space-y-2">
        {report.lines.map((line, index) => (
          <li
            className="rounded-control border border-border bg-surface p-3"
            key={`${line.product_id}-${index}`}
          >
            <p className="break-words font-semibold">
              {line.name}
              {line.variant ? ` · ${line.variant}` : ""}
            </p>
            <p className="mt-1 text-body-small text-ink-muted">
              Żądano: {line.requested_quantity} · dodano: {line.added_quantity}
              {line.status === "already_in_cart" ? " · już w koszyku" : ""}
              {line.reason ? ` · ${line.reason}` : ""}
            </p>
            {line.warnings?.map((warning) => (
              <p
                className="mt-1 text-caption font-semibold text-accent-action"
                key={warning}
              >
                {warning}
              </p>
            ))}
            {line.price_changed && line.new_unit_price_grosz !== null ? (
              <p className="mt-1 text-caption text-ink-muted">
                Cena z poprzedniego zakupu:{" "}
                {formatGrosz(line.old_unit_price_grosz)} · aktualna cena:{" "}
                {formatGrosz(line.new_unit_price_grosz)}
              </p>
            ) : null}
          </li>
        ))}
      </ul>
      {report.discount_revalidation_notice ? (
        <p className="mt-3 text-body-small" role="status">
          {report.discount_revalidation_notice}
        </p>
      ) : null}
    </section>
  );
}

function productCountLabel(count: number): string {
  if (count === 1) return `${count} produkt`;
  const lastTwoDigits = count % 100;
  const lastDigit = count % 10;
  if (lastTwoDigits < 12 || lastTwoDigits > 14) {
    if (lastDigit >= 2 && lastDigit <= 4) return `${count} produkty`;
  }
  return `${count} produktów`;
}

function itemKindLabel(item: CartItem): string {
  if (item.kind === "VOUCHER") return "Voucher";
  if (item.kind === "BOOK") return "Książka papierowa";
  if (item.kind === "AUDIOBOOK") return "Audiobook";
  return item.details?.startsWith("COURSE PDF") ? "Kurs PDF" : "E-book PDF";
}

function CartLine({
  item,
  pendingQuantity,
  removing,
  onQuantity,
  onRemove,
  onToggleGift,
}: {
  item: CartItem;
  pendingQuantity: number | undefined;
  removing: boolean;
  onQuantity: (item: CartItem, next: number) => void;
  onRemove: (item: CartItem) => void;
  onToggleGift: (item: CartItem, checked: boolean) => void;
}) {
  const quantity = pendingQuantity ?? item.quantity;
  const canChangeQuantity = item.kind === "BOOK";
  return (
    <article className="grid min-w-0 grid-cols-[5.5rem_minmax(0,1fr)] gap-4 rounded-card border border-border bg-surface p-4 md:grid-cols-[7rem_minmax(0,1fr)_auto] md:items-center md:p-5">
      <div className="relative aspect-product-image w-full overflow-hidden rounded-card bg-surface-muted md:w-28">
        {item.image ? (
          <Image
            alt=""
            className="object-cover"
            fill
            sizes="(min-width: 768px) 112px, 40vw"
            src={item.image.url}
            unoptimized
          />
        ) : (
          <span className="flex h-full items-center justify-center p-2 text-center text-caption text-ink-muted">
            Obraz produktu niedostępny
          </span>
        )}
      </div>
      <div className="min-w-0">
        <p className="text-caption text-ink-muted">{itemKindLabel(item)}</p>
        <h2 className="mt-1 break-words font-display text-body-small font-extrabold text-ink">
          <Link
            className="rounded-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
            href={`/sklep/${encodeURIComponent(item.slug)}`}
          >
            {item.name}
          </Link>
        </h2>
        {item.details ? (
          <p className="mt-1 break-words text-caption text-ink-muted">
            {item.details}
          </p>
        ) : null}
        {item.variant_kind ? (
          <p className="mt-1 text-caption text-ink-muted">
            Wariant:{" "}
            {item.variant_kind === "IN_PERSON" ? "w gabinecie" : "online"}
          </p>
        ) : null}
        {item.voucher_validity_months ? (
          <p className="mt-1 text-caption text-ink-muted">
            Ważność {item.voucher_validity_months} miesięcy od wystawienia; kod
            powstaje po opłaceniu.
          </p>
        ) : null}
        {item.kind === "VOUCHER" ? (
          <div className="mt-3">
            <Checkbox
              checked={item.is_gift}
              label="Kupuję w prezencie"
              description="Dane obdarowanej osoby i dedykację uzupełnisz w zamówieniu."
              disabled={removing}
              onChange={(event) =>
                onToggleGift(item, event.currentTarget.checked)
              }
            />
          </div>
        ) : null}
        {canChangeQuantity ? (
          <div
            className="mt-3 flex min-h-touch items-center gap-2"
            aria-label={`Ilość ${item.name}`}
          >
            <button
              type="button"
              aria-label={`Zmniejsz ilość ${item.name}`}
              className="min-h-touch min-w-touch rounded-pill border border-border text-label text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action disabled:opacity-50"
              disabled={removing || quantity <= 1}
              onClick={() => onQuantity(item, quantity - 1)}
            >
              −
            </button>
            <span
              className="min-w-8 text-center text-label text-ink"
              aria-live="off"
            >
              {quantity}
            </span>
            <button
              type="button"
              aria-label={`Zwiększ ilość ${item.name}`}
              className="min-h-touch min-w-touch rounded-pill border border-border text-label text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action disabled:opacity-50"
              disabled={removing}
              onClick={() => onQuantity(item, quantity + 1)}
            >
              +
            </button>
          </div>
        ) : (
          <p className="mt-2 text-caption text-ink-muted">Ilość: 1</p>
        )}
        {item.quantity > 1 ? (
          <p className="mt-1 text-caption text-ink-muted">
            {item.quantity} × {formatGrosz(item.unit_price_snapshot)} ·{" "}
            {item.vat_rate_snapshot === "EXEMPT"
              ? "zw. z VAT"
              : `VAT ${item.vat_label}`}
          </p>
        ) : (
          <p className="mt-1 text-caption text-ink-muted">
            {item.vat_rate_snapshot === "EXEMPT"
              ? "Zwolnienie z VAT"
              : `VAT ${item.vat_label}`}
          </p>
        )}
      </div>
      <div className="col-span-2 flex items-center justify-between gap-4 border-t border-border pt-3 md:col-span-1 md:flex-col md:items-end md:justify-center md:border-0 md:pt-0">
        <strong className="font-interface text-subtitle text-ink">
          {formatGrosz(item.line_total_grosz)}
        </strong>
        <button
          type="button"
          className="min-h-touch rounded-card px-2 text-caption text-ink underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
          aria-label={`Usuń ${item.name} z koszyka`}
          disabled={removing}
          onClick={() => onRemove(item)}
        >
          Usuń
        </button>
      </div>
    </article>
  );
}

function ProductRecommendations({
  products,
  cart,
  mutate,
  title,
  showAdd,
}: {
  products: CatalogListItem[];
  cart: CartView;
  mutate: CartMutation;
  title: string;
  showAdd: boolean;
}) {
  const [notice, setNotice] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const selected = products
    .filter(
      (product) => !cart.items.some((item) => item.product_id === product.id),
    )
    .slice(0, 3);
  if (!selected.length) return null;

  async function add(product: CatalogListItem) {
    if (pendingId) return;
    setPendingId(product.id);
    setNotice(null);
    try {
      await mutate("POST", "/items", {
        product_id: product.id,
        variant_id: null,
        quantity: 1,
      });
      setNotice(`Dodano ${product.name} do koszyka.`);
    } catch (cause) {
      setNotice(
        cause instanceof Error
          ? cause.message
          : "Nie udało się dodać produktu.",
      );
    } finally {
      setPendingId(null);
    }
  }

  return (
    <section
      aria-labelledby="cart-recommendations-title"
      className="mt-12 space-y-5"
    >
      <h2
        id="cart-recommendations-title"
        className="font-display text-title text-ink"
      >
        {title}
      </h2>
      {notice ? (
        <p role="status" className="text-body text-ink">
          {notice}
        </p>
      ) : null}
      <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
        {selected.map((product) => {
          const requiresVariant = product.kind === "VOUCHER";
          return (
            <ProductCard
              key={product.id}
              description={product.short_description ?? ""}
              href={
                requiresVariant
                  ? `/sklep/${encodeURIComponent(product.slug)}`
                  : undefined
              }
              actionHref={
                requiresVariant
                  ? `/sklep/${encodeURIComponent(product.slug)}`
                  : undefined
              }
              actionLabel={
                requiresVariant || !showAdd
                  ? "Zobacz"
                  : pendingId === product.id
                    ? "Dodaję…"
                    : "Dodaj"
              }
              image={
                product.image ? (
                  <Image
                    alt=""
                    className="object-cover"
                    fill
                    sizes="(min-width: 1024px) 30vw, 90vw"
                    src={product.image.url}
                    unoptimized
                  />
                ) : (
                  <span className="flex h-full items-center justify-center text-caption text-ink-muted">
                    Brak zdjęcia
                  </span>
                )
              }
              imageAlt={product.image?.alt ?? "Brak zdjęcia produktu"}
              metric={productMetric(product)}
              onAddToCart={
                !requiresVariant && showAdd
                  ? () => void add(product)
                  : undefined
              }
              priceInGrosze={product.price}
              previousPriceInGrosze={product.compare_at_price ?? undefined}
              lowestPriceInGrosze={
                product.compare_at_price
                  ? (product.lowest_price_before_discount ?? null)
                  : undefined
              }
              title={product.name}
              type={productTypeLabel(product)}
            />
          );
        })}
      </div>
    </section>
  );
}

export function CartPageClient() {
  const { acceptConfirmedCount } = useCartCount();
  const [cart, setCart] = useState<CartView | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [dismissingReport, setDismissingReport] = useState(false);
  const [products, setProducts] = useState<CatalogListItem[]>([]);
  const [voucherSlug, setVoucherSlug] = useState<string | null>(null);
  const [email, setEmail] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, number>>({});
  const [pending, setPending] = useState<Record<string, boolean>>({});
  const [removing, setRemoving] = useState<Record<string, boolean>>({});
  const [announcement, setAnnouncement] = useState("");
  const [giftPending, setGiftPending] = useState<Record<string, boolean>>({});
  const timers = useRef(new Map<string, ReturnType<typeof setTimeout>>());
  const draftsRef = useRef(new Map<string, number>());
  const revisions = useRef(new Map<string, number>());
  const removingIds = useRef(new Set<string>());
  const queue = useRef<Promise<unknown>>(Promise.resolve());
  const listHeading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    let active = true;
    const base = apiBase();
    if (!base) {
      setError("Serwer koszyka nie jest skonfigurowany.");
      setLoadState("error");
      return () => {
        active = false;
      };
    }
    void Promise.all([
      fetch(`${base}/cart`, { credentials: "include", cache: "no-store" }),
      fetch(`${base}/products?sort=recommended&per_page=12`, {
        cache: "no-store",
      }),
      fetch(`${base}/catalog/public/search-presentation`, {
        cache: "no-store",
      }),
    ])
      .then(async ([cartResponse, productsResponse, contactResponse]) => {
        if (!cartResponse.ok) throw new Error(await readError(cartResponse));
        const cartValue = (await cartResponse.json()) as CartView;
        if (!active) return;
        setCart(cartValue);
        acceptConfirmedCount(cartValue.item_count);
        setLoadState("ready");
        if (productsResponse.ok) {
          try {
            const result = parseCatalogList(await productsResponse.json());
            setProducts(result.items);
            setVoucherSlug(
              result.items.find((product) => product.kind === "VOUCHER")
                ?.slug ?? null,
            );
          } catch {
            setProducts([]);
          }
        }
        if (contactResponse.ok) {
          try {
            const settings = (await contactResponse.json()) as ContactSettings;
            setEmail(settings.contact_email);
          } catch {
            setEmail(null);
          }
        }
      })
      .catch((cause: unknown) => {
        if (!active) return;
        setError(
          cause instanceof Error
            ? cause.message
            : "Nie udało się pobrać koszyka.",
        );
        setLoadState("error");
      });
    return () => {
      active = false;
    };
  }, [acceptConfirmedCount]);

  useEffect(
    () => () => {
      for (const timer of timers.current.values()) clearTimeout(timer);
      timers.current.clear();
    },
    [],
  );

  const mutate = useCallback<CartMutation>(
    (method, path, body) => {
      const operation = queue.current
        .catch(() => undefined)
        .then(async () => {
          const base = apiBase();
          if (!base) throw new Error("Serwer koszyka nie jest skonfigurowany.");
          const response = await fetch(`${base}/cart${path}`, {
            method,
            credentials: "include",
            headers: body ? { "Content-Type": "application/json" } : undefined,
            body: body ? JSON.stringify(body) : undefined,
            cache: "no-store",
          });
          if (!response.ok) throw new Error(await readError(response));
          const next = (await response.json()) as CartView;
          setCart(next);
          acceptConfirmedCount(next.item_count);
          setError(null);
          return next;
        });
      queue.current = operation;
      return operation;
    },
    [acceptConfirmedCount],
  );

  async function dismissReorderSummary() {
    const report = cart?.reorder_report;
    if (!report || dismissingReport) return;
    setDismissingReport(true);
    try {
      const response = await fetch(
        `${apiBase()}/cart/reorder-report/${encodeURIComponent(report.operation_id)}/dismiss`,
        { method: "POST", credentials: "include", cache: "no-store" },
      );
      if (!response.ok) throw new Error(await readError(response));
      setCart((current) =>
        current ? { ...current, reorder_report: null } : current,
      );
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Nie udało się zamknąć podsumowania.",
      );
    } finally {
      setDismissingReport(false);
    }
  }

  function setQuantity(item: CartItem, desiredQuantity: number) {
    if (desiredQuantity < 1 || removingIds.current.has(item.id)) return;
    const revision = (revisions.current.get(item.id) ?? 0) + 1;
    revisions.current.set(item.id, revision);
    draftsRef.current.set(item.id, desiredQuantity);
    setDrafts((current) => ({ ...current, [item.id]: desiredQuantity }));
    setPending((current) => ({ ...current, [item.id]: true }));
    const prior = timers.current.get(item.id);
    if (prior) clearTimeout(prior);
    timers.current.set(
      item.id,
      setTimeout(() => {
        timers.current.delete(item.id);
        const quantity = draftsRef.current.get(item.id) ?? item.quantity;
        const requestRevision = revisions.current.get(item.id) ?? revision;
        void mutate("PATCH", `/items/${encodeURIComponent(item.id)}`, {
          quantity,
        })
          .then((next) =>
            setAnnouncement(
              `Zmieniono ilość. Suma koszyka: ${formatGrosz(next.calculation.amount_due_grosz)}.`,
            ),
          )
          .catch((cause: unknown) =>
            setError(
              cause instanceof Error
                ? cause.message
                : "Nie udało się zmienić ilości.",
            ),
          )
          .finally(() => {
            if (revisions.current.get(item.id) === requestRevision) {
              draftsRef.current.delete(item.id);
              setDrafts((current) => {
                const next = { ...current };
                delete next[item.id];
                return next;
              });
              setPending((current) => {
                const next = { ...current };
                delete next[item.id];
                return next;
              });
            }
          });
      }, 300),
    );
  }

  function remove(item: CartItem) {
    if (removingIds.current.has(item.id)) return;
    removingIds.current.add(item.id);
    const revision = (revisions.current.get(item.id) ?? 0) + 1;
    revisions.current.set(item.id, revision);
    const timer = timers.current.get(item.id);
    if (timer) clearTimeout(timer);
    timers.current.delete(item.id);
    draftsRef.current.delete(item.id);
    setDrafts((current) => {
      const next = { ...current };
      delete next[item.id];
      return next;
    });
    setPending((current) => ({ ...current, [item.id]: true }));
    setRemoving((current) => ({ ...current, [item.id]: true }));
    void mutate("DELETE", `/items/${encodeURIComponent(item.id)}`)
      .then((next) => {
        setAnnouncement(
          `Usunięto ${item.name}. Suma koszyka: ${formatGrosz(next.calculation.amount_due_grosz)}.`,
        );
        requestAnimationFrame(() => {
          const remaining = next.items[0];
          const target = remaining
            ? document.getElementById(`cart-item-${remaining.id}`)
            : null;
          (target ?? listHeading.current)?.focus();
        });
      })
      .catch((cause: unknown) =>
        setError(
          cause instanceof Error
            ? cause.message
            : "Nie udało się usunąć produktu.",
        ),
      )
      .finally(() => {
        if (revisions.current.get(item.id) === revision) {
          removingIds.current.delete(item.id);
          setRemoving((current) => {
            const next = { ...current };
            delete next[item.id];
            return next;
          });
          setPending((current) => {
            const next = { ...current };
            delete next[item.id];
            return next;
          });
        }
      });
  }

  async function toggleGift(item: CartItem, checked: boolean) {
    if (giftPending[item.id]) return;
    setGiftPending((current) => ({ ...current, [item.id]: true }));
    try {
      const next = await mutate(
        "PATCH",
        `/items/${encodeURIComponent(item.id)}/gift`,
        {
          is_gift: checked,
        },
      );
      setAnnouncement(
        checked
          ? "Voucher oznaczono jako prezent."
          : "Wyłączono opcję prezentu.",
      );
      setCart(next);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Nie udało się zmienić opcji prezentu.",
      );
    } finally {
      setGiftPending((current) => ({ ...current, [item.id]: false }));
    }
  }

  if (loadState === "loading") {
    return (
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto min-h-96 max-w-screen-xl px-4 py-10 focus:outline-none"
        aria-busy="true"
      >
        <h1 className="font-display text-title text-ink">Twój koszyk</h1>
        <p role="status" className="text-body text-ink">
          Wczytujemy koszyk…
        </p>
      </main>
    );
  }
  if (loadState === "error" || !cart) {
    return (
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto max-w-screen-xl px-4 py-10 focus:outline-none"
      >
        <h1 className="text-title text-ink">Nie udało się wczytać koszyka</h1>
        <p role="alert" className="mt-4 text-body text-on-danger">
          {error}
        </p>
        <button
          type="button"
          className="mt-4 min-h-touch rounded-pill border border-accent-action px-5 text-label text-ink"
          onClick={() => window.location.reload()}
        >
          Spróbuj ponownie
        </button>
      </main>
    );
  }

  if (cart.items.length === 0) {
    return (
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto w-full max-w-screen-xl px-4 py-10 focus:outline-none"
      >
        <nav
          aria-label="Okruszki nawigacyjne"
          className="mb-6 text-caption text-ink-muted"
        >
          <Link href="/sklep">Sklep</Link>
          <span aria-hidden="true"> / </span>
          <span aria-current="page">Koszyk</span>
        </nav>
        <section className="mx-auto max-w-3xl rounded-card bg-surface-muted px-6 py-10 text-center sm:px-10">
          <div
            aria-hidden="true"
            className="mx-auto mb-5 flex h-control-lg w-control-lg items-center justify-center rounded-pill bg-accent-action text-surface"
          >
            <svg
              className="h-8 w-8"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M3 4h2l2.4 11.2a2 2 0 0 0 2 1.6h7.8a2 2 0 0 0 2-1.6L21 8H6" />
              <circle cx="10" cy="20" r="1" />
              <circle cx="18" cy="20" r="1" />
            </svg>
          </div>
          <h1 className="font-display text-title text-ink">
            Twój koszyk jest jeszcze pusty
          </h1>
          <p className="mx-auto mt-4 max-w-prose text-body text-ink-muted">
            Nic straconego. Poniżej materiały, od których zaczyna większość osób
            — a jeśli nie wiesz, co wybrać, po prostu napisz do nas.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Link
              href="/sklep"
              className="inline-flex min-h-touch items-center justify-center rounded-pill bg-accent-action px-5 text-label font-bold text-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
            >
              Zobacz wszystkie materiały
            </Link>
            {voucherSlug ? (
              <Link
                href={`/sklep/${encodeURIComponent(voucherSlug)}`}
                className="inline-flex min-h-touch items-center justify-center rounded-pill border border-accent-action px-5 text-label text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
              >
                Kup voucher na wizytę
              </Link>
            ) : null}
          </div>
        </section>
        <ProductRecommendations
          products={products}
          cart={cart}
          mutate={mutate}
          title="Polecane materiały"
          showAdd={false}
        />
        {email ? (
          <p className="mt-10 text-center text-body text-ink-muted">
            Nie wiesz, co będzie dla Ciebie odpowiednie? Napisz:{" "}
            <a
              className="underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
              href={`mailto:${encodeURIComponent(email)}`}
            >
              {email}
            </a>{" "}
            <a
              className="ml-2 inline-flex min-h-touch items-center underline"
              href={`mailto:${encodeURIComponent(email)}`}
            >
              Zadaj pytanie
            </a>
          </p>
        ) : null}
      </main>
    );
  }

  return (
    <main
      id="main-content"
      tabIndex={-1}
      className="mx-auto w-full max-w-screen-xl px-4 py-10 focus:outline-none"
    >
      <nav
        aria-label="Okruszki nawigacyjne"
        className="mb-6 text-caption text-ink-muted"
      >
        <Link href="/sklep">Sklep</Link>
        <span aria-hidden="true"> / </span>
        <span aria-current="page">Koszyk</span>
      </nav>
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-caption font-bold tracking-wide text-accent-action">
            KROK 1 Z 2
          </p>
          <h1
            ref={listHeading}
            tabIndex={-1}
            className="mt-2 font-display text-title text-ink"
          >
            Twój koszyk
          </h1>
        </div>
        <p className="text-body text-ink-muted">
          {productCountLabel(cart.item_count)}
        </p>
      </div>
      {cart.reorder_report ? (
        <ReorderSummary
          report={cart.reorder_report}
          onDismiss={() => void dismissReorderSummary()}
        />
      ) : null}
      {error ? (
        <p role="alert" className="mb-4 text-body text-on-danger">
          {error}
        </p>
      ) : null}
      <p className="sr-only" aria-live="polite">
        {announcement}
      </p>
      <div className="grid min-w-0 gap-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div
          className="min-w-0 space-y-4"
          aria-busy={Object.values(pending).some(Boolean)}
        >
          {cart.items.map((item) => (
            <div key={item.id} id={`cart-item-${item.id}`} tabIndex={-1}>
              <CartLine
                item={item}
                pendingQuantity={drafts[item.id]}
                removing={Boolean(removing[item.id])}
                onQuantity={setQuantity}
                onRemove={remove}
                onToggleGift={toggleGift}
              />
            </div>
          ))}
          {Object.values(pending).some(Boolean) ? (
            <p role="status" className="text-caption text-ink-muted">
              Przeliczamy koszyk…
            </p>
          ) : null}
        </div>
        <div className="min-w-0 space-y-4 lg:sticky lg:top-24 lg:self-start">
          <DiscountSummary cart={cart} mutate={mutate} />
          <div className="space-y-3">
            <Link
              href="/zamowienie"
              aria-disabled={
                !cart.calculation.amount_due_is_final ||
                Object.values(pending).some(Boolean)
              }
              onClick={(event) => {
                if (
                  !cart.calculation.amount_due_is_final ||
                  Object.values(pending).some(Boolean)
                )
                  event.preventDefault();
              }}
              className={`inline-flex min-h-touch w-full items-center justify-center rounded-pill bg-accent-action px-5 text-label font-bold text-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action ${!cart.calculation.amount_due_is_final || Object.values(pending).some(Boolean) ? "pointer-events-none opacity-50" : ""}`}
            >
              Przejdź do płatności
            </Link>
            <Link
              href="/sklep"
              className="inline-flex min-h-touch w-full items-center justify-center rounded-pill border border-accent-action px-5 text-label text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
            >
              Kontynuuj zakupy
            </Link>
          </div>
          <ul className="space-y-2 text-caption text-ink-muted">
            <li>Pliki cyfrowe dostaniesz od razu po opłaceniu.</li>
            <li>Książki wysyłamy w 2 dni robocze.</li>
            <li>Nie musisz zakładać konta.</li>
          </ul>
        </div>
      </div>
      <ProductRecommendations
        products={products}
        cart={cart}
        mutate={mutate}
        title="Polecane do koszyka"
        showAdd
      />
    </main>
  );
}

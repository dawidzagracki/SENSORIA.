"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { Button, Checkbox, Modal, RadioCard } from "@/components/ui";
import type { CartView } from "@/components/cart/cart-types";
import type { PickupPointSnapshot } from "@/components/cart/cart-types";
import { useCartCount } from "@/components/layout/cart-count-provider";

type CheckoutConfig = {
  consent_version: string;
  terms_text: string;
  digital_text: string;
  marketing_text: string;
};
type LoadState = "loading" | "ready" | "error";
type Address = { street: string; postal_code: string; city: string };
type SavedAddress = {
  id: string;
  label: string;
  address_type: "address" | "parcel_locker";
  is_default: boolean;
  street?: string;
  postal_code?: string;
  city?: string;
  code?: string;
};
type CheckoutResult = {
  status: string;
  message: string;
  amount_due_grosz: number;
  order_id: string;
  access_token: string;
  payment_integration: string;
};
type DeliveryMethod = "parcel_locker" | "courier" | "pickup_in_person";
type GiftDraft = {
  recipient_name: string;
  recipient_email: string;
  dedication: string;
  delivery_mode: "immediate" | "scheduled";
  delivery_date: string;
};

function todayWarsaw(): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Warsaw",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const value = Object.fromEntries(
    parts.map((part) => [part.type, part.value]),
  );
  return `${value.year}-${value.month}-${value.day}`;
}

function money(grosz: number): string {
  if (!Number.isSafeInteger(grosz)) return "—";
  return `${Math.trunc(grosz / 100)},${String(Math.abs(grosz % 100)).padStart(2, "0")} zł`;
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const data = (await response.json()) as { error?: { message?: string } };
    return data.error?.message ?? "Nie udało się złożyć zamówienia.";
  } catch {
    return "Nie udało się złożyć zamówienia.";
  }
}

function AddressFields({
  prefix,
  value,
  onChange,
}: {
  prefix: string;
  value: Address;
  onChange: (value: Address) => void;
}) {
  return (
    <div className="grid min-w-0 gap-4 sm:grid-cols-2">
      {(["street", "postal_code", "city"] as const).map((key) => {
        const labels = {
          street: "Ulica i numer",
          postal_code: "Kod pocztowy",
          city: "Miejscowość",
        };
        return (
          <label key={key} className="block min-w-0 text-label text-ink">
            {labels[key]}
            <input
              required
              autoComplete={
                key === "street"
                  ? "street-address"
                  : key === "postal_code"
                    ? "postal-code"
                    : "address-level2"
              }
              value={value[key]}
              onChange={(event) =>
                onChange({ ...value, [key]: event.target.value })
              }
              className="mt-2 min-h-touch w-full min-w-0 rounded-control border border-border bg-surface px-3 text-body text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
              name={`${prefix}_${key}`}
            />
          </label>
        );
      })}
    </div>
  );
}

export function CheckoutPage() {
  const formId = useId();
  const { acceptConfirmedCount } = useCartCount();
  const idempotencyKey = useRef<string | null>(null);
  const [cart, setCart] = useState<CartView | null>(null);
  const [config, setConfig] = useState<CheckoutConfig | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [error, setError] = useState("");
  const [result, setResult] = useState<CheckoutResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [email, setEmail] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");
  const [deliveryMethod, setDeliveryMethod] = useState<DeliveryMethod | null>(
    null,
  );
  const [updatingDelivery, setUpdatingDelivery] = useState(false);
  const [pickupModalOpen, setPickupModalOpen] = useState(false);
  const [pickupQuery, setPickupQuery] = useState("");
  const [pickupCode, setPickupCode] = useState("");
  const [pickupPoints, setPickupPoints] = useState<PickupPointSnapshot[]>([]);
  const [pickupBusy, setPickupBusy] = useState(false);
  const [pickupError, setPickupError] = useState("");
  const [pickupStatus, setPickupStatus] = useState("");
  const [shippingAddress, setShippingAddress] = useState<Address>({
    street: "",
    postal_code: "",
    city: "",
  });
  const [invoiceKind, setInvoiceKind] = useState<"private" | "company">(
    "private",
  );
  const [companyName, setCompanyName] = useState("");
  const [nip, setNip] = useState("");
  const [invoiceAddress, setInvoiceAddress] = useState<Address>({
    street: "",
    postal_code: "",
    city: "",
  });
  const [sameInvoiceAddress, setSameInvoiceAddress] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState("blik");
  const [terms, setTerms] = useState(false);
  const [digitalConsent, setDigitalConsent] = useState(false);
  const [marketing, setMarketing] = useState(false);
  const [reviewRequests, setReviewRequests] = useState(false);
  const [giftDrafts, setGiftDrafts] = useState<Record<string, GiftDraft>>({});
  const [savedAddresses, setSavedAddresses] = useState<SavedAddress[]>([]);
  const [savedAddressMessage, setSavedAddressMessage] = useState("");
  const touchedProfileFields = useRef(new Set<string>());

  useEffect(() => {
    let active = true;
    Promise.all([
      fetch("/api/cart", { credentials: "include", cache: "no-store" }),
      fetch("/api/cart/checkout-config", {
        credentials: "include",
        cache: "no-store",
      }),
      fetch("/api/accounts/checkout-defaults", {
        credentials: "include",
        cache: "no-store",
      }).catch(() => null),
    ])
      .then(async ([cartResponse, configResponse, defaultsResponse]) => {
        if (!cartResponse.ok || !configResponse.ok)
          throw new Error(
            "Nie udało się pobrać koszyka i ustawień zamówienia.",
          );
        const [cartValue, configValue] = (await Promise.all([
          cartResponse.json(),
          configResponse.json(),
        ])) as [CartView, CheckoutConfig];
        if (!active) return;
        setCart(cartValue);
        setConfig(configValue);
        if (defaultsResponse?.ok) {
          const defaults = (await defaultsResponse.json()) as {
            email: string;
            first_name: string;
            last_name: string;
            phone: string | null;
            addresses: SavedAddress[];
          };
          if (Array.isArray(defaults.addresses))
            setSavedAddresses(defaults.addresses);
          if (
            typeof defaults.email === "string" &&
            !touchedProfileFields.current.has("email")
          )
            setEmail(defaults.email);
          if (
            typeof defaults.first_name === "string" &&
            !touchedProfileFields.current.has("first_name")
          )
            setFirstName(defaults.first_name);
          if (
            typeof defaults.last_name === "string" &&
            !touchedProfileFields.current.has("last_name")
          )
            setLastName(defaults.last_name);
          if (
            (typeof defaults.phone === "string" || defaults.phone === null) &&
            !touchedProfileFields.current.has("phone")
          )
            setPhone(defaults.phone ?? "");
        }
        setDeliveryMethod(cartValue.delivery.selected_method);
        acceptConfirmedCount(cartValue.item_count);
        setLoadState("ready");
      })
      .catch(() => {
        if (active) setLoadState("error");
      });
    return () => {
      active = false;
    };
  }, [acceptConfirmedCount]);

  const requiresShipping = Boolean(
    cart?.items.some((item) => item.kind === "BOOK"),
  );
  const containsDigital = Boolean(
    cart?.items.some(
      (item) => item.kind === "DIGITAL" || item.kind === "AUDIOBOOK",
    ),
  );
  const hasCourierAddress = requiresShipping && deliveryMethod === "courier";

  async function searchPickupPoints(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPickupBusy(true);
    setPickupError("");
    const params = new URLSearchParams({ query: pickupQuery.trim() });
    try {
      const response = await fetch(`/api/cart/pickup-points?${params}`, {
        credentials: "include",
        cache: "no-store",
      });
      if (!response.ok) throw new Error(await errorMessage(response));
      const data = (await response.json()) as { items: PickupPointSnapshot[] };
      setPickupPoints(data.items);
      if (data.items.length === 0)
        setPickupStatus("Nie znaleziono punktów w tej lokalizacji.");
    } catch (caught) {
      setPickupError(
        caught instanceof Error
          ? caught.message
          : "Nie udało się wyszukać punktów.",
      );
    } finally {
      setPickupBusy(false);
    }
  }

  async function selectPickupPoint(code: string) {
    setPickupBusy(true);
    setPickupError("");
    setPickupStatus("");
    try {
      const response = await fetch("/api/cart/pickup-point", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code }),
      });
      if (!response.ok) throw new Error(await errorMessage(response));
      const updated = (await response.json()) as CartView;
      setCart(updated);
      setPickupCode("");
      setPickupStatus(`Wybrano punkt ${updated.delivery_point?.code ?? code}.`);
      setPickupModalOpen(false);
      acceptConfirmedCount(updated.item_count);
    } catch (caught) {
      setPickupError(
        caught instanceof Error
          ? caught.message
          : "Nie udało się potwierdzić punktu.",
      );
    } finally {
      setPickupBusy(false);
    }
  }

  async function selectSavedPickupPoint(code: string) {
    setPickupBusy(true);
    setPickupError("");
    setSavedAddressMessage("");
    try {
      const csrfResponse = await fetch("/api/accounts/csrf", {
        credentials: "include",
        cache: "no-store",
      });
      if (!csrfResponse.ok)
        throw new Error("Zaloguj się ponownie, aby użyć zapisanego adresu.");
      const csrf = (await csrfResponse.json()) as { csrf_token: string };
      const response = await fetch("/api/cart/pickup-point", {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": csrf.csrf_token,
        },
        body: JSON.stringify({ code }),
      });
      if (!response.ok) throw new Error(await errorMessage(response));
      const updated = (await response.json()) as CartView;
      setCart(updated);
      acceptConfirmedCount(updated.item_count);
      setSavedAddressMessage(
        "Zapisany punkt został ponownie zweryfikowany i wybrany.",
      );
    } catch (caught) {
      setPickupError(
        caught instanceof Error
          ? caught.message
          : "Nie udało się wybrać zapisanego punktu.",
      );
    } finally {
      setPickupBusy(false);
    }
  }

  async function validatePickupCode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await selectPickupPoint(pickupCode);
  }

  async function chooseDelivery(method: DeliveryMethod) {
    setDeliveryMethod(method);
    setError("");
    setUpdatingDelivery(true);
    try {
      const response = await fetch("/api/cart/delivery", {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ method }),
      });
      if (!response.ok) throw new Error(await errorMessage(response));
      const updated = (await response.json()) as CartView;
      setCart(updated);
      acceptConfirmedCount(updated.item_count);
    } catch (caught) {
      setDeliveryMethod(cart?.delivery.selected_method ?? null);
      setError(
        caught instanceof Error
          ? caught.message
          : "Nie udało się wybrać dostawy.",
      );
    } finally {
      setUpdatingDelivery(false);
    }
  }

  async function toggleGift(itemId: string, isGift: boolean) {
    const response = await fetch(
      `/api/cart/items/${encodeURIComponent(itemId)}/gift`,
      {
        method: "PATCH",
        credentials: "include",
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_gift: isGift }),
      },
    );
    if (!response.ok) throw new Error(await errorMessage(response));
    setCart((await response.json()) as CartView);
    if (!isGift) {
      setGiftDrafts((current) => {
        const next = { ...current };
        delete next[itemId];
        return next;
      });
    }
  }

  function giftDraft(itemId: string): GiftDraft {
    return (
      giftDrafts[itemId] ?? {
        recipient_name: "",
        recipient_email: "",
        dedication: "",
        delivery_mode: "immediate",
        delivery_date: "",
      }
    );
  }

  function updateGift(itemId: string, update: Partial<GiftDraft>) {
    setGiftDrafts((current) => ({
      ...current,
      [itemId]: {
        ...(current[itemId] ?? {
          recipient_name: "",
          recipient_email: "",
          dedication: "",
          delivery_mode: "immediate",
          delivery_date: "",
        }),
        ...update,
      },
    }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!cart || !config || busy) return;
    if (
      requiresShipping &&
      deliveryMethod === "parcel_locker" &&
      !cart.delivery_point
    ) {
      setError("Wybierz Paczkomat InPost przed złożeniem zamówienia.");
      setPickupModalOpen(true);
      return;
    }
    setError("");
    setBusy(true);
    const payload = {
      email,
      ...(requiresShipping
        ? {
            first_name: firstName,
            last_name: lastName,
            phone,
            delivery_method: deliveryMethod,
            ...(hasCourierAddress ? { shipping_address: shippingAddress } : {}),
          }
        : {}),
      invoice_kind: invoiceKind,
      company_name: invoiceKind === "company" ? companyName : null,
      nip: invoiceKind === "company" ? nip : null,
      invoice_address: invoiceKind === "company" ? invoiceAddress : null,
      invoice_same_as_shipping:
        invoiceKind === "company" && sameInvoiceAddress && hasCourierAddress,
      payment_method: paymentMethod,
      terms_accepted: terms,
      digital_consent: containsDigital ? digitalConsent : false,
      marketing_consent: marketing,
      review_requests_consent: reviewRequests,
      consent_version: config.consent_version,
      issuance_mode: "immediate",
      gifts: cart.items
        .filter((item) => item.kind === "VOUCHER" && item.is_gift)
        .map((item) => {
          const gift = giftDraft(item.id);
          return {
            cart_item_id: item.id,
            recipient_name: gift.recipient_name,
            recipient_email: gift.recipient_email || null,
            dedication: gift.dedication,
            delivery_mode: gift.delivery_mode,
            delivery_date:
              gift.delivery_mode === "scheduled" ? gift.delivery_date : null,
          };
        }),
    };
    try {
      const response = await fetch("/api/cart/checkout", {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": (idempotencyKey.current ??= crypto.randomUUID()),
        },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error(await errorMessage(response));
      const created = (await response.json()) as CheckoutResult;
      setResult(created);
      const confirmation = `/zamowienie/potwierdzenie?order=${encodeURIComponent(created.order_id)}&token=${encodeURIComponent(created.access_token)}`;
      if (created.payment_integration === "stripe") {
        // Hosted payment page: card data never touches this site.
        const payment = await fetch(
          `/api/payments/orders/${encodeURIComponent(created.order_id)}/session?token=${encodeURIComponent(created.access_token)}`,
          { method: "POST", credentials: "include" },
        );
        if (payment.ok) {
          const body = (await payment.json()) as { payment_url: string };
          window.location.assign(body.payment_url);
          return;
        }
      }
      window.location.assign(confirmation);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Nie udało się złożyć zamówienia.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (loadState === "loading")
    return (
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto w-full max-w-screen-xl px-4 py-16"
        aria-busy="true"
      >
        <h1 className="font-display text-title text-ink">Zamówienie</h1>
        <p role="status">Wczytujemy koszyk…</p>
      </main>
    );
  if (loadState === "error" || !cart || !config)
    return (
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto w-full max-w-screen-xl px-4 py-16"
      >
        <h1 className="font-display text-title text-ink">
          Nie udało się wczytać zamówienia
        </h1>
        <p className="mt-4 text-body text-ink-muted">
          Spróbuj ponownie za chwilę.
        </p>
        <button
          className="mt-6 min-h-touch rounded-pill border border-border px-5"
          onClick={() => window.location.reload()}
        >
          Spróbuj ponownie
        </button>
      </main>
    );
  if (!cart.items.length)
    return (
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto w-full max-w-screen-xl px-4 py-16"
      >
        <h1 className="font-display text-title text-ink">
          Twój koszyk jest pusty
        </h1>
        <Link
          href="/koszyk"
          className="mt-6 inline-flex min-h-touch items-center text-accent-action underline"
        >
          Wróć do koszyka
        </Link>
      </main>
    );

  return (
    <main
      id="main-content"
      tabIndex={-1}
      className="mx-auto w-full max-w-screen-xl min-w-0 px-4 py-8 focus:outline-none sm:py-12"
    >
      <nav
        aria-label="Okruszki nawigacyjne"
        className="mb-6 text-caption text-ink-muted"
      >
        <Link href="/koszyk">Koszyk</Link>
        <span aria-hidden="true"> → </span>
        <span aria-current="page">Zamówienie</span>
      </nav>
      <p className="text-caption font-bold tracking-wide text-accent-action">
        KROK 2 Z 2
      </p>
      <h1 className="mt-2 font-display text-title text-ink">Zamówienie</h1>
      <ol
        aria-label="Etapy zamówienia"
        className="mt-4 flex flex-wrap gap-2 text-caption text-ink-muted"
      >
        <li>Koszyk</li>
        <li aria-hidden="true">→</li>
        <li aria-current="step">Dane i płatność</li>
        <li aria-hidden="true">→</li>
        <li>Potwierdzenie</li>
      </ol>

      {result ? (
        <section
          role="status"
          className="mt-8 rounded-card border border-warning bg-surface-muted p-5"
        >
          <h2 className="font-display text-title text-ink">
            Przekierowujemy do płatności…
          </h2>
          <p className="mt-2 text-body text-ink">{result.message}</p>
          <p className="mt-2 text-caption text-ink-muted">
            Numer zamówienia: {result.order_id}. Kwota:{" "}
            {money(result.amount_due_grosz)}.
          </p>
        </section>
      ) : null}
      {!result ? (
        <form
          id={formId}
          onSubmit={submit}
          className="mt-8 grid min-w-0 gap-8 lg:grid-cols-[minmax(0,1fr)_22rem]"
        >
          <div className="min-w-0 space-y-8">
            <section className="rounded-card border border-border bg-surface p-5 sm:p-6">
              <h2 className="font-display text-title text-ink">01. Kontakt</h2>
              <label className="mt-5 block text-label text-ink">
                Adres e-mail
                <input
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(event) => {
                    touchedProfileFields.current.add("email");
                    setEmail(event.target.value);
                  }}
                  className="mt-2 min-h-touch w-full rounded-control border border-border px-3 text-body focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
                />
              </label>
              <p className="mt-2 text-caption text-ink-muted">
                Na ten adres wyślemy voucher, pliki i potwierdzenie zamówienia.
              </p>
              <Checkbox
                label={config.marketing_text}
                name="marketing"
                checked={marketing}
                onChange={(event) => setMarketing(event.target.checked)}
                className="mt-4"
              />
              <Checkbox
                label="Prośby o opinię. Zapytamy o zdanie po zakupie. Możesz to wyłączyć w ustawieniach konta."
                name="review_requests"
                checked={reviewRequests}
                onChange={(event) => setReviewRequests(event.target.checked)}
                className="mt-4"
              />
            </section>

            {requiresShipping ? (
              <section className="space-y-5 rounded-card border border-border bg-surface p-5 sm:p-6">
                <div>
                  <h2 className="font-display text-title text-ink">
                    02. Dostawa
                  </h2>
                  <p className="mt-2 text-body text-ink-muted">
                    Twoje zamówienie zawiera książkę, dlatego potrzebujemy
                    danych do wysyłki. Voucher i materiały cyfrowe są niezależne
                    od przesyłki.
                  </p>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <label className="text-label text-ink">
                    Imię
                    <input
                      required
                      autoComplete="given-name"
                      value={firstName}
                      onChange={(event) => {
                        touchedProfileFields.current.add("first_name");
                        setFirstName(event.target.value);
                      }}
                      className="mt-2 min-h-touch w-full rounded-control border border-border px-3"
                    />
                  </label>
                  <label className="text-label text-ink">
                    Nazwisko
                    <input
                      required
                      autoComplete="family-name"
                      value={lastName}
                      onChange={(event) => {
                        touchedProfileFields.current.add("last_name");
                        setLastName(event.target.value);
                      }}
                      className="mt-2 min-h-touch w-full rounded-control border border-border px-3"
                    />
                  </label>
                  <label className="text-label text-ink sm:col-span-2">
                    Telefon
                    <input
                      required
                      type="tel"
                      autoComplete="tel"
                      value={phone}
                      onChange={(event) => {
                        touchedProfileFields.current.add("phone");
                        setPhone(event.target.value);
                      }}
                      className="mt-2 min-h-touch w-full rounded-control border border-border px-3"
                    />
                  </label>
                </div>
                <fieldset className="space-y-3">
                  <legend className="font-bold text-label text-ink">
                    Metoda dostawy
                  </legend>
                  {cart.delivery.available_quotes.map((quote) => (
                    <RadioCard
                      key={quote.method}
                      name="delivery"
                      value={quote.method}
                      checked={deliveryMethod === quote.method}
                      onChange={() => void chooseDelivery(quote.method)}
                      title={
                        quote.method === "parcel_locker"
                          ? "Paczkomat InPost"
                          : quote.method === "pickup_in_person"
                            ? "Odbiór w gabinecie"
                            : "Kurier InPost"
                      }
                      description={
                        quote.method === "pickup_in_person"
                          ? "Bezpłatnie · ul. Knosały 7B/A, Olsztyn. Powiadomimy Cię, gdy zamówienie będzie gotowe."
                          : `${money(quote.gross_grosz)} · ${quote.vat_label}`
                      }
                      disabled={updatingDelivery}
                    />
                  ))}
                  {updatingDelivery ? (
                    <p role="status" className="text-caption text-ink-muted">
                      Aktualizujemy koszt dostawy…
                    </p>
                  ) : null}
                </fieldset>
                {deliveryMethod === "courier" ? (
                  <div className="space-y-3">
                    {savedAddresses.some(
                      (address) => address.address_type === "address",
                    ) && (
                      <label className="block text-label text-ink">
                        Użyj zapisanego adresu
                        <select
                          aria-label="Wybierz zapisany adres do wysyłki kurierem"
                          defaultValue=""
                          onChange={(event) => {
                            const selected = savedAddresses.find(
                              (address) =>
                                address.id === event.target.value &&
                                address.address_type === "address",
                            );
                            if (selected)
                              setShippingAddress({
                                street: selected.street ?? "",
                                postal_code: selected.postal_code ?? "",
                                city: selected.city ?? "",
                              });
                          }}
                          className="mt-2 min-h-touch w-full rounded-control border border-border bg-surface px-3"
                        >
                          <option value="">Wpiszę nowy adres</option>
                          {savedAddresses
                            .filter(
                              (address) => address.address_type === "address",
                            )
                            .map((address) => (
                              <option key={address.id} value={address.id}>
                                {address.label}
                                {address.is_default ? " · domyślny" : ""}
                              </option>
                            ))}
                        </select>
                      </label>
                    )}
                    <AddressFields
                      prefix="shipping"
                      value={shippingAddress}
                      onChange={setShippingAddress}
                    />
                  </div>
                ) : null}
                {deliveryMethod === "parcel_locker" ? (
                  <div className="space-y-3 rounded-control border border-border bg-surface-muted p-4">
                    {cart.delivery_point ? (
                      <div aria-live="polite">
                        <p className="font-bold text-label text-ink">
                          {cart.delivery_point.code} ·{" "}
                          {cart.delivery_point.name}
                        </p>
                        <p className="mt-1 break-words text-caption text-ink-muted">
                          {cart.delivery_point.street},{" "}
                          {cart.delivery_point.postal_code}{" "}
                          {cart.delivery_point.city}
                        </p>
                        {cart.delivery_point.opening_hours ? (
                          <p className="mt-1 text-caption text-ink-muted">
                            Godziny: {cart.delivery_point.opening_hours}
                          </p>
                        ) : null}
                      </div>
                    ) : (
                      <p className="text-caption text-danger">
                        Wybierz punkt odbioru. Bez potwierdzonego Paczkomatu nie
                        można złożyć zamówienia.
                      </p>
                    )}
                    {savedAddresses.some(
                      (address) => address.address_type === "parcel_locker",
                    ) && (
                      <label className="block text-label text-ink">
                        Wybierz zapisany Paczkomat
                        <select
                          aria-label="Wybierz zapisany Paczkomat"
                          defaultValue=""
                          disabled={pickupBusy}
                          onChange={(event) => {
                            if (event.target.value)
                              void selectSavedPickupPoint(event.target.value);
                          }}
                          className="mt-2 min-h-touch w-full rounded-control border border-border bg-surface px-3"
                        >
                          <option value="">Wybierz zapisany punkt…</option>
                          {savedAddresses
                            .filter(
                              (address) =>
                                address.address_type === "parcel_locker",
                            )
                            .map((address) => (
                              <option key={address.id} value={address.code}>
                                {address.label}
                                {address.is_default ? " · domyślny" : ""}
                              </option>
                            ))}
                        </select>
                      </label>
                    )}
                    {savedAddressMessage && (
                      <p role="status" className="text-caption text-ink-muted">
                        {savedAddressMessage}
                      </p>
                    )}
                    <Button
                      onClick={() => {
                        setPickupError("");
                        setPickupModalOpen(true);
                      }}
                      size="sm"
                      variant="secondary"
                    >
                      {cart.delivery_point
                        ? "Zmień Paczkomat"
                        : "Wybierz Paczkomat"}
                    </Button>
                  </div>
                ) : null}
              </section>
            ) : null}

            {cart.items.some((item) => item.kind === "VOUCHER") ? (
              <section className="space-y-5 rounded-card border border-border bg-surface p-5 sm:p-6">
                <div>
                  <h2 className="font-display text-title text-ink">
                    Dane prezentowe
                  </h2>
                  <p className="mt-2 text-body-small text-ink-muted">
                    Każdy voucher ma osobne dane. Bez e-maila obdarowanej
                    dokument trafi do Ciebie.
                  </p>
                </div>
                {cart.items
                  .filter((item) => item.kind === "VOUCHER")
                  .map((item) => (
                    <article
                      key={item.id}
                      className="space-y-4 rounded-control border border-border p-4"
                    >
                      <Checkbox
                        checked={item.is_gift}
                        label="Kupuję w prezencie"
                        description={item.name}
                        onChange={(event) => {
                          setError("");
                          void toggleGift(
                            item.id,
                            event.currentTarget.checked,
                          ).catch((cause: unknown) =>
                            setError(
                              cause instanceof Error
                                ? cause.message
                                : "Nie udało się zmienić opcji prezentu.",
                            ),
                          );
                        }}
                      />
                      {item.is_gift
                        ? (() => {
                            const draft = giftDraft(item.id);
                            return (
                              <div className="grid min-w-0 gap-4 sm:grid-cols-2">
                                <label className="block min-w-0 text-label text-ink">
                                  Imię obdarowanej osoby{" "}
                                  <span aria-hidden="true">*</span>
                                  <input
                                    required
                                    maxLength={160}
                                    autoComplete="off"
                                    value={draft.recipient_name}
                                    onChange={(event) =>
                                      updateGift(item.id, {
                                        recipient_name: event.target.value,
                                      })
                                    }
                                    className="mt-2 min-h-touch w-full min-w-0 rounded-control border border-border px-3"
                                  />
                                </label>
                                <label className="block min-w-0 text-label text-ink">
                                  E-mail obdarowanej osoby (opcjonalnie)
                                  <input
                                    type="email"
                                    autoComplete="email"
                                    value={draft.recipient_email}
                                    onChange={(event) =>
                                      updateGift(item.id, {
                                        recipient_email: event.target.value,
                                      })
                                    }
                                    className="mt-2 min-h-touch w-full min-w-0 rounded-control border border-border px-3"
                                  />
                                </label>
                                <label className="block min-w-0 text-label text-ink sm:col-span-2">
                                  Dedykacja (opcjonalnie)
                                  <textarea
                                    maxLength={300}
                                    value={draft.dedication}
                                    onChange={(event) =>
                                      updateGift(item.id, {
                                        dedication: event.target.value,
                                      })
                                    }
                                    className="mt-2 min-h-24 w-full min-w-0 rounded-control border border-border p-3"
                                    aria-describedby={`gift-dedication-count-${item.id}`}
                                  />
                                  <span
                                    id={`gift-dedication-count-${item.id}`}
                                    className="mt-1 block text-caption text-ink-muted"
                                  >
                                    {draft.dedication.length}/300 znaków
                                  </span>
                                </label>
                                <fieldset className="space-y-2 sm:col-span-2">
                                  <legend className="font-bold text-label text-ink">
                                    Termin wysyłki
                                  </legend>
                                  <label className="flex min-h-touch items-center gap-3">
                                    <input
                                      type="radio"
                                      name={`gift-mode-${item.id}`}
                                      checked={
                                        draft.delivery_mode === "immediate"
                                      }
                                      onChange={() =>
                                        updateGift(item.id, {
                                          delivery_mode: "immediate",
                                          delivery_date: "",
                                        })
                                      }
                                    />
                                    Od razu
                                  </label>
                                  <label className="flex min-h-touch items-center gap-3">
                                    <input
                                      type="radio"
                                      name={`gift-mode-${item.id}`}
                                      checked={
                                        draft.delivery_mode === "scheduled"
                                      }
                                      onChange={() =>
                                        updateGift(item.id, {
                                          delivery_mode: "scheduled",
                                        })
                                      }
                                    />
                                    W wybranym dniu
                                  </label>
                                  {draft.delivery_mode === "scheduled" ? (
                                    <label className="block text-label text-ink">
                                      Dzień wysyłki
                                      <input
                                        type="date"
                                        required
                                        min={todayWarsaw()}
                                        value={draft.delivery_date}
                                        onChange={(event) =>
                                          updateGift(item.id, {
                                            delivery_date: event.target.value,
                                          })
                                        }
                                        className="mt-2 min-h-touch w-full rounded-control border border-border px-3"
                                      />
                                      <span className="mt-1 block text-caption text-ink-muted">
                                        Wysyłka jest planowana na 09:00 czasu
                                        Europe/Warsaw. Jeśli wybierzesz dziś po
                                        tej godzinie, wyślemy możliwie szybko.
                                      </span>
                                    </label>
                                  ) : null}
                                </fieldset>
                              </div>
                            );
                          })()
                        : null}
                    </article>
                  ))}
              </section>
            ) : null}

            <section className="space-y-5 rounded-card border border-border bg-surface p-5 sm:p-6">
              <h2 className="font-display text-title text-ink">
                {requiresShipping ? "03." : "02."} Dane do faktury
              </h2>
              <fieldset className="grid gap-3 sm:grid-cols-2">
                <legend className="mb-3 font-bold text-label text-ink">
                  Dane nabywcy
                </legend>
                <RadioCard
                  name="invoice_kind"
                  value="private"
                  checked={invoiceKind === "private"}
                  onChange={() => setInvoiceKind("private")}
                  title="Osoba prywatna"
                  description="Zakup prywatny"
                />
                <RadioCard
                  name="invoice_kind"
                  value="company"
                  checked={invoiceKind === "company"}
                  onChange={() => setInvoiceKind("company")}
                  title="Firma"
                  description="Dane firmy i NIP"
                />
              </fieldset>
              {invoiceKind === "company" ? (
                <div className="space-y-4">
                  <label className="block text-label text-ink">
                    Nazwa firmy
                    <input
                      required
                      value={companyName}
                      onChange={(event) => setCompanyName(event.target.value)}
                      className="mt-2 min-h-touch w-full rounded-control border border-border px-3"
                    />
                  </label>
                  <label className="block text-label text-ink">
                    NIP
                    <input
                      required
                      inputMode="numeric"
                      autoComplete="tax-id"
                      value={nip}
                      onChange={(event) => setNip(event.target.value)}
                      className="mt-2 min-h-touch w-full rounded-control border border-border px-3"
                    />
                  </label>
                  {hasCourierAddress ? (
                    <Checkbox
                      label="Adres do faktury taki sam jak do wysyłki"
                      name="same-invoice-address"
                      checked={sameInvoiceAddress}
                      onChange={(event) =>
                        setSameInvoiceAddress(event.target.checked)
                      }
                    />
                  ) : null}
                  {!sameInvoiceAddress || !hasCourierAddress ? (
                    <AddressFields
                      prefix="invoice"
                      value={invoiceAddress}
                      onChange={setInvoiceAddress}
                    />
                  ) : null}
                </div>
              ) : null}
            </section>

            <section className="space-y-4 rounded-card border border-border bg-surface p-5 sm:p-6">
              <h2 className="font-display text-title text-ink">
                {requiresShipping ? "04." : "03."} Płatność
              </h2>
              <fieldset className="space-y-3">
                <legend className="mb-3 font-bold text-label text-ink">
                  Wybierz metodę płatności
                </legend>
                <RadioCard
                  name="payment"
                  value="blik"
                  checked={paymentMethod === "blik"}
                  onChange={() => setPaymentMethod("blik")}
                  title="BLIK"
                  description="Wpisujesz sześć cyfr z aplikacji banku"
                />
                <RadioCard
                  name="payment"
                  value="card"
                  checked={paymentMethod === "card"}
                  onChange={() => setPaymentMethod("card")}
                  title="Karta płatnicza"
                  description="Visa, Mastercard"
                />
                <RadioCard
                  name="payment"
                  value="wallet"
                  checked={paymentMethod === "wallet"}
                  onChange={() => setPaymentMethod("wallet")}
                  title="Google Pay lub Apple Pay"
                  description="Płatność jednym dotknięciem"
                />
              </fieldset>
              <p className="text-caption text-ink-muted">
                Płatność obsługuje bezpieczny operator (Stripe). Dane karty nie
                trafiają do naszego sklepu.
              </p>
            </section>

            <section className="space-y-4 rounded-card border border-border bg-surface p-5 sm:p-6">
              <h2 className="font-display text-title text-ink">
                {requiresShipping ? "05." : "04."} Zgody
              </h2>
              <Checkbox
                label={config.terms_text}
                name="terms"
                required
                checked={terms}
                onChange={(event) => setTerms(event.target.checked)}
              />
              <p className="ml-11 text-caption text-ink-muted">
                Wszystkie zgody są domyślnie niezaznaczone.
              </p>
              {containsDigital ? (
                <Checkbox
                  label={config.digital_text}
                  name="digital-consent"
                  required
                  checked={digitalConsent}
                  onChange={(event) => setDigitalConsent(event.target.checked)}
                />
              ) : null}
            </section>
            {error ? (
              <p
                role="alert"
                className="rounded-control border border-danger p-3 text-body text-danger"
              >
                {error}
              </p>
            ) : null}
          </div>

          <aside className="min-w-0 space-y-5 lg:sticky lg:top-24 lg:self-start">
            <section className="space-y-4 rounded-card border border-border bg-surface p-5">
              <h2 className="font-display text-title text-ink">
                Twoje zamówienie
              </h2>
              <ul className="divide-y divide-border">
                {cart.items.map((item) => (
                  <li key={item.id} className="flex min-w-0 gap-3 py-3">
                    <div className="relative h-16 w-14 shrink-0 overflow-hidden rounded-control bg-surface-muted">
                      {item.image ? (
                        <Image
                          src={item.image.url}
                          alt=""
                          fill
                          sizes="56px"
                          className="object-cover"
                        />
                      ) : null}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="break-words text-label font-bold text-ink">
                        {item.name}
                      </p>
                      <p className="text-caption text-ink-muted">
                        {item.variant_kind === "IN_PERSON"
                          ? "w gabinecie"
                          : item.variant_kind === "ONLINE"
                            ? "online"
                            : item.details}{" "}
                        · {item.quantity} szt.
                      </p>
                    </div>
                    <span className="shrink-0 text-label text-ink">
                      {money(
                        cart.calculation.items.find(
                          (line) => line.item_id === item.id,
                        )?.gross_grosz ?? 0,
                      )}
                    </span>
                  </li>
                ))}
              </ul>
              <div className="space-y-2 border-t border-border pt-4 text-caption text-ink">
                <div className="flex justify-between gap-3">
                  <span>Produkty</span>
                  <span>{money(cart.calculation.products_gross_grosz)}</span>
                </div>
                {cart.calculation.discount_grosz > 0 ? (
                  <div className="flex justify-between gap-3">
                    <span>Rabat {cart.calculation.discount_code}</span>
                    <span>−{money(cart.calculation.discount_grosz)}</span>
                  </div>
                ) : null}
                {requiresShipping ? (
                  <div className="flex justify-between gap-3">
                    <span>Dostawa</span>
                    <span>
                      {cart.calculation.delivery.resolved
                        ? money(cart.calculation.delivery.gross_grosz)
                        : "Do wyboru"}
                    </span>
                  </div>
                ) : null}
                {requiresShipping &&
                deliveryMethod === "parcel_locker" &&
                cart.delivery_point ? (
                  <div className="rounded-control bg-surface-muted p-3 text-caption text-ink">
                    <strong>Punkt odbioru</strong>
                    <br />
                    {cart.delivery_point.code} · {cart.delivery_point.street},{" "}
                    {cart.delivery_point.postal_code} {cart.delivery_point.city}
                  </div>
                ) : null}
                {cart.calculation.exempt.gross_grosz > 0 ? (
                  <div className="flex justify-between gap-3">
                    <span>Sprzedaż zwolniona z VAT</span>
                    <span>{money(cart.calculation.exempt.gross_grosz)}</span>
                  </div>
                ) : null}
                {cart.calculation.vat_groups
                  .filter((group) => group.gross_grosz > 0)
                  .map((group) => (
                    <div
                      key={group.vat_rate}
                      className="flex justify-between gap-3"
                    >
                      <span>VAT {group.vat_label}</span>
                      <span>{money(group.tax_grosz)}</span>
                    </div>
                  ))}
                <div className="flex justify-between gap-3 border-t border-border pt-3 font-bold">
                  <span>Do zapłaty</span>
                  <span>{money(cart.calculation.amount_due_grosz)}</span>
                </div>
              </div>
              <button
                type="submit"
                form={formId}
                disabled={
                  busy ||
                  updatingDelivery ||
                  (requiresShipping && !deliveryMethod)
                }
                className="inline-flex min-h-touch w-full items-center justify-center rounded-pill bg-accent-action px-5 font-bold text-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action disabled:cursor-not-allowed disabled:opacity-60"
              >
                {busy ? "Zapisujemy zamówienie…" : "Zamawiam i płacę"}
              </button>
              <p className="text-caption text-ink-muted">
                Nie musisz zakładać konta. Po kliknięciu przejdziesz do
                bezpiecznej płatności.
              </p>
            </section>
          </aside>
        </form>
      ) : null}
      <Modal
        open={pickupModalOpen}
        onOpenChange={setPickupModalOpen}
        title="Wybierz Paczkomat InPost"
      >
        <div className="min-w-0 space-y-5">
          <p className="text-caption text-ink-muted">
            Wyszukaj po mieście lub kodzie pocztowym. Punkt potwierdza serwer
            bezpośrednio w API InPost.
          </p>
          <form className="space-y-3" onSubmit={searchPickupPoints}>
            <label className="block text-label text-ink" htmlFor="pickup-query">
              Miasto lub kod pocztowy
              <input
                id="pickup-query"
                autoComplete="postal-code"
                minLength={2}
                maxLength={100}
                required
                value={pickupQuery}
                onChange={(event) => setPickupQuery(event.target.value)}
                className="mt-2 min-h-touch w-full min-w-0 rounded-control border border-border px-3 text-body focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
              />
            </label>
            <Button
              disabled={pickupBusy}
              loading={pickupBusy}
              type="submit"
              variant="secondary"
            >
              Szukaj punktów
            </Button>
          </form>
          {pickupPoints.length ? (
            <ul className="space-y-3" aria-label="Wyniki wyszukiwania punktów">
              {pickupPoints.map((point) => (
                <li
                  key={point.code}
                  className="min-w-0 rounded-control border border-border p-3"
                >
                  <p className="break-words font-bold text-label text-ink">
                    {point.code} · {point.name}
                  </p>
                  <p className="mt-1 break-words text-caption text-ink-muted">
                    {point.street}, {point.postal_code} {point.city}
                  </p>
                  {point.opening_hours ? (
                    <p className="mt-1 text-caption text-ink-muted">
                      Godziny: {point.opening_hours}
                    </p>
                  ) : null}
                  <Button
                    className="mt-3"
                    disabled={pickupBusy}
                    onClick={() => void selectPickupPoint(point.code)}
                    size="sm"
                    variant="secondary"
                  >
                    Wybierz ten punkt
                  </Button>
                </li>
              ))}
            </ul>
          ) : null}
          {pickupStatus ? (
            <p role="status" className="text-caption text-ink-muted">
              {pickupStatus}
            </p>
          ) : null}
          <form
            className="space-y-3 border-t border-border pt-4"
            onSubmit={validatePickupCode}
          >
            <h3 className="font-bold text-label text-ink">Wpisz kod punktu</h3>
            <label className="block text-label text-ink" htmlFor="pickup-code">
              Kod Paczkomatu
              <input
                id="pickup-code"
                autoCapitalize="characters"
                maxLength={20}
                minLength={3}
                required
                value={pickupCode}
                onChange={(event) =>
                  setPickupCode(event.target.value.toUpperCase())
                }
                className="mt-2 min-h-touch w-full min-w-0 rounded-control border border-border px-3 text-body focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
              />
            </label>
            <Button disabled={pickupBusy} loading={pickupBusy} type="submit">
              Sprawdź i wybierz
            </Button>
          </form>
          {pickupError ? (
            <p role="alert" className="text-caption text-danger">
              {pickupError}
            </p>
          ) : null}
        </div>
      </Modal>
    </main>
  );
}

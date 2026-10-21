"use client";

import Link from "next/link";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
import { Button } from "@/components/ui/button";
import { PrivacyControls } from "@/components/account/privacy-controls";

const API = process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") || "/api";
type AddressType = "address" | "parcel_locker";
type Address = {
  id: string;
  label: string;
  address_type: AddressType;
  is_default: boolean;
  street?: string;
  building_number?: string;
  apartment_number?: string | null;
  postal_code?: string;
  city?: string;
  country?: string;
  code?: string;
  name?: string;
};
type Profile = {
  first_name: string;
  last_name: string;
  email: string;
  pending_email: string | null;
  email_verified: boolean;
  phone: string | null;
  first_purchase_at: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  addresses: Address[];
};
type AddressDraft = {
  label: string;
  address_type: AddressType;
  street: string;
  building_number: string;
  apartment_number: string;
  postal_code: string;
  city: string;
  country: string;
  point_code: string;
};
const emptyAddress: AddressDraft = {
  label: "",
  address_type: "address",
  street: "",
  building_number: "",
  apartment_number: "",
  postal_code: "",
  city: "",
  country: "PL",
  point_code: "",
};

async function responseMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { error?: { message?: string } };
    return body.error?.message ?? "Nie udało się zapisać zmian.";
  } catch {
    return "Nie udało się zapisać zmian.";
  }
}

function monthYear(value: string | null) {
  if (!value) return "bez dotychczasowych zakupów";
  // "21 października 2026" → "października 2026" (genitive, as "od …" requires).
  return new Intl.DateTimeFormat("pl-PL", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "Europe/Warsaw",
  })
    .format(new Date(value))
    .replace(/^\d+\s/, "");
}

export function AccountDataView() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [draft, setDraft] = useState({
    first_name: "",
    last_name: "",
    phone: "",
  });
  const [savedDraft, setSavedDraft] = useState({
    first_name: "",
    last_name: "",
    phone: "",
  });
  const [emailDraft, setEmailDraft] = useState("");
  const [editAddress, setEditAddress] = useState<Address | null>(null);
  const [addressDraft, setAddressDraft] = useState<AddressDraft>(emptyAddress);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [retry, setRetry] = useState(0);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const dirty = Boolean(
    profile &&
    (draft.first_name !== savedDraft.first_name ||
      draft.last_name !== savedDraft.last_name ||
      draft.phone !== savedDraft.phone),
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API}/accounts/profile`, {
        credentials: "include",
        cache: "no-store",
      });
      if (response.status === 401) {
        window.location.assign(
          `/konto?next=${encodeURIComponent("/konto/dane")}`,
        );
        return;
      }
      if (!response.ok) throw new Error(await responseMessage(response));
      const value = (await response.json()) as Profile;
      setProfile(value);
      const personal = {
        first_name: value.first_name,
        last_name: value.last_name,
        phone: value.phone ?? "",
      };
      setDraft(personal);
      setSavedDraft(personal);
      setEmailDraft(value.email);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Nie udało się pobrać danych konta.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load, retry]);
  useEffect(() => {
    if (!dirty) return;
    const beforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    const internalNavigation = (event: MouseEvent) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      const link = target.closest("a[href]");
      if (
        !(link instanceof HTMLAnchorElement) ||
        !link.href.startsWith(window.location.origin)
      )
        return;
      if (
        !window.confirm(
          "Masz niezapisane zmiany. Czy na pewno chcesz opuścić stronę?",
        )
      ) {
        event.preventDefault();
        event.stopPropagation();
      }
    };
    window.addEventListener("beforeunload", beforeUnload);
    document.addEventListener("click", internalNavigation, true);
    return () => {
      window.removeEventListener("beforeunload", beforeUnload);
      document.removeEventListener("click", internalNavigation, true);
    };
  }, [dirty]);

  function openAddress(address?: Address) {
    const fullStreet = address?.street ?? "";
    const suffix = address?.building_number
      ? `${address.building_number}${address.apartment_number ? `/${address.apartment_number}` : ""}`
      : "";
    const editableStreet =
      suffix && fullStreet.endsWith(suffix)
        ? fullStreet.slice(0, -suffix.length).trim()
        : fullStreet;
    const value: AddressDraft = address
      ? {
          ...emptyAddress,
          label: address.label,
          address_type: address.address_type,
          street: editableStreet,
          building_number: address.building_number ?? "",
          apartment_number: address.apartment_number ?? "",
          postal_code: address.postal_code ?? "",
          city: address.city ?? "",
          country: address.country ?? "PL",
          point_code: address.code ?? "",
        }
      : emptyAddress;
    setEditAddress(address ?? null);
    setAddressDraft(value);
    dialogRef.current?.showModal();
  }

  async function csrfHeaders(): Promise<Record<string, string>> {
    const response = await fetch(`${API}/accounts/csrf`, {
      credentials: "include",
      cache: "no-store",
    });
    if (!response.ok) throw new Error("Sesja wygasła. Zaloguj się ponownie.");
    const value = (await response.json()) as { csrf_token: string };
    return {
      "Content-Type": "application/json",
      "X-CSRF-Token": value.csrf_token,
    };
  }

  async function savePersonal(event?: FormEvent) {
    event?.preventDefault();
    setBusy(true);
    setError("");
    setStatus("");
    try {
      const headers = await csrfHeaders();
      const response = await fetch(`${API}/accounts/profile/personal`, {
        method: "PUT",
        credentials: "include",
        headers,
        body: JSON.stringify(draft),
      });
      if (!response.ok) throw new Error(await responseMessage(response));
      const value = (await response.json()) as typeof draft;
      setDraft({ ...value, phone: value.phone ?? "" });
      setSavedDraft({ ...value, phone: value.phone ?? "" });
      setProfile((current) => (current ? { ...current, ...value } : current));
      setStatus("Dane osobowe zostały zapisane.");
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Nie udało się zapisać danych.",
      );
    } finally {
      setBusy(false);
    }
  }

  function cancelPersonal() {
    setDraft(savedDraft);
    setError("");
    setStatus("Przywrócono zapisane dane.");
  }

  async function requestEmailChange() {
    setBusy(true);
    setError("");
    setStatus("");
    try {
      const headers = await csrfHeaders();
      const response = await fetch(`${API}/accounts/profile/email-change`, {
        method: "POST",
        credentials: "include",
        headers,
        body: JSON.stringify({ email: emailDraft }),
      });
      if (!response.ok) throw new Error(await responseMessage(response));
      const value = (await response.json()) as {
        pending_email: string | null;
        message: string;
      };
      setProfile((current) =>
        current ? { ...current, pending_email: value.pending_email } : current,
      );
      setStatus(value.message);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Nie udało się zlecić zmiany e-maila.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function saveAddress(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setStatus("");
    try {
      const headers = await csrfHeaders();
      const response = await fetch(
        `${API}/accounts/profile/addresses${editAddress ? `/${editAddress.id}` : ""}`,
        {
          method: editAddress ? "PUT" : "POST",
          credentials: "include",
          headers,
          body: JSON.stringify(addressDraft),
        },
      );
      if (!response.ok) throw new Error(await responseMessage(response));
      dialogRef.current?.close();
      setStatus(
        editAddress ? "Adres został zapisany." : "Adres został dodany.",
      );
      await load();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Nie udało się zapisać adresu.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function addressAction(id: string, action: "default" | "delete") {
    if (
      action === "delete" &&
      !window.confirm("Czy na pewno usunąć ten zapisany adres?")
    )
      return;
    setBusy(true);
    setError("");
    setStatus("");
    try {
      const headers = await csrfHeaders();
      const response = await fetch(
        `${API}/accounts/profile/addresses/${id}${action === "default" ? "/default" : ""}`,
        {
          method: action === "default" ? "POST" : "DELETE",
          credentials: "include",
          headers,
        },
      );
      if (!response.ok) throw new Error(await responseMessage(response));
      setStatus(
        action === "default"
          ? "Zmieniono domyślny adres."
          : "Adres został usunięty.",
      );
      await load();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Nie udało się zmienić adresu.",
      );
    } finally {
      setBusy(false);
    }
  }

  const fullName = profile
    ? `${profile.first_name} ${profile.last_name}`.trim()
    : "";
  const initials = profile
    ? `${profile.first_name[0] ?? ""}${profile.last_name[0] ?? ""}`
    : "";

  return (
    <main id="main-content" className="min-h-[60vh] bg-surface text-ink">
      <section className="relative overflow-hidden px-4 pb-7 pt-8 sm:px-8 sm:pb-9 sm:pt-10">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 top-0 h-52 bg-gradient-to-r from-surface via-surface-muted to-accent/10"
        />
        <div className="relative mx-auto max-w-page-shell">
          <p className="text-label font-bold tracking-caps text-accent-action">
            TWOJE KONTO
          </p>
          <h1 className="mt-3 font-display text-title font-bold md:text-display">
            Dane i zgody
          </h1>
          <div className="mt-8 grid gap-8 lg:grid-cols-[260px_minmax(0,1fr)] lg:gap-8">
            <aside className="space-y-5">
              <section className="rounded-card bg-surface-muted p-4">
                {loading ? (
                  <p role="status">Ładowanie danych konta…</p>
                ) : profile ? (
                  <div className="flex items-center gap-3">
                    <span
                      aria-hidden="true"
                      className="grid size-11 shrink-0 place-items-center rounded-full bg-accent-action font-bold text-on-accent"
                    >
                      {initials}
                    </span>
                    <div className="min-w-0">
                      <p className="truncate font-bold">{fullName}</p>
                      <p className="text-body-small text-ink-muted">
                        Klientka od {monthYear(profile.first_purchase_at)}
                      </p>
                    </div>
                  </div>
                ) : null}
              </section>
              <nav aria-label="Nawigacja konta" className="grid gap-1">
                {[
                  ["Moja biblioteka", "/konto/biblioteka"],
                  ["Moje vouchery", "/konto/vouchery"],
                  ["Zamówienia", "/konto/zamowienia"],
                  ["Dane i adresy", "/konto/dane"],
                ].map(([label, href]) => (
                  <Link
                    key={href}
                    href={href}
                    aria-current={href === "/konto/dane" ? "page" : undefined}
                    className={`min-h-control-sm rounded-control px-3 py-3 text-label focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action ${href === "/konto/dane" ? "bg-ink text-surface" : "hover:bg-surface-muted"}`}
                  >
                    {label}
                  </Link>
                ))}
                <Link
                  href="#zgody"
                  className="min-h-control-sm rounded-control px-3 py-3 text-label hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
                >
                  Zgody i prywatność
                </Link>
              </nav>
              <section className="rounded-card border border-dashed border-border p-4">
                <h2 className="font-bold">Potrzebujesz pomocy?</h2>
                {profile?.contact_email || profile?.contact_phone ? (
                  <div className="mt-2 space-y-1 text-body-small text-ink-muted">
                    {profile.contact_email && (
                      <p>
                        <a
                          className="underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
                          href={`mailto:${profile.contact_email}`}
                        >
                          {profile.contact_email}
                        </a>
                      </p>
                    )}
                    {profile.contact_phone && (
                      <p>
                        <a
                          className="underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
                          href={`tel:${profile.contact_phone}`}
                        >
                          {profile.contact_phone}
                        </a>
                      </p>
                    )}
                  </div>
                ) : (
                  <p className="mt-2 text-body-small text-ink-muted">
                    Napisz do nas przez formularz w centrum pomocy.
                  </p>
                )}
              </section>
            </aside>

            <div className="min-w-0 space-y-4 pb-24">
              {error && (
                <p
                  role="alert"
                  className="rounded-control bg-danger px-4 py-3 text-on-danger"
                >
                  {error}
                </p>
              )}
              {status && (
                <p
                  role="status"
                  className="rounded-control bg-success px-4 py-3 text-on-success"
                >
                  {status}
                </p>
              )}
              {loading ? (
                <div
                  role="status"
                  className="rounded-card border border-border bg-surface p-6"
                >
                  Ładowanie zapisanych danych…
                </div>
              ) : error && !profile ? (
                <section className="rounded-card border border-border bg-surface p-6">
                  <p>Nie udało się pobrać danych konta.</p>
                  <Button
                    className="mt-4"
                    onClick={() => setRetry((value) => value + 1)}
                  >
                    Spróbuj ponownie
                  </Button>
                </section>
              ) : (
                profile && (
                  <>
                    <form
                      onSubmit={(event) => void savePersonal(event)}
                      className="rounded-card border border-border bg-surface p-5 sm:p-6"
                    >
                      <h2 className="text-subtitle font-bold">Dane osobowe</h2>
                      <p className="mt-2 text-body-small text-ink-muted">
                        Używamy ich tylko do realizacji zamówień i wystawiania
                        dokumentów.
                      </p>
                      <div className="mt-5 grid gap-4 md:grid-cols-2">
                        <label className="block text-label">
                          Imię
                          <input
                            required
                            autoComplete="given-name"
                            value={draft.first_name}
                            onChange={(event) =>
                              setDraft({
                                ...draft,
                                first_name: event.target.value,
                              })
                            }
                            className="mt-2 min-h-touch w-full rounded-control border border-border bg-surface px-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
                          />
                        </label>
                        <label className="block text-label">
                          Nazwisko
                          <input
                            required
                            autoComplete="family-name"
                            value={draft.last_name}
                            onChange={(event) =>
                              setDraft({
                                ...draft,
                                last_name: event.target.value,
                              })
                            }
                            className="mt-2 min-h-touch w-full rounded-control border border-border bg-surface px-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
                          />
                        </label>
                        <label className="block text-label">
                          Adres e-mail
                          <input
                            type="email"
                            autoComplete="email"
                            value={emailDraft}
                            onChange={(event) =>
                              setEmailDraft(event.target.value)
                            }
                            className="mt-2 min-h-touch w-full rounded-control border border-border bg-surface px-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
                            aria-describedby="email-change-help"
                          />
                        </label>
                        <label className="block text-label">
                          Telefon
                          <input
                            type="tel"
                            autoComplete="tel"
                            value={draft.phone}
                            onChange={(event) =>
                              setDraft({ ...draft, phone: event.target.value })
                            }
                            className="mt-2 min-h-touch w-full rounded-control border border-border bg-surface px-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
                          />
                        </label>
                      </div>
                      <p
                        id="email-change-help"
                        className="mt-3 text-body-small text-ink-muted"
                      >
                        Zmiana e-maila wymaga ponownego logowania oraz
                        potwierdzenia nowego adresu. Do tego czasu obowiązuje{" "}
                        {profile.email}.
                      </p>
                      {profile.pending_email && (
                        <p role="status" className="mt-2 text-body-small">
                          Oczekuje na potwierdzenie: {profile.pending_email}
                        </p>
                      )}
                      <div className="mt-4 flex flex-wrap gap-3">
                        <Button
                          type="submit"
                          variant="secondary"
                          disabled={busy || !dirty}
                          loading={busy}
                        >
                          Zapisz dane
                        </Button>
                        <Button
                          type="button"
                          variant="text"
                          disabled={busy || !dirty}
                          onClick={cancelPersonal}
                        >
                          Anuluj
                        </Button>
                        <Button
                          type="button"
                          variant="secondary"
                          disabled={busy || emailDraft === profile.email}
                          loading={busy}
                          onClick={() => void requestEmailChange()}
                        >
                          Wyślij potwierdzenie e-maila
                        </Button>
                      </div>
                    </form>

                    <section className="rounded-card border border-border bg-surface p-5 sm:p-6">
                      <h2 className="text-subtitle font-bold">
                        Adresy dostawy
                      </h2>
                      <p className="mt-2 text-body-small text-ink-muted">
                        Możesz zapisać kilka adresów — wybierzesz je jednym
                        kliknięciem przy zamówieniu.
                      </p>
                      <div className="mt-4 space-y-3">
                        {profile.addresses.map((address) => (
                          <article
                            key={address.id}
                            className={`flex flex-col gap-4 rounded-card border p-4 md:flex-row md:items-center md:justify-between ${address.is_default ? "border-accent-action bg-surface-muted" : "border-border"}`}
                          >
                            <div className="min-w-0">
                              <div className="flex flex-wrap items-center gap-2">
                                <h3 className="font-bold">{address.label}</h3>
                                {address.is_default && (
                                  <span className="shrink-0 whitespace-nowrap rounded-full bg-accent-action px-3 py-1 text-caption font-bold text-on-accent">
                                    DOMYŚLNY
                                  </span>
                                )}
                              </div>
                              <p className="mt-1 break-words text-body-small text-ink-muted">
                                {address.address_type === "parcel_locker"
                                  ? `Paczkomat ${address.code} · ${address.street}, ${address.postal_code} ${address.city}`
                                  : `${address.street}, ${address.postal_code} ${address.city}`}
                              </p>
                              <p className="mt-1 text-caption text-ink-muted">
                                Zapisane na koncie; zmiana nie edytuje
                                historycznych zamówień.
                              </p>
                            </div>
                            <div className="flex shrink-0 flex-wrap gap-2">
                              <Button
                                size="sm"
                                variant="secondary"
                                disabled={busy}
                                onClick={() => openAddress(address)}
                              >
                                Edytuj
                              </Button>
                              {!address.is_default && (
                                <Button
                                  size="sm"
                                  variant="secondary"
                                  disabled={busy}
                                  onClick={() =>
                                    void addressAction(address.id, "default")
                                  }
                                >
                                  Ustaw domyślny
                                </Button>
                              )}
                              <Button
                                size="sm"
                                variant="text"
                                disabled={busy}
                                onClick={() =>
                                  void addressAction(address.id, "delete")
                                }
                              >
                                Usuń
                              </Button>
                            </div>
                          </article>
                        ))}
                      </div>
                      <Button
                        className="mt-4"
                        variant="secondary"
                        disabled={busy}
                        onClick={() => openAddress()}
                      >
                        + Dodaj adres
                      </Button>
                      <p className="mt-3 text-caption text-ink-muted">
                        Zapisywanie i usuwanie adresu działa od razu. „Anuluj”
                        na pasku poniżej dotyczy wyłącznie danych osobowych.
                      </p>
                    </section>
                  </>
                )
              )}
              {profile && !loading && <PrivacyControls email={profile.email} />}
            </div>
          </div>
        </div>
      </section>
      {dirty && (
        <div className="fixed inset-x-0 bottom-0 z-20 border-t border-border bg-surface/95 p-3 backdrop-blur sm:px-8">
          <div className="mx-auto flex max-w-page-shell flex-wrap items-center justify-between gap-3">
            <p className="text-body-small">Masz niezapisane zmiany</p>
            <div className="flex gap-2">
              <Button
                variant="secondary"
                disabled={busy}
                onClick={cancelPersonal}
              >
                Anuluj
              </Button>
              <Button
                disabled={busy}
                loading={busy}
                onClick={() => void savePersonal()}
              >
                Zapisz zmiany
              </Button>
            </div>
          </div>
        </div>
      )}

      <dialog
        ref={dialogRef}
        aria-labelledby="address-dialog-title"
        className="m-auto max-h-[90dvh] w-[calc(100%-2rem)] max-w-2xl rounded-card border border-border bg-surface p-5 text-ink backdrop:bg-ink/40 sm:p-7"
      >
        <form onSubmit={(event) => void saveAddress(event)}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 id="address-dialog-title" className="text-subtitle font-bold">
                {editAddress ? "Edytuj adres" : "Dodaj adres"}
              </h2>
              <p className="mt-1 text-body-small text-ink-muted">
                Zapis adresu jest niezależny od paska zmian danych osobowych.
              </p>
            </div>
            <button
              type="button"
              aria-label="Zamknij formularz adresu"
              className="min-h-touch min-w-touch rounded-control focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action"
              onClick={() => dialogRef.current?.close()}
            >
              ×
            </button>
          </div>
          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <label className="block text-label md:col-span-2">
              Nazwa adresu
              <input
                required
                maxLength={80}
                value={addressDraft.label}
                onChange={(event) =>
                  setAddressDraft({
                    ...addressDraft,
                    label: event.target.value,
                  })
                }
                className="mt-2 min-h-touch w-full rounded-control border border-border px-3"
              />
            </label>
            <label className="block text-label md:col-span-2">
              Typ adresu
              <select
                value={addressDraft.address_type}
                onChange={(event) =>
                  setAddressDraft({
                    ...emptyAddress,
                    label: addressDraft.label,
                    address_type: event.target.value as AddressType,
                  })
                }
                className="mt-2 min-h-touch w-full rounded-control border border-border bg-surface px-3"
              >
                <option value="address">Zwykły adres</option>
                <option value="parcel_locker">Paczkomat</option>
              </select>
            </label>
            {addressDraft.address_type === "address" ? (
              <>
                <label className="block text-label">
                  Ulica
                  <input
                    required
                    maxLength={180}
                    value={addressDraft.street}
                    onChange={(event) =>
                      setAddressDraft({
                        ...addressDraft,
                        street: event.target.value,
                      })
                    }
                    className="mt-2 min-h-touch w-full rounded-control border border-border px-3"
                    autoComplete="street-address"
                  />
                </label>
                <label className="block text-label">
                  Numer budynku
                  <input
                    required
                    maxLength={20}
                    value={addressDraft.building_number}
                    onChange={(event) =>
                      setAddressDraft({
                        ...addressDraft,
                        building_number: event.target.value,
                      })
                    }
                    className="mt-2 min-h-touch w-full rounded-control border border-border px-3"
                  />
                </label>
                <label className="block text-label">
                  Numer lokalu (opcjonalnie)
                  <input
                    maxLength={20}
                    value={addressDraft.apartment_number}
                    onChange={(event) =>
                      setAddressDraft({
                        ...addressDraft,
                        apartment_number: event.target.value,
                      })
                    }
                    className="mt-2 min-h-touch w-full rounded-control border border-border px-3"
                  />
                </label>
                <label className="block text-label">
                  Kod pocztowy
                  <input
                    required
                    maxLength={20}
                    value={addressDraft.postal_code}
                    onChange={(event) =>
                      setAddressDraft({
                        ...addressDraft,
                        postal_code: event.target.value,
                      })
                    }
                    className="mt-2 min-h-touch w-full rounded-control border border-border px-3"
                    autoComplete="postal-code"
                  />
                </label>
                <label className="block text-label md:col-span-2">
                  Miasto
                  <input
                    required
                    maxLength={100}
                    value={addressDraft.city}
                    onChange={(event) =>
                      setAddressDraft({
                        ...addressDraft,
                        city: event.target.value,
                      })
                    }
                    className="mt-2 min-h-touch w-full rounded-control border border-border px-3"
                    autoComplete="address-level2"
                  />
                </label>
              </>
            ) : (
              <label className="block text-label md:col-span-2">
                Kod Paczkomatu
                <input
                  required
                  maxLength={20}
                  value={addressDraft.point_code}
                  onChange={(event) =>
                    setAddressDraft({
                      ...emptyAddress,
                      label: addressDraft.label,
                      address_type: "parcel_locker",
                      point_code: event.target.value.toUpperCase(),
                    })
                  }
                  className="mt-2 min-h-touch w-full rounded-control border border-border px-3"
                />
                <span className="mt-1 block text-caption text-ink-muted">
                  Kod zostanie sprawdzony w katalogu punktów przed zapisaniem.
                </span>
              </label>
            )}
          </div>
          <div className="mt-6 flex flex-wrap justify-end gap-3">
            <Button
              type="button"
              variant="secondary"
              onClick={() => dialogRef.current?.close()}
            >
              Anuluj
            </Button>
            <Button type="submit" disabled={busy} loading={busy}>
              Zapisz adres
            </Button>
          </div>
        </form>
      </dialog>
    </main>
  );
}

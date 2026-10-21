"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { useCartCount } from "@/components/layout/cart-count-provider";
import {
  Accordion,
  Badge,
  Breadcrumbs,
  Button,
  Checkbox,
  Price,
  RadioCard,
} from "@/components/ui";
import { addVoucherToCart, addVoucherAndContinue } from "@/lib/voucher-cart";
import type {
  CatalogProductDetail,
  CatalogVoucherVariant,
  VoucherVariantKind,
} from "@/types/catalog";

type Props = {
  initialVariantKey: string;
  product: CatalogProductDetail;
};

const EMPTY_VARIANTS: CatalogVoucherVariant[] = [];

const variantKeys: Record<VoucherVariantKind, string> = {
  IN_PERSON: "gabinet",
  ONLINE: "online",
};

function keyForVariant(variant: CatalogVoucherVariant): string {
  return variantKeys[variant.kind];
}

function variantTitle(kind: VoucherVariantKind): string {
  return kind === "IN_PERSON" ? "W gabinecie w Olsztynie" : "Online";
}

function variantDescription(kind: VoucherVariantKind): string {
  return kind === "IN_PERSON"
    ? "ul. Knosały 7B/A, parter, wejście z ulicy"
    : "Wideorozmowa, link przychodzi przed spotkaniem";
}

function validityLabel(months: number): string {
  const lastTwoDigits = months % 100;
  const lastDigit = months % 10;
  const unit =
    months === 1
      ? "MIESIĄC"
      : lastTwoDigits < 12 || lastTwoDigits > 14
        ? lastDigit >= 2 && lastDigit <= 4
          ? "MIESIĄCE"
          : "MIESIĘCY"
        : "MIESIĘCY";
  return `${months} ${unit}`;
}

function validitySentence(months: number): string {
  if (months === 12) return "masz rok";
  const lastTwoDigits = months % 100;
  const lastDigit = months % 10;
  const unit =
    months === 1
      ? "miesiąc"
      : lastTwoDigits < 12 || lastTwoDigits > 14
        ? lastDigit >= 2 && lastDigit <= 4
          ? "miesiące"
          : "miesięcy"
        : "miesięcy";
  return `masz ${months} ${unit}`;
}

function formatApiError(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "Nie udało się wykonać operacji. Spróbuj ponownie później.";
}

function VoucherCover({ product }: { product: CatalogProductDetail }) {
  const image = product.images[0];
  if (!image) return <TicketPreview product={product} />;
  return (
    <figure className="min-w-0 space-y-3">
      <div className="relative aspect-ebook-cover w-full overflow-hidden rounded-card bg-surface-muted shadow-subtle lg:aspect-square">
        <Image
          alt={image.alt}
          className="object-cover"
          fill
          priority
          sizes="(min-width: 1024px) 40vw, 100vw"
          src={image.url}
          unoptimized
        />
        <div className="absolute left-4 top-4">
          <Badge label="VOUCHER" />
        </div>
      </div>
      <figcaption className="text-center text-caption text-ink-muted">
        Voucher przychodzi na e-mail jako plik PDF z kodem i kodem QR.
      </figcaption>
    </figure>
  );
}

function TicketPreview({ product }: { product: CatalogProductDetail }) {
  return (
    <figure
      aria-label="Przykładowy podgląd vouchera, nieaktywny przed opłaceniem"
      className="relative isolate flex aspect-ticket-preview min-w-0 flex-col justify-between overflow-hidden rounded-card bg-surface-muted p-4 shadow-subtle md:p-6"
    >
      <figcaption className="relative z-20 w-fit rounded-pill bg-surface px-3 py-2 text-caption font-bold text-ink-muted">
        Przykładowy podgląd — nieaktywny voucher
      </figcaption>
      <span
        aria-hidden="true"
        className="pointer-events-none absolute -left-1/4 top-1/4 aspect-square w-3/4 rounded-full border border-accent-action/40"
      />
      <span
        aria-hidden="true"
        className="pointer-events-none absolute left-1/4 top-1/4 aspect-square w-1/2 rounded-full border border-dashed border-accent-action/40"
      />
      <article className="relative z-10 my-auto w-11/12 self-center -rotate-2 rounded-card border border-border bg-surface p-3 shadow-subtle md:w-4/5 md:p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 space-y-2">
            <p className="text-caption font-bold uppercase tracking-caps text-accent-action">
              Voucher na wizytę
            </p>
            <h2 className="break-words font-interface text-label font-bold text-ink">
              {product.name}
            </h2>
          </div>
          <span
            aria-label={`Ważność: ${validityLabel(product.voucher?.validity_months ?? 12)}`}
            className="inline-flex size-12 shrink-0 flex-col items-center justify-center rounded-full bg-accent text-center text-caption font-bold leading-tight text-ink md:size-14"
          >
            <span>{product.voucher?.validity_months ?? 12}</span>
            <span className="whitespace-nowrap text-label">mies.</span>
          </span>
        </div>
        <div className="my-2 flex items-center gap-3 border-y border-border py-2 md:gap-4">
          <div
            aria-hidden="true"
            className="grid size-12 shrink-0 grid-cols-5 gap-0.5 bg-surface p-1 md:size-14 md:gap-1"
          >
            {Array.from({ length: 25 }, (_, index) => (
              <span
                className={
                  (index * 7 + (index % 4)) % 5 < 2
                    ? "bg-ink"
                    : "bg-surface-muted"
                }
                key={index}
              />
            ))}
          </div>
          <div className="min-w-0">
            <p className="text-caption font-bold uppercase tracking-caps text-accent-action">
              Kod przykładowy
            </p>
            <p className="break-all font-interface text-body-small font-bold text-ink md:text-body">
              SEN-4K2P-9WQ1
            </p>
          </div>
        </div>
        <p className="break-words text-caption text-ink-muted">
          SENSORIA · szczegóły realizacji podane przy wyborze wariantu
        </p>
      </article>
      <ul className="relative z-10 flex flex-wrap justify-center gap-2 text-caption text-ink-muted md:gap-3">
        <li className="min-h-touch rounded-pill border border-border bg-surface px-3 py-3">
          PDF do wydruku
        </li>
        <li className="min-h-touch rounded-pill border border-border bg-surface px-3 py-3">
          Można przekazać
        </li>
      </ul>
    </figure>
  );
}

export function VoucherProductView({ product, initialVariantKey }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { acceptConfirmedCount } = useCartCount();
  const variants = product.voucher?.variants ?? EMPTY_VARIANTS;
  const defaultVariant = variants[0];
  const [selectedKey, setSelectedKey] = useState(initialVariantKey);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [gift, setGift] = useState(false);

  useEffect(() => {
    const current = searchParams.get("variant");
    if (
      current &&
      variants.some((variant) => keyForVariant(variant) === current)
    ) {
      setSelectedKey(current);
    } else if (!current && defaultVariant) {
      setSelectedKey(keyForVariant(defaultVariant));
    }
  }, [defaultVariant, searchParams, variants]);

  const selectedVariant = useMemo(
    () =>
      variants.find((variant) => keyForVariant(variant) === selectedKey) ??
      defaultVariant,
    [defaultVariant, selectedKey, variants],
  );
  const selectedVariantKey = selectedVariant
    ? keyForVariant(selectedVariant)
    : "";
  const offerPrice = selectedVariant?.price;

  function selectVariant(variant: CatalogVoucherVariant) {
    const key = keyForVariant(variant);
    setSelectedKey(key);
    setNotice("");
    const params = new URLSearchParams(searchParams.toString());
    params.set("variant", key);
    router.push(`${pathname}?${params.toString()}`, { scroll: false });
  }

  async function handlePurchase(continueToOrder: boolean) {
    if (!selectedVariant || !product.is_available || busy) return;
    setBusy(true);
    setNotice("");
    try {
      await addVoucherAndContinue(
        { productId: product.id, variantId: selectedVariant.id, gift },
        addVoucherToCart,
        ({ count }) => acceptConfirmedCount(count),
        () => {
          if (continueToOrder) router.push("/zamowienie");
        },
      );
      setNotice(
        continueToOrder
          ? "Voucher dodano do koszyka. Przechodzimy do zamówienia."
          : "Voucher dodano do koszyka.",
      );
    } catch (error: unknown) {
      setNotice(formatApiError(error));
    } finally {
      setBusy(false);
    }
  }

  const description =
    product.description ??
    product.short_description ??
    product.meta_description;
  const subtitle = product.short_description;
  const faqItems = [
    {
      id: "gift",
      title: "Czy voucher mogę podarować komuś innemu?",
      content: (
        <p>
          Tak. Kod nie jest przypisany do osoby kupującej — może go wykorzystać
          ktokolwiek. Przy zamówieniu możesz zaznaczyć opcję prezentu, wtedy
          dołączymy dedykację.
        </p>
      ),
    },
    {
      id: "validity",
      title: `Co, jeśli nie wykorzystam go w ciągu ${product.voucher?.validity_months ?? ""} ${product.voucher?.validity_months === 1 ? "miesiąca" : "miesięcy"}?`,
      content: (
        <p>
          Voucher jest ważny {product.voucher?.validity_months ?? "—"} mies.
          Jeśli nie zdążysz, poproś o przedłużenie w koncie klienta albo
          wiadomością do nas — przedłużamy ważność po kontakcie.
        </p>
      ),
    },
    {
      id: "invoice",
      title: "Czy dostanę fakturę?",
      content: (
        <p>
          Paragon wystawiamy automatycznie. Fakturę VAT na firmę wystawimy,
          jeśli podasz NIP w zamówieniu.
        </p>
      ),
    },
    {
      id: "return",
      title: "Czy mogę zwrócić voucher?",
      content: (
        <p>
          Masz 14 dni na odstąpienie od umowy od dnia zakupu — napisz do nas lub
          skorzystaj z formularza na stronie{" "}
          <Link className="underline" href="/pomoc/odstapienie">
            odstąpienie od umowy
          </Link>
          .
        </p>
      ),
    },
  ];
  const steps = [
    [
      "01",
      "Kupujesz",
      "Wybierasz formę spotkania i płacisz BLIK-iem albo kartą.",
    ],
    [
      "02",
      "Dostajesz kod",
      "Voucher w PDF trafia na maila w kilkanaście sekund.",
    ],
    [
      "03",
      "Umawiasz termin",
      `Dzwonisz lub piszesz, podajesz kod. Bez pośpiechu — ${validitySentence(product.voucher?.validity_months ?? 12)}.`,
    ],
    [
      "04",
      "Przychodzisz",
      "Pokazujesz kod na telefonie albo wydruku. To wszystko.",
    ],
  ];

  return (
    <main
      className="page-shell space-y-8 pb-24 md:space-y-12 lg:pb-0"
      id="main-content"
      tabIndex={-1}
    >
      <Breadcrumbs
        items={[
          { label: "Sklep", href: "/sklep" },
          { label: "Vouchery", href: "/sklep?kind=VOUCHER" },
          { label: product.name },
        ]}
      />
      <article className="grid min-w-0 gap-8 lg:grid-cols-2 lg:gap-12">
        <VoucherCover product={product} />
        <section
          aria-labelledby="voucher-title"
          className="min-w-0 space-y-5 lg:sticky lg:top-24 lg:self-start"
        >
          <Badge label="VOUCHER" />
          <h1
            className="break-words font-display text-title font-extrabold tracking-tight text-ink"
            id="voucher-title"
          >
            {product.name}
          </h1>
          {subtitle ? (
            <p className="font-decorative text-emphasis italic text-accent-action">
              {subtitle}
            </p>
          ) : null}
          <p className="break-words text-body text-ink-muted">{description}</p>

          {variants.length > 0 ? (
            <fieldset className="space-y-3">
              <legend className="mb-2 font-interface text-label font-bold text-ink">
                Forma spotkania
              </legend>
              {variants.map((variant) => {
                const key = keyForVariant(variant);
                return (
                  <RadioCard
                    checked={selectedVariantKey === key}
                    description={variantDescription(variant.kind)}
                    key={variant.id}
                    name="voucher-variant"
                    onChange={() => selectVariant(variant)}
                    title={variantTitle(variant.kind)}
                    trailingContent={<Price amountInGrosze={variant.price} />}
                    value={key}
                  />
                );
              })}
            </fieldset>
          ) : (
            <p className="text-body-small text-ink-muted" role="status">
              Ten voucher nie ma obecnie dostępnych wariantów.
            </p>
          )}

          <Checkbox
            checked={gift}
            description="W zamówieniu podasz imię, dedykację i wybierzesz termin wysyłki."
            label="Kupujesz w prezencie? Zaznacz przy zamówieniu — dołączymy dedykację i wyślemy voucher w wybranym dniu."
            onChange={(event) => setGift(event.currentTarget.checked)}
            title="Kupujesz w prezencie?"
            variant="card"
          />

          <div className="space-y-4 rounded-card border border-border bg-surface p-4 shadow-subtle md:p-6">
            <div className="space-y-2">
              {offerPrice !== undefined ? (
                <Price
                  amountInGrosze={offerPrice}
                  vatRate={product.vat_rate ?? undefined}
                />
              ) : null}
              {product.vat_rate === "EXEMPT" ? (
                <p className="text-caption text-ink-muted">
                  Usługa zwolniona z VAT · cena ostateczna
                </p>
              ) : null}
            </div>
            <div className="flex flex-col gap-3 sm:flex-row">
              <Button
                className="w-full"
                disabled={!product.is_available || !selectedVariant}
                loading={busy}
                onClick={() => void handlePurchase(true)}
                size="lg"
              >
                Kup voucher
              </Button>
              <Button
                className="w-full"
                disabled={!product.is_available || !selectedVariant}
                loading={busy}
                onClick={() => void handlePurchase(false)}
                size="lg"
                variant="secondary"
              >
                Do koszyka
              </Button>
            </div>
            <p
              aria-live="polite"
              className="min-h-6 text-body-small text-ink-muted"
              role="status"
            >
              {notice ||
                "Wybierz formę spotkania, a potem kliknij „Kup voucher”."}
            </p>
            <ul className="space-y-3 border-t border-border pt-4 text-body-small text-ink-muted">
              <li>
                Zapłacisz BLIK-iem w 15 sekund. Nie musisz zakładać konta.
              </li>
              <li>
                Voucher w PDF przychodzi na Twój e-mail zaraz po opłaceniu.
              </li>
              <li>
                Termin umawiasz telefonicznie albo przez formularz, kiedy
                będziesz gotowa.
              </li>
              <li>
                Jeśli nie wykorzystasz go w terminie, przedłużymy ważność po
                kontakcie z nami.
              </li>
            </ul>
          </div>
        </section>
      </article>

      <section
        aria-labelledby="steps-title"
        className="-mx-4 space-y-6 bg-surface-muted px-4 py-8 md:-mx-4 md:px-4 xl:-mx-12 xl:px-12"
      >
        <div>
          <p className="uppercase-label text-accent-action">Jak to działa</p>
          <h2
            className="mt-2 font-display text-subtitle font-bold text-ink"
            id="steps-title"
          >
            Od zakupu do wizyty
          </h2>
        </div>
        <ol className="grid min-w-0 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {steps.map(([number, title, body]) => (
            <li
              className="min-w-0 rounded-card border border-border bg-surface p-4"
              key={number}
            >
              <span className="text-label font-bold text-accent-action">
                {number}
              </span>
              <h3 className="mt-3 font-interface text-label font-bold text-ink">
                {title}
              </h3>
              <p className="mt-2 break-words text-body-small text-ink-muted">
                {body}
              </p>
            </li>
          ))}
        </ol>
      </section>

      <section
        aria-labelledby="faq-title"
        className="mx-auto w-full max-w-content space-y-5"
      >
        <div>
          <p className="uppercase-label text-accent-action">Pytania</p>
          <h2
            className="mt-2 font-display text-subtitle font-bold text-ink"
            id="faq-title"
          >
            Zanim kupisz
          </h2>
        </div>
        <Accordion
          defaultExpandedIds={["gift"]}
          items={faqItems}
          mode="single"
        />
      </section>

      {selectedVariant && offerPrice !== undefined ? (
        <div className="fixed inset-x-0 bottom-0 z-20 border-t border-border bg-surface p-4 pb-[calc(theme(spacing.4)+env(safe-area-inset-bottom))] shadow-overlay lg:hidden">
          <div className="mx-auto flex max-w-page-shell items-center gap-4">
            <div className="min-w-0 flex-1">
              <Price
                amountInGrosze={offerPrice}
                vatRate={product.vat_rate ?? undefined}
              />
            </div>
            <Button
              disabled={!product.is_available || busy}
              loading={busy}
              onClick={() => void handlePurchase(true)}
              size="md"
            >
              Kup voucher
            </Button>
          </div>
        </div>
      ) : null}
    </main>
  );
}

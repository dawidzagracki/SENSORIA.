import { Accordion } from "@/components/ui";
import { CatalogRelatedProducts } from "@/components/products/catalog-related-products";
import { ProductPurchaseActions } from "@/components/products/product-purchase-actions";
import {
  ProductBreadcrumbs,
  ProductCover,
  ProductHeading,
} from "@/components/products/product-detail-shared";
import {
  formatDurationPolish,
  hasConsistentAudiobookDuration,
  sumChapterSeconds,
} from "@/lib/catalog-product";
import type { CatalogProductDetail } from "@/types/catalog";
import { AudioSamplePlayer } from "@/components/products/audio-sample-player";

export function AudiobookProductView({
  product,
}: {
  product: CatalogProductDetail;
}) {
  const audiobook = product.audiobook;
  if (!audiobook)
    throw new Error("Produkt AUDIOBOOK nie zawiera danych audiobooka.");
  const chapters = [...audiobook.chapters].sort(
    (left, right) => left.position - right.position,
  );
  const durationIsConsistent = hasConsistentAudiobookDuration(
    audiobook.duration_seconds,
    chapters,
  );
  const totalDuration = formatDurationPolish(sumChapterSeconds(chapters));
  const faqItems = [
    {
      id: "audio-delivery",
      title: "Kiedy otrzymam audiobook?",
      content: (
        <p>
          Wydanie pliku po opłaceniu wymaga integracji zamówień. Aplikacja nie
          udostępnia jeszcze pliku ani biblioteki klienta.
        </p>
      ),
    },
  ];

  return (
    <main
      className="page-shell space-y-8 pb-28 md:space-y-12 lg:pb-0"
      id="main-content"
      tabIndex={-1}
    >
      <ProductBreadcrumbs product={product} categoryLabel="Audiobooki" />
      <article className="grid min-w-0 gap-8 lg:grid-cols-2 lg:gap-12">
        <div className="space-y-4">
          <ProductCover product={product} label="AUDIOBOOK" />
          {audiobook.sample_available && audiobook.sample_duration_seconds ? (
            <AudioSamplePlayer
              durationSeconds={audiobook.sample_duration_seconds}
              slug={product.slug}
            />
          ) : null}
        </div>
        <section
          aria-label="Informacje o audiobooku i zakup"
          className="min-w-0 space-y-5 lg:sticky lg:top-24 lg:self-start"
        >
          <ProductHeading product={product} label="AUDIOBOOK" />
          <dl className="grid grid-cols-1 gap-3 text-body-small text-ink-muted sm:grid-cols-2">
            {audiobook.duration_seconds !== null ? (
              <div className="rounded-card border border-border p-3">
                <dt className="text-caption">Czas trwania</dt>
                <dd className="font-bold text-ink">
                  {formatDurationPolish(audiobook.duration_seconds)}
                </dd>
              </div>
            ) : null}
            {audiobook.narrator ? (
              <div className="rounded-card border border-border p-3">
                <dt className="text-caption">Czyta</dt>
                <dd className="break-words font-bold text-ink">
                  {audiobook.narrator}
                </dd>
              </div>
            ) : null}
            {audiobook.file_format ? (
              <div className="rounded-card border border-border p-3">
                <dt className="text-caption">Format pliku</dt>
                <dd className="font-bold text-ink">{audiobook.file_format}</dd>
              </div>
            ) : null}
          </dl>
          <p className="rounded-card border border-border bg-surface-muted p-4 text-body-small text-ink">
            Kupując treść cyfrową, potwierdzasz przy płatności zgodę na jej
            udostępnienie przed upływem terminu odstąpienia od umowy — co
            oznacza utratę prawa do odstąpienia. Bez tej zgody plik wyślemy po
            14 dniach.
            <span className="mt-2 block text-caption text-ink-muted">
              Ta strona nie zapisuje zgody ani nie uruchamia odroczonego
              wydania.
            </span>
          </p>
          <ul className="space-y-2 border-y border-border py-4 text-body-small text-ink-muted">
            <li>
              Plik {audiobook.file_format ?? "w niepodanym formacie"} po
              opłaceniu wymaga integracji zamówień [24].
            </li>
            <li>
              Ponowne pobranie z konta nie jest dostępne bez integracji
              biblioteki klienta.
            </li>
          </ul>
          <ProductPurchaseActions
            available={product.is_available}
            compareAtPrice={product.compare_at_price}
            mobileLabel="Kup i pobierz"
            price={product.price}
            productId={product.id}
            primaryLabel="Kup i pobierz teraz"
            vatRate={product.vat_rate}
          />
        </section>
      </article>
      <section
        aria-labelledby="audio-chapters-title"
        className="-mx-4 space-y-5 bg-surface-muted px-4 py-8 md:-mx-4 md:px-4 xl:-mx-12 xl:px-12"
      >
        <p className="text-label font-bold uppercase tracking-caps text-accent-action">
          Spis rozdziałów
        </p>
        <h2
          className="font-display text-subtitle font-bold text-ink"
          id="audio-chapters-title"
        >
          Rozdziały audiobooka
        </h2>
        {chapters.length > 0 ? (
          <ol className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {chapters.map((chapter, index) => (
              <li
                className="flex min-w-0 items-start justify-between gap-4 rounded-card border border-border bg-surface p-4"
                key={String(chapter.position) + chapter.title}
              >
                <span className="min-w-0 break-words text-body-small text-ink">
                  <span className="mr-2 font-bold text-accent-action">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  {chapter.title}
                </span>
                <span className="shrink-0 text-caption text-ink-muted">
                  {formatDurationPolish(chapter.length_seconds)}
                </span>
              </li>
            ))}
          </ol>
        ) : (
          <p className="text-body-small text-ink-muted">
            Spis rozdziałów nie został podany.
          </p>
        )}
        {!durationIsConsistent ? (
          <p
            className="rounded-card border border-warning bg-surface p-4 text-body-small text-ink"
            role="alert"
          >
            Suma czasów rozdziałów ({totalDuration}) nie zgadza się z czasem
            całego audiobooka
            {audiobook.duration_seconds !== null
              ? " (" + formatDurationPolish(audiobook.duration_seconds) + ")"
              : ""}
            . Dane produktu wymagają korekty.
          </p>
        ) : null}
      </section>
      <section
        aria-labelledby="audio-faq-title"
        className="mx-auto w-full max-w-content space-y-5"
      >
        <p className="text-label font-bold uppercase tracking-caps text-accent-action">
          Pytania
        </p>
        <h2
          className="font-display text-subtitle font-bold text-ink"
          id="audio-faq-title"
        >
          Zanim kupisz
        </h2>
        <Accordion defaultExpandedIds={[]} items={faqItems} mode="single" />
      </section>
      <CatalogRelatedProducts
        currentId={product.id}
        products={product.related_products}
      />
    </main>
  );
}

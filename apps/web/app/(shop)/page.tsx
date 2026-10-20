import type { Metadata } from "next";
import { Homepage } from "@/components/home/homepage";
import { getCatalogList } from "@/lib/catalog-list-api";
import {
  organizationJsonLd,
  serializeJsonLd,
  websiteJsonLd,
} from "@/lib/json-ld";
import { getHomepageContent } from "@/lib/homepage-api";
import { selectHomepageFeaturedProducts } from "@/lib/homepage-products";
import type { CatalogListResponse } from "@/types/catalog-list";
import { ApiError } from "@/lib/api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Sensoria Terapia — Anna Parakiewicz",
  description:
    "Vouchery na wizyty, książki, audiobooki i kursy przygotowane przez zespół Sensoria.",
};

async function loadKind(kind: string): Promise<CatalogListResponse> {
  return getCatalogList(
    new URLSearchParams({ kind, per_page: "48", sort: "recommended" }),
  );
}

export default async function HomePage() {
  let content;
  try {
    content = await getHomepageContent();
  } catch (error: unknown) {
    const isApiError = error instanceof ApiError;
    return (
      <main className="page-shell min-h-screen" id="main-content" tabIndex={-1}>
        <h1 className="font-display text-title font-bold text-ink">
          Sensoria Terapia
        </h1>
        <p className="mt-6 text-body text-ink-muted" role="status">
          {isApiError
            ? "Nie można teraz wczytać treści strony. Spróbuj ponownie później."
            : "Wystąpił błąd. Spróbuj ponownie później."}
        </p>
      </main>
    );
  }

  const [voucherResult, audiobookResult, digitalResult, recommendationsResult] =
    await Promise.allSettled([
      loadKind("VOUCHER"),
      loadKind("AUDIOBOOK"),
      loadKind("DIGITAL"),
      getCatalogList(
        new URLSearchParams({ per_page: "4", sort: "recommended" }),
      ),
    ]);

  const voucherProducts =
    voucherResult.status === "fulfilled" ? voucherResult.value.items : [];
  const audiobookProducts =
    audiobookResult.status === "fulfilled" ? audiobookResult.value.items : [];
  const digitalProducts =
    digitalResult.status === "fulfilled" ? digitalResult.value.items : [];
  const recommendations =
    recommendationsResult.status === "fulfilled"
      ? recommendationsResult.value.items
      : [];
  const featuredLoadFailed = [
    voucherResult,
    audiobookResult,
    digitalResult,
  ].some((result) => result.status === "rejected");

  return (
    <>
      <Homepage
        catalogUnavailable={featuredLoadFailed}
        content={content}
        featured={selectHomepageFeaturedProducts(
          voucherProducts,
          audiobookProducts,
          digitalProducts,
          content,
        )}
        recommendations={recommendations}
        recommendationsUnavailable={recommendationsResult.status === "rejected"}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: serializeJsonLd([organizationJsonLd(), websiteJsonLd()]),
        }}
      />
    </>
  );
}

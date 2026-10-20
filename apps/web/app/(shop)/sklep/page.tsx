import type { Metadata } from "next";
import { Suspense } from "react";
import { CatalogView } from "@/components/catalog/catalog-view";
import { CatalogLoading } from "@/components/catalog/catalog-loading";
import { getCatalogList } from "@/lib/catalog-list-api";
import { getSearchPresentation } from "@/lib/search-presentation-api";
import type { SearchPresentationSettings } from "@/types/search-presentation";
import {
  normalizeCatalogParams,
  type SearchParamValues,
} from "@/lib/catalog-query";

export const metadata: Metadata = {
  title: "Sklep — materiały Sensoria",
  description:
    "Vouchery, książki, audiobooki i kursy przygotowane przez zespół Sensoria.",
};
export const dynamic = "force-dynamic";

type StorePageProps = { searchParams: Promise<SearchParamValues> };

async function CatalogResults({ query }: { query: URLSearchParams }) {
  let data;
  let allCategoriesTotal = 0;
  let globalTotal = 0;
  let loadError: string | undefined;
  let searchPresentation: SearchPresentationSettings | null = null;

  try {
    const resultsPromise = getCatalogList(query);
    const presentationPromise = getSearchPresentation().catch(() => null);
    data = await resultsPromise;
    searchPresentation = await presentationPromise;
    const noCategory = new URLSearchParams(query);
    noCategory.delete("category");
    noCategory.delete("page");
    const hasCatalogFilters = [
      "category",
      "kind",
      "audience",
      "price_min",
      "price_max",
      "delivery",
      "q",
    ].some((key) => query.has(key));
    const [unfilteredTotal, withoutCategoryTotal] = await Promise.all([
      hasCatalogFilters
        ? getCatalogList(new URLSearchParams())
        : Promise.resolve(data),
      query.has("category")
        ? getCatalogList(noCategory, { recordSearch: false })
        : Promise.resolve(data),
    ]);
    globalTotal = unfilteredTotal.total;
    allCategoriesTotal = withoutCategoryTotal.total;
  } catch {
    loadError =
      "Nie można teraz pobrać produktów. Sprawdź połączenie i spróbuj ponownie.";
    data = {
      items: [],
      total: 0,
      page: Number(query.get("page") ?? 1),
      per_page: 12,
      total_pages: 0,
      facets: {
        categories: [],
        kinds: [],
        audiences: [],
        deliveries: [],
        prices: [],
      },
      suggestions: null,
    } satisfies Awaited<ReturnType<typeof getCatalogList>>;
  }

  return (
    <CatalogView
      allCategoriesTotal={allCategoriesTotal}
      data={data}
      globalTotal={globalTotal}
      loadError={loadError}
      searchPresentation={searchPresentation}
    />
  );
}

export default async function StorePage({ searchParams }: StorePageProps) {
  const query = normalizeCatalogParams(await searchParams);
  return (
    <Suspense fallback={<CatalogLoading />}>
      <CatalogResults query={query} />
    </Suspense>
  );
}

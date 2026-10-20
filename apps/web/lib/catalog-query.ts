export const catalogParams = [
  "category",
  "kind",
  "audience",
  "price_min",
  "price_max",
  "delivery",
  "sort",
  "page",
  "per_page",
  "q",
] as const;
export type CatalogParam = (typeof catalogParams)[number];
export type SearchParamValues = Record<string, string | string[] | undefined>;
export const catalogPriceBands = [
  { value: "up_to_5000", label: "do 50 zł", min: "0", max: "5000" },
  { value: "5001_to_15000", label: "50–150 zł", min: "5001", max: "15000" },
  { value: "over_15000", label: "powyżej 150 zł", min: "15001", max: null },
] as const;

export function normalizeCatalogParams(
  input: SearchParamValues,
): URLSearchParams {
  const result = new URLSearchParams();
  for (const key of catalogParams) {
    const raw = input[key];
    const value = Array.isArray(raw) ? raw[0] : raw;
    if (
      value &&
      value.trim() &&
      !(key === "page" && value === "1") &&
      !(key === "per_page" && value === "12") &&
      !(key === "sort" && value === "recommended")
    )
      result.set(key, value.trim());
  }
  return result;
}

export function updateCatalogParams(
  current: URLSearchParams,
  changes: Partial<Record<CatalogParam, string | null>>,
  clearFilters = false,
): string {
  const next = new URLSearchParams(current);
  if (clearFilters) {
    for (const key of [
      "category",
      "kind",
      "audience",
      "price_min",
      "price_max",
      "delivery",
    ] as const)
      next.delete(key);
    next.delete("page");
  }
  for (const [key, value] of Object.entries(changes) as Array<
    [CatalogParam, string | null]
  >) {
    if (value === null || !value.trim()) next.delete(key);
    else next.set(key, value.trim());
  }
  const resetsPage = Object.keys(changes).some(
    (key) => key !== "page" && key !== "per_page",
  );
  if (resetsPage) next.delete("page");
  const query = next.toString();
  return query ? `/sklep?${query}` : "/sklep";
}

export function apiCatalogUrl(params: URLSearchParams): string {
  const apiParams = new URLSearchParams(params);
  if (!apiParams.has("page")) apiParams.set("page", "1");
  if (!apiParams.has("per_page")) apiParams.set("per_page", "12");
  if (!apiParams.has("sort") && !apiParams.has("q"))
    apiParams.set("sort", "recommended");
  return `/products?${apiParams.toString()}`;
}

export function countActiveCatalogFilters(params: URLSearchParams): number {
  let count = 0;
  for (const key of ["category", "kind", "audience", "delivery"] as const)
    if (params.has(key)) count += 1;
  if (params.has("price_min") || params.has("price_max")) count += 1;
  return count;
}

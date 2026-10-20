import type { MetadataRoute } from "next";
import { getPublicSitemapData } from "@/lib/catalog-api";
import { requestJson } from "@/lib/api";
import { getServerApiUrl } from "@/lib/server-api-url";
import { categoryPath, productPath, publicUrl } from "@/lib/catalog-urls";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const catalog = await getPublicSitemapData();
  const fixedPages = ["/", "/sklep", "/pomoc"];
  // Only published information pages are listed; a drafted page must not be indexed.
  let pages: string[] = [];
  try {
    const apiUrl = getServerApiUrl();
    if (apiUrl) {
      const body = (await requestJson(apiUrl, "/pages", {
        cache: "no-store",
      })) as { items?: Array<{ slug: string }> };
      const known = new Set([
        "regulamin",
        "polityka-prywatnosci",
        "polityka-cookies",
        "o-autorce",
        "dostawa-i-platnosci",
      ]);
      pages = (body.items ?? [])
        .filter((page) => known.has(page.slug))
        .map((page) => `/${page.slug}`);
    }
  } catch {
    pages = [];
  }
  return [
    ...[...fixedPages, ...pages].map((path) => ({ url: publicUrl(path) })),
    ...catalog.entries.map((entry) => ({
      url: publicUrl(
        entry.kind === "product"
          ? productPath(entry.slug)
          : categoryPath(entry.slug),
      ),
      lastModified: new Date(entry.last_modified),
    })),
  ];
}

import type { MetadataRoute } from "next";
import { getPublicSitemapData } from "@/lib/catalog-api";
import { categoryPath, productPath, publicUrl } from "@/lib/catalog-urls";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const catalog = await getPublicSitemapData();
  const fixedPages = ["/", "/sklep", "/pomoc"];
  return [
    ...fixedPages.map((path) => ({ url: publicUrl(path) })),
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

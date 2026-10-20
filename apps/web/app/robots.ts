import type { MetadataRoute } from "next";
import { publicUrl } from "@/lib/catalog-urls";

export const dynamic = "force-dynamic";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/konto", "/koszyk", "/zamowienie", "/dev", "/dev/"],
    },
    sitemap: publicUrl("/sitemap.xml"),
  };
}

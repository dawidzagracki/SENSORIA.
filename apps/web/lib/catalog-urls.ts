import "server-only";

export function getPublicSiteUrl(): URL {
  // Standalone Next.js development does not load the repository root .env.
  // Keep this fallback local to development; production still requires an
  // explicit trusted public origin.
  const configured =
    process.env.SITE_URL?.trim() ||
    (process.env.NODE_ENV === "development" ? "http://localhost:3000" : null);
  if (!configured?.trim()) {
    throw new Error("Wymagana jest serwerowa zmienna SITE_URL.");
  }
  let siteUrl: URL;
  try {
    siteUrl = new URL(configured);
  } catch {
    throw new Error("Zmienna SITE_URL musi być poprawnym adresem publicznym.");
  }
  if (
    !["http:", "https:"].includes(siteUrl.protocol) ||
    siteUrl.username ||
    siteUrl.password ||
    siteUrl.search ||
    siteUrl.hash
  ) {
    throw new Error(
      "Zmienna SITE_URL musi wskazywać publiczny adres HTTP(S) bez danych logowania.",
    );
  }
  if (
    process.env.ENVIRONMENT === "production" &&
    siteUrl.protocol !== "https:"
  ) {
    throw new Error("W production zmienna SITE_URL musi używać HTTPS.");
  }
  return new URL(siteUrl.origin);
}

export function productPath(slug: string): string {
  return `/sklep/${encodeURIComponent(slug)}`;
}

export function voucherProductPath(slug: string, variant?: string): string {
  const path = `/sklep/${encodeURIComponent(slug)}`;
  return variant ? `${path}?variant=${encodeURIComponent(variant)}` : path;
}

export function categoryPath(slug: string): string {
  return `/kategoria/${encodeURIComponent(slug)}`;
}

export function publicUrl(path: string): string {
  return new URL(path, getPublicSiteUrl()).toString();
}

export function absoluteImageUrl(source: string): string {
  const image = safePublicImageUrl(source);
  if (!image)
    throw new Error("Obraz SEO musi mieć poprawny publiczny adres HTTP(S).");
  return image;
}

export function safePublicImageUrl(source: string): string | undefined {
  try {
    const image = new URL(source, getPublicSiteUrl());
    if (
      !["http:", "https:"].includes(image.protocol) ||
      image.username ||
      image.password ||
      image.hostname.endsWith(".invalid")
    ) {
      return undefined;
    }
    return image.toString();
  } catch {
    return undefined;
  }
}

import { ApiError } from "@/lib/api";

export type ProductSample = {
  url: string;
  contentType: "application/pdf" | "audio/mpeg";
  pages: number | null;
  durationSeconds: number | null;
};

function sampleApiBase(): string {
  const value = process.env.NEXT_PUBLIC_API_URL;
  if (!value) {
    throw new ApiError(
      "API_NOT_CONFIGURED",
      "Podgląd fragmentu nie jest teraz dostępny.",
    );
  }
  try {
    return new URL(value.endsWith("/") ? value : `${value}/`).toString();
  } catch {
    throw new ApiError(
      "INVALID_API_URL",
      "Adres serwera API jest nieprawidłowy.",
    );
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export async function openProductSample(
  slug: string,
  signal?: AbortSignal,
): Promise<ProductSample> {
  const base = sampleApiBase();
  const safeSlug = encodeURIComponent(slug);
  let response: Response;
  try {
    response = await fetch(new URL(`products/${safeSlug}/sample/open`, base), {
      method: "POST",
      headers: { "X-Sample-Open-Id": crypto.randomUUID() },
      cache: "no-store",
      signal,
    });
  } catch {
    throw new ApiError("NETWORK_ERROR", "Nie można teraz otworzyć fragmentu.");
  }

  const body: unknown = await response.json().catch(() => undefined);
  if (!response.ok) {
    const envelope = isRecord(body) && isRecord(body.error) ? body.error : null;
    throw new ApiError(
      typeof envelope?.code === "string" ? envelope.code : "SAMPLE_UNAVAILABLE",
      typeof envelope?.message === "string"
        ? envelope.message
        : "Fragment nie jest teraz dostępny.",
      response.status,
    );
  }

  if (
    !isRecord(body) ||
    typeof body.sample_url !== "string" ||
    !body.sample_url.startsWith(`/products/${safeSlug}/sample?grant=`) ||
    (body.content_type !== "application/pdf" &&
      body.content_type !== "audio/mpeg") ||
    !(
      body.pages === null ||
      (Number.isSafeInteger(body.pages) && Number(body.pages) > 0)
    ) ||
    !(
      body.duration_seconds === null ||
      (Number.isSafeInteger(body.duration_seconds) &&
        Number(body.duration_seconds) > 0)
    )
  ) {
    throw new ApiError(
      "INVALID_RESPONSE",
      "Serwer zwrócił nieprawidłowy fragment.",
    );
  }

  return {
    url: new URL(body.sample_url.slice(1), base).toString(),
    contentType: body.content_type,
    pages: body.pages as number | null,
    durationSeconds: body.duration_seconds as number | null,
  };
}

import { ApiError } from "../lib/api";

export type SearchPresentationSettings = {
  suggested_queries: string[];
  contact_email: string | null;
  contact_phone: string | null;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function validEmail(value: string): boolean {
  return value.length <= 254 && /^[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+$/.test(value);
}

function validPhone(value: string): boolean {
  return (
    /^[+0-9(). -]{7,32}$/.test(value) &&
    (value.match(/[0-9]/g)?.length ?? 0) >= 7
  );
}

export function parseSearchPresentationSettings(
  value: unknown,
): SearchPresentationSettings {
  if (
    !isRecord(value) ||
    Object.keys(value).some(
      (key) =>
        !["suggested_queries", "contact_email", "contact_phone"].includes(key),
    ) ||
    !Array.isArray(value.suggested_queries) ||
    value.suggested_queries.length < 1 ||
    value.suggested_queries.length > 8 ||
    !value.suggested_queries.every(
      (query) =>
        typeof query === "string" &&
        query.trim().length > 0 &&
        query.trim().length <= 80,
    ) ||
    !(
      value.contact_email === null ||
      (typeof value.contact_email === "string" &&
        validEmail(value.contact_email))
    ) ||
    !(
      value.contact_phone === null ||
      (typeof value.contact_phone === "string" &&
        validPhone(value.contact_phone))
    )
  ) {
    throw new ApiError(
      "INVALID_RESPONSE",
      "Serwer zwrócił nieprawidłowe ustawienia strony braku wyników.",
    );
  }
  const queries = value.suggested_queries.map((query) => query.trim());
  if (
    new Set(queries.map((query) => query.toLocaleLowerCase("pl-PL"))).size !==
    queries.length
  ) {
    throw new ApiError(
      "INVALID_RESPONSE",
      "Serwer zwrócił powtórzone podpowiedzi wyszukiwania.",
    );
  }
  return {
    suggested_queries: queries,
    contact_email: value.contact_email as string | null,
    contact_phone: value.contact_phone as string | null,
  };
}

/** Browser-side API helpers shared by account, order, library and admin screens. */

export const API =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") || "/api";

export class ClientApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ClientApiError";
    this.status = status;
    this.code = code;
  }
}

type Init = Omit<RequestInit, "body"> & {
  json?: unknown;
  csrf?: string;
};

async function readError(response: Response): Promise<ClientApiError> {
  let code = "HTTP_ERROR";
  let message = "Nie udało się wykonać operacji. Spróbuj ponownie.";
  try {
    const body = (await response.json()) as {
      error?: { code?: string; message?: string };
    };
    if (body.error?.code) code = body.error.code;
    if (body.error?.message) message = body.error.message;
  } catch {
    /* non-JSON error body keeps the generic message */
  }
  return new ClientApiError(response.status, code, message);
}

/** JSON request with cookies; throws ClientApiError carrying the server's Polish message. */
export async function apiJson<T>(path: string, init: Init = {}): Promise<T> {
  const { json, csrf, headers, ...rest } = init;
  const merged: Record<string, string> = {
    Accept: "application/json",
    ...(headers as Record<string, string> | undefined),
  };
  if (json !== undefined) merged["Content-Type"] = "application/json";
  if (csrf) merged["X-CSRF-Token"] = csrf;
  let response: Response;
  try {
    response = await fetch(`${API}${path}`, {
      credentials: "include",
      cache: "no-store",
      ...rest,
      headers: merged,
      body: json === undefined ? undefined : JSON.stringify(json),
    });
  } catch {
    throw new ClientApiError(
      0,
      "NETWORK_ERROR",
      "Nie można połączyć się z serwerem. Sprawdź internet i spróbuj ponownie.",
    );
  }
  if (!response.ok) throw await readError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function money(grosz: number): string {
  if (!Number.isSafeInteger(grosz)) return "—";
  const sign = grosz < 0 ? "-" : "";
  const abs = Math.abs(grosz);
  const whole = new Intl.NumberFormat("pl-PL", {
    maximumFractionDigits: 0,
  }).format(Math.floor(abs / 100));
  return `${sign}${whole},${String(abs % 100).padStart(2, "0")} zł`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("pl-PL", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "Europe/Warsaw",
  }).format(new Date(value));
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("pl-PL", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Warsaw",
  }).format(new Date(value));
}

export function formatDuration(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds));
  const h = Math.floor(safe / 3600);
  const m = Math.floor((safe % 3600) / 60);
  const s = safe % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h > 0 ? `${h}:${mm}:${ss}` : `${m}:${ss}`;
}

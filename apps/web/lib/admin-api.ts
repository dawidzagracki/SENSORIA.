import { apiJson, ClientApiError } from "@/lib/client-api";

export type AdminIdentity = {
  id: string;
  email: string;
  display_name: string;
  role: "owner" | "staff";
};

let csrfToken: string | null = null;
let identity: AdminIdentity | null = null;

/** Loads the identity and a freshly rotated CSRF token; call once per page load. */
export async function loadAdminSession(): Promise<AdminIdentity> {
  const data = await apiJson<{ admin: AdminIdentity; csrf_token: string }>(
    "/admin/auth/session",
  );
  csrfToken = data.csrf_token;
  identity = data.admin;
  return data.admin;
}

export function currentAdmin(): AdminIdentity | null {
  return identity;
}

export function setSession(admin: AdminIdentity, csrf: string): void {
  identity = admin;
  csrfToken = csrf;
}

export function clearSession(): void {
  identity = null;
  csrfToken = null;
}

type Init = Omit<RequestInit, "body"> & { json?: unknown };

/** Admin request: CSRF is attached to unsafe methods and a stale token is refreshed once. */
export async function adminJson<T>(path: string, init: Init = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const unsafe = method !== "GET" && method !== "HEAD";
  try {
    if (unsafe && !csrfToken) await loadAdminSession();
    return await apiJson<T>(`/admin${path}`, {
      ...init,
      csrf: unsafe ? (csrfToken ?? undefined) : undefined,
    });
  } catch (error) {
    if (error instanceof ClientApiError) {
      if (error.status === 401) {
        clearSession();
        if (typeof window !== "undefined")
          window.location.assign("/admin/logowanie");
      }
      if (unsafe && error.code === "ADMIN_CSRF_REJECTED") {
        await loadAdminSession();
        return apiJson<T>(`/admin${path}`, {
          ...init,
          csrf: csrfToken ?? undefined,
        });
      }
    }
    throw error;
  }
}

export function adminDownloadUrl(path: string): string {
  const base = process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") || "/api";
  return `${base}/admin${path}`;
}

export function errorText(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

/** Multipart upload (files). The browser sets the multipart boundary itself. */
export async function adminUpload<T>(path: string, form: FormData): Promise<T> {
  if (!csrfToken) await loadAdminSession();
  const base = process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") || "/api";
  const send = () =>
    fetch(`${base}/admin${path}`, {
      method: "POST",
      credentials: "include",
      headers: { "X-CSRF-Token": csrfToken ?? "" },
      body: form,
    });
  let response = await send();
  if (response.status === 403) {
    await loadAdminSession();
    response = await send();
  }
  if (response.status === 401) {
    clearSession();
    window.location.assign("/admin/logowanie");
  }
  if (!response.ok) {
    let message = "Nie udało się przesłać pliku.";
    try {
      const body = (await response.json()) as { error?: { message?: string } };
      if (body.error?.message) message = body.error.message;
    } catch {
      /* keep generic message */
    }
    throw new ClientApiError(response.status, "UPLOAD_FAILED", message);
  }
  return (await response.json()) as T;
}

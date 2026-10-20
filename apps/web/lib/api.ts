export type ApiErrorCode =
  | "API_NOT_CONFIGURED"
  | "INVALID_API_URL"
  | "HTTP_ERROR"
  | "NETWORK_ERROR"
  | "REQUEST_TIMEOUT"
  | "INVALID_RESPONSE";

export class ApiError extends Error {
  readonly code: string;
  readonly status: number | undefined;

  constructor(
    code: string,
    message: string,
    status: number | undefined = undefined,
  ) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

type ApiRequestOptions = Omit<RequestInit, "signal"> & {
  timeoutMs?: number;
};

function buildUrl(baseUrl: string, endpointPath: string): string {
  try {
    const normalizedBase = baseUrl.replace(/\/+$/, "");
    const normalizedPath = endpointPath.replace(/^\/+/, "");
    return new URL(normalizedPath, `${normalizedBase}/`).toString();
  } catch {
    throw new ApiError(
      "INVALID_API_URL",
      "Adres serwera API jest nieprawidłowy.",
    );
  }
}

function readApiError(
  value: unknown,
): { code: string; message: string } | undefined {
  if (typeof value !== "object" || value === null || !("error" in value)) {
    return undefined;
  }

  const error = value.error;
  if (
    typeof error !== "object" ||
    error === null ||
    !("code" in error) ||
    typeof error.code !== "string" ||
    !("message" in error) ||
    typeof error.message !== "string"
  ) {
    return undefined;
  }

  return { code: error.code, message: error.message };
}

export async function requestJson(
  baseUrl: string,
  endpointPath: string,
  options: ApiRequestOptions = {},
): Promise<unknown> {
  const { timeoutMs = 5_000, ...requestOptions } = options;
  const url = buildUrl(baseUrl, endpointPath);
  const controller = new AbortController();
  let didTimeout = false;
  const timeout = setTimeout(() => {
    didTimeout = true;
    controller.abort();
  }, timeoutMs);

  try {
    const response = await fetch(url, {
      ...requestOptions,
      cache: requestOptions.cache ?? "no-store",
      signal: controller.signal,
    });
    const bodyText = await response.text();
    let body: unknown;

    try {
      body = JSON.parse(bodyText) as unknown;
    } catch {
      if (response.ok) {
        throw new ApiError(
          "INVALID_RESPONSE",
          "Serwer zwrócił odpowiedź w nieprawidłowym formacie.",
          response.status,
        );
      }
    }

    if (!response.ok) {
      const apiError = readApiError(body);
      throw new ApiError(
        apiError?.code ?? "HTTP_ERROR",
        apiError?.message ?? "Serwer nie może teraz obsłużyć żądania.",
        response.status,
      );
    }

    if (body === undefined) {
      throw new ApiError(
        "INVALID_RESPONSE",
        "Serwer zwrócił pustą odpowiedź.",
        response.status,
      );
    }

    return body;
  } catch (error: unknown) {
    if (error instanceof ApiError) {
      throw error;
    }

    if (didTimeout) {
      throw new ApiError("REQUEST_TIMEOUT", "Serwer nie odpowiedział na czas.");
    }

    throw new ApiError(
      "NETWORK_ERROR",
      "Nie można teraz połączyć się z serwerem.",
    );
  } finally {
    clearTimeout(timeout);
  }
}

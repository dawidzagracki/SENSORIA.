import "server-only";
import { ApiError, requestJson } from "@/lib/api";
import { getServerApiUrl } from "@/lib/server-api-url";
import { parseHealthResponse, type HealthResponse } from "@/types/health";

export async function getServerHealth(): Promise<HealthResponse> {
  const apiUrl = getServerApiUrl();
  if (!apiUrl) {
    throw new ApiError(
      "API_NOT_CONFIGURED",
      "Serwer API nie jest skonfigurowany.",
    );
  }

  const response = await requestJson(apiUrl, "/health", { cache: "no-store" });
  return parseHealthResponse(response);
}

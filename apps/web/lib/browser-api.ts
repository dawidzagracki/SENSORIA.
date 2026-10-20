import { ApiError, requestJson } from "@/lib/api";
import { parseHealthResponse, type HealthResponse } from "@/types/health";

export async function getBrowserHealth(): Promise<HealthResponse> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!apiUrl) {
    throw new ApiError(
      "API_NOT_CONFIGURED",
      "Serwer API nie jest skonfigurowany.",
    );
  }

  const response = await requestJson(apiUrl, "/health", { cache: "no-store" });
  return parseHealthResponse(response);
}

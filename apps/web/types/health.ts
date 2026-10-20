import { ApiError } from "@/lib/api";

export type HealthResponse = {
  status: "ok";
  version: string;
  database: "ok";
};

export function parseHealthResponse(value: unknown): HealthResponse {
  if (
    typeof value === "object" &&
    value !== null &&
    "status" in value &&
    value.status === "ok" &&
    "version" in value &&
    typeof value.version === "string" &&
    value.version.length > 0 &&
    "database" in value &&
    value.database === "ok"
  ) {
    return {
      status: value.status,
      version: value.version,
      database: value.database,
    };
  }

  throw new ApiError(
    "INVALID_RESPONSE",
    "Serwer zwrócił nieprawidłowe dane.",
    undefined,
  );
}

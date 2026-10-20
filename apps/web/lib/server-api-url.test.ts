import { describe, expect, it, vi } from "vitest";

import { getServerApiUrl } from "./server-api-url";

describe("getServerApiUrl", () => {
  it("uses the configured private API origin", () => {
    vi.stubEnv("API_URL", "http://api.internal:8000/");
    vi.stubEnv("NODE_ENV", "development");
    expect(getServerApiUrl()).toBe("http://api.internal:8000/");
    vi.unstubAllEnvs();
  });

  it("uses localhost for standalone development when API_URL is absent", () => {
    vi.stubEnv("API_URL", "");
    vi.stubEnv("NODE_ENV", "development");
    expect(getServerApiUrl()).toBe("http://localhost:8000");
    vi.unstubAllEnvs();
  });

  it("does not guess the API origin outside development", () => {
    vi.stubEnv("API_URL", "");
    vi.stubEnv("NODE_ENV", "production");
    expect(getServerApiUrl()).toBeNull();
    vi.unstubAllEnvs();
  });
});

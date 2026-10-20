import { describe, expect, it } from "vitest";
import { ApiError } from "../lib/api";
import { parseSearchPresentationSettings } from "./search-presentation";

describe("search presentation settings", () => {
  it("accepts configured suggestions and safe contact values", () => {
    expect(
      parseSearchPresentationSettings({
        suggested_queries: ["integracja sensoryczna", "terapia ręki"],
        contact_email: "kontakt@example.invalid",
        contact_phone: "+48 111 222 333",
      }),
    ).toEqual({
      suggested_queries: ["integracja sensoryczna", "terapia ręki"],
      contact_email: "kontakt@example.invalid",
      contact_phone: "+48 111 222 333",
    });
  });

  it("rejects unsafe protocols, duplicate entries, and unknown settings", () => {
    for (const value of [
      {
        suggested_queries: ["voucher"],
        contact_email: "javascript:alert(1)",
        contact_phone: null,
      },
      {
        suggested_queries: ["voucher", "Voucher"],
        contact_email: null,
        contact_phone: null,
      },
      {
        suggested_queries: ["voucher"],
        contact_email: null,
        contact_phone: null,
        secret: "never-public",
      },
    ]) {
      expect(() => parseSearchPresentationSettings(value)).toThrow(ApiError);
    }
  });
});

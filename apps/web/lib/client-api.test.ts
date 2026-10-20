import { afterEach, describe, expect, it, vi } from "vitest";
import {
  apiJson,
  ClientApiError,
  formatDuration,
  money,
} from "@/lib/client-api";

afterEach(() => vi.unstubAllGlobals());

describe("money", () => {
  it("formats integer grosz without floating point", () => {
    expect(money(7900)).toBe("79,00 zł");
    expect(money(5)).toBe("0,05 zł");
    expect(money(-150)).toBe("-1,50 zł");
    expect(money(Number.NaN)).toBe("—");
  });
});

describe("formatDuration", () => {
  it("renders minutes and hours", () => {
    expect(formatDuration(75)).toBe("1:15");
    expect(formatDuration(3725)).toBe("1:02:05");
    expect(formatDuration(-4)).toBe("0:00");
  });
});

describe("apiJson", () => {
  it("returns parsed JSON and sends credentials and csrf", async () => {
    const fetchMock = vi.fn<typeof fetch>(
      async () => new Response(JSON.stringify({ ok: 1 }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const result = await apiJson<{ ok: number }>("/x", {
      method: "POST",
      json: { a: 1 },
      csrf: "tok",
    });
    expect(result).toEqual({ ok: 1 });
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(init.credentials).toBe("include");
    expect((init.headers as Record<string, string>)["X-CSRF-Token"]).toBe(
      "tok",
    );
  });

  it("surfaces the server error message and code", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({ error: { code: "NOPE", message: "Nie wolno." } }),
            { status: 409 },
          ),
      ),
    );
    await expect(apiJson("/x")).rejects.toMatchObject({
      status: 409,
      code: "NOPE",
      message: "Nie wolno.",
    });
  });

  it("maps network failures to a safe Polish message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("fetch failed");
      }),
    );
    const error = await apiJson("/x").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ClientApiError);
    expect((error as ClientApiError).code).toBe("NETWORK_ERROR");
  });
});

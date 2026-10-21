import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AccountAuthPanel } from "./auth-panel";
import { LoginLinkConfirmation } from "./login-link-confirmation";

const { replace } = vi.hoisted(() => ({ replace: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, refresh: vi.fn() }),
}));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  replace.mockReset();
});

describe("account passwordless login action", () => {
  it("uses only the email and does not require a password", async () => {
    const json = (body: unknown, status = 200) =>
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      });
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, _init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/accounts/session")) return json({}, 401);
        if (url.endsWith("/accounts/oauth/providers"))
          return json({ google: false });
        if (url.endsWith("/accounts/csrf"))
          return json({ csrf_token: "csrf-token" });
        return json({
          message:
            "Jeśli konto istnieje, wyślemy wiadomość z linkiem do logowania.",
        });
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<AccountAuthPanel />);
    await user.type(screen.getByLabelText(/Adres e-mail/), "anna@example.test");
    await user.click(
      screen.getByRole("button", { name: "Wyślij mi link do logowania" }),
    );
    expect(
      await screen.findByText(
        "Jeśli konto istnieje, wyślemy wiadomość z linkiem do logowania.",
      ),
    ).toBeInTheDocument();
    const loginRequest = fetchMock.mock.calls.at(-1);
    expect(loginRequest?.[0]).toBe("/api/auth/login-link");
    expect(JSON.parse(String(loginRequest?.[1]?.body))).toEqual({
      email: "anna@example.test",
      return_to: "/konto",
    });
    expect(
      fetchMock.mock.calls.some(([url]) => url === "/api/accounts/login"),
    ).toBe(false);
  });

  it("checks a path token without consuming it until an explicit click", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ valid: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<LoginLinkConfirmation initialToken="one-time-secret" />);
    expect(
      await screen.findByRole("button", { name: "Zaloguj mnie" }),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "/api/auth/login-link/one-time-secret",
    );
    expect(fetchMock.mock.calls[0]?.[1]?.method).toBe("GET");
    expect(window.location.pathname).toBe("/konto/link-logowania");
  });
});

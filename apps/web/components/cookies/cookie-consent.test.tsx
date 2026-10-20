import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  CookieConsent,
  COOKIE_NAME,
  OPEN_EVENT,
  readChoice,
} from "@/components/cookies/cookie-consent";

function clearCookie() {
  document.cookie = `${COOKIE_NAME}=; Path=/; Max-Age=0`;
}

beforeEach(() => {
  clearCookie();
  // jsdom has no <dialog> modal support.
  HTMLDialogElement.prototype.showModal = function showModal() {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function close() {
    this.removeAttribute("open");
  };
});
afterEach(() => {
  cleanup();
  clearCookie();
  vi.unstubAllGlobals();
});

describe("readChoice", () => {
  it("rejects garbage and other policy versions", () => {
    expect(readChoice("")).toBeNull();
    expect(readChoice(`${COOKIE_NAME}=%7Bbad`)).toBeNull();
    expect(
      readChoice(
        `${COOKIE_NAME}=${encodeURIComponent(JSON.stringify({ v: "v0", analytics: true, marketing: true }))}`,
      ),
    ).toBeNull();
  });
});

describe("CookieConsent", () => {
  it("records a necessary-only choice, hides the banner and remembers it", async () => {
    const fetchMock = vi.fn<typeof fetch>(
      async () =>
        new Response(JSON.stringify({ subject_id: "s-1" }), { status: 201 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<CookieConsent />);
    await user.click(
      await screen.findByRole("button", { name: "Tylko niezbędne" }),
    );
    await waitFor(() =>
      expect(
        screen.queryByRole("region", { name: "Pliki cookies" }),
      ).not.toBeInTheDocument(),
    );
    const sent = JSON.parse(
      String((fetchMock.mock.calls[0]?.[1] as RequestInit).body),
    ) as Record<string, unknown>;
    expect(sent).toMatchObject({ analytics: false, marketing: false });
    expect(readChoice(document.cookie)).toMatchObject({
      subject: "s-1",
      analytics: false,
      marketing: false,
    });
  });

  it("keeps the visitor's choice even when the register is unreachable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("offline");
      }),
    );
    const user = userEvent.setup();
    render(<CookieConsent />);
    await user.click(
      await screen.findByRole("button", { name: "Akceptuję wszystkie" }),
    );
    await waitFor(() =>
      expect(readChoice(document.cookie)).toMatchObject({
        analytics: true,
        marketing: true,
      }),
    );
  });

  it("reopens settings from the footer event and saves granular choices", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ subject_id: "s-2" }), { status: 201 }),
      ),
    );
    document.cookie = `${COOKIE_NAME}=${encodeURIComponent(JSON.stringify({ v: "v1", subject: "s-1", analytics: false, marketing: false }))}; Path=/`;
    const user = userEvent.setup();
    render(<CookieConsent />);
    expect(
      screen.queryByRole("region", { name: "Pliki cookies" }),
    ).not.toBeInTheDocument();
    window.dispatchEvent(new Event(OPEN_EVENT));
    const analytics = await screen.findByRole("checkbox", {
      name: /Analityczne/,
    });
    await user.click(analytics);
    await user.click(screen.getByRole("button", { name: "Zapisz wybór" }));
    await waitFor(() =>
      expect(readChoice(document.cookie)).toMatchObject({
        analytics: true,
        marketing: false,
      }),
    );
  });
});

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ReviewForm } from "@/components/reviews/review-form";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status });

describe("ReviewForm", () => {
  it("validates before sending and submits a verified-purchase review", async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.includes("/reviews/eligible"))
          return json({
            items: [{ order_item_id: "i-1", name: "E-book", reviewed: false }],
          });
        if (url.includes("/reviews") && init?.method === "POST")
          return json({ id: "r", status: "pending" }, 201);
        return json({}, 404);
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<ReviewForm orderId="o-1" itemId="i-1" token={"t".repeat(40)} />);
    await screen.findByText("E-book");
    await user.click(screen.getByRole("button", { name: "Wyślij opinię" }));
    expect(
      screen.getByText("Wybierz ocenę od 1 do 5 gwiazdek."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Opinia musi mieć co najmniej 10 znaków."),
    ).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([, init]) => init?.method === "POST"),
    ).toBe(false);

    await user.click(screen.getByRole("radio", { name: /5 z 5/ }));
    await user.type(
      screen.getByLabelText(/Twoja opinia/),
      "Bardzo dobry materiał, polecam.",
    );
    await user.click(screen.getByRole("button", { name: "Wyślij opinię" }));
    await screen.findByText("Dziękujemy!");
    const post = fetchMock.mock.calls.find(
      ([, init]) => init?.method === "POST",
    );
    expect(JSON.parse(String(post?.[1]?.body))).toMatchObject({
      order_id: "o-1",
      order_item_id: "i-1",
      rating: 5,
    });
  });

  it("asks for the e-mail link when the order is unknown", () => {
    render(<ReviewForm orderId={null} itemId={null} token={null} />);
    expect(
      screen.getByText(/Użyj linku z wiadomości e-mail/),
    ).toBeInTheDocument();
  });

  it("surfaces the server's refusal", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        json(
          {
            error: {
              code: "ORDER_NOT_FOUND",
              message: "Nie znaleziono zamówienia.",
            },
          },
          404,
        ),
      ),
    );
    render(<ReviewForm orderId="o-1" itemId={null} token={"t".repeat(40)} />);
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Nie znaleziono zamówienia.",
      ),
    );
  });
});

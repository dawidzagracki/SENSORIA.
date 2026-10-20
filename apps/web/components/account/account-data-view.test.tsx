import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AccountDataView } from "./account-data-view";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const profile = {
  first_name: "Anna",
  last_name: "Kowalska",
  email: "anna@example.test",
  pending_email: null,
  email_verified: true,
  phone: null,
  first_purchase_at: "2025-04-12T10:00:00Z",
  contact_email: "pomoc@example.test",
  contact_phone: null,
  addresses: [
    {
      id: "address-1",
      label: "Dom",
      address_type: "address" as const,
      is_default: true,
      street: "Leśna 4",
      building_number: "4",
      postal_code: "10-001",
      city: "Olsztyn",
    },
  ],
};

describe("AccountDataView", () => {
  it("shows profile, saved default and configured support contact", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify(profile), { status: 200 }),
        ),
    );

    render(<AccountDataView />);

    expect(await screen.findByText("Anna Kowalska")).toBeInTheDocument();
    expect(screen.getByText("DOMYŚLNY")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "pomoc@example.test" }),
    ).toHaveAttribute("href", "mailto:pomoc@example.test");
    expect(
      screen.queryByText("Masz niezapisane zmiany"),
    ).not.toBeInTheDocument();
  });

  it("shows the real dirty-state bar and cancel restores saved data", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify(profile), { status: 200 }),
        ),
    );

    render(<AccountDataView />);
    const firstName = await screen.findByRole("textbox", { name: "Imię" });
    fireEvent.change(firstName, { target: { value: "Agnieszka" } });
    expect(
      await screen.findByText("Masz niezapisane zmiany"),
    ).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: "Anuluj" })[0]);
    await waitFor(() => {
      expect(
        screen.queryByText("Masz niezapisane zmiany"),
      ).not.toBeInTheDocument();
    });
    expect(firstName).toHaveValue("Anna");
  });
});

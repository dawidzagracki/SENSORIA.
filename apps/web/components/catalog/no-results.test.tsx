import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { NoResults } from "./no-results";

describe("NoResults", () => {
  it("shows a voucher-specific empty state without unrelated search prompts", () => {
    render(
      <NoResults
        draft=""
        emptyCollectionLabel="voucherów"
        hasFilters
        onChooseQuery={vi.fn()}
        onClearFilters={vi.fn()}
        onDraftChange={vi.fn()}
        onSearch={vi.fn()}
        query=""
        settings={{
          suggested_queries: ["terapia ręki"],
          contact_email: null,
          contact_phone: null,
        }}
        suggestions={null}
      />,
    );

    expect(
      screen.getByRole("heading", {
        name: "Nie ma teraz dostępnych voucherów",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("VOUCHERY NA WIZYTY")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "terapia ręki" })).toBeNull();
    expect(
      screen.queryByText("Dane kontaktowe nie są obecnie skonfigurowane."),
    ).toBeNull();
    expect(
      screen.getByRole("button", { name: "Wyczyść filtry" }),
    ).toBeInTheDocument();
  });
});

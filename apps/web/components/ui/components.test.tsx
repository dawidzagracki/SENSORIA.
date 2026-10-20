import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { contrastRatio } from "../../lib/contrast";
import { formatMoney } from "../../lib/format-money";
import {
  badgeTokens,
  colorTokens,
  contrastPairs,
  gradientTokens,
  productTypeTokens,
  statusLabelTokens,
} from "../../tailwind.config";
import { Accordion } from "./accordion";
import { Alert } from "./alert";
import { Badge } from "./badge";
import { Breadcrumbs } from "./breadcrumbs";
import { Button } from "./button";
import { Checkbox } from "./checkbox";
import { Modal } from "./modal";
import { Price } from "./price";
import { ProductCard } from "./product-card";
import { Radio } from "./radio";
import { RadioCard } from "./radio-card";
import { Select } from "./select";
import { Textarea } from "./textarea";
import { TextField } from "./text-field";

afterEach(() => {
  cleanup();
  document.body.style.overflow = "";
});

describe("formatMoney and Price", () => {
  it("formats zero, fractional-zloty and larger integer-grosz amounts", () => {
    expect(formatMoney(44700)).toBe("447,00 zł");
    expect(formatMoney(0)).toBe("0,00 zł");
    expect(formatMoney(5)).toBe("0,05 zł");
    expect(formatMoney(123456789)).toBe("1 234 567,89 zł");
  });

  it("rejects floats, booleans, negative and unsafe amounts", () => {
    for (const amount of [
      1.5,
      Number.NaN,
      Number.POSITIVE_INFINITY,
      -1,
      Number.MAX_SAFE_INTEGER + 1,
      true,
    ]) {
      expect(() => formatMoney(amount as number)).toThrow(RangeError);
    }
  });

  it("renders previous price accessibly and keeps EXEMPT separate from RATE_0", () => {
    const { rerender } = render(
      <Price
        amountInGrosze={44700}
        previousAmountInGrosze={49900}
        vatRate="EXEMPT"
      />,
    );
    expect(screen.getByText("447,00 zł")).toBeInTheDocument();
    expect(screen.getByText(/Poprzednia cena:/)).toBeInTheDocument();
    expect(screen.getByText("499,00 zł")).toHaveTextContent("499,00 zł");
    expect(screen.getByText("zw. z VAT")).toBeInTheDocument();
    rerender(<Price amountInGrosze={44700} vatRate="RATE_0" />);
    expect(screen.getByText("VAT 0%")).toBeInTheDocument();
    expect(screen.queryByText("zw. z VAT")).not.toBeInTheDocument();
  });

  it.each([
    ["RATE_23", "VAT 23%"],
    ["RATE_8", "VAT 8%"],
    ["RATE_5", "VAT 5%"],
  ] as const)("shows visible VAT for %s", (vatRate, expected) => {
    render(<Price amountInGrosze={44700} vatRate={vatRate} />);
    expect(screen.getByText(expected)).toBeInTheDocument();
  });
});

describe("token contrast", () => {
  it("keeps every used semantic, product, status and badge pair accessible", () => {
    const pairs = [
      ...contrastPairs.filter(
        (pair) => !("status" in pair && pair.status === "blocked"),
      ),
      ...productTypeTokens,
      ...statusLabelTokens,
      ...badgeTokens,
    ];
    for (const pair of pairs) {
      expect(
        contrastRatio(
          colorTokens[pair.foreground].value,
          colorTokens[pair.background].value,
        ),
        `${pair.foreground} on ${pair.background}`,
      ).toBeGreaterThanOrEqual(4.5);
    }
    for (const background of [
      gradientTokens.footer.start,
      gradientTokens.footer.end,
    ]) {
      for (const foreground of ["ink", "ink-muted"] as const)
        expect(
          contrastRatio(colorTokens[foreground].value, background),
        ).toBeGreaterThanOrEqual(4.5);
    }
  });
});

describe("accessible controls", () => {
  it("uses native button semantics, defaults type to button, and blocks loading actions", async () => {
    const user = userEvent.setup();
    const action = vi.fn();
    const { rerender } = render(<Button onClick={action}>Akcja</Button>);
    const button = screen.getByRole("button", { name: "Akcja" });
    expect(button).toHaveAttribute("type", "button");
    expect(button.querySelectorAll("span")).toHaveLength(1);
    button.focus();
    await user.keyboard("{Enter}");
    expect(action).toHaveBeenCalledOnce();
    rerender(
      <Button disabled onClick={action}>
        Akcja
      </Button>,
    );
    await user.click(screen.getByRole("button", { name: "Akcja" }));
    expect(action).toHaveBeenCalledOnce();
    rerender(
      <Button loading onClick={action}>
        Akcja
      </Button>,
    );
    expect(
      screen.getByRole("button", { name: /Akcja.*Ładowanie/ }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: /Akcja.*Ładowanie/ }),
    ).toHaveAttribute("aria-busy", "true");
    expect(
      screen
        .getByRole("button", { name: /Akcja.*Ładowanie/ })
        .querySelectorAll("span"),
    ).toHaveLength(3);
    await user.click(screen.getByRole("button", { name: /Akcja.*Ładowanie/ }));
    expect(action).toHaveBeenCalledOnce();
  });

  it("associates each field label, required state, hint, error and supplied description", () => {
    render(
      <>
        <p id="external-note">Dodatkowa informacja.</p>
        <TextField
          aria-describedby="external-note"
          error="Błędny e-mail."
          hint="Adres do kontaktu."
          label="E-mail"
          required
        />
        <Textarea label="Wiadomość" hint="Kilka zdań." />
        <Select label="Typ" error="Wybierz typ.">
          <option value="">Wybierz</option>
        </Select>
      </>,
    );
    const email = screen.getByRole("textbox", { name: /E-mail/ });
    const emailIds = email.getAttribute("aria-describedby")?.split(" ") ?? [];
    expect(email).toHaveAttribute("required");
    expect(email).toHaveAttribute("aria-required", "true");
    expect(email).toHaveAttribute("aria-invalid", "true");
    expect(emailIds).toContain("external-note");
    for (const id of emailIds)
      expect(document.getElementById(id)).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Wiadomość" })).toHaveAttribute(
      "aria-describedby",
    );
    expect(screen.getByRole("combobox", { name: /Typ/ })).toHaveAttribute(
      "aria-invalid",
      "true",
    );
  });

  it("generates unique control IDs and activates the entire checkbox and radio card labels", async () => {
    const user = userEvent.setup();
    const { container } = render(
      <>
        <Checkbox label="Zgoda A" name="consent-a" />
        <Checkbox label="Zgoda B" name="consent-b" />
        <fieldset>
          <legend>Dostawa</legend>
          <Radio label="Odbiór" name="delivery" value="pickup" />
          <RadioCard
            description="Pod wskazany adres."
            name="delivery"
            title="Kurier"
            value="courier"
            trailingContent="14,99 zł"
          />
        </fieldset>
      </>,
    );
    const ids = Array.from(container.querySelectorAll("input")).map(
      (input) => input.id,
    );
    expect(new Set(ids).size).toBe(ids.length);
    const consent = screen.getByRole("checkbox", { name: "Zgoda A" });
    await user.click(screen.getByText("Zgoda A"));
    expect(consent).toBeChecked();
    const courier = screen.getByRole("radio", { name: /Kurier/ });
    await user.click(screen.getByText("Kurier"));
    expect(courier).toBeChecked();
    expect(screen.getByRole("group", { name: "Dostawa" })).toBeInTheDocument();
  });

  it("supports keyboard selection and disabled state for radio groups", async () => {
    const user = userEvent.setup();
    render(
      <fieldset>
        <legend>Płatność</legend>
        <Radio label="Karta" name="payment" value="card" />
        <Radio label="BLIK" name="payment" value="blik" disabled />
      </fieldset>,
    );
    const card = screen.getByRole("radio", { name: "Karta" });
    card.focus();
    await user.keyboard(" ");
    expect(card).toBeChecked();
    expect(screen.getByRole("radio", { name: "BLIK" })).toBeDisabled();
  });
});

describe("gallery components", () => {
  it("renders all product types and their text labels with configured colors", () => {
    expect(productTypeTokens).toHaveLength(5);
    const { rerender } = render(<Badge label="VOUCHER" />);
    expect(screen.getByText("VOUCHER")).toHaveStyle({
      backgroundColor: colorTokens[productTypeTokens[0].background].value,
    });
    rerender(
      <>
        <Badge label="AKTYWNY" />
        <Badge label="WYGASA WKRÓTCE" />
        <Badge label="ZREALIZOWANY" />
        <Badge label="BESTSELLER" />
        <Badge label="OPŁACONE" />
        <Badge label="WYSYŁKA W TOKU" />
      </>,
    );
    for (const token of badgeTokens)
      expect(screen.getByText(token.label)).toBeInTheDocument();
  });

  it("renders product card image, title link, price, metric and callback without nesting controls", async () => {
    const user = userEvent.setup();
    const add = vi.fn();
    render(
      <ProductCard
        description="Opis"
        href="/sklep/test"
        image={<span>Grafika</span>}
        imageAlt="Okładka produktu"
        metric="PDF · 148 stron"
        onAddToCart={add}
        priceInGrosze={44700}
        title="Poradnik"
        type="E-BOOK PDF"
      />,
    );
    expect(
      screen.getByRole("img", { name: "Okładka produktu" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Poradnik" })).toHaveAttribute(
      "href",
      "/sklep/test",
    );
    await user.click(screen.getByRole("button", { name: "Do koszyka" }));
    expect(add).toHaveBeenCalledOnce();
  });

  it("handles accordion expand/collapse, ids, arrow and Home/End navigation", async () => {
    const user = userEvent.setup();
    render(
      <Accordion
        items={[
          {
            id: "a",
            title: "Pytanie A",
            content: <a href="#a">Odpowiedź A</a>,
          },
          { id: "b", title: "Pytanie B", content: "Odpowiedź B" },
        ]}
      />,
    );
    const first = screen.getByRole("button", { name: "Pytanie A" });
    const second = screen.getByRole("button", { name: "Pytanie B" });
    first.focus();
    await user.keyboard("{ArrowDown}");
    expect(second).toHaveFocus();
    await user.keyboard("{ArrowUp}");
    expect(first).toHaveFocus();
    await user.keyboard("{End}");
    expect(second).toHaveFocus();
    await user.keyboard("{Home}");
    expect(first).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(first).toHaveAttribute("aria-expanded", "true");
    const panelId = first.getAttribute("aria-controls");
    expect(document.getElementById(panelId ?? "")).toBeVisible();
    await user.keyboard(" ");
    expect(first).toHaveAttribute("aria-expanded", "false");
    expect(document.getElementById(panelId ?? "")).not.toBeVisible();
    expect(
      screen.queryByRole("link", { name: "Odpowiedź A" }),
    ).not.toBeInTheDocument();
  });

  it("allows multiple open panels only when mode=multiple is selected", async () => {
    const user = userEvent.setup();
    render(
      <Accordion
        defaultExpandedIds={["a"]}
        mode="multiple"
        items={[
          { id: "a", title: "Panel A", content: "Treść A" },
          { id: "b", title: "Panel B", content: "Treść B" },
        ]}
      />,
    );
    const first = screen.getByRole("button", { name: "Panel A" });
    const second = screen.getByRole("button", { name: "Panel B" });
    await user.click(second);
    expect(first).toHaveAttribute("aria-expanded", "true");
    expect(second).toHaveAttribute("aria-expanded", "true");
    await user.click(second);
    expect(first).toHaveAttribute("aria-expanded", "true");
    expect(second).toHaveAttribute("aria-expanded", "false");
  });

  it("uses status and alert roles according to urgency and marks current breadcrumb", () => {
    const { container } = render(
      <>
        <Alert variant="info">Informacja</Alert>
        <Alert variant="error">Pilny błąd</Alert>
        <Breadcrumbs
          items={[
            { href: "/sklep", label: "Sklep" },
            { href: "/sklep/vouchery", label: "Vouchery" },
            { label: "Konsultacja" },
          ]}
        />
      </>,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Informacja");
    expect(screen.getByRole("alert")).toHaveTextContent("Pilny błąd");
    expect(
      screen.getByRole("navigation", { name: "Okruszki nawigacyjne" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sklep" })).toHaveAttribute(
      "href",
      "/sklep",
    );
    expect(screen.getByText("Konsultacja")).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(
      Array.from(container.querySelectorAll('[aria-hidden="true"]')).every(
        (node) => node.textContent === "/",
      ),
    ).toBe(true);
  });
});

describe("Modal focus and document behavior", () => {
  beforeEach(() => {
    Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
      configurable: true,
      value: vi.fn(function (this: HTMLDialogElement) {
        this.setAttribute("open", "");
      }),
    });
    Object.defineProperty(HTMLDialogElement.prototype, "close", {
      configurable: true,
      value: vi.fn(function (this: HTMLDialogElement) {
        this.removeAttribute("open");
        this.dispatchEvent(new Event("close"));
      }),
    });
  });

  it("focuses the dialog, locks scroll, closes on Escape and restores focus", async () => {
    const user = userEvent.setup();
    function Harness() {
      const [open, setOpen] = useState(false);
      return (
        <>
          <button onClick={() => setOpen(true)}>Otwórz</button>
          <Modal onOpenChange={setOpen} open={open} title="Szczegóły">
            Treść.
          </Modal>
        </>
      );
    }
    render(<Harness />);
    const trigger = screen.getByRole("button", { name: "Otwórz" });
    await user.click(trigger);
    const dialog = screen.getByRole("dialog", { name: "Szczegóły" });
    await waitFor(() => expect(dialog).toHaveAttribute("open"));
    expect(document.activeElement).toHaveAccessibleName("Zamknij okno");
    expect(document.body.style.overflow).toBe("hidden");
    fireEvent(dialog, new Event("cancel", { cancelable: true }));
    await waitFor(() => expect(dialog).not.toHaveAttribute("open"));
    expect(trigger).toHaveFocus();
    expect(document.body.style.overflow).toBe("");
  });
});

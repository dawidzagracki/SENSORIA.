import { describe, expect, it } from "vitest";
import { ApiError } from "../lib/api";
import { parseHomepageContent } from "./homepage";

const validContent = {
  eyebrow: "INSTYTUT DIAGNOZY I TERAPII SENSORIA",
  headline: {
    before_emphasis: "Terapia",
    emphasis: "nie kończy się",
    after_emphasis: "w gabinecie.",
  },
  paragraph: "Treść z ustawień.",
  catalog_button_label: "Zobacz materiały",
  voucher_button_label: "Kup voucher na wizytę",
  catalog_button_target: "/sklep",
  benefits: [
    { icon: "payment", text: "Płatność" },
    { icon: "email", text: "Pliki" },
    { icon: "parcel", text: "Paczkomat" },
    { icon: "voucher", text: "Ważność" },
  ],
  product_selection: { voucher_id: null, audiobook_id: null, course_id: null },
};

describe("homepage settings response", () => {
  it("accepts only the public typed shape", () => {
    expect(parseHomepageContent(validContent).paragraph).toBe(
      "Treść z ustawień.",
    );
  });

  it("rejects malformed or secret-bearing settings", () => {
    expect(() =>
      parseHomepageContent({ ...validContent, secret: "private" }),
    ).toThrow(ApiError);
    expect(() =>
      parseHomepageContent({ ...validContent, benefits: [] }),
    ).toThrow(ApiError);
  });
});
